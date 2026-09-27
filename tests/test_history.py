from verbalogic.history import History


def test_recent_is_newest_first_and_moves_repeats_to_top():
    h = History(None)
    for w in ("bank", "improve", "banco"):
        h.add(w, "en", {"es": w.upper()})
    h.add("bank", "en", {"es": "banco"})
    assert [e.text for e in h.recent()] == ["bank", "banco", "improve"]
    assert h.recent()[0].translations == {"es": "banco"}


def test_trimming_keeps_saved_words():
    h = History(None, size=3)
    h.add("keep me", "en", {})
    h.set_star("keep me", True, gloss="a meaning")
    for i in range(10):
        h.add(f"w{i}", "en", {})
    texts = [e.text for e in h.recent(50)]
    assert "keep me" in texts
    assert len([t for t in texts if t.startswith("w")]) == 3
    assert h.starred()[0].gloss == "a meaning"


def test_star_survives_a_new_lookup_and_can_be_removed():
    h = History(None)
    h.set_star("orilla", True, "es", {"en": "shore"})   # saved before the lookup was recorded
    h.add("orilla", "es", {"en": "bank"})
    assert h.is_starred("orilla")
    assert h.starred()[0].translation() == "bank"
    h.set_star("orilla", False)
    assert not h.is_starred("orilla") and h.starred() == []


def test_clear_recent_keeps_saved(tmp_path):
    h = History(tmp_path / "history.sqlite")
    h.add("a", "en", {})
    h.add("b", "en", {})
    h.set_star("b", True)
    h.clear_recent()
    assert [e.text for e in History(tmp_path / "history.sqlite").recent()] == ["b"]


def test_translation_skips_the_original_column():
    h = History(None)
    h.add("bank", "en", {"en": "bank", "es": "banco"})
    assert h.recent()[0].translation() == "banco"


def test_counts_saved_and_recent():
    h = History(None)
    assert h.counts() == (0, 0)
    for w in ("a", "b", "c"):
        h.add(w, "en", {})
    h.set_star("b", True)
    assert h.counts() == (1, 2)
