"""Language codes and display names."""
from __future__ import annotations

NAMES = {
    "es": "Español", "en": "English", "pt": "Português", "fr": "Français", "it": "Italiano",
    "de": "Deutsch", "nl": "Nederlands", "ca": "Català", "ja": "日本語", "zh-cn": "中文",
    "ko": "한국어", "ru": "Русский", "ar": "العربية", "tr": "Türkçe", "pl": "Polski",
}
# English names, used inside prompts.
ENGLISH_NAMES = {
    "es": "Spanish", "en": "English", "pt": "Portuguese", "fr": "French", "it": "Italian",
    "de": "German", "nl": "Dutch", "ca": "Catalan", "ja": "Japanese", "zh-cn": "Chinese",
    "ko": "Korean", "ru": "Russian", "ar": "Arabic", "tr": "Turkish", "pl": "Polish",
}


def norm(code: str) -> str:
    return (code or "").strip().lower()


def base(code: str) -> str:
    """'pt-BR' -> 'pt'. Used to compare languages."""
    return norm(code).split("-")[0]


def same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and base(a) == base(b)


def name(code: str) -> str:
    c = norm(code)
    return NAMES.get(c) or NAMES.get(base(c)) or c.upper()


def english_name(code: str) -> str:
    c = norm(code)
    return ENGLISH_NAMES.get(c) or ENGLISH_NAMES.get(base(c)) or c


def short(code: str) -> str:
    return base(code).upper()
