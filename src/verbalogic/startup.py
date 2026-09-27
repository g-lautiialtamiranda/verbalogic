"""Windows shortcuts, per user (no registry, no admin):
- 'Start with Windows': a shortcut in the Startup folder that starts VerbaLogic quietly in the tray.
- Start menu: a 'VerbaLogic' entry that opens the popup, so it can be searched and pinned like any app.
- Icons: every VerbaLogic shortcut, including a taskbar pin, shows the mark in the current accent colour.
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


def pinned_shortcut_path() -> Path:
    """Where Windows keeps its copy of the Start menu entry once it's pinned to the taskbar."""
    return Path(os.environ["APPDATA"], "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar",
                "VerbaLogic.lnk")


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


def update_icons(icon_path: Path) -> bool:
    """Point the Start menu entry, the Startup shortcut and a taskbar pin at icon_path, then remove
    older icon files. A new file name (not a redrawn file) is what makes Windows drop its cached icon."""
    links = [p for p in (menu_shortcut_path(), shortcut_path(), pinned_shortcut_path()) if p.exists()]
    ok = True
    if links:
        lines = []
        for link in links:  # only shortcuts that really start VerbaLogic
            lines += [
                "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s')" % _esc(link),
                "if ($s.Arguments -like '*-m verbalogic*') { $s.IconLocation = '%s,0'; $s.Save() }" % _esc(icon_path),
            ]
        ok = _powershell(lines)
        from .win32 import refresh_shell_icons

        refresh_shell_icons([str(p) for p in links])
    if ok:
        for old in icon_path.parent.glob("verbalogic*.ico"):
            if old != icon_path:
                old.unlink(missing_ok=True)
    return ok


def _esc(s) -> str:
    return str(s).replace("'", "''")  # PowerShell single-quote escaping


def _powershell(lines: list[str]) -> bool:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "; ".join(lines)],
        capture_output=True, creationflags=CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def _create(link: Path, arguments: str, description: str, icon_path: Path | None) -> bool:
    esc = _esc
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
    return _powershell(lines) and link.exists()
