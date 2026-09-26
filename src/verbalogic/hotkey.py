"""Global hotkey via Win32 RegisterHotKey, on a dedicated thread with its own message loop.

No keyboard hook and no admin rights. Registration fails cleanly when another program
already owns the combination, and we report that instead of failing silently.
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from . import win32
from .keys import KeyCombo, parse_combo

_HOTKEY_ID = 0xB0B1
_PROBE_ID = 0xB0B2
_WM_SET = win32.WM_APP + 1
_WM_PROBE = win32.WM_APP + 2
_WM_QUIT = win32.WM_APP + 3


class HotkeyError(Exception):
    pass


class HotkeyListener(threading.Thread):
    """Calls on_press(combo) on this thread whenever the hotkey fires."""

    def __init__(self, on_press: Callable[[KeyCombo], None]):
        super().__init__(name="verbalogic-hotkey", daemon=True)
        self._on_press = on_press
        self._thread_id = 0
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._request: KeyCombo | None = None
        self._reply = threading.Event()
        self._reply_value: tuple[bool, str] = (False, "")
        self.current: KeyCombo | None = None

    # --- public API (call from any thread) ---
    def start_and_wait(self) -> None:
        self.start()
        self._ready.wait(2)

    def set_hotkey(self, spec: str) -> KeyCombo:
        """Register a new combo (replacing the old one). Raises HotkeyError if Windows refuses."""
        combo = parse_combo(spec, for_hotkey=True)
        ok, msg = self._call(_WM_SET, combo)
        if not ok:
            raise HotkeyError(msg)
        return combo

    def probe(self, spec: str) -> tuple[bool, str]:
        """Is this combo free system-wide? Doesn't change the current hotkey."""
        try:
            combo = parse_combo(spec, for_hotkey=True)
        except ValueError as e:
            return False, str(e)
        if self.current and str(combo) == str(self.current):
            return True, "That's VerbaLogic's current shortcut."
        return self._call(_WM_PROBE, combo)

    def unregister(self) -> None:
        """Temporarily release the hotkey (used while recording a new one)."""
        self._call(_WM_SET, None)

    def stop(self) -> None:
        if self._thread_id:
            win32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)

    # --- internals ---
    def _call(self, message: int, combo: KeyCombo | None) -> tuple[bool, str]:
        with self._lock:
            self._request = combo
            self._reply.clear()
            win32.PostThreadMessageW(self._thread_id, message, 0, 0)
            if not self._reply.wait(2):
                return False, "The hotkey thread didn't answer."
            return self._reply_value

    @staticmethod
    def _register(ident: int, combo: KeyCombo) -> tuple[bool, str]:
        if win32.RegisterHotKey(None, ident, combo.mod_flags | win32.MOD_NOREPEAT, combo.vk):
            return True, ""
        err = ctypes.get_last_error()
        if err == win32.ERROR_HOTKEY_ALREADY_REGISTERED:
            return False, f"{combo.pretty()} is already used by another program. Pick a different shortcut."
        return False, f"Windows refused {combo.pretty()} (error {err})."

    def run(self) -> None:
        msg = wintypes.MSG()
        # Force creation of this thread's message queue before anyone posts to it.
        win32.PeekMessageW(ctypes.byref(msg), None, win32.WM_APP, win32.WM_APP, 0)
        self._thread_id = win32.GetCurrentThreadId()
        self._ready.set()
        while win32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == win32.WM_HOTKEY and msg.wParam == _HOTKEY_ID and self.current:
                try:
                    self._on_press(self.current)
                except Exception:  # noqa: BLE001 - never let the listener die
                    import traceback
                    traceback.print_exc()
            elif msg.message == _WM_SET:
                if self.current:
                    win32.UnregisterHotKey(None, _HOTKEY_ID)
                previous, self.current = self.current, None
                if self._request is None:
                    self._reply_value = (True, "")
                else:
                    ok, text = self._register(_HOTKEY_ID, self._request)
                    if ok:
                        self.current = self._request
                    elif previous and self._register(_HOTKEY_ID, previous)[0]:
                        self.current = previous  # keep the old one working
                    self._reply_value = (ok, text)
                self._reply.set()
            elif msg.message == _WM_PROBE:
                ok, text = self._register(_PROBE_ID, self._request)
                if ok:
                    win32.UnregisterHotKey(None, _PROBE_ID)
                    text = f"{self._request.pretty()} is free in Windows."
                self._reply_value = (ok, text)
                self._reply.set()
            elif msg.message == _WM_QUIT:
                break
        if self.current:
            win32.UnregisterHotKey(None, _HOTKEY_ID)
