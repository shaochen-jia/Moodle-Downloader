from __future__ import annotations

import ctypes
import os
from pathlib import Path


def _lock_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local"))
    d = base / "moodle-downloader"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    return bool(ok) and code.value == STILL_ACTIVE


def acquire(name: str) -> bool:
    """Take the named lock; False if another live process holds it."""
    path = _lock_dir() / f"{name}.lock"
    if path.exists():
        try:
            pid = int(path.read_text().strip())
        except (ValueError, OSError):
            pid = -1
        if pid > 0 and pid != os.getpid() and _pid_alive(pid):
            return False
    path.write_text(str(os.getpid()))
    return True


def release(name: str) -> None:
    path = _lock_dir() / f"{name}.lock"
    try:
        if path.exists() and path.read_text().strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass
