import pytest

from verbalogic import config
from verbalogic.keys import known_conflict, parse_combo, parse_copy_keys


def test_parse_hotkey_canonical_order():
    c = parse_combo("Alt+Ctrl+D", for_hotkey=True)
    assert str(c) == "ctrl+alt+d"
    assert c.pretty() == "Ctrl+Alt+D"
    assert c.vk == ord("D")
    assert c.mod_flags == 0x0002 | 0x0001


@pytest.mark.parametrize("spec", ["", "ctrl+alt", "hyper+d", "ctrl+alt+nope", "shift+d"])
def test_bad_hotkeys(spec):
    with pytest.raises(ValueError):
        parse_combo(spec, for_hotkey=True)


def test_function_key_alone_is_allowed():
    assert parse_combo("f9", for_hotkey=True).vk == 0x78


def test_known_conflicts():
    assert "Warp" in known_conflict(parse_combo("ctrl+alt+t"))
    assert known_conflict(parse_combo("ctrl+alt+d")) is None


def test_copy_keys_none():
    assert parse_copy_keys("none") is None
    assert str(parse_copy_keys("ctrl+shift+c")) == "ctrl+shift+c"


def test_defaults_are_valid():
    d = config.defaults()
    clean, warnings = config.validate(d, d)
    assert warnings == []
    assert clean["hotkey"]["open"] == "ctrl+alt+d"
    assert clean["capture"]["copy_keys"]["warp.exe"] == "ctrl+shift+c"


def test_bad_values_fall_back(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[hotkey]\nopen = "shift+x"\n[ui]\naccent = "purple"\nwidth = 5\n'
        '[languages]\nprimary = "en"\nsecondary = "en"\n[capture.copy_keys]\n"foo.exe" = "ctrl+banana"\n',
        encoding="utf-8",
    )
    cfg, warnings = config.load(p)
    assert cfg["hotkey"]["open"] == "ctrl+alt+d"
    assert cfg["ui"]["accent"] == "#6C5CE7"
    assert cfg["ui"]["width"] == 820
    assert cfg["languages"]["primary"] != cfg["languages"]["secondary"]
    assert "foo.exe" not in cfg["capture"]["copy_keys"]
    assert cfg["capture"]["copy_keys"]["warp.exe"] == "ctrl+shift+c"  # defaults still merged in
    assert len(warnings) >= 4


def test_save_keeps_comments(tmp_path):
    p = tmp_path / "config.toml"
    config.ensure_file(p)
    config.save({"hotkey": {"open": "ctrl+alt+space"}, "languages": {"extra": ["pt"]}}, p)
    text = p.read_text(encoding="utf-8")
    assert "# Avoid ctrl+alt+t" in text
    cfg, warnings = config.load(p)
    assert cfg["hotkey"]["open"] == "ctrl+alt+space"
    assert cfg["languages"]["extra"] == ["pt"]
    assert warnings == []


def test_file_with_bom_loads(tmp_path):
    p = tmp_path / "config.toml"
    p.write_bytes(b"\xef\xbb\xbf" + b'[ui]\ntheme = "light"\n')
    cfg, warnings = config.load(p)
    assert cfg["ui"]["theme"] == "light"
    assert warnings == []


def test_broken_toml_uses_defaults(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[ui\nwidth = ", encoding="utf-8")
    cfg, warnings = config.load(p)
    assert cfg["ui"]["width"] == 820
    assert warnings
