"""Pronunciation: Google's free text-to-speech (same family as the translate endpoints, no key),
played through Windows MCI so no audio library is needed.

Clips are saved on disk, so a word you've heard once plays again instantly and offline.
"""
from __future__ import annotations

import ctypes
import hashlib
import itertools
from pathlib import Path

import httpx

TTS_URL = "https://translate.google.com/translate_tts"
MAX_CHARS = 200  # the endpoint's limit per request

_alias = itertools.count(1)


class SpeechError(Exception):
    pass


def fetch(http: httpx.Client, text: str, lang: str, folder: Path) -> Path:
    """The MP3 for text in lang, downloaded once and cached in folder."""
    text = text.strip()[:MAX_CHARS]
    name = hashlib.sha1(f"{lang}|{text}".encode("utf-8")).hexdigest() + ".mp3"
    path = folder / name
    if path.exists() and path.stat().st_size:
        return path
    try:
        r = http.get(TTS_URL, params={"ie": "UTF-8", "client": "tw-ob", "tl": lang, "q": text})
    except httpx.HTTPError as e:
        raise SpeechError(f"Couldn't reach Google ({e.__class__.__name__}).") from e
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("audio"):
        raise SpeechError(f"No pronunciation available (Google answered {r.status_code}).")
    folder.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path


def play(path: Path) -> None:
    """Play an MP3 and wait until it ends. Call from a worker thread."""
    mci = ctypes.windll.winmm.mciSendStringW
    alias = f"vl{next(_alias)}"
    err = mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
    if err:
        raise SpeechError(f"Windows couldn't play the sound (MCI error {err}).")
    try:
        mci(f"play {alias} wait", None, 0, None)
    finally:
        mci(f"close {alias}", None, 0, None)
