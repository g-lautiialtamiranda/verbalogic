"""Runs one lookup: translations first (fast), then dictionary data and AI rewrites in parallel.

For words with several meanings, the dictionary data is split per meaning: definition,
synonyms and example in the source language, plus the matching translation (see senses.py).

Results are emitted as Qt signals tagged with a generation number, so answers for an old
lookup never land in the popup after the user has asked something new.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

import httpx
from PySide6.QtCore import QObject, Signal

from . import credentials
from . import languages as L
from .cache import Cache
from .providers import datamuse
from .providers.google_free import GoogleFree, RateLimited, ServiceError
from .providers.llm import ChatClient, LLMError
from .rewrites import build_prompt, parse_rewrites
from .senses import fallback_translation, match_translations, pick_synonyms, similar_words, synonyms_line

log = logging.getLogger("verbalogic.lookup")


def wants_rewrites(cfg: dict, text: str) -> bool:
    """Rewrites run when enabled, allowed for this length of text, and a key is set."""
    rw = cfg["rewrites"]
    return (rw["enabled"] and not (rw["only_for_sentences"] and is_word_mode(text))
            and bool(credentials.get_key(rw["api_key_env"])))


def is_word_mode(text: str) -> bool:
    """Words and short expressions get dictionary data; longer text only gets translations."""
    t = text.strip()
    return bool(t) and "\n" not in t and len(t) <= 40 and len(t.split()) <= 3


class Lookup(QObject):
    detected = Signal(int, str)                 # gen, source language
    translated = Signal(int, str, str, bool)    # gen, lang, text, is_original
    details = Signal(int, str, dict)            # gen, lang, column data
    rewrites_ready = Signal(int, dict, str)     # gen, {lang: [rewrite dicts]}, model
    rewrites_failed = Signal(int, str)          # gen, message
    failed = Signal(int, str)                   # gen, message
    timing = Signal(int, int)                   # gen, milliseconds until translations were shown
    sense_synonyms_ready = Signal(int, str, int, dict)  # gen, lang, meaning index, column data

    def __init__(self, http: httpx.Client, cache: Cache, parent=None):
        super().__init__(parent)
        self.http = http
        self.cache = cache
        self.google = GoogleFree(http)
        self._runner = ThreadPoolExecutor(2, thread_name_prefix="vl-lookup")
        self._io = ThreadPoolExecutor(10, thread_name_prefix="vl-io")
        self.gen = 0

    def start(self, text: str, cfg: dict, langs: list[str]) -> int:
        self.gen += 1
        gen = self.gen
        self._runner.submit(self._safe_run, gen, text.strip(), cfg, list(dict.fromkeys(langs)))
        return gen

    def _alive(self, gen: int) -> bool:
        return gen == self.gen

    def _safe_run(self, gen: int, text: str, cfg: dict, langs: list[str]) -> None:
        try:
            self._run(gen, text, cfg, langs)
        except Exception as e:  # noqa: BLE001 - report instead of dying silently
            log.exception("lookup failed")
            if self._alive(gen):
                self.failed.emit(gen, f"Something went wrong: {e}")

    # --- cached provider calls ---
    def _translate(self, text: str, lang: str) -> tuple[str, str]:
        key = f"tr|{lang}|{text}"
        hit = self.cache.get(key)
        if hit:
            return hit[0], hit[1]
        trans, src = self.google.translate(text, lang)
        self.cache.set(key, [trans, src])
        return trans, src

    def _dictionary(self, text: str, target: str, source: str) -> dict:
        key = f"dict2|{source}|{target}|{text.lower()}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        data = asdict(self.google.dictionary(text, target, source))
        self.cache.set(key, data)
        return data

    # --- the lookup itself ---
    def _run(self, gen: int, text: str, cfg: dict, langs: list[str]) -> None:
        if not text:
            return
        t0 = time.monotonic()
        log.info("lookup %d started: %r -> %s", gen, text[:40], langs)
        futures = {self._io.submit(self._translate, text, lang): lang for lang in langs}
        translations: dict[str, str] = {}
        src = ""
        errors: list[str] = []
        for fut in as_completed(futures):
            lang = futures[fut]
            try:
                trans, detected = fut.result()
            except (httpx.HTTPError, ServiceError, RateLimited, ValueError) as e:
                errors.append(str(e))
                continue
            if not src and detected:
                src = detected
                if self._alive(gen):
                    self.detected.emit(gen, src)
            original = L.same(lang, src)
            translations[lang] = text if original else trans
            if self._alive(gen):
                self.translated.emit(gen, lang, translations[lang], original)
        if not self._alive(gen):
            return
        if not translations:
            self.failed.emit(gen, "Couldn't translate. Check your internet connection. " + (errors[0] if errors else ""))
            return
        ms = int((time.monotonic() - t0) * 1000)
        log.info("lookup %d translated in %d ms (source %s)", gen, ms, src)
        self.timing.emit(gen, ms)

        word = is_word_mode(text)
        if wants_rewrites(cfg, text):
            self._io.submit(self._rewrites, gen, text, src, [l for l in langs[:2]], cfg)
        if word:
            self._details(gen, text, src, langs, translations, cfg)

    def _translate_many(self, texts: list[str], target: str, source: str) -> list[str]:
        """Translate the non-empty texts in one request; empty stays empty. Cached as a batch."""
        key = f"trm|{source}|{target}|" + "".join(texts)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        todo = [i for i, t in enumerate(texts) if t]
        out = [""] * len(texts)
        for i, t in zip(todo, self.google.translate_many([texts[i] for i in todo], target, source)):
            out[i] = t
        self.cache.set(key, out)
        return out

    def _details(self, gen: int, text: str, src: str, langs: list[str], translations: dict[str, str], cfg: dict) -> None:
        source_col = next((l for l in langs if L.same(l, src)), None)
        targets = [l for l in langs if not L.same(l, src) and l in translations]
        jobs = [
            self._io.submit(self._details_for_target, gen, text, src, lang, translations[lang],
                            source_col if i == 0 else None, cfg["ui"]["max_meanings"])
            for i, lang in enumerate(targets)
        ]
        if source_col and not targets:
            jobs.append(self._io.submit(self._details_for_target, gen, text, src, None, "", source_col,
                                        cfg["ui"]["max_meanings"]))
        for j in jobs:
            j.result()

    def _details_for_target(self, gen: int, text: str, src: str, lang: str | None, trans: str, source_col: str | None,
                            max_meanings: int = 8) -> None:
        target_data: dict = {}
        source_data: dict = {}
        a_alts: list[dict] = []   # the text's translations, each with the words it translates back to
        b_alts: list[dict] = []   # the same for the main translation
        # A: the selected text itself -> alternative translations + source-language synonyms/examples.
        dict_target = lang or ("en" if not L.same(src, "en") else "es")
        try:
            a = self._dictionary(text, dict_target, src)
            a_alts = a["alternatives"]
            if lang:
                target_data["alternatives"] = a["alternatives"]
            if source_col:
                source_data.update(_word_info(a, "google"))
            senses = (a.get("senses") or [])[:max_meanings]
            if len(senses) >= 2:
                if source_col:
                    source_data["senses"] = [
                        {"pos": x["pos"], "gloss": x["gloss"], "example": x["example"],
                         "synonyms": [{"pos": "", "words": x["synonyms"], "source": "google"}] if x["synonyms"] else []}
                        for x in senses
                    ]
                if lang:
                    target_data["senses"] = self._target_senses(senses, a["alternatives"], src, lang, trans)
                if source_col and lang and not L.same(source_col, "en"):
                    _similar_per_sense(source_data["senses"], target_data["senses"], a_alts, text)
        except RateLimited as e:
            note = f"Dictionary resting (Google limit). Back in ~{e.seconds}s."
            target_data["note"] = source_data["note"] = note
        except (ServiceError, httpx.HTTPError, ValueError):
            target_data["note"] = source_data["note"] = "Dictionary unavailable right now."

        # B: the main translation -> synonyms and examples in the target language.
        if lang and trans and is_word_mode(trans) and trans.lower() != text.lower() and "note" not in target_data:
            try:
                b = self._dictionary(trans, src, lang)
                b_alts = b["alternatives"]
                target_data.update(_word_info(b, "google"))
            except RateLimited as e:
                target_data["note"] = f"Dictionary resting (Google limit). Back in ~{e.seconds}s."
            except (ServiceError, httpx.HTTPError, ValueError):
                pass

        # English fallback: Datamuse.
        for data, code, word in ((target_data, lang, trans), (source_data, source_col, text)):
            if code and L.same(code, "en") and not data.get("synonyms") and word:
                words = self._datamuse(word)
                if words:
                    data["synonyms"] = [{"pos": "", "words": words, "source": "datamuse"}]

        # Still nothing (often Spanish; English has Datamuse): the words Google translates back
        # to. "Also translates as" already lists the text's own translations, so those are left out.
        shown = [x["word"] for x in a_alts]
        for data, code, word, alts, skip in ((target_data, lang, trans, b_alts, shown),
                                             (source_data, source_col, text, a_alts, [])):
            if code and not L.same(code, "en") and word and alts and not data.get("synonyms"):
                words = similar_words(alts, [word, *skip])
                if words:
                    data["synonyms"] = [{"pos": "", "words": words, "source": "similar"}]

        if not self._alive(gen):
            return
        if lang:
            self.details.emit(gen, lang, target_data)
        if source_col:
            self.details.emit(gen, source_col, source_data)

    def _target_senses(self, senses: list[dict], alternatives: list[dict], src: str, lang: str, trans: str) -> list[dict]:
        """For each meaning: the translation that fits it, other fitting ones, and the
        definition and example translated into the target language."""
        n = len(senses)
        texts = [x["gloss"] for x in senses] + [x["example"] for x in senses] + [synonyms_line(x) for x in senses]
        try:
            tr = self._translate_many(texts, lang, src)
        except ServiceError:
            tr = [""] * len(texts)
        out = []
        for i, x in enumerate(senses):
            matched = match_translations(x, alternatives, tr[i], tr[n + i], tr[2 * n + i])
            word = matched[0] if matched else fallback_translation(x["pos"], alternatives, trans)
            out.append({"pos": x["pos"], "word": word, "also": [w for w in matched if w != word][:6], "matched": matched,
                        "gloss": tr[i], "example": tr[n + i],
                        "hints": matched + [h.strip() for h in tr[2 * n + i].split(",")]})
        return out

    def sense_synonyms(self, gen: int, lang: str, index: int, sense: dict, src: str) -> None:
        """Synonyms of one meaning's translation, fetched only when that meaning is opened."""
        self._io.submit(self._sense_synonyms, gen, lang, index, sense, src)

    def _sense_synonyms(self, gen: int, lang: str, index: int, sense: dict, src: str) -> None:
        data: dict = {}
        word = sense["word"]
        alts: list[dict] = []
        try:
            if is_word_mode(word):
                d = self._dictionary(word, src, lang)
                alts = d["alternatives"]
                picked = pick_synonyms(d.get("senses") or [], sense["pos"], sense.get("hints") or [])
                if picked:
                    data["synonyms"] = [{"pos": "", "words": picked, "source": "google"}]
                elif picked is None:  # no meaning data: same part of speech, else everything
                    groups = [g for g in d["synonyms"] if g["pos"] == sense["pos"]] or d["synonyms"]
                    data = _word_info({**d, "synonyms": groups}, "google")
                    data.pop("definition", None)
                    data.pop("examples", None)
                else:
                    data["picked_none"] = True
        except RateLimited as e:
            data["note"] = f"Dictionary resting (Google limit). Back in ~{e.seconds}s."
        except (ServiceError, httpx.HTTPError, ValueError):
            pass
        except Exception:  # noqa: BLE001 - a background job must not die silently
            log.exception("sense synonyms failed")
        picked_none = data.pop("picked_none", False)
        if not data.get("synonyms") and not data.get("note") and alts and not L.same(lang, "en"):
            # Words that translate back into this meaning's other words (not the word itself,
            # which every alternative translates back to). Nothing to go on: nothing shown.
            hints = [h for h in sense.get("hints") or [] if h.strip().lower() != word.lower()]
            words = similar_words(alts, [word, *(sense.get("also") or [])], sense["pos"], hints)
            if words:
                data["synonyms"] = [{"pos": "", "words": words, "source": "similar"}]
        if not data.get("synonyms") and not picked_none and L.same(lang, "en"):
            words = self._datamuse(word)
            if words:
                data["synonyms"] = [{"pos": "", "words": words, "source": "datamuse"}]
        if self._alive(gen):
            self.sense_synonyms_ready.emit(gen, lang, index, data)

    def _datamuse(self, word: str) -> list[str]:
        key = f"dm|{word.lower()}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        words = datamuse.synonyms(self.http, word)
        if words:
            self.cache.set(key, words)
        return words

    def _rewrites(self, gen: int, text: str, src: str, langs: list[str], cfg: dict) -> None:
        rw = cfg["rewrites"]
        key = f"rw|{rw['spanish_variant']}|{rw['count']}|{','.join(langs)}|{text}"
        hit = self.cache.get(key)
        if hit:
            if self._alive(gen):
                self.rewrites_ready.emit(gen, hit["items"], hit["model"])
            return
        client = ChatClient(self.http, rw["base_url"], rw["models"], credentials.get_key(rw["api_key_env"]), rw["timeout_seconds"])
        try:
            prompt = build_prompt(text, src, langs, rw["count"], rw["spanish_variant"])
            data, model = client.complete_json(prompt)
            parsed = parse_rewrites(data, text, langs, rw["count"])
            items = {lang: [asdict(r) for r in rs] for lang, rs in parsed.items()}
            if not any(items.values()):
                raise LLMError("The AI answer didn't contain usable options. Try again.")
            self.cache.set(key, {"items": items, "model": model})
            if self._alive(gen):
                self.rewrites_ready.emit(gen, items, model)
        except LLMError as e:
            if self._alive(gen):
                self.rewrites_failed.emit(gen, str(e))


def _similar_per_sense(source_senses: list[dict], target_senses: list[dict], alternatives: list[dict], text: str) -> None:
    """Meanings of the looked-up word with no synonyms get similar words: what the
    translations matched to that meaning translate back to."""
    for s, t in zip(source_senses, target_senses):
        if s["synonyms"] or not t.get("matched"):
            continue
        matched = set(t["matched"])
        words = similar_words([x for x in alternatives if x["word"] in matched], [text])
        if words:
            s["synonyms"] = [{"pos": "", "words": words, "source": "similar"}]


def _word_info(d: dict, source: str) -> dict:
    info: dict = {}
    if d.get("synonyms"):
        info["synonyms"] = [{**g, "source": source} for g in d["synonyms"]]
    if d.get("examples"):
        info["examples"] = d["examples"]
    if d.get("definitions"):
        pos, gloss = d["definitions"][0]
        info["definition"] = gloss
    return info
