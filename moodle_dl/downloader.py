from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import Config

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _long(p: Path) -> Path:
    """Windows extended-length form so paths beyond 260 chars still work."""
    s = str(p)
    if os.name == "nt" and not s.startswith("\\\\?\\") and len(s) > 240:
        return Path("\\\\?\\" + s)
    return p


def sanitize(name: str, limit: int = 150) -> str:
    """Make a filename safe and short enough, without losing its extension.

    Trimming blindly to a length cut the suffix off a long name, which leaves
    Windows with a file it will not open - and hides the extension from the
    skip-list and video checks that read it back.
    """
    name = _ILLEGAL.sub("_", name).strip(" .")
    if len(name) <= limit:
        return name or "file"
    stem, dot, suffix = name.rpartition(".")
    if dot and stem and 0 < len(suffix) <= 10:
        keep = max(1, limit - len(suffix) - 1)
        name = f"{stem[:keep].strip(' .')}.{suffix}"
    else:
        name = name[:limit]
    return name.strip(" ") or "file"


def filename_from_response(resp, fallback_url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
    if m:
        return sanitize(unquote(m.group(1)))
    m = re.search(r'filename="?([^";]+)"?', cd)
    if m:
        return sanitize(m.group(1))
    path = urlparse(resp.url or fallback_url).path
    return sanitize(unquote(path.rsplit("/", 1)[-1]))


class Manifest:
    """Tracks what has already been downloaded so re-runs only fetch new files."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {}

    def key(self, url: str) -> str:
        return url.split("?")[0] if "pluginfile.php" in url else url

    def has(self, url: str) -> bool:
        entry = self.data.get(self.key(url))
        if not isinstance(entry, dict) or not entry.get("path"):
            return False  # missing or hand-edited entry: fetch it again
        # If the file was deleted locally, download it again.
        return _long(Path(entry["path"])).exists()

    def add(self, url: str, path: Path, size: int) -> None:
        self.data[self.key(url)] = {"path": str(path), "size": size}
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def unique_path(directory: Path, filename: str) -> Path:
    p = directory / filename
    stem, suffix = p.stem, p.suffix
    n = 1
    while _long(p).exists():
        p = directory / f"{stem} ({n}){suffix}"
        n += 1
    return p


def save_response(resp, directory: Path, cfg: Config,
                  manifest: Manifest, source_url: str) -> Path | None:
    """Write a binary response to disk; returns the path or None if skipped."""
    filename = filename_from_response(resp, source_url)
    ext = Path(filename).suffix.lower()
    if cfg.skip_extensions and ext in cfg.skip_extensions:
        return None
    # Recordings are wanted as text, not as gigabytes of video.
    from .captions import VIDEO_EXTS
    if not cfg.download_videos and ext in VIDEO_EXTS:
        return None
    _long(directory).mkdir(parents=True, exist_ok=True)
    body = resp.body()

    # If this exact file is already on disk, adopt it instead of writing a
    # second copy. Without this, a lost or damaged manifest would refill the
    # folders with "name (1).pdf" duplicates.
    target = directory / filename
    if _long(target).exists():
        try:
            if _long(target).stat().st_size == len(body) \
                    and _long(target).read_bytes() == body:
                manifest.add(source_url, target, len(body))
                return None
        except OSError:
            pass

    path = unique_path(directory, filename)
    _long(path).write_bytes(body)
    manifest.add(source_url, path, len(body))
    return path
