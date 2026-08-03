"""Best-effort desktop notification.

Used when a background sync genuinely needs the user - otherwise the login
window can open unnoticed and the run quietly gives up.
"""
from __future__ import annotations

import subprocess
import sys

_PS_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
      [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName('text')
$x.Item(0).AppendChild($t.CreateTextNode('{title}')) > $null
$x.Item(1).AppendChild($t.CreateTextNode('{body}')) > $null
$n = [Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(
      '{app}').Show($n)
"""


def notify(title: str, body: str) -> None:
    if sys.platform != "win32":
        return
    safe = lambda s: s.replace("'", " ").replace("\n", " ")  # noqa: E731
    script = _PS_TOAST.format(title=safe(title), body=safe(body),
                              app="Moodle Downloader")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=20,
            creationflags=0x08000000,  # no console window
        )
    except Exception:
        pass  # a missing notification must never break a sync
