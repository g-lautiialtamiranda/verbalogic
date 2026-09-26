"""'Other ways to say it': build the prompt and clean the model's answer.

The cleaning step is the second line of defence against AI-sounding output: options with
banned words are dropped, em dashes are removed, duplicates and echoes of the input go away.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from string import Template

from . import languages as L

TONES = ("casual", "neutral", "formal")
BANNED = (
    "delve", "elevate", "seamless", "leverage", "unlock", "tapestry", "embark", "foster",
    "robust", "realm", "synergy", "game-changer", "game changer", "in today's world",
    "it's worth noting", "navigate the", "a testament to",
)
_BANNED_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BANNED) + r")", re.I)
_DASH_RE = re.compile(r"\s*[—–]\s*")


@dataclass
class Rewrite:
    tone: str
    text: str = ""
    variants: dict[str, str] = field(default_factory=dict)  # Spanish: {"vos": ..., "neutral": ...}


def _spanish_variants(setting: str) -> list[str]:
    return {"both": ["vos", "neutral"], "rioplatense": ["vos"], "neutral": ["neutral"]}[setting]


def build_prompt(text: str, source_lang: str, target_langs: list[str], count: int, spanish_variant: str) -> str:
    schema: dict[str, list] = {}
    notes: list[str] = []
    for lang in target_langs:
        key = L.base(lang)
        if key == "es" and spanish_variant == "both":
            schema[key] = [{"tone": "casual|neutral|formal", "vos": "...", "neutral": "..."}]
            notes.append(
                '- Spanish: give each option twice. "vos" = Rioplatense Spanish from Argentina '
                '(vos, tenés, podés; only use local words like "dale" if they sound natural). '
                '"neutral" = neutral Latin American Spanish with tú.'
            )
        else:
            schema[key] = [{"tone": "casual|neutral|formal", "text": "..."}]
            if key == "es":
                notes.append(
                    "- Spanish: use Rioplatense Spanish from Argentina (vos, tenés, podés)."
                    if spanish_variant == "rioplatense"
                    else "- Spanish: use neutral Latin American Spanish with tú."
                )
    template = Template(resources.files("verbalogic").joinpath("prompts/rewrites.md").read_text(encoding="utf-8"))
    return template.safe_substitute(
        text=text.strip(),
        source_language=L.english_name(source_lang) if source_lang else "an unknown language",
        count=count,
        language_notes="\n".join(notes) + ("\n" if notes else ""),
        schema=json.dumps(schema, ensure_ascii=False),
    )


def _clean(s: object) -> str:
    if not isinstance(s, str):
        return ""
    s = _DASH_RE.sub(", ", s.strip())
    s = s.strip().strip('"“”«»').strip()
    s = re.sub(r"^\d+[.)]\s*", "", s)
    return s.replace(" ,", ",").strip(" ,")


def parse_rewrites(data: dict, source_text: str, target_langs: list[str], count: int) -> dict[str, list[Rewrite]]:
    out: dict[str, list[Rewrite]] = {}
    echo = source_text.strip().lower().rstrip(".!?")
    for lang in target_langs:
        items = data.get(L.base(lang)) or data.get(lang) or []
        seen: set[str] = set()
        result: list[Rewrite] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            tone = str(item.get("tone", "neutral")).lower()
            tone = tone if tone in TONES else "neutral"
            variants = {k: _clean(item.get(k)) for k in ("vos", "neutral") if item.get(k)}
            text = _clean(item.get("text"))
            candidates = [text, *variants.values()]
            if any(_BANNED_RE.search(c) for c in candidates if c):
                continue
            variants = {k: v for k, v in variants.items() if v}
            if not text and not variants:
                continue
            key = (text or " / ".join(variants.values())).lower()
            if key in seen or key.rstrip(".!?") == echo:
                continue
            seen.add(key)
            result.append(Rewrite(tone, text, variants))
            if len(result) >= count:
                break
        out[lang] = result
    return out
