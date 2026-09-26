import json
from pathlib import Path

import pytest

from verbalogic.providers.google_free import ServiceError, parse_chrome, parse_chrome_many, parse_dictionary

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8-sig"))


def test_chrome_auto_and_fixed_source():
    assert parse_chrome([["mejorar", "en"]], "auto") == ("mejorar", "en")
    assert parse_chrome(["mejorar"], "en") == ("mejorar", "en")


@pytest.mark.skipif(not (FIX / "improve_en_es.json").exists(), reason="fixture not captured")
def test_word_en_to_es():
    d = parse_dictionary(load("improve_en_es.json"))
    assert d.src == "en"
    assert d.translation.lower() == "mejorar"
    syns = [w for g in d.synonyms for w in g.words]
    assert "enhance" in syns
    assert d.alternatives and d.alternatives[0].reverse
    assert d.examples


@pytest.mark.skipif(not (FIX / "aprovechar_es_en.json").exists(), reason="fixture not captured")
def test_word_es_to_en_rare_last():
    d = parse_dictionary(load("aprovechar_es_en.json"))
    assert d.src == "es"
    verbs = next(g for g in d.synonyms if g.pos == "verb")
    assert "usar" in verbs.words
    assert len(verbs.words) == len(set(verbs.words))


@pytest.mark.skipif(not (FIX / "sentence_en_es.json").exists(), reason="fixture not captured")
def test_sentence_has_translation_only():
    d = parse_dictionary(load("sentence_en_es.json"))
    assert "reunión" in d.translation
    assert d.synonyms == []


def test_senses_link_synonyms_by_definition_id():
    d = parse_dictionary(load("bank_en_es.json"))
    assert len(d.senses) >= 8
    river = d.senses[0]
    assert river.pos == "noun" and "river" in river.gloss
    assert river.example == "willows lined the bank"
    assert "edge" in river.synonyms and "financial institution" not in river.synonyms
    money = next(s for s in d.senses if "financial" in s.gloss)
    assert "financial institution" in money.synonyms
    tilt = next(s for s in d.senses if "tilt" in s.gloss)
    assert tilt.pos == "verb" and "lean" in tilt.synonyms


def test_senses_spanish_source():
    d = parse_dictionary(load("banco_es_en.json"))
    seat = d.senses[0]
    assert seat.gloss.startswith("Asiento") and "banqueta" in seat.synonyms


def test_parse_chrome_many():
    assert parse_chrome_many(["orilla", "un banco de nieve"], 2) == ["orilla", "un banco de nieve"]
    assert parse_chrome_many([["hola", "en"], ["adiós", "en"]], 2) == ["hola", "adiós"]
    with pytest.raises(ServiceError):
        parse_chrome_many(["solo uno"], 2)
