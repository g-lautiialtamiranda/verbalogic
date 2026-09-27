import json
from dataclasses import asdict
from pathlib import Path

from verbalogic.providers.google_free import parse_dictionary
from verbalogic.senses import fallback_translation, match_translations, pick_synonyms, similar_words, synonyms_line

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return asdict(parse_dictionary(json.loads((FIX / name).read_text(encoding="utf-8-sig"))))


BANK = load("bank_en_es.json")
BANCO = load("banco_es_en.json")


def sense(d, needle):
    return next(s for s in d["senses"] if needle in s["gloss"])


def test_reverse_translations_pick_the_meaning():
    # orilla translates back to "edge"/"side", the riverbank synonyms
    assert match_translations(sense(BANK, "river"), BANK["alternatives"])[0] == "orilla"
    assert match_translations(sense(BANK, "tilt"), BANK["alternatives"])[0] == "ladear"
    assert match_translations(sense(BANK, "heap"), BANK["alternatives"])[0] == "amontonar"


def test_part_of_speech_is_respected():
    words = match_translations(sense(BANK, "tilt"), BANK["alternatives"])
    assert "orilla" not in words and "banco" not in words


def test_translated_example_matches_by_stem():
    deposit = sense(BANK, "deposit (money")
    words = match_translations(deposit, BANK["alternatives"], example_tr="deposité el cheque")
    assert words[0] == "depositar en un banco"


def test_translated_synonyms_break_ties():
    seat = BANCO["senses"][0]
    assert synonyms_line(seat).startswith("banca, asiento")
    words = match_translations(seat, BANCO["alternatives"], synonyms_tr="bench, seat, banquette, stool")
    assert words[0] == "bench"


def test_no_match_falls_back_to_top_translation_for_pos():
    cushion = sense(BANK, "pool table")
    assert match_translations(cushion, BANK["alternatives"]) == []
    assert fallback_translation("noun", BANK["alternatives"], "banco") == "banco"
    assert fallback_translation("verb", BANK["alternatives"], "banco") == BANK["alternatives"][
        next(i for i, a in enumerate(BANK["alternatives"]) if a["pos"] == "verb")]["word"]
    assert fallback_translation("adverb", BANK["alternatives"], "banco") == "banco"


def test_pick_synonyms_follows_the_meaning():
    pendiente = [
        {"pos": "noun", "synonyms": ["arete", "zarcillo"]},              # earring
        {"pos": "noun", "synonyms": ["cuesta", "subida", "declive"]},    # slope
        {"pos": "adjective", "synonyms": ["atento", "alerta"]},
    ]
    assert pick_synonyms(pendiente, "noun", ["montón", "subida"]) == ["cuesta", "subida", "declive"]
    assert pick_synonyms(pendiente, "noun", ["nada que ver"]) == []
    assert pick_synonyms(pendiente, "noun", ["alerta"]) == []          # wrong part of speech
    assert pick_synonyms([], "noun", ["subida"]) is None


def test_similar_words_come_from_reverse_translations():
    words = similar_words(BANCO["alternatives"], ["banco"])
    assert words[:2] == ["orilla", "batería"]
    assert "banco" not in words and "escaño" in words
    assert len(words) == len(set(words))


def test_similar_words_follow_one_meaning():
    shoal = [a for a in BANCO["alternatives"] if a["word"] == "shoal"]
    assert similar_words(shoal, ["banco"]) == ["cardumen", "banco de arena", "multitud"]


def test_similar_words_with_hints_keep_only_that_meaning():
    # translations of "orilla" back to Spanish: only those linked to "ribera" count
    alts = [{"word": "shore", "pos": "noun", "reverse": ["orilla", "costa", "ribera"]},
            {"word": "edge", "pos": "noun", "reverse": ["borde", "filo", "orilla"]},
            {"word": "border", "pos": "verb", "reverse": ["bordear", "ribera"]}]
    assert similar_words(alts, ["orilla"], "noun", ["ribera"]) == ["costa", "ribera"]
    assert similar_words(alts, ["orilla"], "noun", []) == []


def test_exclamation_and_interjection_are_the_same_part_of_speech():
    hello = {"pos": "exclamation", "synonyms": ["hi", "hullo"]}
    alts = [{"word": "¡Hola!", "pos": "interjection", "reverse": ["Hello!", "Hi!", "Hullo!"]},
            {"word": "saludo", "pos": "noun", "reverse": ["greeting", "hi"]}]
    assert match_translations(hello, alts) == ["¡Hola!"]  # "Hi!" counts as "hi"
    assert similar_words(alts, ["hello"], "exclamation") == ["Hi!", "Hullo!"]  # not the noun's "greeting"
