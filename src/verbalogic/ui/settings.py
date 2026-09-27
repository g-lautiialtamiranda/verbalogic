"""Settings window, laid out like Windows 11 Settings: pages in a sidebar, grouped rows with a
short description each, and a live preview of the popup under Appearance.
Writes to config.toml (keeping comments); the app reloads from the file."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, Qt, QThreadPool, QRunnable, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QFrame, QHBoxLayout, QKeySequenceEdit, QLabel,
    QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import __version__, config, credentials
from .. import languages as L
from ..keys import known_conflict, parse_combo
from .icon import mark_pixmap
from .theme import ACCENTS, palette, stylesheet
from .widgets import Chip, MeaningNav, caps_label

if TYPE_CHECKING:
    from ..app import VerbaLogicApp

REPO = "https://github.com/g-lautiialtamiranda/verbalogic"
PAGES = ("General", "Languages", "Appearance", "Rewrites", "History", "About")
THEMES = (("Same as Windows", "system"), ("Light", "light"), ("Dark", "dark"), ("Paper (warm off-white)", "paper"))

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


def _label(text: str, name: str, wrap: bool = True) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class Preview(QFrame):
    """A small static popup that restyles itself with the settings being edited."""

    def __init__(self):
        super().__init__()
        self.setObjectName("previewBox")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 16)
        v.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.mark = QLabel()
        self.mark.setObjectName("brandMark")
        head.addWidget(self.mark)
        head.addWidget(caps_label("VERBALOGIC", "brand"))
        head.addStretch(1)
        toggle = QToolButton()
        toggle.setObjectName("toggle")
        toggle.setText("PT")
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setFocusPolicy(Qt.NoFocus)
        head.addWidget(toggle)
        v.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(0)
        for i, (lang, word, pos, gloss, title, chips, kind) in enumerate((
            ("ENGLISH", "bank", "noun", "the land alongside a river or lake.", "SYNONYMS", ("shore", "edge", "margin"), ""),
            ("ESPAÑOL", "orilla", "noun", "el terreno al lado de un río o lago.", "ALSO TRANSLATES AS", ("banco", "ribera"), "alt"),
        )):
            if i:
                divider = QFrame()
                divider.setObjectName("divider")
                row.addWidget(divider)
            col = QVBoxLayout()
            col.setContentsMargins(0 if i == 0 else 16, 4, 0 if i else 16, 0)
            col.setSpacing(6)
            col.addWidget(caps_label(lang, "langName"))
            main = QLabel(word)
            main.setObjectName("main")
            main.setProperty("word", True)
            col.addWidget(main)
            col.addWidget(_label(pos, "headPos"))
            if i == 0:
                nav = MeaningNav()
                nav.set_state(0, 8)
                nav.show()
                col.addWidget(nav)
            col.addWidget(_label(gloss, "definition"))
            col.addWidget(caps_label(title, "sectionTitle"))
            chip_row = QHBoxLayout()
            chip_row.setSpacing(6)
            for c in chips:
                chip_row.addWidget(Chip(c, kind))
            chip_row.addStretch(1)
            col.addLayout(chip_row)
            col.addStretch(1)
            row.addLayout(col, 1)
        v.addLayout(row)

    def restyle(self, ui: dict) -> None:
        self.setStyleSheet(stylesheet(ui) + "\n#previewBox { background: transparent; }")
        self.mark.setPixmap(mark_pixmap(palette(ui)["accent"], 18, self.devicePixelRatioF()))


class SettingsDialog(QDialog):
    def __init__(self, app: "VerbaLogicApp"):
        super().__init__(None, Qt.Window | Qt.WindowCloseButtonHint)
        self.app = app
        self.setObjectName("settings")
        self.setWindowTitle("VerbaLogic settings")
        self.setMinimumSize(780, 600)
        cfg = app.cfg
        self._accent = cfg["ui"]["accent"]
        self._jobs: list[_Job] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 16, 20, 16)
        root.setSpacing(16)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(180)
        self.nav.addItems(PAGES)
        root.addWidget(self.nav)

        right = QVBoxLayout()
        right.setSpacing(12)
        self.page_title = _label("", "pageTitle", wrap=False)
        right.addWidget(self.page_title)
        self.stack = QStackedWidget()
        for name in PAGES:
            scroll = QScrollArea()
            scroll.setObjectName("page")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            body = QWidget()
            body.setObjectName("pageBody")
            layout = QVBoxLayout(body)
            layout.setContentsMargins(0, 0, 8, 8)
            layout.setSpacing(16)
            getattr(self, f"_page_{name.lower()}")(layout)
            layout.addStretch(1)
            scroll.setWidget(body)
            self.stack.addWidget(scroll)
        right.addWidget(self.stack, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        right.addLayout(buttons)
        root.addLayout(right, 1)

        self.nav.currentRowChanged.connect(self._show_page)
        self.nav.setCurrentRow(0)
        self._refresh_preview()

    # --- layout helpers ---
    @staticmethod
    def _group(layout: QVBoxLayout, title: str, *rows: QWidget) -> None:
        """A titled card of rows with hairlines between them."""
        if title:
            layout.addWidget(_label(title, "groupTitle", wrap=False))
        group = QFrame()
        group.setObjectName("group")
        v = QVBoxLayout(group)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        for i, row in enumerate(rows):
            if i:
                line = QFrame()
                line.setObjectName("rowLine")
                v.addWidget(line)
            v.addWidget(row)
        layout.addWidget(group)

    @staticmethod
    def _row(title: str, desc: str = "", control: QWidget | QHBoxLayout | None = None,
             below: QWidget | None = None) -> QWidget:
        """Title and description on the left, the control on the right, optional extra line below."""
        row = QWidget()
        row.setObjectName("row")
        v = QVBoxLayout(row)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)
        h = QHBoxLayout()
        h.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(_label(title, "rowTitle"))
        if desc:
            text.addWidget(_label(desc, "rowDesc"))
        h.addLayout(text, 1)
        if isinstance(control, QHBoxLayout):
            h.addLayout(control)
        elif control is not None:
            h.addWidget(control, 0, Qt.AlignVCenter)
        v.addLayout(h)
        if below is not None:
            v.addWidget(below)
        return row

    @staticmethod
    def _spin(lo: int, hi: int, value: int, suffix: str) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        s.setSuffix(suffix)
        return s

    @staticmethod
    def _check(on: bool) -> QCheckBox:
        c = QCheckBox()
        c.setChecked(on)
        return c

    @staticmethod
    def _button(text: str, slot: Callable, name: str = "secondary") -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(name)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    # --- pages ---
    def _page_general(self, layout: QVBoxLayout) -> None:
        cfg = self.app.cfg
        self.hotkey = QKeySequenceEdit(QKeySequence(parse_combo(cfg["hotkey"]["open"]).pretty()))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setFixedWidth(170)
        self.hotkey.keySequenceChanged.connect(self._check_hotkey)
        hk = QHBoxLayout()
        hk.addWidget(self.hotkey)
        hk.addWidget(self._button("Check", self._check_hotkey))
        self.hotkey_status = _label("Click the box and press the new shortcut.", "hint")
        self.auto_copy = self._check(cfg["capture"]["auto_copy"])
        self.close_blur = self._check(cfg["ui"]["close_on_focus_loss"])
        self.startup = self._check(cfg["startup"]["start_with_windows"])
        self._group(layout, "Shortcut",
                    self._row("Open VerbaLogic", "Select text anywhere and press this.", hk, self.hotkey_status),
                    self._row("Copy the selection for me", "Sends the app's copy keys when you press the shortcut. "
                              "Off: reads what is already on the clipboard.", self.auto_copy))
        self._group(layout, "Behaviour",
                    self._row("Close when I click somewhere else", "Pin the popup to keep it open.", self.close_blur),
                    self._row("Start with Windows", "The shortcut works after every restart.", self.startup))
        self.syn_spin = self._spin(0, 60, cfg["ui"]["max_synonyms"], "")
        self._group(layout, "Results",
                    self._row("Synonyms to show", "Per column, across all parts of speech.", self.syn_spin))

    def _page_languages(self, layout: QVBoxLayout) -> None:
        lg = self.app.cfg["languages"]
        self.primary = self._lang_combo(lg["primary"])
        self.secondary = self._lang_combo(lg["secondary"])
        self._group(layout, "Columns",
                    self._row("First column", "Always shown.", self.primary),
                    self._row("Second column", "Always shown. Must differ from the first.", self.secondary))
        self.available = QLineEdit(", ".join(lg["available_extra"]))
        self.available.setFixedWidth(220)
        self.extra_on = QLineEdit(", ".join(lg["extra"]))
        self.extra_on.setFixedWidth(220)
        self._group(layout, "Extra languages",
                    self._row("Available", "Codes separated by commas (pt, fr, it, de…). "
                              "Each one gets a + button in the popup.", self.available),
                    self._row("On from the start", "Extra columns shown without pressing +.", self.extra_on))

    def _page_appearance(self, layout: QVBoxLayout) -> None:
        ui = self.app.cfg["ui"]
        self.preview = Preview()
        layout.addWidget(self.preview)

        self.theme = QComboBox()
        for label, value in THEMES:
            self.theme.addItem(label, value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(ui["theme"])))
        self.theme.currentIndexChanged.connect(self._refresh_preview)

        swatches = QHBoxLayout()
        swatches.setSpacing(8)
        self.swatch_group = QButtonGroup(self)
        for name, color in ACCENTS.items():
            b = QToolButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QToolButton#swatch {{ background: {color}; }}")
            b.setProperty("color", color)
            b.clicked.connect(lambda _=False, c=color: self._set_accent(c))
            self.swatch_group.addButton(b)
            swatches.addWidget(b)
        self.accent_btn = self._button("Custom…", self._pick_accent)
        swatches.addSpacing(4)
        swatches.addWidget(self.accent_btn)

        self.font_spin = self._spin(9, 28, ui["font_size"], " px")
        self.font_spin.valueChanged.connect(self._refresh_preview)
        size = QHBoxLayout()
        self.width_spin = self._spin(480, 2400, ui["width"], " px")
        self.height_spin = self._spin(320, 1600, ui["height"], " px")
        size.addWidget(self.width_spin)
        size.addWidget(QLabel("×"))
        size.addWidget(self.height_spin)
        self.backdrop = self._check(ui["backdrop"] == "acrylic")
        self._group(layout, "",
                    self._row("Theme", "Paper is a warm off-white, easy on the eyes for reading.", self.theme),
                    self._row("Accent colour", "Used for selection, focus and the meaning arrows.", swatches),
                    self._row("Translucent background", "The desktop shows through the popup, softly blurred, "
                              "like the Start menu. Windows 11 only.", self.backdrop),
                    self._row("Text size", "", self.font_spin),
                    self._row("Popup size", "Width × height. Extra languages make it wider.", size))
        self._mark_accent()

    def _page_rewrites(self, layout: QVBoxLayout) -> None:
        r = self.app.cfg["rewrites"]
        self.rw_on = self._check(r["enabled"])
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-or-v1-…  (paste your free key)")
        kr = QHBoxLayout()
        kr.addWidget(self.key_edit, 1)
        kr.addWidget(self._button("Save key", self._save_key))
        kr.addWidget(self._button("Remove", self._remove_key))
        key_box = QWidget()
        kb = QVBoxLayout(key_box)
        kb.setContentsMargins(0, 0, 0, 0)
        kb.setSpacing(6)
        kb.addLayout(kr)
        self.key_status = _label("", "hint")
        self.key_status.setOpenExternalLinks(True)
        kb.addWidget(self.key_status)
        self._refresh_key_status()
        self._group(layout, "",
                    self._row("Other ways to say it", "Short, natural rewrites from a free AI model on OpenRouter. "
                              "Free providers may log what you send: don't use it on confidential text.", self.rw_on),
                    self._row("OpenRouter key", "Stored in Windows Credential Manager, never in a file. "
                              "Only free models (ids ending in :free) are ever used, so the key can't spend credits.",
                              None, key_box))

        self.variant = QComboBox()
        self.variant.addItem("Both: vos (Argentina) + neutral", "both")
        self.variant.addItem("Rioplatense (vos)", "rioplatense")
        self.variant.addItem("Neutral (tú)", "neutral")
        self.variant.setCurrentIndex(max(0, self.variant.findData(r["spanish_variant"])))
        self.count_spin = self._spin(1, 8, r["count"], " options")
        self.only_sentences = self._check(r["only_for_sentences"])
        self._group(layout, "Options",
                    self._row("Spanish style", "", self.variant),
                    self._row("Rewrites per language", "", self.count_spin),
                    self._row("Only for sentences", "Skip single words.", self.only_sentences))

        self.models = QPlainTextEdit("\n".join(r["models"]))
        self.models.setObjectName("models")
        self.models.setFixedHeight(80)
        self.test_status = _label("", "hint")
        test_row = QHBoxLayout()
        test_row.addWidget(self._button("Test rewrites", self._test_rewrites))
        test_row.addWidget(self.test_status, 1)
        test_box = QWidget()
        tb = QVBoxLayout(test_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.addWidget(self.models)
        tb.addLayout(test_row)
        self._group(layout, "Models",
                    self._row("Tried in order", "One per line. If none answers, VerbaLogic picks a free model "
                              "OpenRouter lists today.", None, test_box))

    def _page_history(self, layout: QVBoxLayout) -> None:
        h = self.app.cfg["history"]
        self.history_on = self._check(h["enabled"])
        self.history_size = self._spin(10, 5000, h["size"], " lookups")
        self.history_counts = _label("", "rowDesc")
        self._refresh_counts()
        self._group(layout, "",
                    self._row("Keep a history", "Recent lookups and saved words stay only on this PC.", self.history_on),
                    self._row("Recent lookups to keep", "Older ones are removed. Saved words are never removed.",
                              self.history_size),
                    self._row("Clear recent lookups", "Saved words are kept.", self._button("Clear", self._clear_recent),
                              self.history_counts))

    def _page_about(self, layout: QVBoxLayout) -> None:
        links = (f'<a href="{REPO}">Project page</a> · <a href="{REPO}/issues/new/choose">Report a problem or idea</a>'
                 f' · <a href="{REPO}/blob/main/LICENSE">MIT license</a>')
        link_label = _label(links, "rowDesc")
        link_label.setOpenExternalLinks(True)
        self._group(layout, "",
                    self._row(f"VerbaLogic {__version__}", "Select text anywhere, press the shortcut, and get "
                              "translations, synonyms and natural rewrites.", None, link_label),
                    self._row("Config file", "Per-app copy keys and every other setting live here.",
                              self._button("Open", lambda: os.startfile(config.ensure_file()))),
                    self._row("Data folder", "History, cache, pronunciation clips and the log.",
                              self._button("Open", lambda: os.startfile(config.app_dir()))))

    def show_tab(self, name: str) -> None:
        """Open on a given page (e.g. "Rewrites" from the popup's setup button)."""
        if name in PAGES:
            self.nav.setCurrentRow(PAGES.index(name))

    def _show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index])

    # --- helpers ---
    @staticmethod
    def _lang_combo(current: str) -> QComboBox:
        c = QComboBox()
        c.setEditable(True)
        c.setFixedWidth(220)
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

    def _draft_ui(self) -> dict:
        return {**self.app.cfg["ui"], "theme": self.theme.currentData(), "accent": self._accent,
                "font_size": self.font_spin.value()}

    def _refresh_preview(self, *_) -> None:
        self.preview.restyle(self._draft_ui())

    def _set_accent(self, color: str) -> None:
        self._accent = color.upper()
        self._mark_accent()
        self._refresh_preview()

    def _mark_accent(self) -> None:
        """Check the matching preset, or show a custom colour on the Custom… button."""
        preset = False
        for b in self.swatch_group.buttons():
            on = b.property("color").upper() == self._accent.upper()
            b.setChecked(on)
            preset |= on
        if preset:
            self.accent_btn.setIcon(QIcon())
            self.accent_btn.setText("Custom…")
            return
        swatch = QPixmap(16, 16)
        swatch.fill(Qt.transparent)
        p = QPainter(swatch)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._accent))
        p.drawRoundedRect(0, 0, 16, 16, 8, 8)
        p.end()
        self.accent_btn.setIcon(QIcon(swatch))
        self.accent_btn.setText(f" {self._accent}")

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(QColor(self._accent), self, "Accent colour")
        if color.isValid():
            self._set_accent(color.name())

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
            self._set_status(self.key_status, 'No key yet. Get a free one at <a href="https://openrouter.ai/keys">'
                             'openrouter.ai/keys</a> (no card needed).', None)

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

    def _refresh_counts(self) -> None:
        saved, recent = self.app.history.counts()
        plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")  # noqa: E731
        self.history_counts.setText(f"{plural(recent, 'recent lookup')} · {plural(saved, 'saved word')}")

    def _clear_recent(self) -> None:
        self.app.history.clear_recent()
        self._refresh_counts()

    def _save(self) -> None:
        spec = self._hotkey_spec()
        if spec and spec != self.app.cfg["hotkey"]["open"] and not self._check_hotkey():
            self.show_tab("General")
            return
        split = lambda s: [c.strip().lower() for c in s.split(",") if c.strip()]  # noqa: E731
        primary, secondary = self._combo_code(self.primary), self._combo_code(self.secondary)
        if L.same(primary, secondary):
            self.show_tab("Languages")
            self.secondary.setFocus()
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
                "theme": self.theme.currentData(), "accent": self._accent,
                "backdrop": "acrylic" if self.backdrop.isChecked() else "none",
                "width": self.width_spin.value(), "height": self.height_spin.value(),
                "font_size": self.font_spin.value(), "max_synonyms": self.syn_spin.value(),
                "close_on_focus_loss": self.close_blur.isChecked(),
            },
            "rewrites": {
                "enabled": self.rw_on.isChecked(), "spanish_variant": self.variant.currentData(),
                "count": self.count_spin.value(), "only_for_sentences": self.only_sentences.isChecked(),
                "models": models or self.app.cfg["rewrites"]["models"],
            },
            "history": {"enabled": self.history_on.isChecked(), "size": self.history_size.value()},
            "startup": {"start_with_windows": self.startup.isChecked()},
        }
        config.save(changes)
        self.app.reload_config()
        self.accept()
