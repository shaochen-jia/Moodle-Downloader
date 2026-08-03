"""Ed (edstem.org) lessons: fetch course lessons and turn each slide's
content into Markdown filed under the matching week folder.

Ed authenticates its own API with a short-lived `x-token` header that its
front-end sends. We never ask for a token: we load a page in the already
signed-in browser and read the token off the requests the page makes.
"""
from __future__ import annotations

import base64
import dataclasses
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from .downloader import Manifest, sanitize
from .session import MoodleSession

API = "https://edstem.org/api"
TOKEN_WAIT_MS = 20_000


@dataclasses.dataclass
class Lesson:
    id: int
    title: str
    available_at: str | None
    updated_at: str | None


class EdClient:
    """Thin wrapper over Ed's own JSON API, borrowing the browser session."""

    def __init__(self, sess: MoodleSession):
        self.sess = sess
        self.token: str | None = None

    def sign_in(self, course_id: int) -> bool:
        """Load a course page so the front-end reveals its API token."""
        tokens: list[str] = []

        def grab(req):
            tok = req.headers.get("x-token")
            if tok and "edstem" in req.url and tok not in tokens:
                tokens.append(tok)

        page = self.sess.ctx.new_page()
        page.on("request", grab)
        try:
            page.goto(f"https://edstem.org/au/courses/{course_id}/lessons",
                      wait_until="domcontentloaded")
            waited = 0
            while not tokens and waited < TOKEN_WAIT_MS:
                page.wait_for_timeout(1000)
                waited += 1000
            if not tokens and "/login" in page.url:
                # Ed needs its own first sign-in; it uses the same university
                # account, so this is usually one click.
                self.sess._show_window(page)
                print("  Sign in to Ed in the browser window "
                      "(same university account)...")
                waited = 0
                while not tokens and waited < 5 * 60_000:
                    page.wait_for_timeout(2000)
                    waited += 2000
                if tokens:
                    self.sess._hide_window(page)
        finally:
            page.close()
        self.token = tokens[0] if tokens else None
        return bool(self.token)

    def _get(self, path: str):
        resp = self.sess.ctx.request.get(f"{API}{path}",
                                         headers={"x-token": self.token or ""})
        if not resp.ok:
            raise RuntimeError(f"Ed API {path} -> HTTP {resp.status}")
        # Ed serves UTF-8 without always declaring it, and the default decode
        # turns every dash and quote into mojibake - decode explicitly.
        return json.loads(resp.body().decode("utf-8", errors="replace"))

    def lessons(self, course_id: int) -> list[Lesson]:
        data = self._get(f"/courses/{course_id}/lessons")
        out = []
        for l in data.get("lessons", []):
            if l.get("is_hidden"):
                continue
            out.append(Lesson(id=int(l["id"]), title=(l.get("title") or "").strip(),
                              available_at=l.get("available_at"),
                              updated_at=l.get("updated_at")))
        return out

    def slides(self, lesson_id: int) -> list[dict]:
        data = self._get(f"/lessons/{lesson_id}")
        return data.get("lesson", {}).get("slides", [])


# ─── content conversion ──────────────────────────────────────────────────────

_INLINE = {"bold": "**", "italic": "*", "code": "`", "underline": "_"}


def _inner(node, images, depth, sep: str = "") -> str:
    """Text of a node's children, keeping the text that follows each child.

    ElementTree stores text after a child element on that child's `.tail`;
    ignoring it silently drops half of every sentence that contains bold or
    inline code.
    """
    parts = [node.text or ""]
    for child in node:
        parts.append(_convert(child, images, depth + 1))
        if child.tail:
            parts.append(child.tail)
        if sep:
            parts.append(sep)
    return "".join(parts)


