"""Building blocks for the popup: flow layout, chips, clickable labels and a language column."""
from __future__ import annotations

import html
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import languages as L
from .. import win32

ICON_COPY = ""
ICON_PIN = ""
ICON_SETTINGS = ""
ICON_CLOSE = ""
ICON_SPEAK = ""      # Segoe Fluent Icons: Volume
ICON_STAR = ""       # FavoriteStar
ICON_STAR_ON = ""    # FavoriteStarFill
ICON_HISTORY = ""    # History


def caps_label(text: str, name: str) -> QLabel:
    """A small spaced-capitals label. Kerning off: at this size it made "OT" collide."""
    lab = QLabel(text)
    lab.setObjectName(name)
    font = lab.font()
    font.setKerning(False)
    lab.setFont(font)
    return lab


def icon_button(glyph: str, tip: str, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setObjectName("icon")
    b.setText(glyph)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    return b


def fade_in(widget: QWidget, start: float = 0.4, ms: int = 150) -> None:
    """A short fade so it's clear what changed. The effect is removed at the end: while a
    QGraphicsEffect is on, the whole column is re-rendered offscreen, which slows scrolling."""
    if not win32.animations_enabled():
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.graphicsEffect() is effect and widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)


class Skeleton(QWidget):
    """Grey placeholder bars shown while results load, so the layout doesn't jump.
    chips: a row of chip-sized bars (px widths). lines: text lines as fractions of the width."""

    def __init__(self, chips: tuple[int, ...] = (), lines: tuple[float, ...] = (), height: int = 12):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(8)
        if chips:
            row = QHBoxLayout()
            row.setSpacing(6)
            for w in chips:
                row.addWidget(self._bar(height, w))
            row.addStretch(1)
            v.addLayout(row)
        for frac in lines:
            row = QHBoxLayout()
            row.setSpacing(0)
            row.addWidget(self._bar(height), int(frac * 100))
            row.addStretch(100 - int(frac * 100))
            v.addLayout(row)

    @staticmethod
    def _bar(height: int, width: int = 0) -> QFrame:
        bar = QFrame()
        bar.setObjectName("skeleton")
        bar.setFixedHeight(height)
        if width:
            bar.setFixedWidth(width)
        return bar


class FlowLayout(QLayout):
    """Wraps children onto new lines, like words in a paragraph."""

    def __init__(self, parent=None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), dry=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, dry=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _layout(self, rect: QRect, dry: bool) -> int:
        x, y, line_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_h > 0:
                x, y, line_h = rect.x(), y + line_h + self._spacing, 0
            if not dry:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


class Chip(QPushButton):
    double_clicked = Signal(str)

    def __init__(self, text: str, kind: str = "", tip: str = ""):
        super().__init__(text)
        self.setObjectName("chip")
        if kind:
            self.setProperty("kind", kind)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(tip or "Click to copy · double-click to look it up")

    def mouseDoubleClickEvent(self, e):  # noqa: N802
        self.double_clicked.emit(self.text())
        super().mouseDoubleClickEvent(e)


class ClickLabel(QLabel):
    clicked = Signal(str)

    def __init__(self, text: str, name: str = "rewriteText"):
        super().__init__(text)
        self.setObjectName(name)
        self.setWordWrap(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to copy")
        self._value = text

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._value)
        super().mousePressEvent(e)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class Section(QWidget):
    def __init__(self, title: str):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 8, 0, 0)  # here, not as QSS padding: that shifted the title right
        v.setSpacing(8)
        self.title = caps_label(title.upper(), "sectionTitle")
        v.addWidget(self.title)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        v.addLayout(self.body)
        self.hide()

    def clear(self) -> None:
        clear_layout(self.body)
        self.hide()

    def loading(self, placeholder: QWidget) -> None:
        self.clear()
        self.body.addWidget(placeholder)
        self.show()

    def message(self, text: str, name: str = "muted") -> None:
        self.clear()
        lab = QLabel(text)
        lab.setObjectName(name)
        lab.setWordWrap(True)
        self.body.addWidget(lab)
        self.show()


