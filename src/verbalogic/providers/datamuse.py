"""Datamuse: free English synonyms, no key. Used when Google's dictionary has none or is resting."""
from __future__ import annotations

import httpx

URL = "https://api.datamuse.com/words"


def synonyms(client: httpx.Client, word: str, limit: int = 12) -> list[str]:
    try:
        r = client.get(URL, params={"rel_syn": word, "max": limit})
        r.raise_for_status()
        words = [w["word"] for w in r.json() if w.get("word")]
        if not words:  # "means like" is looser, but better than nothing for phrases
            r = client.get(URL, params={"ml": word, "max": limit})
            r.raise_for_status()
            words = [w["word"] for w in r.json() if w.get("word")]
        return words[:limit]
    except (httpx.HTTPError, ValueError, KeyError):
        return []
