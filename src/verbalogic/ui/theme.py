"""Light/dark palettes + accent → the QSS in theme.qss."""
from __future__ import annotations

import winreg
from importlib import resources
from string import Template

from PySide6.QtGui import QColor

LIGHT = {
    "bg": "#FFFFFF", "surface": "#F7F7FA", "border": "#E3E3EA", "hover": "#EEEEF3",
    "text": "#1B1B22", "text_soft": "#3D3D48", "muted": "#72727F", "chip": "#EFEFF4",
    "error": "#C62828", "ok": "#2E7D32",
}
DARK = {
    "bg": "#1B1B21", "surface": "#23232B", "border": "#34343F", "hover": "#2E2E38",
    "text": "#EDEDF2", "text_soft": "#C9C9D3", "muted": "#9696A6", "chip": "#2E2E38",
    "error": "#EF7A7A", "ok": "#7BC47F",
}


def windows_prefers_dark() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def is_dark(theme: str) -> bool:
    return theme == "dark" or (theme == "system" and windows_prefers_dark())


def palette(ui: dict) -> dict:
    dark = is_dark(ui["theme"])
    p = dict(DARK if dark else LIGHT)
    accent = QColor(ui["accent"])
    soft = QColor(accent)
    soft.setAlpha(60 if dark else 34)
    p["accent"] = accent.name()
    p["accent_hover"] = accent.lighter(112).name()
    p["accent_soft"] = f"rgba({soft.red()},{soft.green()},{soft.blue()},{soft.alpha()})"
    p["accent_text"] = accent.lighter(150).name() if dark else accent.darker(130).name()
    p["dark"] = dark
    return p


def stylesheet(ui: dict) -> str:
    p = palette(ui)
    size = ui["font_size"]
    ui_dir = resources.files("verbalogic").joinpath("ui")
    qss = ui_dir.joinpath("theme.qss").read_text(encoding="utf-8")
    return Template(qss).safe_substitute(
        {k: v for k, v in p.items() if isinstance(v, str)},
        check_svg=str(ui_dir.joinpath("check.svg")).replace("\\", "/"),
        font=size, font_xs=size - 3, font_sm=size - 1, font_lg=size + 1, font_xl=size + 6,
    )
