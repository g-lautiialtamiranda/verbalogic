"""Which translation goes with which meaning.

Google gives a word's meanings (definition + synonyms + example) and, separately, its
alternative translations (each with the words it translates back to). It doesn't say which
translation belongs to which meaning, so we score them: a translation that translates back
to this meaning's synonyms, or that shows up in the translated synonyms, example or
definition, wins.
Pure functions, tested with real responses.
"""
from __future__ import annotations

import re

_PAREN = re.compile(r"\s*\([^)]*\)")
_WORD = re.compile(r"\w+")
STEM = 5  # "deposité" and "depositar" share "depos"


def _norm(text: str) -> str:
    return _PAREN.sub("", text).strip().lower()


def _stems(text: str) -> set[str]:
    return {w[:STEM] for w in _WORD.findall(text.lower()) if len(w) >= 3}


def _appears(candidate: str, stems: set[str]) -> bool:
    """The candidate's main word (its longest, so "depositar" in "depositar en un banco")
    appears in the text, compared by stem."""
    head = max(_WORD.findall(_norm(candidate)), key=len, default="")
    if len(head) < 3:
        return False
    return head[:STEM] in stems


def match_translations(sense: dict, alternatives: list[dict], gloss_tr: str = "", example_tr: str = "",
                       synonyms_tr: str = "") -> list[str]:
    """Translations for one meaning, best first. Empty if nothing fits (caller falls back).

    sense: {"pos", "synonyms"}; alternatives: [{"word", "pos", "reverse"}] in Google's order.
    """
    synonyms = {_norm(s) for s in sense.get("synonyms") or []}
    example_stems, gloss_stems, syn_stems = _stems(example_tr), _stems(gloss_tr), _stems(synonyms_tr)
    scored = []
    for order, alt in enumerate(alternatives):
        if sense.get("pos") and alt.get("pos") and alt["pos"] != sense["pos"]:
            continue
        score = 2 * len(synonyms & {_norm(r) for r in alt.get("reverse") or []})
        if _appears(alt["word"], syn_stems):
            score += 3
        if _appears(alt["word"], example_stems):
            score += 3
        if _appears(alt["word"], gloss_stems):
            score += 1
        if score:
            scored.append((-score, order, alt["word"]))
    return [w for _, _, w in sorted(scored)]


def fallback_translation(pos: str, alternatives: list[dict], default: str) -> str:
    """Google's top translation for this part of speech, else the plain translation."""
    return next((a["word"] for a in alternatives if a.get("pos") == pos), default)


def synonyms_line(sense: dict, count: int = 4) -> str:
    """The meaning's first synonyms as one short text, to translate alongside the definition."""
    return ", ".join(_norm(w) for w in (sense.get("synonyms") or [])[:count])


def pick_synonyms(senses: list[dict], pos: str, hints: list[str]) -> list[str] | None:
    """Synonyms of the translated word, for the meaning we're showing.

    The translation has meanings of its own ("pendiente": slope, earring, pending…). Pick the
    one whose synonyms share words with the hints (the other translations of this meaning and
    its translated synonyms). None if the word has no meaning data at all (caller falls back);
    [] if it has some but none fits (better nothing than an earring for a riverbank).
    """
    if not senses:
        return None
    hint = {_norm(h) for h in hints if h}
    best, best_score = [], 0
    for s in senses:
        if pos and s.get("pos") and s["pos"] != pos:
            continue
        score = len(hint & {_norm(w) for w in s.get("synonyms") or []})
        if score > best_score:
            best, best_score = s["synonyms"], score
    return best
