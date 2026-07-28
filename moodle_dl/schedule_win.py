from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TASK_NAME = "MoodleDownloader"

# Keeps schtasks from flashing a console window in the windowed build
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          creationflags=_NO_WINDOW)

# Preferred route: a scheduled task that fires at logon and then repeats
# every few hours all day. StartWhenAvailable catches missed runs after
# boot/wake, so people who first turn the PC on at night still sync.
_TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Moodle Downloader - sync course files automatically</Description>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>{userid}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Triggers>
    <LogonTrigger>
      <Repetition>
        <Interval>PT{hours}H</Interval>
        <Duration>P1D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <Enabled>true</Enabled>
      <Delay>PT1M</Delay>
    </LogonTrigger>
    <CalendarTrigger>
      <Repetition>
        <Interval>PT{hours}H</Interval>
        <Duration>P1D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _command_and_args(mode: str) -> tuple[str, str]:
    if getattr(sys, "frozen", False):  # packaged exe
        return sys.executable, mode
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    return sys.executable, f'"{run_py}" {mode}'


def _startup_bat() -> Path:
    return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows"
            / "Start Menu" / "Programs" / "Startup" / "MoodleDownloader.bat")


def autosync_enabled() -> bool:
    """Used by the background loop to notice it has been turned off."""
    return _startup_bat().exists()


def _enable_task(interval_hours: int) -> bool:
    command, arguments = _command_and_args("sync")
    userid = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    xml = _TASK_XML.format(command=command, arguments=arguments,
                           userid=userid, hours=interval_hours)
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                     encoding="utf-16") as f:
        f.write(xml)
        xml_path = f.name
    try:
        result = _run(["schtasks", "/Create", "/TN", TASK_NAME,
                       "/XML", xml_path, "/F"])
    finally:
        Path(xml_path).unlink(missing_ok=True)
    return result.returncode == 0


def _enable_startup_folder() -> bool:
    """Fallback: a Startup-folder script that starts the background loop."""
    command, arguments = _command_and_args("autosync")
    bat = _startup_bat()
    try:
        bat.write_text(f'@echo off\nstart "" /min "{command}" {arguments}\n',
                       encoding="ascii", errors="replace")
    except OSError:
        return False
    # start the loop right away too - no reboot needed
    try:
        DETACHED_PROCESS = 0x00000008
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "autosync"]
        else:
            run_py = Path(__file__).resolve().parent.parent / "run.py"
            cmd = [sys.executable, str(run_py), "autosync"]
        subprocess.Popen(cmd, creationflags=DETACHED_PROCESS | _NO_WINDOW,
                         close_fds=True)
    except Exception:
        pass
    return True


def enable(interval_hours: int = 3) -> bool:
    """Turn on auto-sync: at logon and then every `interval_hours`."""
    if _enable_task(interval_hours):
        print("Done - your files now sync automatically:")
        print(f"  - when you log in to Windows, then every {interval_hours} "
              "hours while the PC is on")
        print("(It runs silently in the background - no window appears.)")
        return True
    # Task Scheduler can be locked down (e.g. managed laptops) - fall back
    # to a Startup script + background loop, which never needs rights.
    if _enable_startup_folder():
        print("Done - your files now sync automatically:")
        print(f"  - when you log in to Windows, then every {interval_hours} "
              "hours in the background")
        return True
    print("Sorry - couldn't set up auto-sync on this PC. "
          "You can still sync manually.")
    return False


def disable() -> bool:
    removed = False
    removed |= _run(["schtasks", "/Delete", "/TN", TASK_NAME,
                     "/F"]).returncode == 0
    bat = _startup_bat()
    if bat.exists():
        bat.unlink()
        removed = True
    print("Auto-sync removed." if removed
          else "Auto-sync wasn't on (nothing to remove).")
    if removed:
        print("(Any background loop notices within a minute and stops.)")
    return removed