"""Two-level cache: in-memory LRU + SQLite on disk. Repeat lookups are instant and don't
spend Google's patience or OpenRouter's free quota."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

MONTH = 30 * 24 * 3600


class Cache:
    def __init__(self, path: Path | None, memory_items: int = 300):
        self._mem: OrderedDict[str, Any] = OrderedDict()
        self._max = memory_items
        self._lock = threading.Lock()
        self._db = None
        if path:
            try:
                self._db = sqlite3.connect(str(path), check_same_thread=False)
                self._db.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL, ts REAL NOT NULL)")
                self._db.execute("DELETE FROM kv WHERE ts < ?", (time.time() - MONTH,))
                self._db.commit()
            except sqlite3.Error:
                self._db = None

    def get(self, key: str, max_age: float = MONTH) -> Any | None:
        with self._lock:
            if key in self._mem:
                self._mem.move_to_end(key)
                return self._mem[key]
            if not self._db:
                return None
            row = self._db.execute("SELECT v, ts FROM kv WHERE k = ?", (key,)).fetchone()
        if not row or time.time() - row[1] > max_age:
            return None
        value = json.loads(row[0])
        self._remember(key, value)
        return value

    def set(self, key: str, value: Any) -> None:
        self._remember(key, value)
        if self._db:
            with self._lock:
                try:
                    self._db.execute(
                        "INSERT OR REPLACE INTO kv (k, v, ts) VALUES (?, ?, ?)",
                        (key, json.dumps(value, ensure_ascii=False), time.time()),
                    )
                    self._db.commit()
                except sqlite3.Error:
                    pass

    def _remember(self, key: str, value: Any) -> None:
        with self._lock:
            self._mem[key] = value
            self._mem.move_to_end(key)
            while len(self._mem) > self._max:
                self._mem.popitem(last=False)
