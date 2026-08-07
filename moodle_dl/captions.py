"""Lecture transcripts.

Recordings themselves are huge and often not downloadable, but their
captions are just text - and text is what makes a lecture searchable,
skimmable, and summarisable later.

Panopto captions come from the university's own Panopto site (one extra
single sign-on, no password); YouTube captions come from the public
transcript endpoint.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import documents
from .downloader import sanitize
from .session import MoodleSession

TRANSCRIPT_DIR = "Transcripts"

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".wmv", ".flv",
              ".mp3", ".m4a", ".wav"}

# Why a recording produced no transcript. The distinction matters: "none"
# is final, "blocked" and "error" are worth trying again next sync.
NONE = "none"            # the recording genuinely has no captions
BLOCKED = "blocked"      # the platform is rate-limiting us
ERROR = "error"          # network or platform failure
SIGNIN = "needs-signin"  # the platform wants a human to authenticate
DEFERRED = "deferred"    # held back on purpose to avoid a burst of requests

RETRYABLE = {BLOCKED, ERROR, SIGNIN, DEFERRED}

YOUTUBE_MIN_GAP_S = 4.0  # spacing between YouTube caption requests

_REASON_TEXT = {
    NONE: "no captions published",
    BLOCKED: "the platform is rate-limiting us - will retry",
    ERROR: "could not be reached - will retry",
    SIGNIN: "needs you to sign in to the video platform",
    DEFERRED: "queued for the next sync, to stay under YouTube's limits",
}


def reason_text(reason: str) -> str:
    return _REASON_TEXT.get(reason, reason)


def is_video_file(name_or_url: str) -> bool:
    lowered = name_or_url.split("?")[0].lower()
    return any(lowered.endswith(ext) for ext in VIDEO_EXTS)

_PANOPTO_HOST = re.compile(r"https://([\w.-]*panopto\.com)", re.I)
_YT_ID = re.compile(r"(?:v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def panopto_ids(url: str) -> tuple[str, str] | None:
    """(host, session guid) for a Panopto viewer link."""
    host = _PANOPTO_HOST.match(url)
    if not host:
        return None
    guid = parse_qs(urlparse(url).query).get("id", [None])[0]
    return (host.group(1), guid) if guid else None


def youtube_id(url: str) -> str | None:
    m = _YT_ID.search(url)
    return m.group(1) if m else None


def srt_to_text(srt: str) -> str:
    """Strip cue numbers and timestamps, leaving readable prose."""
    lines = []
    for raw in srt.splitlines():
        line = raw.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\[Auto-generated transcript[^\]]*\]\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Break into paragraphs so the file is readable rather than one blob
    sentences = re.split(r"(?<=[.!?])\s+", text)
    paras, buf = [], []
    for s in sentences:
        buf.append(s)
        if len(buf) >= 6:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)


class PanoptoClient:
    """Fetches captions from a Panopto site, signing in through the
    institution's identity provider on first use."""

    def __init__(self, sess: MoodleSession):
        self.sess = sess
        self.ready: set[str] = set()

    @staticmethod
    def _choose_institution(page) -> None:
        """Panopto's login page asks which identity provider to use."""
        try:
            options = page.evaluate(
                "() => { const s = document.querySelector('select');"
                " return s ? [...s.options].map(o => ({t:o.text, v:o.value})) : []; }")
            pick = next((o for o in options
                         if "okta" in o["t"].lower()
                         or "monash" in o["t"].lower()), None)
            if pick:
                page.select_option("select", pick["v"])
                page.wait_for_timeout(400)
            for sel in ("#loginButton", "input[type=submit]",
                        "button[type=submit]", "a:has-text('Sign in')"):
                el = page.query_selector(sel)
                if el:
                    el.click()
                    return
        except Exception:
            pass

    def _open(self, url: str, done: str, tries: int = 3) -> bool:
        """Open a Panopto page, completing sign-in as many times as it asks."""
        page = self.sess.ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            for _ in range(tries):
                if "Login.aspx" not in page.url:
                    break
                self._choose_institution(page)
                for _ in range(20):
                    page.wait_for_timeout(1500)
                    if "Login.aspx" not in page.url:
                        break
            return done in page.url and "Login.aspx" not in page.url
        except Exception:
            return False
        finally:
            page.close()

    def _sign_in(self, host: str) -> bool:
        ok = self._open(f"https://{host}/Panopto/Pages/Sessions/List.aspx",
                        done="/Panopto/Pages/")
        if ok:
            self.ready.add(host)
        return ok

    def _authorise_video(self, host: str, guid: str) -> bool:
        """Panopto grants access per recording, not once per site.

        Reading a session's metadata without opening its viewer first returns
        an empty response - which looks exactly like "this video has no
        captions". Opening the viewer performs the per-video authorisation.
        """
        return self._open(
            f"https://{host}/Panopto/Pages/Viewer.aspx?id={guid}",
            done="Viewer.aspx")

    def _delivery(self, host: str, guid: str) -> dict:
        info = self.sess.ctx.request.post(
            f"https://{host}/Panopto/Pages/Viewer/DeliveryInfo.aspx",
            form={"deliveryId": guid, "responseType": "json"})
        if not info.ok:
            return {}
        try:
            return info.json().get("Delivery", {}) or {}
        except Exception:
            return {}

    def transcript(self, host: str, guid: str) -> tuple[str, str] | None:
        """Returns (session title, transcript text) when captions exist."""
        if host not in self.ready and not self._sign_in(host):
            return None
        base = f"https://{host}/Panopto"
        deliv = self._delivery(host, guid)
        if not deliv.get("SessionName"):
            # Empty means "not authorised for this recording yet", not
            # "no such recording" - open its viewer and ask again.
            if self._authorise_video(host, guid):
                deliv = self._delivery(host, guid)
        if not deliv:
            return None
        if not deliv.get("HasCaptions"):
            return None
        title = deliv.get("SessionName") or guid
        # The language code varies per site; take it from the session itself.
        langs = [c.get("Language") for c in deliv.get("AvailableCaptions", [])]
        for lang in langs or [0]:
            r = self.sess.ctx.request.get(
                f"{base}/Pages/Transcription/GenerateSRT.ashx"
                f"?id={guid}&language={lang}")
            if r.ok:
                srt = r.text()
                if len(srt) > 50:
                    return title, srt_to_text(srt)
        return None


