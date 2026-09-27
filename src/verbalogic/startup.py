"""Windows shortcuts, per user (no registry, no admin):
- 'Start with Windows': a shortcut in the Startup folder that starts VerbaLogic quietly in the tray.
- Start menu: a 'VerbaLogic' entry that opens the popup, so it can be searched and pinned like any app.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


def _programs() -> Path:
    return Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs"


def shortcut_path() -> Path:
    return _programs() / "Startup" / "VerbaLogic.lnk"


def menu_shortcut_path() -> Path:
    return _programs() / "VerbaLogic.lnk"


def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def is_enabled() -> bool:
    return shortcut_path().exists()


def set_enabled(enabled: bool, icon_path: Path | None = None) -> bool:
    link = shortcut_path()
    if not enabled:
        link.unlink(missing_ok=True)
        return True
    return _create(link, "-m verbalogic", "VerbaLogic translator", icon_path)


def ensure_menu_shortcut(icon_path: Path | None = None) -> bool:
    """Create the Start menu entry if it's missing. It opens the popup (starting the app if needed)."""
    link = menu_shortcut_path()
    if link.exists():
        return True
    return _create(link, "-m verbalogic --open", "Open the VerbaLogic translator", icon_path)


def _create(link: Path, arguments: str, description: str, icon_path: Path | None) -> bool:
    esc = lambda s: str(s).replace("'", "''")  # noqa: E731 - PowerShell single-quote escaping
    lines = [
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s')" % esc(link),
        "$s.TargetPath = '%s'" % esc(_pythonw()),
        "$s.Arguments = '%s'" % esc(arguments),
        "$s.WorkingDirectory = '%s'" % esc(Path.home()),
        "$s.Description = '%s'" % esc(description),
    ]
    if icon_path and icon_path.exists():
        lines.append("$s.IconLocation = '%s'" % esc(icon_path))
    lines.append("$s.Save()")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "; ".join(lines)],
        capture_output=True, creationflags=CREATE_NO_WINDOW,
    )
    return result.returncode == 0 and link.exists()
