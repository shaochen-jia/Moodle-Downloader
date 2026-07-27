from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import yaml


@dataclasses.dataclass
class Unit:
    code: str
    course_id: int


@dataclasses.dataclass
class Config:
    base_url: str
    root_dir: Path
    week_start: int
    week_end: int
    units: list[Unit]
    section_patterns: list[str]
    unmatched_folder: str
    skip_extensions: list[str]
    config_dir: Path
    course_selection: str = "manual"  # "manual" | "starred"

    @property
    def weeks(self) -> range:
        return range(self.week_start, self.week_end + 1)

    @property
    def session_dir(self) -> Path:
        # Keep the browser profile (cookies!) out of the project folder so it
        # never ends up in git or cloud-synced directories like OneDrive.
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local"))
        return base / "moodle-downloader" / "session"

    @property
    def manifest_path(self) -> Path:
        return self.root_dir / ".manifest.json"


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    units = [Unit(code=str(u["code"]), course_id=int(u["course_id"]))
             for u in raw.get("units", [])]

    root_dir = Path(str(raw.get("root_dir", "./MoodleFiles")))
    if not root_dir.is_absolute():
        root_dir = (path.parent / root_dir).resolve()

    return Config(
        base_url=str(raw.get("base_url", "https://learning.monash.edu")).rstrip("/"),
        root_dir=root_dir,
        week_start=int(raw.get("week_start", 0)),
        week_end=int(raw.get("week_end", 12)),
        units=units,
        section_patterns=list(raw.get("section_patterns",
                                      [r"week\s*0*{week}\b", r"topic\s*0*{week}\b"])),
        unmatched_folder=str(raw.get("unmatched_folder", "_Other")),
        skip_extensions=[e.lower() for e in raw.get("skip_extensions", []) or []],
        config_dir=path.parent,
        course_selection=str(raw.get("course_selection", "manual")),
    )
