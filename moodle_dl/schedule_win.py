from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TASK_NAME = "MoodleDownloader"


def _sync_command() -> str:
    if getattr(sys, "frozen", False):  # packaged exe
        return f'"{sys.executable}" sync'
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{sys.executable}" "{run_py}" sync'


def enable_daily(time_str: str = "09:00") -> bool:
    """Create/replace a Windows scheduled task that syncs daily."""
    result = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", _sync_command(),
         "/SC", "DAILY", "/ST", time_str, "/F"],
        capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Could not create the scheduled task: {result.stderr.strip()}")
        return False
    print(f"Done - files will sync automatically every day at {time_str}.")
    print("(A small console window appears briefly while it runs.)")
    return True


def disable() -> bool:
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True)
    if result.returncode != 0:
        print("No auto-sync task was found (nothing to remove).")
        return False
    print("Auto-sync removed.")
    return True