class MeaningNav(QWidget):
    """‹  Meaning 2 of 5 ▾  › — steps through a word's meanings; the label opens a list."""
    moved = Signal(int)  # -1 / +1
    list_requested = Signal()

    def __init__(self):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(6)
        self.prev = self._arrow("‹", "Previous meaning (Alt+←)", -1)
        self.label = QToolButton()
        self.label.setObjectName("navLabel")
        self.label.setToolTip("See all meanings (Alt+↓)")
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.setFocusPolicy(Qt.NoFocus)
        self.label.clicked.connect(self.list_requested)
        self.next = self._arrow("›", "Next meaning (Alt+→)", 1)
        h.addWidget(self.prev)
        h.addWidget(self.label)
        h.addWidget(self.next)
        h.addStretch(1)
        self.hide()

    def _arrow(self, glyph: str, tip: str, step: int) -> QToolButton:
        b = QToolButton()
        b.setObjectName("navArrow")
        b.setText(glyph)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(lambda: self.moved.emit(step))
        return b

    def set_state(self, index: int, count: int) -> None:
        self.label.setText(f"Meaning {index + 1} of {count}  ▾")
        self.prev.setEnabled(index > 0)
        self.next.setEnabled(index < count - 1)


class LanguageColumn(QFrame):
    """One language: main translation, other translations, synonyms, examples, rewrites."""

    def __init__(self, lang: str, ui: dict, on_copy: Callable[[str], None], on_lookup: Callable[[str], None],
                 on_speak: Callable[[str, str], None] | None = None):
        super().__init__()
        self.lang = lang
        self.ui = ui
        self._copy = on_copy
        self._lookup = on_lookup
        self._word_mode = False
        self.setObjectName("column")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 8)  # the popup sets the sides: no box, just a divider between columns
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.name = caps_label(L.name(lang).upper(), "langName")
        self.badge = QLabel("original")
        self.badge.setObjectName("badge")
        self.badge.hide()
        self.speak_btn = icon_button(ICON_SPEAK, "Listen (Ctrl+Shift+number)")
        self.speak_btn.hide()
        if on_speak:
            self.speak_btn.clicked.connect(lambda: self.main_text() and on_speak(self.main_text(), self.lang))
        self.copy_btn = icon_button(ICON_COPY, "Copy (Ctrl+number)")
        self.copy_btn.clicked.connect(lambda: self._copy(self.main_text()))
        head.addWidget(self.name)
        head.addWidget(self.badge)
        head.addStretch(1)
        head.addWidget(self.speak_btn)
        head.addWidget(self.copy_btn)
        v.addLayout(head)

        self.main = QLabel("")
        self.main.setObjectName("main")
        self.main.setWordWrap(True)
        self.main.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.main)
        self.main_skeleton = Skeleton(lines=(0.55,), height=22)
        self.main_skeleton.hide()
        v.addWidget(self.main_skeleton)

        # Like a printed dictionary: the part of speech in small italics right under the headword.
        self.head_pos = QLabel("")
        self.head_pos.setObjectName("headPos")
        self.head_pos.hide()
        v.addWidget(self.head_pos)

        self.nav = MeaningNav()
        v.addWidget(self.nav)

        self.definition = QLabel("")
        self.definition.setObjectName("definition")
        self.definition.setWordWrap(True)
        self.definition.hide()
        v.addWidget(self.definition)

        self.alts = Section("Also translates as")
        self.syns = Section("Synonyms")
        self.examples = Section("In real use")
        self.rewrites = Section("Other ways to say it")
        for s in (self.alts, self.syns, self.examples, self.rewrites):
            v.addWidget(s)
        v.addStretch(1)
        self._senses: list[dict] = []
        self._sense_syns: dict[int, dict] = {}   # meaning index -> synonyms data (target columns)
        self._sense_i = -1
        self._general: dict = {}  # the word's overall details, before picking a meaning

    def main_text(self) -> str:
        return self.main.property("value") or ""

    def can_speak(self) -> bool:
        return self._word_mode and bool(self.main_text())

    def current_meaning(self) -> tuple[str, str]:
        """(definition, example) of what's on screen: the chosen meaning, else the word's."""
        if 0 <= self._sense_i < len(self._senses):
            s = self._senses[self._sense_i]
            return s["gloss"], s["example"]
        examples = self._general.get("examples") or []
        return self._general.get("definition", ""), (examples[0] if examples else "")

    # --- state ---
    def reset(self, word_mode: bool, rewrites_on: bool, loading: bool = True) -> None:
        self._word_mode = word_mode
        self._set_main("")
        if loading:
            self.main.hide()
            self.main_skeleton.show()
        self.speak_btn.hide()
        self.badge.hide()
        self.definition.hide()
        self.head_pos.hide()
        self.nav.hide()
        self._senses, self._sense_syns, self._sense_i = [], {}, -1
        self._general: dict = {}
        self.examples.title.show()
        for s in (self.alts, self.syns, self.examples, self.rewrites):
            s.clear()
        if word_mode:
            self.syns.loading(Skeleton(chips=(58, 74, 50, 66, 44)))
        if rewrites_on:
            self.rewrites.loading(Skeleton(lines=(0.9, 0.75, 0.82)))

    def _set_main(self, text: str) -> None:
        self.main_skeleton.hide()
        self.main.show()
        self.main.setText(text)
        self.main.setProperty("value", text)
        self.main.setProperty("word", self._word_mode)  # serif headword for words only
        self.main.style().unpolish(self.main)
        self.main.style().polish(self.main)

    def set_translation(self, text: str, is_original: bool) -> None:
        self._set_main(text)
        self.badge.setVisible(is_original)
        self.speak_btn.setVisible(self._word_mode and bool(text))

    def set_error(self, text: str) -> None:
        self._set_main("")
        self.speak_btn.hide()
        self.head_pos.hide()
        self.syns.clear()
        self.rewrites.clear()
        self.examples.message(text, "error")
        self.examples.title.hide()

    def set_details(self, data: dict) -> None:
        self._senses = data.get("senses") or []
        self._general = data
        if data.get("definition"):
            self.definition.setText(data["definition"])
            self.definition.show()
        alts = [a for a in data.get("alternatives") or [] if a["word"].lower() != self.main_text().lower()]
        if alts:
            self._chips(self.alts, [(None, [a["word"] for a in alts[:8]])], kind="alt",
                        tips={a["word"]: "means: " + ", ".join(a["reverse"][:5]) for a in alts})
        self._show_synonyms(data)
        self._show_examples(data.get("examples") or [])

    def _show_synonyms(self, data: dict) -> None:
        synonyms = data.get("synonyms") or []
        if synonyms:
            budget = self.ui["max_synonyms"]
            groups = []
            for g in synonyms:
                words = [w for w in g["words"] if w.lower() != self.main_text().lower()][:budget]
                budget -= len(words)
                if words:
                    groups.append((g["pos"], words))
                if budget <= 0:
                    break
            self._chips(self.syns, groups)
            source = synonyms[0].get("source")
            self.syns.title.setText("SIMILAR WORDS" if source == "similar"
                                    else "SYNONYMS" + (" · DATAMUSE" if source == "datamuse" else ""))
            self.syns.setToolTip("Other words Google translates the same way" if source == "similar" else "")
        elif data.get("note"):
            self.syns.message(data["note"])
        else:
            self.syns.clear()

    def _show_examples(self, examples: list[str]) -> None:
        examples = examples[: self.ui["max_examples"]]
        self.examples.clear()
        if examples:
            for ex in examples:
                lab = QLabel(f"“{ex}”")
                lab.setObjectName("example")
                lab.setWordWrap(True)
                lab.setTextFormat(Qt.RichText)
                self.examples.body.addWidget(lab)
            self.examples.show()

    # --- meanings ---
    def sense_count(self) -> int:
        return len(self._senses)

    def sense_pos(self, index: int) -> str:
        return self._senses[index]["pos"] if 0 <= index < len(self._senses) else ""

    def sense_gloss(self, index: int) -> str:
        return self._senses[index]["gloss"] if 0 <= index < len(self._senses) else ""

    def is_target(self) -> bool:
        return bool(self._senses) and "word" in self._senses[0]

    def show_sense(self, index: int) -> dict | None:
        """Show one meaning. Returns it if its synonyms still need loading (target columns)."""
        if not 0 <= index < len(self._senses) or index == self._sense_i:
            return None
        self._sense_i = index
        s = self._senses[index]
        self._set_pos(s["pos"])
        self.definition.setText(s["gloss"])
        self.definition.setVisible(bool(s["gloss"]))
        self._show_examples([html.escape(s["example"])] if s["example"] else [])  # plain text; rich label
        if not self.is_target():
            self._show_sense_synonyms(s)
            return None
        self._set_main(s["word"])
        if s["also"]:
            self._chips(self.alts, [(None, s["also"])], kind="alt")
        else:
            self.alts.clear()
        if index in self._sense_syns:
            self.set_sense_synonyms(index, self._sense_syns[index])
            return None
        self.syns.loading(Skeleton(chips=(58, 74, 50, 66)))
        return s

    def _set_pos(self, pos: str) -> None:
        self.head_pos.setText(pos)
        self.head_pos.setVisible(self._word_mode and bool(pos))

    def set_sense_synonyms(self, index: int, data: dict) -> None:
        self._sense_syns[index] = data
        if index == self._sense_i:
            self._show_sense_synonyms(data)

    def _show_sense_synonyms(self, data: dict) -> None:
        """This meaning's synonyms. Without any, fall back to Datamuse's general list for the
        word (it isn't split by meaning anyway), else hide the section."""
        general = self._general.get("synonyms") or []
        if data.get("synonyms") or data.get("note"):
            self._show_synonyms(data)
        elif general and general[0].get("source") == "datamuse":
            self._show_synonyms(self._general)
        else:
            self.syns.clear()  # nothing to show: let the useful parts move up

    def _chips(self, section: Section, groups: list[tuple[str | None, list[str]]], kind: str = "", tips=None) -> None:
        section.clear()
        for pos, words in groups:
            if pos:
                p = QLabel(pos)
                p.setObjectName("pos")
                section.body.addWidget(p)
            holder = QWidget()
            flow = FlowLayout(holder)
            for w in words:
                chip = Chip(w, kind, (tips or {}).get(w, ""))
                chip.clicked.connect(lambda _=False, t=w: self._copy(t))
                chip.double_clicked.connect(self._lookup)
                flow.addWidget(chip)
            section.body.addWidget(holder)
        section.show()

    def show_rewrites_setup(self, on_setup: Callable[[], None]) -> None:
        """No OpenRouter key yet: a short line and a button to Settings instead of an error."""
        self.rewrites.message("Natural rewrites need a free OpenRouter key.")
        b = QPushButton("Set up rewrites")
        b.setObjectName("secondary")
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(on_setup)
        row = QHBoxLayout()
        row.addWidget(b)
        row.addStretch(1)
        self.rewrites.body.addLayout(row)

    def set_rewrites(self, items: list[dict]) -> None:
        self.rewrites.clear()
        if not items:
            return
        for n, it in enumerate(items):
            row = QFrame()
            row.setObjectName("rewrite")
            row.setProperty("first", n == 0)  # hairlines between rows, none above the first
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 8, 8, 8)
            h.setSpacing(10)
            tone = QLabel(it["tone"])
            tone.setObjectName("tone")
            h.addWidget(tone, 0, Qt.AlignTop)
            lines = QVBoxLayout()
            lines.setSpacing(4)
            if it.get("variants"):
                for variant, text in it["variants"].items():
                    line = QHBoxLayout()
                    tag = QLabel("vos" if variant == "vos" else "neutral")
                    tag.setObjectName("variant")
                    lab = ClickLabel(text)
                    lab.clicked.connect(self._copy)
                    line.addWidget(tag, 0, Qt.AlignTop)
                    line.addWidget(lab, 1)
                    lines.addLayout(line)
            else:
                lab = ClickLabel(it["text"])
                lab.clicked.connect(self._copy)
                lines.addWidget(lab)
            h.addLayout(lines, 1)
            self.rewrites.body.addWidget(row)
        self.rewrites.show()
