from __future__ import annotations

import re
from pathlib import Path

from . import ai, captions, history, lock
from .config import Config, Unit
from .notify import notify
from .downloader import Manifest, sanitize, save_response
from .folders import init_folders, unit_dir, week_dir
from . import notes
from .scraper import (ASSESS_MODS, LINK_MODS, Activity, SectionInfo,
                      extract_pluginfile_links, find_section_links,
                      match_week, parse_section_page)
from .session import LoginRequired, MoodleSession

# Only files the lecturer attached to the assignment brief - never the
# student's own submissions or marker feedback.
_ASSIGN_FILE_RE = re.compile(r"/mod_assign/(intro|introattachment)/")
_DUE_RE = re.compile(r"<strong>\s*Due:\s*</strong>\s*([^<]+)")

MAX_SECTIONS = 120     # safety cap on crawled section numbers
SEED_SECTIONS = 8      # always try section 0..7 even if not linked anywhere


def crawl_sections(sess: MoodleSession, cfg: Config,
                   unit: Unit) -> dict[int, SectionInfo]:
    """Fetch the course page and every section page, following subsection
    links, and merge what we learn about each section."""
    course_url = f"{cfg.base_url}/course/view.php?id={unit.course_id}"
    infos: dict[int, SectionInfo] = {}

    def merge(page_infos: list[SectionInfo], own_number: int | None) -> None:
        for pi in page_infos:
            info = infos.setdefault(pi.number, SectionInfo(number=pi.number))
            info.titles |= pi.titles
            if pi.parent is not None:
                info.parent = pi.parent
            if pi.activities and (pi.number == own_number or not info.activities):
                info.activities = pi.activities

    html = sess.get_html(course_url)
    merge(parse_section_page(html, cfg.base_url), own_number=None)
    queue = set(range(SEED_SECTIONS)) | find_section_links(html, unit.course_id)
    visited: set[int] = set()

    while queue:
        n = queue.pop()
        visited.add(n)
        try:
            page = sess.get_html(f"{course_url}&section={n}")
        except Exception:
            continue  # hidden / orphaned section numbers 404 - that's fine
        queue |= {k for k in find_section_links(page, unit.course_id)
                  if k not in visited and k <= MAX_SECTIONS}
        merge(parse_section_page(page, cfg.base_url), own_number=n)
    return infos


def week_of(infos: dict[int, SectionInfo], number: int, cfg: Config) -> int | None:
    """Week of a section: its own title, or the nearest ancestor's."""
    seen: set[int] = set()
    n: int | None = number
    while n is not None and n not in seen:
        seen.add(n)
        info = infos.get(n)
        if info is None:
            return None
        week = match_week(info.title, cfg.section_patterns, cfg.weeks)
        if week is not None:
            return week
        n = info.parent
    return None


def _download_activity(sess: MoodleSession, cfg: Config, manifest: Manifest,
                       act: Activity, dest: Path) -> list[str]:
    """Download one activity into dest. Returns list of new file paths."""
    new: list[str] = []

    if act.mod == "folder":
        html = sess.get_html(act.url)
        for _, url in extract_pluginfile_links(html, cfg.base_url):
            if manifest.has(url):
                continue
            resp = sess.get_raw(url)
            if resp.ok:
                p = save_response(resp, dest, cfg, manifest, url)
                if p:
                    new.append(str(p))
        return new

    # resource / pluginfile
    if manifest.has(act.url):
        return new
    resp = sess.get_raw(act.url)
    if not resp.ok:
        print(f"    ! HTTP {resp.status} for {act.name}")
        return new
    ctype = resp.headers.get("content-type", "")
    if "text/html" in ctype:
        # resource rendered as an embed page - find the real file link inside
        links = extract_pluginfile_links(resp.text(), cfg.base_url)
        if not links:
            return new
        _, file_url = links[0]
        if manifest.has(file_url):
            existing = manifest.data[manifest.key(file_url)]["path"]
            manifest.add(act.url, Path(existing), 0)  # remember the view url too
            return new
        resp = sess.get_raw(file_url)
        if not resp.ok:
            return new
        p = save_response(resp, dest, cfg, manifest, file_url)
        if p:
            manifest.add(act.url, p, 0)
            new.append(str(p))
        return new

    p = save_response(resp, dest, cfg, manifest, act.url)
    if p:
        new.append(str(p))
    return new


