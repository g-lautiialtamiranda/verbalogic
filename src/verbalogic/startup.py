"""'Start with Windows': a shortcut in the user's Startup folder (no registry, no admin)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


def shortcut_path() -> Path:
    return Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup\VerbaLogic.lnk"


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
    esc = lambda s: str(s).replace("'", "''")  # noqa: E731 - PowerShell single-quote escaping
    lines = [
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s')" % esc(link),
        "$s.TargetPath = '%s'" % esc(_pythonw()),
        "$s.Arguments = '-m verbalogic'",
        "$s.WorkingDirectory = '%s'" % esc(Path.home()),
        "$s.Description = 'VerbaLogic translator'",
    ]
    if icon_path and icon_path.exists():
        lines.append("$s.IconLocation = '%s'" % esc(icon_path))
    lines.append("$s.Save()")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "; ".join(lines)],
        capture_output=True, creationflags=CREATE_NO_WINDOW,
    )
    return result.returncode == 0 and link.exists()
