"""Lookup history and saved words, in SQLite next to the config.

Kept apart from the cache: the cache forgets after a month, saved words never do. Recent
lookups are trimmed to the newest N; saved (starred) ones are never trimmed.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Entry:
    text: str
    src: str = ""
    translations: dict[str, str] = field(default_factory=dict)
    ts: float = 0.0
    starred: bool = False
    gloss: str = ""       # the meaning that was on screen when it was saved
    example: str = ""

    def translation(self) -> str:
        """The first translation that isn't the text itself."""
        return next((t for lang, t in self.translations.items() if lang != self.src and t != self.text), "")


class History:
    def __init__(self, path: Path | str | None, size: int = 200):
        self.size = size
        try:
            self._db = sqlite3.connect(str(path) if path else ":memory:")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS lookups (text TEXT PRIMARY KEY, src TEXT NOT NULL DEFAULT '', "
                "translations TEXT NOT NULL DEFAULT '{}', ts REAL NOT NULL, starred INTEGER NOT NULL DEFAULT 0, "
                "gloss TEXT NOT NULL DEFAULT '', example TEXT NOT NULL DEFAULT '')"
            )
            self._db.commit()
        except sqlite3.Error:
            self._db = sqlite3.connect(":memory:")  # history for this session only
            self._db.execute("CREATE TABLE lookups (text TEXT PRIMARY KEY, src TEXT, translations TEXT, ts REAL, "
                             "starred INTEGER DEFAULT 0, gloss TEXT DEFAULT '', example TEXT DEFAULT '')")

    def _write(self, sql: str, args: tuple = ()) -> None:
        try:
            self._db.execute(sql, args)
            self._db.commit()
        except sqlite3.Error:
            pass

    def add(self, text: str, src: str, translations: dict[str, str]) -> None:
        """Record a lookup (or move it to the top). Keeps its star."""
        self._write(
            "INSERT INTO lookups (text, src, translations, ts) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(text) DO UPDATE SET src = excluded.src, translations = excluded.translations, ts = excluded.ts",
            (text, src, json.dumps(translations, ensure_ascii=False), time.time()),
        )
        self._write(
            "DELETE FROM lookups WHERE starred = 0 AND text NOT IN "
            "(SELECT text FROM lookups WHERE starred = 0 ORDER BY ts DESC LIMIT ?)",
            (self.size,),
        )

    def set_star(self, text: str, on: bool, src: str = "", translations: dict[str, str] | None = None,
                 gloss: str = "", example: str = "") -> None:
        if on:
            self._write(
                "INSERT INTO lookups (text, src, translations, ts, starred, gloss, example) VALUES (?, ?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(text) DO UPDATE SET starred = 1, gloss = excluded.gloss, example = excluded.example",
                (text, src, json.dumps(translations or {}, ensure_ascii=False), time.time(), gloss, example),
            )
        else:
            self._write("UPDATE lookups SET starred = 0 WHERE text = ?", (text,))

    def is_starred(self, text: str) -> bool:
        row = self._db.execute("SELECT starred FROM lookups WHERE text = ?", (text,)).fetchone()
        return bool(row and row[0])

    def recent(self, n: int = 15) -> list[Entry]:
        return self._select("ORDER BY ts DESC LIMIT ?", (n,))

    def starred(self, n: int = 50) -> list[Entry]:
        return self._select("WHERE starred = 1 ORDER BY ts DESC LIMIT ?", (n,))

    def clear_recent(self) -> None:
        """Forget recent lookups; saved words stay."""
        self._write("DELETE FROM lookups WHERE starred = 0")

    def _select(self, where: str, args: tuple) -> list[Entry]:
        try:
            rows = self._db.execute(
                f"SELECT text, src, translations, ts, starred, gloss, example FROM lookups {where}", args
            ).fetchall()
        except sqlite3.Error:
            return []
        out = []
        for text, src, tr, ts, starred, gloss, example in rows:
            try:
                translations = json.loads(tr or "{}")
            except ValueError:
                translations = {}
            out.append(Entry(text, src or "", translations, ts, bool(starred), gloss or "", example or ""))
        return out