def _sync_assessments(sess: MoodleSession, cfg: Config, manifest: Manifest,
                      unit: Unit,
                      assessments: list[tuple[Activity, str]],
                      collected: list[notes.Assessment] | None = None) -> int:
    """Download assignment briefs and write an index of all assessments."""
    if not cfg.assignments_folder or not assessments:
        return 0

    # De-duplicate (the same assignment is often listed in several sections);
    # keep external (lti) tools only when they sit in an assessment section.
    seen: set[str] = set()
    kept: list[Activity] = []
    for act, section_title in assessments:
        key = act.url.split("#")[0]
        if key in seen:
            continue
        if act.mod == "lti" and "assess" not in section_title.lower():
            continue
        seen.add(key)
        kept.append(act)
    if not kept:
        return 0

    assign_root = unit_dir(cfg, unit.code) / cfg.assignments_folder
    total_new = 0
    index_lines = ["Assessments found on Moodle for " + unit.code,
                   "(auto-generated by Moodle Downloader on every sync - "
                   "do not edit)", ""]

    for act in kept:
        due = ""
        if act.mod == "assign":
            try:
                html = sess.get_html(act.url)
            except Exception as e:
                print(f"    ! {act.name}: {e}")
                html = ""
            m = _DUE_RE.search(html)
            due = m.group(1).strip() if m else ""
            dest = assign_root / sanitize(act.name)
            for _, url in extract_pluginfile_links(html, cfg.base_url):
                if not _ASSIGN_FILE_RE.search(url) or manifest.has(url):
                    continue
                resp = sess.get_raw(url)
                if resp.ok:
                    p = save_response(resp, dest, cfg, manifest, url)
                    if p:
                        print(f"    + {_rel(cfg, p)}")
                        total_new += 1
        index_lines.append(f"[{act.mod}] {act.name}")
        if due:
            index_lines.append(f"    Due: {due}")
        index_lines.append(f"    {act.url}")
        index_lines.append("")
        if collected is not None:
            collected.append(notes.Assessment(name=act.name, due=due,
                                              url=act.url, mod=act.mod))

    assign_root.mkdir(parents=True, exist_ok=True)
    (assign_root / "Assessments.txt").write_text(
        "\n".join(index_lines), encoding="utf-8")
    print(f"  [assessments] {len(kept)} item(s) indexed in "
          f"{cfg.assignments_folder}/Assessments.txt")
    return total_new


def _rel(cfg: Config, path) -> str:
    """Show paths relative to the download root - keeps usernames and
    personal folder layouts out of shareable console output."""
    try:
        return str(Path(path).relative_to(cfg.root_dir))
    except ValueError:
        return str(path)




def sync_unit(sess: MoodleSession, cfg: Config, manifest: Manifest,
              unit: Unit) -> int:
    print(f"\n=== {unit.code} "
          f"({cfg.base_url}/course/view.php?id={unit.course_id}) ===")
    infos = crawl_sections(sess, cfg, unit)
    if not infos:
        print("  ! No sections found - the page layout may be unusual.")
        return 0

    total_new = 0
    assessments: list[tuple[Activity, str]] = []
    week_links: dict[int, list[tuple[str, str]]] = {}
    for n in sorted(infos):
        info = infos[n]
        files = [a for a in info.activities
                 if a.mod not in ASSESS_MODS + LINK_MODS + ("media",)]
        assessments += [(a, info.title) for a in info.activities
                        if a.mod in ASSESS_MODS]
        links = [a for a in info.activities if a.mod in LINK_MODS + ("media",)]
        if links:
            wk = week_of(infos, n, cfg)
            if wk is not None:
                week_links.setdefault(wk, []).extend((a.name, a.url) for a in links)
        if not files:
            continue
        week = week_of(infos, n, cfg)
        if week is not None:
            dest = week_dir(cfg, unit.code, week)
            label = f"Week {week}"
        elif cfg.unmatched_folder:
            dest = unit_dir(cfg, unit.code) / cfg.unmatched_folder
            label = "other"
        else:
            continue
        print(f"  [{label}] {info.title} - {len(files)} item(s)")
        for act in files:
            try:
                new = _download_activity(sess, cfg, manifest, act, dest)
            except Exception as e:
                print(f"    ! {act.name}: {e}")
                continue
            for p in new:
                print(f"    + {_rel(cfg, p)}")
            total_new += len(new)

    found: list[notes.Assessment] = []
    try:
        total_new += _sync_assessments(sess, cfg, manifest, unit, assessments,
                                       found)
    except Exception as e:
        print(f"  ! assessments: {e}")

    if cfg.transcripts:
        try:
            total_new += _sync_transcripts(sess, cfg, manifest, unit, week_links)
        except Exception as e:
            print(f"  ! transcripts: {e}")

    if cfg.weekly_notes:
        try:
            written = _write_week_notes(cfg, unit, week_links, found)
            for p in written:
                print(f"    ~ {_rel(cfg, p)}")
        except Exception as e:
            print(f"  ! weekly notes: {e}")
    return total_new


