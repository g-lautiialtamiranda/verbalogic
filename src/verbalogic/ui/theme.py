"""Light/dark/paper palettes + accent → the QSS in theme.qss."""
from __future__ import annotations

import winreg
from importlib import resources
from string import Template

from PySide6.QtGui import QColor

LIGHT = {
    "bg": "#FFFFFF", "surface": "#F6F6F9", "border": "#E4E4EA", "border_strong": "#C8C8D2", "hover": "#EEEEF3",
    "text": "#1B1B22", "text_soft": "#3D3D48", "muted": "#72727F", "chip": "#EFEFF4",
    "error": "#C62828", "ok": "#2E7D32",
}
PAPER = {  # warm off-white page, dark ink
    "bg": "#FAF7F0", "surface": "#F2EDE2", "border": "#E2DACB", "border_strong": "#CCC1AD", "hover": "#ECE5D6",
    "text": "#1F1B16", "text_soft": "#3F3930", "muted": "#7A7164", "chip": "#EEE7D9",
    "error": "#B3261E", "ok": "#2E6B34",
}
DARK = {
    "bg": "#1B1B21", "surface": "#23232B", "border": "#33333D", "border_strong": "#4C4C59", "hover": "#2E2E38",
    "text": "#EDEDF2", "text_soft": "#C9C9D3", "muted": "#9696A6", "chip": "#2E2E38",
    "error": "#EF7A7A", "ok": "#7BC47F",
}

# Quiet ink colours for the accent (Settings offers these; any #RRGGBB still works).
ACCENTS = {
    "Ink blue": "#2F4A7A",
    "Deep teal": "#1F6B66",
    "Oxblood": "#7A2E34",
    "Graphite": "#4A4F57",
}


def _uses_dark(value: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, value)[0] == 0
    except OSError:
        return False


def windows_prefers_dark() -> bool:
    return _uses_dark("AppsUseLightTheme")


def icon_accent(ui: dict) -> str:
    """The accent for the tray and Start menu icon: lifted, like in the dark theme, on a dark taskbar."""
    return palette({**ui, "theme": "dark" if _uses_dark("SystemUsesLightTheme") else "light"})["accent"]


def is_dark(theme: str) -> bool:
    return theme == "dark" or (theme == "system" and windows_prefers_dark())


def palette(ui: dict) -> dict:
    dark = is_dark(ui["theme"])
    p = dict(DARK if dark else PAPER if ui["theme"] == "paper" else LIGHT)
    accent = QColor(ui["accent"])
    hue, sat = accent.hslHue(), accent.hslSaturation()
    if dark and accent.lightness() < 130:  # ink colours vanish on a dark card: same hue, lighter, calmer
        accent = QColor.fromHsl(hue, min(sat, 110), 130)
    soft = QColor(accent)
    soft.setAlpha(60 if dark else 34)
    p["accent"] = accent.name()
    p["accent_hover"] = accent.lighter(112).name()
    p["accent_soft"] = f"rgba({soft.red()},{soft.green()},{soft.blue()},{soft.alpha()})"
    p["accent_text"] = QColor.fromHsl(hue, min(sat, 110), 190).name() if dark else accent.darker(130).name()
    p["dark"] = dark
    return p


def acrylic_tint(ui: dict) -> tuple[int, int, int, int]:
    """The theme's background, mostly opaque: enough blur to feel light, enough tint to read."""
    bg = QColor(palette(ui)["bg"])
    return bg.red(), bg.green(), bg.blue(), 0xD8


def stylesheet(ui: dict) -> str:
    p = palette(ui)
    size = ui["font_size"]
    ui_dir = resources.files("verbalogic").joinpath("ui")
    qss = ui_dir.joinpath("theme.qss").read_text(encoding="utf-8")
    return Template(qss).safe_substitute(
        {k: v for k, v in p.items() if isinstance(v, str)},
        **{f"{name}_svg": str(ui_dir.joinpath(f"{name.replace('_', '-')}.svg")).replace("\\", "/")
           for name in ("check", "chevron_down", "chevron_up")},
        font=size, font_xs=size - 3, font_sm=size - 1, font_lg=size + 1, font_xl=size + 6, font_head=size + 12,
    )
