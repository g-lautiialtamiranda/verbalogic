"""Grab the current selection: send the focused app's copy keystroke, then read the clipboard.

Safety rule: the keystroke comes from the per-app map in the config. Terminals get
ctrl+shift+c or nothing, never plain ctrl+c (which means "stop" there).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from . import win32
from .keys import MOD_VK, KeyCombo, parse_copy_keys

_OWN_PROCESSES = {"python.exe", "pythonw.exe", "verbalogic.exe"}


@dataclass
class Capture:
    text: str
    app: str          # process name of the focused app, e.g. "warp.exe"
    fresh: bool       # True if the clipboard changed after we asked the app to copy
    keystroke: str    # what we sent, or "none"


def copy_keystroke_for(app: str, copy_keys: dict[str, str]) -> KeyCombo | None:
    spec = copy_keys.get(app.lower(), copy_keys.get("default", "ctrl+c"))
    try:
        return parse_copy_keys(spec)
    except ValueError:
        return None


def _wait_for_release(combo: KeyCombo | None, timeout: float = 0.6) -> None:
    """Wait until the user lets go of the hotkey, so our keystroke isn't mixed with theirs."""
    vks = [MOD_VK[m] for m in ("ctrl", "alt", "shift", "win")] + [0x5C]  # + right Win
    if combo:
        vks.append(combo.vk)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(win32.GetAsyncKeyState(vk) & 0x8000 for vk in vks):
            return
        time.sleep(0.01)


def send_keys(combo: KeyCombo) -> None:
    mods = [MOD_VK[m] for m in combo.modifiers]
    for vk in mods:
        win32.keybd_event(vk, win32.MapVirtualKeyW(vk, 0), 0, 0)
    win32.keybd_event(combo.vk, win32.MapVirtualKeyW(combo.vk, 0), 0, 0)
    win32.keybd_event(combo.vk, win32.MapVirtualKeyW(combo.vk, 0), win32.KEYEVENTF_KEYUP, 0)
    for vk in reversed(mods):
        win32.keybd_event(vk, win32.MapVirtualKeyW(vk, 0), win32.KEYEVENTF_KEYUP, 0)


def grab_selection(cfg: dict, hotkey: KeyCombo | None) -> Capture:
    cap = cfg["capture"]
    _, app = win32.foreground_process_name()
    keystroke = None
    if cap["auto_copy"] and app not in _OWN_PROCESSES:
        keystroke = copy_keystroke_for(app, cap["copy_keys"])

    fresh = False
    if keystroke:
        _wait_for_release(hotkey)
        before = win32.GetClipboardSequenceNumber()
        send_keys(keystroke)
        deadline = time.monotonic() + cap["wait_ms"] / 1000
        while time.monotonic() < deadline:
            if win32.GetClipboardSequenceNumber() != before:
                fresh = True
                time.sleep(0.02)  # let the app finish writing all formats
                break
            time.sleep(0.01)

    text = (win32.read_clipboard_text() or "").strip()
    return Capture(text=text, app=app, fresh=fresh, keystroke=str(keystroke) if keystroke else "none")
