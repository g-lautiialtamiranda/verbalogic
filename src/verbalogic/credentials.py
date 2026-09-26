"""Store the OpenRouter key in Windows Credential Manager (never in the config or repo)."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .win32 import advapi32

TARGET = "VerbaLogic/openrouter"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_CredWriteW = advapi32.CredWriteW
_CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
_CredWriteW.restype = wintypes.BOOL
_CredReadW = advapi32.CredReadW
_CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
_CredReadW.restype = wintypes.BOOL
_CredDeleteW = advapi32.CredDeleteW
_CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
_CredDeleteW.restype = wintypes.BOOL
_CredFree = advapi32.CredFree
_CredFree.argtypes = [ctypes.c_void_p]
_CredFree.restype = None


def save_key(secret: str) -> bool:
    data = secret.encode("utf-16-le")
    blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    cred = _CREDENTIAL()
    cred.Type = _CRED_TYPE_GENERIC
    cred.TargetName = TARGET
    cred.CredentialBlobSize = len(data)
    cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = "openrouter"
    return bool(_CredWriteW(ctypes.byref(cred), 0))


def read_stored_key() -> str | None:
    ptr = ctypes.POINTER(_CREDENTIAL)()
    if not _CredReadW(TARGET, _CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        raw = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return raw.decode("utf-16-le") or None
    finally:
        _CredFree(ptr)


def delete_key() -> bool:
    return bool(_CredDeleteW(TARGET, _CRED_TYPE_GENERIC, 0))


def get_key(env_var: str) -> str | None:
    """Credential Manager first, then the environment variable."""
    return read_stored_key() or (os.environ.get(env_var) or "").strip() or None
