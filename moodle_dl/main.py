from __future__ import annotations

from pathlib import Path

from .config import Config, Unit
from .downloader import Manifest, save_response
from .folders import init_folders, unit_dir, week_dir
from .scraper import (Activity, SectionInfo, extract_pluginfile_links,
                      find_section_links, match_week, parse_section_page)
from .session import MoodleSession

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


def sync_unit(sess: MoodleSession, cfg: Config, manifest: Manifest,
              unit: Unit) -> int:
    print(f"\n=== {unit.code} "
          f"({cfg.base_url}/course/view.php?id={unit.course_id}) ===")
    infos = crawl_sections(sess, cfg, unit)
    if not infos:
        print("  ! No sections found - the page layout may be unusual.")
        return 0

    total_new = 0
    for n in sorted(infos):
        info = infos[n]
        if not info.activities:
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
        print(f"  [{label}] {info.title} - {len(info.activities)} item(s)")
        for act in info.activities:
            try:
                new = _download_activity(sess, cfg, manifest, act, dest)
            except Exception as e:
                print(f"    ! {act.name}: {e}")
                continue
            for p in new:
                print(f"    + {p}")
            total_new += len(new)
    return total_new


def sync(cfg: Config, headful: bool = False,
         only_units: list[str] | None = None) -> None:
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
            return
        init_folders(cfg, units)

        total = 0
        for unit in units:
            total += sync_unit(sess, cfg, manifest, unit)
    print(f"\nDone. {total} new file(s) downloaded.")
