"""Free Google Translate endpoints (no key).

- translate(): the Chrome dictionary-extension endpoint. Fast, lenient, translation only.
  Falls back to the dictionary endpoint.
- dictionary(): the "single" endpoint with dictionary data: alternative translations, synonyms
  by part of speech, definitions and real example sentences. We call it with the Chrome
  extension's client id: Google blocks client=gtx per IP (HTTP 429 from the very first
  request), while dict-chrome-ex answers normally. We still only call it for words and short
  phrases, cache results, and back off on HTTP 429.

Both are unofficial. Everything Google-specific lives in this file so it can be swapped.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import httpx

CHROME_URL = "https://clients5.google.com/translate_a/t"
DICT_URL = "https://clients5.google.com/translate_a/single"
DICT_CLIENT = "dict-chrome-ex"
MAX_CHARS = 3000


class RateLimited(Exception):
    def __init__(self, seconds: int):
        super().__init__(f"Google is limiting requests. Try again in about {seconds}s.")
        self.seconds = seconds


class ServiceError(Exception):
    pass


@dataclass
class Alternative:
    word: str
    pos: str
    reverse: list[str] = field(default_factory=list)


@dataclass
class SynGroup:
    pos: str
    words: list[str]


@dataclass
class Sense:
    """One meaning of the looked-up word: Google links definitions and synonyms by id."""
    id: str
    pos: str
    gloss: str
    example: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass
class DictResult:
    src: str
    translation: str
    alternatives: list[Alternative] = field(default_factory=list)
    synonyms: list[SynGroup] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)      # may contain <b>…</b>
    definitions: list[tuple[str, str]] = field(default_factory=list)  # (pos, gloss)
    senses: list[Sense] = field(default_factory=list)


def parse_dictionary(data: dict) -> DictResult:
    """Parse a translate_a/single response requested with dj=1. Pure function (tested with fixtures)."""
    sentences = data.get("sentences") or []
    translation = "".join(s.get("trans", "") for s in sentences if "trans" in s).strip()

    alternatives: list[Alternative] = []
    for block in data.get("dict") or []:
        pos = block.get("pos", "")
        for entry in block.get("entry") or []:
            word = entry.get("word")
            if word:
                alternatives.append(Alternative(word, pos, list(entry.get("reverse_translation") or [])))

    synonyms: list[SynGroup] = []
    for block in data.get("synsets") or []:
        pos = block.get("pos", "")
        common: list[str] = []
        rare: list[str] = []
        for entry in block.get("entry") or []:
            target = rare if entry.get("label_info") else common
            target.extend(entry.get("synonym") or [])
        words = list(dict.fromkeys(common + rare))  # dedupe, keep order, labelled (rare) last
        if words:
            synonyms.append(SynGroup(pos, words))

    examples = [e["text"] for e in (data.get("examples") or {}).get("example") or [] if e.get("text")]

    definitions: list[tuple[str, str]] = []
    senses: list[Sense] = []
    for block in data.get("definitions") or []:
        for entry in block.get("entry") or []:
            if entry.get("gloss"):
                definitions.append((block.get("pos", ""), entry["gloss"]))
                senses.append(Sense(entry.get("definition_id", ""), block.get("pos", ""),
                                    entry["gloss"], entry.get("example", "")))
    by_id = {s.id: s for s in senses if s.id}
    for block in data.get("synsets") or []:
        for entry in block.get("entry") or []:
            sense = by_id.get(entry.get("definition_id", ""))
            if sense:
                sense.synonyms = list(dict.fromkeys(sense.synonyms + list(entry.get("synonym") or [])))

    return DictResult(
        src=data.get("src", ""),
        translation=translation,
        alternatives=alternatives,
        synonyms=synonyms,
        examples=examples,
        definitions=definitions,
        senses=senses,
    )


def parse_chrome(data, source: str) -> tuple[str, str]:
    """clients5 returns [["texto","en"]] with sl=auto, or ["texto"] with a fixed source."""
    if not data:
        raise ServiceError("Empty response.")
    parts = []
    src = source
    for item in data:
        if isinstance(item, list):
            parts.append(item[0])
            if len(item) > 1 and source == "auto":
                src = item[1]
        else:
            parts.append(str(item))
    return " ".join(p.strip() for p in parts if p).strip(), src


def parse_chrome_many(data, count: int) -> list[str]:
    """Several q= in one request come back as a list, one item per text (a string, or
    [text, lang] with sl=auto)."""
    if not isinstance(data, list) or len(data) != count:
        raise ServiceError("Unexpected response.")
    return [(item[0] if isinstance(item, list) else str(item)).strip() for item in data]


class GoogleFree:
    def __init__(self, client: httpx.Client):
        self.client = client
        self._lock = threading.Lock()
        self._cool_until = 0.0
        self._cool_step = 60

    # --- rate-limit bookkeeping for the dictionary endpoint ---
    def cooling_seconds(self) -> int:
        return max(0, int(self._cool_until - time.monotonic()))

    def _hit_limit(self) -> RateLimited:
        with self._lock:
            self._cool_until = time.monotonic() + self._cool_step
            seconds = self._cool_step
            self._cool_step = min(self._cool_step * 2, 900)
        return RateLimited(seconds)

    def _ok(self) -> None:
        with self._lock:
            self._cool_step = 60

    # --- API ---
    def translate(self, text: str, target: str, source: str = "auto") -> tuple[str, str]:
        text = text[:MAX_CHARS]
        try:
            r = self.client.get(CHROME_URL, params={"client": "dict-chrome-ex", "sl": source, "tl": target, "q": text})
            r.raise_for_status()
            return parse_chrome(r.json(), source)
        except (httpx.HTTPError, ValueError, ServiceError):
            d = self._single(text, target, source, ["t"])
            return d.translation, d.src or source

    def translate_many(self, texts: list[str], target: str, source: str) -> list[str]:
        """Translate several short texts in one request (definitions, example sentences)."""
        if not texts:
            return []
        params = [("client", "dict-chrome-ex"), ("sl", source), ("tl", target)]
        params += [("q", t[:MAX_CHARS]) for t in texts]
        try:
            r = self.client.get(CHROME_URL, params=params)
            r.raise_for_status()
            return parse_chrome_many(r.json(), len(texts))
        except (httpx.HTTPError, ValueError) as e:
            raise ServiceError(f"Couldn't translate ({e.__class__.__name__}).") from e

    def dictionary(self, text: str, target: str, source: str = "auto") -> DictResult:
        return self._single(text[:MAX_CHARS], target, source, ["t", "bd", "ss", "ex", "md"])

    def _single(self, text: str, target: str, source: str, dts: list[str]) -> DictResult:
        if self.cooling_seconds():
            raise RateLimited(self.cooling_seconds())
        params = [("client", DICT_CLIENT), ("dj", "1"), ("sl", source), ("tl", target), ("q", text)]
        params += [("dt", d) for d in dts]
        try:
            r = self.client.get(DICT_URL, params=params)
        except httpx.HTTPError as e:
            raise ServiceError(f"Couldn't reach Google ({e.__class__.__name__}).") from e
        if r.status_code == 429 or "sorry" in str(r.url):
            raise self._hit_limit()
        if r.status_code >= 400:
            raise ServiceError(f"Google answered {r.status_code}.")
        self._ok()
        return parse_dictionary(r.json())
