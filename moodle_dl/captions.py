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
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .downloader import sanitize
from .session import MoodleSession

TRANSCRIPT_DIR = "Transcripts"

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

    def _sign_in(self, host: str) -> bool:
        page = self.sess.ctx.new_page()
        try:
            page.goto(f"https://{host}/Panopto/Pages/Sessions/List.aspx",
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            if "Login.aspx" in page.url:
                # Choose the university provider, then submit.
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
                            break
                except Exception:
                    pass
                for _ in range(30):
                    page.wait_for_timeout(2000)
                    if "Login.aspx" not in page.url:
                        break
            ok = "Login.aspx" not in page.url
        except Exception:
            ok = False
        finally:
            page.close()
        if ok:
            self.ready.add(host)
        return ok

    def transcript(self, host: str, guid: str) -> tuple[str, str] | None:
        """Returns (session title, transcript text) when captions exist."""
        if host not in self.ready and not self._sign_in(host):
            return None
        base = f"https://{host}/Panopto"
        info = self.sess.ctx.request.post(
            f"{base}/Pages/Viewer/DeliveryInfo.aspx",
            form={"deliveryId": guid, "responseType": "json"})
        if not info.ok:
            return None
        try:
            deliv = info.json().get("Delivery", {})
        except Exception:
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


def youtube_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(snippet.text for snippet in fetched)
        return srt_to_text(text) if text.strip() else None
    except Exception:
        return None  # no captions, age-gated, or region blocked


def save_transcript(dest: Path, title: str, source: str, url: str,
                    text: str, summary: str = "") -> Path:
    folder = dest / TRANSCRIPT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sanitize(title)}.md"
    header = (f"# {title}\n\n"
              f"*Transcript from {source} — [original recording]({url})*\n\n"
              f"---\n\n")
    if summary:
        header += (f"## Summary\n\n{summary}\n\n---\n\n"
                   f"## Full transcript\n\n")
    path.write_text(header + text + "\n", encoding="utf-8")
    return path
