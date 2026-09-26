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
