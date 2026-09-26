"""Key-combination parsing shared by the global hotkey and the per-app copy keystrokes.

Pure Python (no Win32 calls), so it can be tested anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

# RegisterHotKey modifier flags.
MOD_FLAGS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
# Virtual-key codes for the modifiers (used when sending keystrokes).
MOD_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}
MOD_ORDER = ("ctrl", "alt", "shift", "win")
MOD_ALIASES = {"control": "ctrl", "ctl": "ctrl", "option": "alt", "super": "win", "windows": "win", "meta": "win"}

NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "backspace": 0x08,
    "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "pause": 0x13, "`": 0xC0, ";": 0xBA, ",": 0xBC, ".": 0xBE, "/": 0xBF, "-": 0xBD,
    "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, "'": 0xDE,
}
for _n in range(1, 25):
    NAMED_KEYS[f"f{_n}"] = 0x70 + _n - 1

# Shortcuts other apps (or Windows) already use. RegisterHotKey can't detect app-local
# shortcuts like Warp's, so we warn from this list instead.
KNOWN_CONFLICTS = {
    "ctrl+alt+t": "Warp uses it to reopen a closed tab.",
    "ctrl+alt+v": "Warp uses it for accessibility announcements.",
    "ctrl+alt+f": "Warp uses it to fold selected text.",
    "ctrl+alt+[": "Warp uses it to fold.",
    "ctrl+alt+]": "Warp uses it to unfold.",
    "ctrl+alt+up": "Warp uses it to switch panes.",
    "ctrl+alt+down": "Warp uses it to switch panes.",
    "ctrl+alt+left": "Warp uses it to switch panes / move by subword.",
    "ctrl+alt+right": "Warp uses it to switch panes / move by subword.",
    "ctrl+alt+delete": "Windows reserves it.",
    "ctrl+shift+c": "Terminals use it to copy.",
    "ctrl+shift+v": "Terminals use it to paste.",
    "ctrl+c": "It's copy everywhere (and 'stop' in terminals).",
    "ctrl+v": "It's paste everywhere.",
    "ctrl+x": "It's cut everywhere.",
    "ctrl+z": "It's undo everywhere.",
    "ctrl+a": "It's select-all everywhere.",
    "ctrl+s": "It's save everywhere.",
    "alt+tab": "Windows reserves it.",
    "alt+f4": "Windows uses it to close windows.",
    "alt+space": "Windows (and PowerToys Run) use it.",
}


@dataclass(frozen=True)
class KeyCombo:
    modifiers: tuple[str, ...]
    key: str
    vk: int

    @property
    def mod_flags(self) -> int:
        flags = 0
        for m in self.modifiers:
            flags |= MOD_FLAGS[m]
        return flags

    def __str__(self) -> str:
        return "+".join((*self.modifiers, self.key))

    def pretty(self) -> str:
        parts = [m.capitalize() for m in self.modifiers]
        key = self.key.upper() if len(self.key) == 1 else self.key.capitalize()
        return "+".join((*parts, key))


def parse_combo(spec: str, *, for_hotkey: bool = False) -> KeyCombo:
    """Parse "ctrl+alt+d" into a KeyCombo. Raises ValueError with a readable message."""
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("The shortcut is empty.")
    raw = spec.strip().lower().replace(" ", "")
    # Allow "+" itself as a key only at the end ("ctrl++" is unusual; not supported).
    parts = [p for p in raw.split("+") if p]
    if not parts:
        raise ValueError(f"'{spec}' is not a valid shortcut.")
    *mod_parts, key = parts
    mods: set[str] = set()
    for m in mod_parts:
        m = MOD_ALIASES.get(m, m)
        if m not in MOD_FLAGS:
            raise ValueError(f"'{m}' is not a modifier. Use ctrl, alt, shift or win.")
        mods.add(m)
    key = MOD_ALIASES.get(key, key)
    if key in MOD_FLAGS:
        raise ValueError("The shortcut needs a normal key after the modifiers (e.g. ctrl+alt+d).")
    if len(key) == 1 and (key.isalpha() or key.isdigit()):
        vk = ord(key.upper())
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    else:
        raise ValueError(f"'{key}' is not a key VerbaLogic knows.")
    if for_hotkey:
        is_fkey = key.startswith("f") and key[1:].isdigit()
        if not (mods & {"ctrl", "alt", "win"}) and not is_fkey:
            raise ValueError("A global shortcut needs Ctrl, Alt or Win, or you'd block normal typing.")
    ordered = tuple(m for m in MOD_ORDER if m in mods)
    return KeyCombo(ordered, key, vk)


def known_conflict(combo: KeyCombo) -> str | None:
    note = KNOWN_CONFLICTS.get(str(combo))
    if note:
        return note
    if "win" in combo.modifiers:
        return "Windows reserves many Win+ shortcuts; if it doesn't fire, pick another."
    return None


def parse_copy_keys(spec: str) -> KeyCombo | None:
    """Per-app copy keystroke. "none" means: don't send anything."""
    if isinstance(spec, str) and spec.strip().lower() == "none":
        return None
    return parse_combo(spec)
