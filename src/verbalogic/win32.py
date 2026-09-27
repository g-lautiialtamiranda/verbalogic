"""Thin ctypes bindings for the few Win32 calls VerbaLogic needs.

Every function declares argtypes/restype so 64-bit handles aren't truncated.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_APP = 0x8000
MOD_NOREPEAT = 0x4000
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT = 13
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409


def _fn(dll, name, restype, *argtypes):
    f = getattr(dll, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


RegisterHotKey = _fn(user32, "RegisterHotKey", wintypes.BOOL, wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
UnregisterHotKey = _fn(user32, "UnregisterHotKey", wintypes.BOOL, wintypes.HWND, ctypes.c_int)
GetMessageW = _fn(user32, "GetMessageW", wintypes.BOOL, ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
PeekMessageW = _fn(user32, "PeekMessageW", wintypes.BOOL, ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT)
PostThreadMessageW = _fn(user32, "PostThreadMessageW", wintypes.BOOL, wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
GetCurrentThreadId = _fn(kernel32, "GetCurrentThreadId", wintypes.DWORD)

GetAsyncKeyState = _fn(user32, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
keybd_event = _fn(user32, "keybd_event", None, wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t)
MapVirtualKeyW = _fn(user32, "MapVirtualKeyW", wintypes.UINT, wintypes.UINT, wintypes.UINT)

GetForegroundWindow = _fn(user32, "GetForegroundWindow", wintypes.HWND)
SetForegroundWindow = _fn(user32, "SetForegroundWindow", wintypes.BOOL, wintypes.HWND)
GetWindowThreadProcessId = _fn(user32, "GetWindowThreadProcessId", wintypes.DWORD, wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
OpenProcess = _fn(kernel32, "OpenProcess", wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
CloseHandle = _fn(kernel32, "CloseHandle", wintypes.BOOL, wintypes.HANDLE)
QueryFullProcessImageNameW = _fn(kernel32, "QueryFullProcessImageNameW", wintypes.BOOL, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))

OpenClipboard = _fn(user32, "OpenClipboard", wintypes.BOOL, wintypes.HWND)
CloseClipboard = _fn(user32, "CloseClipboard", wintypes.BOOL)
GetClipboardData = _fn(user32, "GetClipboardData", wintypes.HANDLE, wintypes.UINT)
IsClipboardFormatAvailable = _fn(user32, "IsClipboardFormatAvailable", wintypes.BOOL, wintypes.UINT)
GetClipboardSequenceNumber = _fn(user32, "GetClipboardSequenceNumber", wintypes.DWORD)
GlobalLock = _fn(kernel32, "GlobalLock", ctypes.c_void_p, wintypes.HGLOBAL)
GlobalUnlock = _fn(kernel32, "GlobalUnlock", wintypes.BOOL, wintypes.HGLOBAL)

SPI_GETCLIENTAREAANIMATION = 0x1042
SystemParametersInfoW = _fn(user32, "SystemParametersInfoW", wintypes.BOOL, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT)


def animations_enabled() -> bool:
    """Windows' "Animation effects" setting (Settings > Accessibility > Visual effects)."""
    on = wintypes.BOOL(True)
    if not SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(on), 0):
        return True
    return bool(on.value)


def foreground_process_name() -> tuple[int, str]:
    """(hwnd, 'warp.exe') of the window that has focus. Name is '' if unknown."""
    hwnd = GetForegroundWindow()
    if not hwnd:
        return 0, ""
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return hwnd, ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return hwnd, os.path.basename(buf.value).lower()
        return hwnd, ""
    finally:
        CloseHandle(handle)


def read_clipboard_text(retries: int = 10) -> str | None:
    """Unicode text on the clipboard, or None. Retries because other apps hold it briefly."""
    import time

    for _ in range(retries):
        if OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        return None
    try:
        if not IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            GlobalUnlock(handle)
    finally:
        CloseClipboard()


# --- Windows 11 acrylic backdrop (F-06) ---
# DWMWA_SYSTEMBACKDROP_TYPE only drew a flat grey on our frameless, per-pixel-alpha popup, so this uses
# the accent policy that Windows' own flyouts use, plus DWM's rounded corners (which also bring its shadow).
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_WCA_ACCENT_POLICY = 19
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_DEFAULT, _DWMWCP_ROUND = 0, 2


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", wintypes.DWORD), ("AnimationId", ctypes.c_int)]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


def _set_accent(hwnd: int, state: int, abgr: int = 0) -> bool:
    try:
        swca = _fn(user32, "SetWindowCompositionAttribute", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_WINCOMPATTRDATA))
    except AttributeError:
        return False
    policy = _ACCENT_POLICY(state, 0, abgr, 0)
    data = _WINCOMPATTRDATA(_WCA_ACCENT_POLICY, ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p), ctypes.sizeof(policy))
    return bool(swca(hwnd, ctypes.byref(data)))


def _set_corners(hwnd: int, preference: int) -> bool:
    try:
        dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        return False
    value = ctypes.c_int(preference)
    return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), _DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value), 4) == 0


def supports_acrylic() -> bool:
    """Windows 11 (build 22000+). On Windows 10 this blur makes dragging windows lag."""
    import sys

    return sys.getwindowsversion().build >= 22000


def set_acrylic(hwnd: int, rgba: tuple[int, int, int, int] | None) -> bool:
    """Blur the desktop behind the window, tinted with rgba, with rounded corners and a shadow
    drawn by Windows. None turns it off. Returns True if the backdrop is on."""
    if rgba is None or not supports_acrylic():
        _set_accent(hwnd, _ACCENT_DISABLED)
        _set_corners(hwnd, _DWMWCP_DEFAULT)
        return False
    r, g, b, a = rgba
    if not _set_accent(hwnd, _ACCENT_ENABLE_ACRYLICBLURBEHIND, (a << 24) | (b << 16) | (g << 8) | r):
        return False
    if not _set_corners(hwnd, _DWMWCP_ROUND):
        _set_accent(hwnd, _ACCENT_DISABLED)  # square blurred corners under a rounded card look broken
        return False
    return True


# --- shell icon refresh ---
_SHCNE_UPDATEITEM = 0x00002000
_SHCNE_ASSOCCHANGED = 0x08000000
_SHCNF_IDLIST, _SHCNF_PATHW = 0x0000, 0x0005


def refresh_shell_icons(paths: list[str]) -> None:
    """Tell Explorer these shortcuts changed, so the taskbar and Start menu redraw their icons."""
    shell32 = ctypes.WinDLL("shell32")
    notify = shell32.SHChangeNotify
    notify.restype = None
    notify.argtypes = [wintypes.LONG, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
    for path in paths:
        notify(_SHCNE_UPDATEITEM, _SHCNF_PATHW, ctypes.c_wchar_p(path), None)
    notify(_SHCNE_ASSOCCHANGED, _SHCNF_IDLIST, None, None)
