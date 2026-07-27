from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TASK_NAME = "MoodleDownloader"

# Two triggers: every Windows logon (1 min delay), plus a daily 09:00 run
# with StartWhenAvailable so a missed 09:00 fires as soon as the PC wakes.
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
      <Enabled>true</Enabled>
      <Delay>PT1M</Delay>
    </LogonTrigger>
    <CalendarTrigger>
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


def _command_and_args() -> tuple[str, str]:
    if getattr(sys, "frozen", False):  # packaged exe
        return sys.executable, "sync"
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    return sys.executable, f'"{run_py}" sync'


def _startup_bat() -> Path:
    return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows"
            / "Start Menu" / "Programs" / "Startup" / "MoodleDownloader.bat")


def _enable_task() -> bool:
    command, arguments = _command_and_args()
    userid = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    xml = _TASK_XML.format(command=command, arguments=arguments, userid=userid)
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                     encoding="utf-16") as f:
        f.write(xml)
        xml_path = f.name
    try:
        result = subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME,
             "/XML", xml_path, "/F"],
            capture_output=True, text=True)
    finally:
        Path(xml_path).unlink(missing_ok=True)
    return result.returncode == 0


def _enable_startup_folder() -> bool:
    command, arguments = _command_and_args()
    bat = _startup_bat()
    try:
        bat.write_text(f'@echo off\nstart "" /min "{command}" {arguments}\n',
                       encoding="ascii", errors="replace")
    except OSError:
        return False
    return True


def enable() -> bool:
    """Turn on auto-sync: at every logon, plus a daily catch-up run."""
    if _enable_task():
        print("Done - your files now sync automatically:")
        print("  - every time you log in to Windows (1 minute after logon)")
        print("  - plus a daily 09:00 run if the PC is already on")
        print("(A small console window appears briefly while it runs.)")
        return True
    # Task Scheduler can be locked down (e.g. managed laptops) - fall back
    # to a script in the user's Startup folder, which never needs rights.
    if _enable_startup_folder():
        print("Done - your files now sync automatically every time you "
              "log in to Windows.")
        print("(A small console window appears briefly while it runs.)")
        return True
    print("Sorry - couldn't set up auto-sync on this PC. "
          "You can still sync manually.")
    return False


def disable() -> bool:
    removed = False
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True)
    removed |= result.returncode == 0
    bat = _startup_bat()
    if bat.exists():
        bat.unlink()
        removed = True
    print("Auto-sync removed." if removed
          else "Auto-sync wasn't on (nothing to remove).")
    return removed