def _sync_transcripts(sess: MoodleSession, cfg: Config, manifest: Manifest,
                      unit: Unit,
                      week_links: dict[int, list[tuple[str, str]]]) -> int:
    """Save captions for the week's recordings as readable transcripts."""
    panopto: captions.PanoptoClient | None = None
    summariser = ai.Summariser(cfg)
    new = 0
    for week, links in sorted(week_links.items()):
        dest = week_dir(cfg, unit.code, week)
        for label, url in links:
            ids = captions.panopto_ids(url)
            vid = captions.youtube_id(url) if not ids else None
            if not ids and not vid:
                continue
            key = f"transcript:{ids[1] if ids else vid}"
            if manifest.has(key):
                continue
            if ids:
                if panopto is None:
                    panopto = captions.PanoptoClient(sess)
                got = panopto.transcript(*ids)
                if not got:
                    continue
                title, text = got
                source = "Panopto"
            else:
                text = captions.youtube_transcript(vid)
                if not text:
                    continue
                title, source = label or f"YouTube {vid}", "YouTube"
            summary = ""
            if summariser and summariser.enabled:
                try:
                    summary = summariser.summarise(title, text)
                except ai.AIError as e:
                    print(f"    ! summary for {title}: {e}")
            path = captions.save_transcript(dest, title, source, url, text,
                                            summary)
            manifest.add(key, path, path.stat().st_size)
            print(f"    + {_rel(cfg, path)}  ({len(text):,} chars)")
            new += 1

    # Transcripts saved before the AI was configured still deserve a summary.
    if summariser.enabled:
        for week in cfg.weeks:
            for path in captions.transcripts_without_summary(
                    week_dir(cfg, unit.code, week)):
                try:
                    body = path.read_text(encoding="utf-8")
                    summary = summariser.summarise(path.stem, body)
                except (OSError, ai.AIError) as e:
                    print(f"    ! summary for {path.stem}: {e}")
                    continue
                if summary:
                    captions.add_summary(path, summary)
                    print(f"    ~ summary added to {_rel(cfg, path)}")
    return new


def _write_week_notes(cfg: Config, unit: Unit,
                      week_links: dict[int, list[tuple[str, str]]],
                      assessments: list[notes.Assessment]) -> list[Path]:
    """Refresh the per-week summary note for every week that has content."""
    written = []
    for week in cfg.weeks:
        note = notes.WeekNote(
            unit=unit.code, week=week,
            folder=week_dir(cfg, unit.code, week),
            links=week_links.get(week, []),
            assessments=assessments,
        )
        path = notes.write_note(cfg, note)
        if path:
            written.append(path)
    return written


def sync(cfg: Config, headful: bool = False,
         only_units: list[str] | None = None,
         background: bool = False) -> None:
    """Run one sync. `background` adds a desktop notification on new files,
    since an unattended run has no console for the user to read."""
    if not lock.acquire("sync"):
        print("Another sync is already running - skipping this one.")
        return
    try:
        new_files = _sync_locked(cfg, headful, only_units)
        history.record("ok", new_files)
        if background and new_files:
            notify(f"{new_files} new file{'s' if new_files != 1 else ''} "
                   "downloaded", f"Saved under {cfg.root_dir.name}.")
    except LoginRequired as e:
        history.record("login-needed", detail=str(e))
        raise
    except Exception as e:
        history.record("error", detail=f"{type(e).__name__}: {e}")
        raise
    finally:
        lock.release("sync")


def _sync_locked(cfg: Config, headful: bool,
                 only_units: list[str] | None) -> int:
    manifest = Manifest(cfg.manifest_path)

    with MoodleSession(cfg, headful=headful) as sess:
        if cfg.course_selection == "starred":
            from .courses import _CODE_RE, fetch_courses
            starred = fetch_courses(sess, cfg.base_url, "favourites")
            units = [Unit(code=c.unit_code, course_id=c.id)
                     for c in starred if _CODE_RE.search(c.unit_code)]
            print("Starred units: " + (", ".join(u.code for u in units)
                                       or "(none - star some on Moodle!)"))
        else:
            units = cfg.units
        if only_units:
            wanted = {u.upper() for u in only_units}
            units = [u for u in units if u.code.upper() in wanted]
        if not units:
            print("No units to sync - check your config.yaml.")
            return 0
        init_folders(cfg, units)
        print(f"Saving files to: {cfg.root_dir}")

        total = 0
        for unit in units:
            total += sync_unit(sess, cfg, manifest, unit)
        # Refresh the stored session after real work, so the next run starts
        # from a session that is minutes old rather than days old.
        sess.refresh_saved_session()
    print(f"\nDone. {total} new file(s) downloaded.")
    return total
