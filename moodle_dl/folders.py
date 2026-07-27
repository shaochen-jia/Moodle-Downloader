from __future__ import annotations

from pathlib import Path

from .config import Config


def week_folder_name(week: int) -> str:
    return f"Week {week:02d}"


def unit_dir(cfg: Config, unit_code: str) -> Path:
    return cfg.root_dir / unit_code


def week_dir(cfg: Config, unit_code: str, week: int) -> Path:
    return unit_dir(cfg, unit_code) / week_folder_name(week)


def init_folders(cfg: Config, units=None) -> list[Path]:
    """Create root/<UNIT>/Week 00..Week NN for every unit."""
    created: list[Path] = []
    for unit in (units if units is not None else cfg.units):
        for week in cfg.weeks:
            d = week_dir(cfg, unit.code, week)
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created.append(d)
        if cfg.unmatched_folder:
            d = unit_dir(cfg, unit.code) / cfg.unmatched_folder
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created.append(d)
    return created