def youtube_title(video_id: str) -> str | None:
    """The video's real title, so several videos in one week do not all end
    up sharing a filename."""
    import json
    import urllib.request
    url = ("https://www.youtube.com/oembed?format=json&url="
           f"https://www.youtube.com/watch%3Fv%3D{video_id}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")).get("title")
    except Exception:
        return None


_last_youtube_call = 0.0


def youtube_transcript(video_id: str) -> tuple[str | None, str]:
    """(text, reason). Requests are spaced out: fetching many transcripts
    back to back is what gets an IP rate-limited in the first place."""
    global _last_youtube_call
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None, ERROR

    wait = YOUTUBE_MIN_GAP_S - (time.monotonic() - _last_youtube_call)
    if wait > 0:
        time.sleep(wait)
    _last_youtube_call = time.monotonic()

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(snippet.text for snippet in fetched)
        return (srt_to_text(text), "ok") if text.strip() else (None, NONE)
    except Exception as e:
        name = type(e).__name__
        if "IpBlocked" in name or "TooManyRequests" in name or "429" in str(e):
            return None, BLOCKED
        if "Disabled" in name or "NoTranscript" in name or "NotFound" in name:
            return None, NONE
        return None, ERROR


def caption_track_urls(html: str, base_url: str) -> list[str]:
    """Subtitle files a Moodle player advertises next to a video."""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for track in soup.select("track[src]"):
        kind = (track.get("kind") or "").lower()
        if kind in ("", "captions", "subtitles"):
            out.append(urljoin(base_url, track["src"]))
    for a in soup.select('a[href$=".vtt"], a[href$=".srt"]'):
        out.append(urljoin(base_url, a["href"]))
    return out


def vtt_to_text(vtt: str) -> str:
    """WebVTT shares SRT's shape once the header and cue ids are gone."""
    body = re.sub(r"^WEBVTT.*?\n\n", "", vtt, flags=re.S)
    body = re.sub(r"^\s*\d+\s*$", "", body, flags=re.M)
    return srt_to_text(body)


SUMMARY_HEADING = "## Summary"


def transcripts_without_summary(week_folder: Path) -> list[Path]:
    """Transcripts still waiting for a summary.

    The readable copy is what we inspect, because the Word version cannot be
    read back as text - and a summary that failed on one run has to be
    retried on the next.
    """
    folder = week_folder / TRANSCRIPT_DIR
    if not folder.exists():
        return []
    out = []
    for ext in (".txt", ".md"):
        for p in sorted(folder.glob(f"*{ext}")):
            if p.with_suffix(".txt") in out or p.with_suffix(".md") in out:
                continue
            try:
                body = p.read_text(encoding="utf-8")
            except OSError:
                continue
            head = "\n".join(body.splitlines()[:40])
            if "Summary" not in head:
                out.append(p)
    return out


def _split_transcript(text: str) -> tuple[str, str, str]:
    """(title, source line, transcript body) from a saved transcript."""
    lines = text.splitlines()
    title = ""
    source = ""
    for line in lines[:8]:
        clean = line.lstrip("# ").strip()
        if clean and not title and not set(clean) <= set("-="):
            title = clean
        elif clean.lower().startswith("transcript from"):
            source = clean
    marker = "Full transcript"
    if marker in text:
        body = text.split(marker, 1)[1]
    else:
        # No summary yet: everything after the source line is the transcript.
        body = text.split(source, 1)[-1] if source else text
    return title, source, body.lstrip("\n-\n").lstrip()


def add_summary(path: Path, summary: str,
                formats=documents.DEFAULT_FORMATS) -> None:
    """Rebuild a transcript with its summary, in every chosen format."""
    title, source, body = _split_transcript(
        path.read_text(encoding="utf-8"))
    md = (f"# {title}\n\n*{source}*\n\n---\n\n"
          f"{SUMMARY_HEADING}\n\n{summary}\n\n---\n\n"
          f"## Full transcript\n\n{body}\n")
    documents.write(path.with_suffix(""), md, formats)


def save_transcript(dest: Path, title: str, source: str, url: str,
                    text: str, summary: str = "",
                    formats=documents.DEFAULT_FORMATS) -> Path:
    folder = dest / TRANSCRIPT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / sanitize(title)
    header = (f"# {title}\n\n"
              f"*Transcript from {source} — [original recording]({url})*\n\n"
              f"---\n\n")
    if summary:
        header += (f"## Summary\n\n{summary}\n\n---\n\n"
                   f"## Full transcript\n\n")
    written = documents.write(stem, header + text + "\n", formats)
    return written[0] if written else stem.with_suffix(".txt")
