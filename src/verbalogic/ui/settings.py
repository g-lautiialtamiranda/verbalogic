"""Settings window. Writes to config.toml (keeping comments); the app reloads from the file."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, Qt, QThreadPool, QRunnable, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .. import config, credentials
from .. import languages as L
from ..keys import known_conflict, parse_combo

if TYPE_CHECKING:
    from ..app import VerbaLogicApp

_QT_MODS = ((Qt.ControlModifier, "ctrl"), (Qt.AltModifier, "alt"), (Qt.ShiftModifier, "shift"), (Qt.MetaModifier, "win"))
_QT_NAMED = {
    Qt.Key_Space: "space", Qt.Key_Return: "enter", Qt.Key_Enter: "enter", Qt.Key_Tab: "tab",
    Qt.Key_Insert: "insert", Qt.Key_Delete: "delete", Qt.Key_Home: "home", Qt.Key_End: "end",
    Qt.Key_PageUp: "pageup", Qt.Key_PageDown: "pagedown", Qt.Key_Up: "up", Qt.Key_Down: "down",
    Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Pause: "pause",
}


def sequence_to_spec(seq: QKeySequence) -> str | None:
    if seq.isEmpty():
        return None
    combo = seq[0]
    mods = [name for flag, name in _QT_MODS if combo.keyboardModifiers() & flag]
    key = combo.key()
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        name = chr(key).lower()
    elif Qt.Key_F1 <= key <= Qt.Key_F24:
        name = f"f{key - Qt.Key_F1 + 1}"
    else:
        name = _QT_NAMED.get(key)
    return "+".join([*mods, name]) if name else None


class _Job(QRunnable):
    class _Signals(QObject):
        done = Signal(object)

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self.fn = fn
        self.signals = self._Signals()

    def run(self):
        try:
            result = self.fn()
        except Exception as e:  # noqa: BLE001
            result = e
        self.signals.done.emit(result)


class SettingsDialog(QDialog):
    def __init__(self, app: "VerbaLogicApp"):
        super().__init__(None, Qt.Window | Qt.WindowCloseButtonHint)
        self.app = app
        self.setObjectName("settings")
        self.setWindowTitle("VerbaLogic settings")
        self.setMinimumWidth(560)
        cfg = app.cfg
        self._accent = cfg["ui"]["accent"]
        self._jobs: list[_Job] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(12)
        tabs = self.tabs = QTabWidget()
        root.addWidget(tabs)

        # ---- General ----
        g = QWidget()
        gf = QFormLayout(g)
        gf.setContentsMargins(16, 16, 16, 16)
        gf.setVerticalSpacing(12)
        self.hotkey = QKeySequenceEdit(QKeySequence(parse_combo(cfg["hotkey"]["open"]).pretty()))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.keySequenceChanged.connect(self._check_hotkey)
        check = QPushButton("Check")
        check.setObjectName("secondary")
        check.clicked.connect(self._check_hotkey)
        hk = QHBoxLayout()
        hk.addWidget(self.hotkey, 1)
        hk.addWidget(check)
        gf.addRow("Shortcut", hk)
        self.hotkey_status = QLabel("Click the box and press the new shortcut.")
        self.hotkey_status.setObjectName("hint")
        self.hotkey_status.setWordWrap(True)
        gf.addRow("", self.hotkey_status)

        self.auto_copy = QCheckBox("Copy the selection automatically when I press the shortcut")
        self.auto_copy.setChecked(cfg["capture"]["auto_copy"])
        gf.addRow("", self.auto_copy)
        self.close_blur = QCheckBox("Close the popup when I click somewhere else")
        self.close_blur.setChecked(cfg["ui"]["close_on_focus_loss"])
        gf.addRow("", self.close_blur)
        self.startup = QCheckBox("Start VerbaLogic with Windows")
        self.startup.setChecked(cfg["startup"]["start_with_windows"])
        gf.addRow("", self.startup)

        self.theme = QComboBox()
        self.theme.addItems(["system", "light", "dark"])
        self.theme.setCurrentText(cfg["ui"]["theme"])
        gf.addRow("Theme", self.theme)
        self.accent_btn = QPushButton()
        self.accent_btn.setObjectName("secondary")
        self.accent_btn.clicked.connect(self._pick_accent)
        self._paint_accent()
        accent_row = QHBoxLayout()
        accent_row.addWidget(self.accent_btn)
        accent_row.addStretch(1)
        gf.addRow("Accent color", accent_row)
        size = QHBoxLayout()
        self.width_spin = self._spin(480, 2400, cfg["ui"]["width"], " px")
        self.height_spin = self._spin(320, 1600, cfg["ui"]["height"], " px")
        size.addWidget(self.width_spin)
        size.addWidget(QLabel("×"))
        size.addWidget(self.height_spin)
        size.addStretch(1)
        gf.addRow("Popup size", size)
        self.font_spin = self._spin(9, 28, cfg["ui"]["font_size"], " px")
        gf.addRow("Text size", self.font_spin)
        self.syn_spin = self._spin(0, 60, cfg["ui"]["max_synonyms"], "")
        gf.addRow("Max synonyms", self.syn_spin)
        tabs.addTab(g, "General")

        # ---- Languages ----
        lw = QWidget()
        lf = QFormLayout(lw)
        lf.setContentsMargins(16, 16, 16, 16)
        lf.setVerticalSpacing(12)
        self.primary = self._lang_combo(cfg["languages"]["primary"])
        self.secondary = self._lang_combo(cfg["languages"]["secondary"])
        lf.addRow("First column", self.primary)
        lf.addRow("Second column", self.secondary)
        self.available = QLineEdit(", ".join(cfg["languages"]["available_extra"]))
        lf.addRow("Extra languages", self.available)
        hint = QLabel("Comma-separated codes (pt, fr, it, de…). They appear as + buttons in the popup.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lf.addRow("", hint)
        self.extra_on = QLineEdit(", ".join(cfg["languages"]["extra"]))
        lf.addRow("Show by default", self.extra_on)
        tabs.addTab(lw, "Languages")

        # ---- Rewrites ----
        rw = QWidget()
        rf = QFormLayout(rw)
        rf.setContentsMargins(16, 16, 16, 16)
        rf.setVerticalSpacing(12)
        r = cfg["rewrites"]
        self.rw_on = QCheckBox("Show “Other ways to say it” (free AI via OpenRouter)")
        self.rw_on.setChecked(r["enabled"])
        rf.addRow("", self.rw_on)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-or-v1-…  (paste your free key)")
        save_key = QPushButton("Save key")
        save_key.setObjectName("secondary")
        save_key.clicked.connect(self._save_key)
        remove_key = QPushButton("Remove")
        remove_key.setObjectName("secondary")
        remove_key.clicked.connect(self._remove_key)
        kr = QHBoxLayout()
        kr.addWidget(self.key_edit, 1)
        kr.addWidget(save_key)
        kr.addWidget(remove_key)
        rf.addRow("API key", kr)
        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        self.key_status.setOpenExternalLinks(True)
        rf.addRow("", self.key_status)
        self._refresh_key_status()
        self.variant = QComboBox()
        self.variant.addItem("Both: vos (Argentina) + neutral", "both")
        self.variant.addItem("Rioplatense (vos)", "rioplatense")
        self.variant.addItem("Neutral (tú)", "neutral")
        self.variant.setCurrentIndex(max(0, self.variant.findData(r["spanish_variant"])))
        rf.addRow("Spanish style", self.variant)
        self.count_spin = self._spin(1, 8, r["count"], " options")
        rf.addRow("Per language", self.count_spin)
        self.only_sentences = QCheckBox("Only for sentences (skip single words)")
        self.only_sentences.setChecked(r["only_for_sentences"])
        rf.addRow("", self.only_sentences)
        self.models = QPlainTextEdit("\n".join(r["models"]))
        self.models.setObjectName("models")
        self.models.setFixedHeight(80)
        rf.addRow("Models (in order)", self.models)
        test = QPushButton("Test rewrites")
        test.setObjectName("secondary")
        test.clicked.connect(self._test_rewrites)
        self.test_status = QLabel("")
        self.test_status.setObjectName("hint")
        self.test_status.setWordWrap(True)
        tr = QHBoxLayout()
        tr.addWidget(test)
        tr.addWidget(self.test_status, 1)
        rf.addRow("", tr)
        tabs.addTab(rw, "Rewrites")

        # ---- buttons ----
        buttons = QHBoxLayout()
        open_file = QPushButton("Open config file")
        open_file.setObjectName("secondary")
        open_file.clicked.connect(lambda: os.startfile(config.ensure_file()))
        more = QLabel("Per-app copy keys live in the file.")
        more.setObjectName("hint")
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(open_file)
        buttons.addWidget(more)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def show_tab(self, name: str) -> None:
        """Open on a given tab (e.g. "Rewrites" from the popup's setup button)."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == name:
                self.tabs.setCurrentIndex(i)
                return

    # --- helpers ---
    @staticmethod
    def _spin(lo: int, hi: int, value: int, suffix: str) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        s.setSuffix(suffix)
        return s

    @staticmethod
    def _lang_combo(current: str) -> QComboBox:
        c = QComboBox()
        c.setEditable(True)
        for code in L.NAMES:
            c.addItem(f"{L.name(code)} ({code})", code)
        i = c.findData(current)
        if i >= 0:
            c.setCurrentIndex(i)
        else:
            c.setEditText(current)
        return c

    @staticmethod
    def _combo_code(c: QComboBox) -> str:
        i = c.findText(c.currentText())
        return (c.itemData(i) if i >= 0 else c.currentText()).strip().lower()

    def _paint_accent(self) -> None:
        swatch = QPixmap(16, 16)
        swatch.fill(Qt.transparent)
        p = QPainter(swatch)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._accent))
        p.drawRoundedRect(0, 0, 16, 16, 4, 4)
        p.end()
        self.accent_btn.setIcon(QIcon(swatch))
        self.accent_btn.setText(f" {self._accent}   Change…")

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(QColor(self._accent), self, "Accent color")
        if color.isValid():
            self._accent = color.name().upper()
            self._paint_accent()

    def _hotkey_spec(self) -> str | None:
        return sequence_to_spec(self.hotkey.keySequence())

    def _set_status(self, label: QLabel, text: str, good: bool | None) -> None:
        label.setObjectName({True: "ok", False: "bad", None: "hint"}[good])
        label.setText(text)
        label.style().unpolish(label)
        label.style().polish(label)

    def _check_hotkey(self, *_):
        spec = self._hotkey_spec()
        if not spec:
            self._set_status(self.hotkey_status, "Press a combination like Ctrl+Alt+D.", None)
            return False
        try:
            combo = parse_combo(spec, for_hotkey=True)
        except ValueError as e:
            self._set_status(self.hotkey_status, str(e), False)
            return False
        ok, msg = self.app.hotkeys.probe(spec)
        conflict = known_conflict(combo)
        if ok and conflict:
            self._set_status(self.hotkey_status, f"{msg} Heads-up: {conflict}", None)
        else:
            self._set_status(self.hotkey_status, msg, ok)
        return ok

    def _refresh_key_status(self) -> None:
        if credentials.read_stored_key():
            self._set_status(self.key_status, "Key saved in Windows Credential Manager.", True)
        elif os.environ.get(self.app.cfg["rewrites"]["api_key_env"]):
            self._set_status(self.key_status, f"Using the {self.app.cfg['rewrites']['api_key_env']} environment variable.", True)
        else:
            self.key_status.setText('No key yet. Get a free one at <a href="https://openrouter.ai/keys">openrouter.ai/keys</a> (no card needed).')
            self.key_status.setObjectName("hint")

    def _save_key(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            return
        if credentials.save_key(key):
            self.key_edit.clear()
            self._refresh_key_status()
        else:
            self._set_status(self.key_status, "Windows didn't let VerbaLogic store the key.", False)

    def _remove_key(self) -> None:
        credentials.delete_key()
        self._refresh_key_status()

    def _test_rewrites(self) -> None:
        self._set_status(self.test_status, "Asking the AI…", None)
        models = [m.strip() for m in self.models.toPlainText().splitlines() if m.strip()]
        job = _Job(lambda: self.app.test_rewrites(models))
        job.signals.done.connect(self._test_done)
        self._jobs.append(job)
        QThreadPool.globalInstance().start(job)

    def _test_done(self, result) -> None:
        if isinstance(result, Exception):
            self._set_status(self.test_status, str(result), False)
        else:
            model, sample = result
            self._set_status(self.test_status, f"Works with {model.split('/')[-1]}: “{sample}”", True)

    def _save(self) -> None:
        spec = self._hotkey_spec()
        if spec and spec != self.app.cfg["hotkey"]["open"] and not self._check_hotkey():
            return
        split = lambda s: [c.strip().lower() for c in s.split(",") if c.strip()]  # noqa: E731
        primary, secondary = self._combo_code(self.primary), self._combo_code(self.secondary)
        if L.same(primary, secondary):
            self.primary.setFocus()
            return
        models = [m.strip() for m in self.models.toPlainText().splitlines() if m.strip()]
        changes = {
            "hotkey": {"open": spec or self.app.cfg["hotkey"]["open"]},
            "languages": {
                "primary": primary, "secondary": secondary,
                "available_extra": split(self.available.text()), "extra": split(self.extra_on.text()),
            },
            "capture": {"auto_copy": self.auto_copy.isChecked()},
            "ui": {
                "theme": self.theme.currentText(), "accent": self._accent,
                "width": self.width_spin.value(), "height": self.height_spin.value(),
                "font_size": self.font_spin.value(), "max_synonyms": self.syn_spin.value(),
                "close_on_focus_loss": self.close_blur.isChecked(),
            },
            "rewrites": {
                "enabled": self.rw_on.isChecked(), "spanish_variant": self.variant.currentData(),
                "count": self.count_spin.value(), "only_for_sentences": self.only_sentences.isChecked(),
                "models": models or self.app.cfg["rewrites"]["models"],
            },
            "startup": {"start_with_windows": self.startup.isChecked()},
        }
        config.save(changes)
        self.app.reload_config()
        self.accept()
