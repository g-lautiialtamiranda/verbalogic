"""Load, validate and save the user config (%APPDATA%/VerbaLogic/config.toml).

The user file is merged over config.default.toml, so a partial file is fine.
Saving goes through tomlkit, which keeps the user's comments and ordering.
"""
from __future__ import annotations

import copy
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

import tomlkit

from .keys import parse_combo, parse_copy_keys

APP_NAME = "VerbaLogic"
OLD_DEFAULT_ACCENT = "#6C5CE7"  # the first versions' purple, copied into every user's file

_LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,4})?$", re.I)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_INT_RANGES = {
    ("capture", "wait_ms"): (50, 2000),
    ("ui", "width"): (480, 2400),
    ("ui", "height"): (320, 1600),
    ("ui", "font_size"): (9, 28),
    ("ui", "max_synonyms"): (0, 60),
    ("ui", "max_examples"): (0, 10),
    ("ui", "max_meanings"): (1, 20),
    ("rewrites", "count"): (1, 8),
    ("rewrites", "timeout_seconds"): (3, 120),
    ("history", "size"): (10, 5000),
}
_CHOICES = {
    ("ui", "theme"): {"system", "light", "dark", "paper"},
    ("ui", "backdrop"): {"acrylic", "none"},
    ("rewrites", "spanish_variant"): {"both", "rioplatense", "neutral"},
}


def app_dir() -> Path:
    d = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return app_dir() / "config.toml"


def default_text() -> str:
    return resources.files("verbalogic").joinpath("config.default.toml").read_text(encoding="utf-8")


def defaults() -> dict[str, Any]:
    return tomlkit.parse(default_text()).unwrap()


def ensure_file(path: Path | None = None) -> Path:
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default_text(), encoding="utf-8")
    return path


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _type_ok(value: Any, default: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if isinstance(default, dict):
        return isinstance(value, dict)
    return True


def validate(cfg: dict, dflt: dict) -> tuple[dict, list[str]]:
    """Replace bad values with defaults. Returns (clean_config, warnings)."""
    warnings: list[str] = []
    cfg = copy.deepcopy(cfg)

    def reset(section: str, key: str, why: str) -> None:
        warnings.append(f"[{section}] {key}: {why} Using the default ({dflt[section][key]!r}).")
        cfg[section][key] = copy.deepcopy(dflt[section][key])

    for section, keys in dflt.items():
        if not isinstance(cfg.get(section), dict):
            if section in cfg:
                warnings.append(f"[{section}] should be a section. Using defaults.")
            cfg[section] = copy.deepcopy(keys)
            continue
        for key, dval in keys.items():
            if key not in cfg[section]:
                cfg[section][key] = copy.deepcopy(dval)
            elif not _type_ok(cfg[section][key], dval):
                reset(section, key, f"expected {type(dval).__name__}.")

    for (section, key), (lo, hi) in _INT_RANGES.items():
        if not lo <= cfg[section][key] <= hi:
            reset(section, key, f"must be between {lo} and {hi}.")
    for (section, key), options in _CHOICES.items():
        if cfg[section][key] not in options:
            reset(section, key, f"must be one of {sorted(options)}.")

    try:
        parse_combo(cfg["hotkey"]["open"], for_hotkey=True)
    except ValueError as e:
        reset("hotkey", "open", str(e))

    langs = cfg["languages"]
    for key in ("primary", "secondary"):
        if not _LANG_RE.match(langs[key]):
            reset("languages", key, "not a language code.")
    if langs["primary"].lower() == langs["secondary"].lower():
        reset("languages", "secondary", "must differ from primary.")
        if langs["primary"].lower() == langs["secondary"].lower():
            langs["primary"], langs["secondary"] = dflt["languages"]["primary"], dflt["languages"]["secondary"]
    for key in ("extra", "available_extra"):
        bad = [c for c in langs[key] if not _LANG_RE.match(c)]
        if bad:
            warnings.append(f"[languages] {key}: ignoring {bad}.")
            langs[key] = [c for c in langs[key] if _LANG_RE.match(c)]
    langs["primary"], langs["secondary"] = langs["primary"].lower(), langs["secondary"].lower()
    langs["extra"] = [c.lower() for c in langs["extra"]]
    langs["available_extra"] = [c.lower() for c in langs["available_extra"]]

    if cfg["ui"]["accent"].upper() == OLD_DEFAULT_ACCENT:  # nobody picked it: move them to today's default
        cfg["ui"]["accent"] = dflt["ui"]["accent"]
    if not _HEX_RE.match(cfg["ui"]["accent"]):
        reset("ui", "accent", "must look like #2F4A7A.")

    copy_keys = cfg["capture"]["copy_keys"]
    clean_keys: dict[str, str] = {}
    for app, spec in copy_keys.items():
        try:
            parse_copy_keys(spec)
            clean_keys[str(app).lower()] = spec
        except (ValueError, AttributeError):
            warnings.append(f"[capture.copy_keys] {app}: {spec!r} is not a valid keystroke. Ignoring it.")
    clean_keys.setdefault("default", "ctrl+c")
    cfg["capture"]["copy_keys"] = clean_keys

    if not cfg["rewrites"]["models"]:
        reset("rewrites", "models", "needs at least one model.")
    if not cfg["rewrites"]["base_url"].startswith("http"):
        reset("rewrites", "base_url", "must be a URL.")
    return cfg, warnings


def load(path: Path | None = None) -> tuple[dict, list[str]]:
    """Returns (config, warnings). Never raises for a bad user file."""
    path = ensure_file(path)
    dflt = defaults()
    try:
        user = tomlkit.parse(path.read_text(encoding="utf-8-sig")).unwrap()
    except Exception as e:  # noqa: BLE001 - any parse error falls back to defaults
        return dflt, [f"Couldn't read {path.name} ({e}). Using defaults until it's fixed."]
    return validate(deep_merge(dflt, user), dflt)


def _apply(doc: Any, changes: dict) -> None:
    for k, v in changes.items():
        if isinstance(v, dict):
            if k not in doc or not isinstance(doc[k], dict):
                doc[k] = tomlkit.table()
            _apply(doc[k], v)
        else:
            doc[k] = v


def save(changes: dict, path: Path | None = None) -> None:
    """Write nested changes into the user file, keeping comments."""
    path = ensure_file(path)
    doc = tomlkit.parse(path.read_text(encoding="utf-8-sig"))
    _apply(doc, changes)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
