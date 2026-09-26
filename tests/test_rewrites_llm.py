from verbalogic.lookup import is_word_mode
from verbalogic.providers.llm import extract_json
from verbalogic.rewrites import build_prompt, parse_rewrites


def test_extract_json_handles_think_and_fences():
    raw = '<think>hmm</think>\n```json\n{"en": [{"tone": "casual", "text": "Can\'t make it"}]}\n```'
    assert extract_json(raw)["en"][0]["text"] == "Can't make it"


def test_prompt_mentions_both_spanish_variants():
    p = build_prompt("I can't make it", "en", ["es", "en"], 3, "both")
    assert '"vos"' in p and '"neutral"' in p and "Rioplatense" in p
    assert "English" in p and "I can't make it" in p


def test_prompt_single_variant():
    p = build_prompt("hola", "es", ["es"], 2, "neutral")
    assert '"vos"' not in p and "tú" in p


def test_parse_filters_slop_dashes_and_echoes():
    data = {
        "en": [
            {"tone": "casual", "text": "I can't make it tomorrow — sorry"},
            {"tone": "formal", "text": "Let me delve into my schedule"},
            {"tone": "neutral", "text": "I can't make it to the meeting tomorrow."},
            {"tone": "weird", "text": "\"Tomorrow's not going to work for me\""},
            {"tone": "casual", "text": "I can't make it tomorrow, sorry"},
        ],
        "es": [{"tone": "casual", "vos": "Mañana no puedo ir", "neutral": "Mañana no puedo asistir"}],
    }
    out = parse_rewrites(data, "I can't make it to the meeting tomorrow", ["en", "es"], 4)
    en = [r.text for r in out["en"]]
    assert en == ["I can't make it tomorrow, sorry", "Tomorrow's not going to work for me"]
    assert out["en"][1].tone == "neutral"
    assert out["es"][0].variants == {"vos": "Mañana no puedo ir", "neutral": "Mañana no puedo asistir"}


def test_word_mode():
    assert is_word_mode("aprovechar")
    assert is_word_mode("take advantage of")
    assert not is_word_mode("I can't make it to the meeting tomorrow")
    assert not is_word_mode("")
