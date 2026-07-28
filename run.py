#!/usr/bin/env python3
"""Moodle Downloader - sync Moodle course files into weekly folders.

Double-click (or run with no arguments) for the interactive menu.

Command line usage:
  run.py setup               # first-time setup wizard
  run.py init                # create the unit/week folder structure
  run.py sync                # download new files (login window on first run)
  run.py sync --unit FIT1045 # only one unit
  run.py sync --headful      # force a visible browser window
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from moodle_dl.config import load_config
from moodle_dl.folders import init_folders
from moodle_dl.main import sync
from moodle_dl.setup_wizard import run_setup


def app_dir() -> Path:
    if getattr(sys, "frozen", False):  # packaged exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_config_path() -> Path:
    return app_dir() / "config.yaml"


def _load_or_offer_setup(config_path: Path):
    if not config_path.exists():
        print("No settings found yet - let's set things up first.")
        return run_setup(config_path)
    return load_config(config_path)


def menu() -> int:
    config_path = default_config_path()
    while True:
        print()
        print("=== Moodle Downloader ===")
        print("  [1] Sync course files now")
        print("  [2] First-time setup / change courses")
        print("  [3] Turn ON auto-sync (at login, then every few hours)")
        print("  [4] Turn OFF auto-sync")
        print("  [5] Exit")
        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if choice == "1":
            cfg = _load_or_offer_setup(config_path)
            if cfg:
                _try_sync(cfg)
        elif choice == "2":
            cfg = run_setup(config_path)
            if cfg:
                try:
                    now = input("Sync your files right now? [Y/n]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    now = "n"
                if now in ("", "y", "yes"):
                    _try_sync(cfg)
        elif choice == "3":
            if sys.platform != "win32":
                print("Auto-sync setup is Windows-only for now; "
                      "use cron on macOS/Linux.")
                continue
            from moodle_dl.schedule_win import enable
            hours = 3
            if config_path.exists():
                try:
                    hours = max(1, round(load_config(config_path)
                                         .sync_interval_hours))
                except Exception:
                    pass
            enable(hours)
        elif choice == "4":
            if sys.platform != "win32":
                continue
            from moodle_dl.schedule_win import disable
            disable()
        elif choice == "5":
            return 0
        else:
            print(f"'{choice}' is not an option - please enter a number "
                  "from 1 to 5.")


def _try_sync(cfg) -> None:
    try:
        sync(cfg)
    except Exception as e:
        print(f"\nSomething went wrong: {e}")
        print("Try again; if it keeps failing, report it on GitHub.")


def _hide_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def autosync_loop(config_path: Path) -> int:
    """Background mode used on PCs where Task Scheduler is locked down:
    started at logon, hides its console, then syncs every few hours until
    the user turns auto-sync off (the loop notices within a minute)."""
    import random
    import time

    from moodle_dl import lock
    from moodle_dl.schedule_win import autosync_enabled

    _hide_console()
    if not lock.acquire("autosync"):
        return 0  # another loop is already running
    try:
        while autosync_enabled():
            interval_h = 3.0
            try:
                cfg = load_config(config_path)
                interval_h = max(cfg.sync_interval_hours, 0.5)
                sync(cfg)
            except Exception:
                pass  # network hiccup etc. - try again next round
            # spread users out a little so everyone doesn't hit Moodle
            # at the same instant
            wake = time.monotonic() + interval_h * 3600 + random.uniform(-900, 900)
            while time.monotonic() < wake:
                if not autosync_enabled():
                    return 0
                time.sleep(60)
    finally:
        lock.release("autosync")
    return 0


def cli() -> int:
    if len(sys.argv) == 1:
        return menu()

    ap = argparse.ArgumentParser(prog="moodle-dl", description=__doc__)
    ap.add_argument("-c", "--config", default=str(default_config_path()),
                    help="path to config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="interactive first-time setup")
    sub.add_parser("menu", help="interactive menu")
    sub.add_parser("init", help="create the unit/week folder structure")
    sub.add_parser("autosync", help="background loop used by auto-sync")

    p_sync = sub.add_parser("sync", help="download new files from Moodle")
    p_sync.add_argument("--headful", action="store_true",
                        help="show the browser window")
    p_sync.add_argument("--unit", action="append", default=None,
                        help="sync only this unit code (repeatable)")

    args = ap.parse_args()
    config_path = Path(args.config)

    if args.cmd == "setup":
        return 0 if run_setup(config_path) else 1
    if args.cmd == "menu":
        return menu()
    if args.cmd == "autosync":
        return autosync_loop(config_path)

    cfg = _load_or_offer_setup(config_path)
    if cfg is None:
        return 1

    if args.cmd == "init":
        for d in init_folders(cfg):
            print(f"+ {d}")
        print(f"Folder structure ready under: {cfg.root_dir}")
        return 0
    if args.cmd == "sync":
        sync(cfg, headful=args.headful, only_units=args.unit)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(cli())