def _convert(node, images: list[tuple[str, bytes]], depth: int = 0) -> str:
    """Ed's <document> XML -> Markdown. Images are collected for saving."""
    tag = node.tag

    if tag == "document":
        blocks = []
        for c in node:
            block = _convert(c, images, depth + 1)
            if c.tail and c.tail.strip():
                block = (block + " " + c.tail.strip()).strip()
            if block.strip():
                blocks.append(block)
        return "\n\n".join(blocks)
    if tag == "heading":
        level = int(node.get("level", 2))
        return "#" * min(level, 6) + " " + _inner(node, images, depth).strip()
    if tag == "paragraph":
        return re.sub(r"[ \t]{2,}", " ", _inner(node, images, depth)).strip()
    if tag in _INLINE:
        mark = _INLINE[tag]
        inner = _inner(node, images, depth).strip()
        return f"{mark}{inner}{mark}" if inner else ""
    if tag == "link":
        label = _inner(node, images, depth).strip()
        href = node.get("href", "")
        return f"[{label or href}]({href})"
    if tag == "list":
        numbered = node.get("style") == "number"
        items = []
        for i, c in enumerate(node, 1):
            mark = f"{i}." if numbered else "-"
            body = _convert(c, images, depth + 1).strip()
            body = body.replace("\n", "\n  ")
            items.append(f"{mark} {body}")
        return "\n".join(items)
    if tag == "list-item":
        return _inner(node, images, depth, sep="\n").strip()
    if tag == "snippet":
        lang = node.get("language", "")
        body = "\n".join((c.text or "") for c in node if c.tag == "snippet-file")
        return f"```{lang}\n{body}\n```"
    if tag == "callout":
        kind = (node.get("type") or "note").title()
        body = "\n\n".join(
            b for b in (_convert(c, images, depth + 1) for c in node) if b.strip())
        quoted = "\n".join("> " + line for line in body.splitlines())
        return f"> **{kind}**\n>\n{quoted}"
    if tag == "figure":
        return "\n\n".join(
            b for b in (_convert(c, images, depth + 1) for c in node) if b.strip())
    if tag == "image":
        src = node.get("src", "")
        if src.startswith("data:"):
            try:
                head, b64 = src.split(",", 1)
                ext = "png" if "png" in head else "jpg"
                images.append((f"image-{len(images) + 1}.{ext}",
                               base64.b64decode(b64)))
                return f"![]({'images/' + images[-1][0]})"
            except Exception:
                return ""
        return f"![]({src})"
    if tag in ("break", "hr"):
        return "---"
    # unknown wrapper: keep whatever text it holds
    return _inner(node, images, depth).strip()


def to_markdown(content: str) -> tuple[str, list[tuple[str, bytes]]]:
    """Returns (markdown, [(image filename, bytes), ...])."""
    images: list[tuple[str, bytes]] = []
    if not content:
        return "", images
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        text = re.sub(r"<[^>]+>", " ", content)
        return re.sub(r"\s{2,}", " ", text).strip(), images
    md = _convert(root, images)
    return re.sub(r"\n{3,}", "\n\n", md).strip(), images


# ─── syncing ─────────────────────────────────────────────────────────────────

def lesson_key(lesson: Lesson, slides: list[dict]) -> str:
    """Manifest key that changes whenever staff edit any slide in the lesson."""
    stamps = ":".join(f"{s['id']}@{s.get('updated_at') or ''}" for s in slides)
    return f"ed-lesson:{lesson.id}:{abs(hash(stamps))}"


def save_lesson(lesson: Lesson, slides: list[dict], dest: Path,
                fetch=None) -> Path | None:
    """Write one lesson as a single Markdown file.

    A seminar is dozens of slides; as separate files they are unreadable, so
    each slide becomes a section of one document instead.
    """
    title = sanitize(lesson.title or "Ed lesson")
    images: list[tuple[str, bytes]] = []
    body: list[str] = []

    for slide in slides:
        md, imgs = to_markdown(slide.get("content") or "")
        if not md.strip():
            continue
        slide_title = (slide.get("title") or "").strip()
        # A slide whose content already opens with its own heading needs no
        # second one.
        if slide_title and not md.lstrip().startswith(("# ", "## ")):
            body.append(f"## {slide_title}\n\n{md}")
        else:
            body.append(md)
        images.extend(imgs)

    if not body:
        return None

    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"Ed - {title}.md"
    text = "\n\n---\n\n".join(body)

    # Spaces in an image path break the Markdown link in most viewers.
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-")
    img_dir = dest / "images"

    if images:
        img_dir.mkdir(parents=True, exist_ok=True)
        for name, blob in images:
            fname = f"{stem}-{name}"
            (img_dir / fname).write_bytes(blob)
            text = text.replace(f"images/{name}", f"images/{fname}")

    # Ed also hosts images remotely; pull them down so the notes work offline.
    if fetch:
        for i, url in enumerate(dict.fromkeys(
                re.findall(r"!\[\]\((https?://[^)]+)\)", text)), 1):
            try:
                blob = fetch(url)
            except Exception:
                continue
            if not blob:
                continue
            ext = ".png" if blob[:4] == b"\x89PNG" else ".jpg"
            fname = f"{stem}-remote-{i}{ext}"
            img_dir.mkdir(parents=True, exist_ok=True)
            (img_dir / fname).write_bytes(blob)
            text = text.replace(f"]({url})", f"](images/{fname})")

    header = f"# {lesson.title}\n\n*Synced from Ed*\n\n---\n\n"
    path.write_text(header + text + "\n", encoding="utf-8")
    return path
