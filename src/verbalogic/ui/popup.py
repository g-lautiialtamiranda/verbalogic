"""The popup: source box on top, one column per language, status line at the bottom."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPlainTextEdit, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from .. import config, credentials
from .. import languages as L
from .. import win32
from ..lookup import is_word_mode, wants_rewrites
from ..providers import speech
from .widgets import (
    ICON_CLOSE, ICON_HISTORY, ICON_PIN, ICON_SETTINGS, ICON_STAR, ICON_STAR_ON, LanguageColumn, caps_label,
    clear_layout, icon_button,
)

if TYPE_CHECKING:
    from ..app import VerbaLogicApp

SHADOW = 18          # px of soft shadow around the card
SETUP_HINTS = 3      # lookups that show "Set up rewrites" while there's no OpenRouter key
EXTRA_COLUMN_W = 270  # how much wider the popup gets per extra language
MENU_ITEMS = 15       # saved / recent lookups listed in the history menu
_TAGS = re.compile(r"<[^>]+>")


class SourceEdit(QPlainTextEdit):
    def __init__(self, on_submit):
        super().__init__()
        self._submit = on_submit
        self.setObjectName("source")
        self.setPlaceholderText("Select text anywhere and press the shortcut, or type here and press Enter")
        self.setTabChangesFocus(True)

    def keyPressEvent(self, e):  # noqa: N802
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self._submit(self.toPlainText())
            return
        super().keyPressEvent(e)


class Popup(QWidget):
    speech_failed = Signal(str)

    def __init__(self, app: "VerbaLogicApp"):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("VerbaLogic")
        self._gen = 0
        self._columns: dict[str, LanguageColumn] = {}
        self._active_extras: set[str] = set(app.cfg["languages"]["extra"])
        self._drag_from = None
        self._src = ""          # detected source language of the current lookup
        self._sense_i = 0       # meaning shown (0-based)
        self._text = ""         # the text of the current lookup
        self._translations: dict[str, str] = {}
        self._speaker = ThreadPoolExecutor(1, thread_name_prefix="vl-speech")  # one clip at a time
        self.speech_failed.connect(self.flash)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW, SHADOW - 6, SHADOW, SHADOW + 6)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        v = QVBoxLayout(self.card)
        v.setContentsMargins(18, 12, 14, 12)
        v.setSpacing(10)

        # header
        self.header = QWidget()
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        dot = QLabel()
        dot.setObjectName("brandDot")
        brand = caps_label("VERBALOGIC", "brand")
        self.pill = QLabel("")
        self.pill.setObjectName("pill")
        self.pill.hide()
        head.addWidget(dot)
        head.addWidget(brand)
        head.addSpacing(6)
        head.addWidget(self.pill)
        head.addStretch(1)
        self.extras_box = QHBoxLayout()
        self.extras_box.setSpacing(6)
        head.addLayout(self.extras_box)
        head.addSpacing(4)
        self.history_btn = icon_button(ICON_HISTORY, "Saved and recent lookups (Ctrl+H)")
        self.history_btn.clicked.connect(self.open_history)
        self.star = icon_button(ICON_STAR, "Save this word (Ctrl+S)", checkable=True)
        self.star.setEnabled(False)
        self.star.toggled.connect(self._on_star)
        self.pin = icon_button(ICON_PIN, "Keep open when clicking elsewhere", checkable=True)
        settings = icon_button(ICON_SETTINGS, "Settings (Ctrl+,)")
        settings.clicked.connect(self.app.open_settings)
        close = icon_button(ICON_CLOSE, "Close (Esc)")
        close.clicked.connect(self.hide)
        for b in (self.history_btn, self.star, self.pin, settings, close):
            head.addWidget(b)
        v.addWidget(self.header)

        self.source = SourceEdit(self.run_lookup)
        self.source.setFixedHeight(64)
        v.addWidget(self.source)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("body")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("bodyInner")
        self.columns_row = QHBoxLayout(inner)
        self.columns_row.setContentsMargins(0, 0, 4, 0)
        self.columns_row.setSpacing(10)
        self.scroll.setWidget(inner)
        v.addWidget(self.scroll, 1)

        foot = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("footer")
        self.toast = QLabel("")
        self.toast.setObjectName("toast")
        hint = QLabel("Enter translate · Alt+←/→/↓ meanings · Ctrl+1/2/3 copy · Ctrl+S save · Esc close")
        hint.setToolTip("Ctrl+Shift+1/2/3 listen · Ctrl+H saved and recent lookups · Ctrl+, settings")
        hint.setObjectName("footer")
        foot.addWidget(self.status)
        foot.addSpacing(8)
        foot.addWidget(self.toast)
        foot.addStretch(1)
        foot.addWidget(hint)
        v.addLayout(foot)
        self._toast_timer = QTimer(self, singleShot=True, interval=1800, timeout=lambda: self.toast.setText(""))

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.app.open_settings)
        for n in range(1, 5):
            QShortcut(QKeySequence(f"Ctrl+{n}"), self, activated=lambda n=n: self._copy_column(n - 1))
            QShortcut(QKeySequence(f"Ctrl+Shift+{n}"), self, activated=lambda n=n: self._speak_column(n - 1))
        QShortcut(QKeySequence("Ctrl+S"), self, activated=lambda: self.star.isEnabled() and self.star.toggle())
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self.open_history)
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self._step_sense(-1))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self._step_sense(1))
        QShortcut(QKeySequence("Alt+Down"), self, activated=self._open_meanings)

        lk = app.lookup
        lk.detected.connect(self._on_detected)
        lk.translated.connect(self._on_translated)
        lk.details.connect(self._on_details)
        lk.rewrites_ready.connect(self._on_rewrites)
        lk.rewrites_failed.connect(self._on_rewrites_failed)
        lk.failed.connect(self._on_failed)
        lk.timing.connect(self._on_timing)
        lk.sense_synonyms_ready.connect(self._on_sense_synonyms)
        self.rebuild()

    # --- config-driven parts ---
    def rebuild(self) -> None:
        """Re-create extras toggles and columns (after a config change)."""
        cfg = self.app.cfg
        self._active_extras &= set(cfg["languages"]["available_extra"]) | set(cfg["languages"]["extra"])
        clear_layout(self.extras_box)
        for code in cfg["languages"]["available_extra"]:
            if L.same(code, cfg["languages"]["primary"]) or L.same(code, cfg["languages"]["secondary"]):
                continue
            b = QToolButton()
            b.setObjectName("toggle")
            b.setText(("+ " if code not in self._active_extras else "") + L.short(code))
            b.setCheckable(True)
            b.setChecked(code in self._active_extras)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(f"Show {L.name(code)}")
            b.toggled.connect(lambda on, c=code, btn=b: self._toggle_extra(c, on, btn))
            self.extras_box.addWidget(b)
        self._ensure_columns()

    def languages(self) -> list[str]:
        lg = self.app.cfg["languages"]
        extras = [c for c in lg["available_extra"] + lg["extra"] if c in self._active_extras]
        return list(dict.fromkeys([lg["primary"], lg["secondary"], *extras]))

    def _ensure_columns(self) -> None:
        langs = self.languages()
        if list(self._columns) == langs:
            return
        clear_layout(self.columns_row)
        self._columns = {}
        for lang in langs:
            col = LanguageColumn(lang, self.app.cfg["ui"], self.copy_text, self.lookup_word, self.speak)
            col.nav.moved.connect(self._step_sense)
            col.nav.list_requested.connect(self._open_meanings)
            self._columns[lang] = col
            self.columns_row.addWidget(col, 1)
        self._resize()

    def _toggle_extra(self, code: str, on: bool, btn: QToolButton) -> None:
        (self._active_extras.add if on else self._active_extras.discard)(code)
        btn.setText(("" if on else "+ ") + L.short(code))
        self._ensure_columns()
        text = self.source.toPlainText().strip()
        if text:
            self.run_lookup(text)

    def _resize(self) -> None:
        ui = self.app.cfg["ui"]
        extra = max(0, len(self._columns) - 2)
        w = ui["width"] + extra * EXTRA_COLUMN_W + 2 * SHADOW
        h = ui["height"] + 2 * SHADOW
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        w, h = min(w, geo.width() - 20), min(h, geo.height() - 20)
        self.resize(w, h)

    def _place(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self._resize()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + int((geo.height() - self.height()) * 0.4)
        self.move(x, y)

    # --- showing ---
    def present(self, text: str, note: str = "") -> None:
        self._ensure_columns()
        self.source.setPlainText(text)
        if not self.isVisible():
            self._place()
        self.show()
        self.raise_()
        self.activateWindow()
        win32.SetForegroundWindow(int(self.winId()))
        self.source.setFocus()
        self.source.selectAll()
        if text:
            self.run_lookup(text)
            if note:
                self.flash(note)
        else:
            self._gen = 0
            self._text = ""
            self._set_star(False, enabled=False)
            self.pill.hide()
            for col in self._columns.values():
                col.reset(False, False)
            self.status.setText(note or "Nothing selected. Type or paste text above.")

    def run_lookup(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._ensure_columns()
        cfg = self.app.cfg
        word = is_word_mode(text)
        rewrites_on = wants_rewrites(cfg, text)
        langs = list(self._columns)
        self._src, self._sense_i = "", 0
        self._text, self._translations = text, {}
        self._set_star(self.app.history.is_starred(text))
        for i, col in enumerate(self._columns.values()):
            col.reset(word, rewrites_on and i < 2)
        if not rewrites_on and cfg["rewrites"]["enabled"] and self._take_setup_hint():
            next(iter(self._columns.values())).show_rewrites_setup(lambda: self.app.open_settings("Rewrites"))
        self.pill.setText("Detecting…")
        self.pill.show()
        self.status.setText("Translating…")
        self.scroll.verticalScrollBar().setValue(0)
        self._gen = self.app.lookup.start(text, cfg, langs)

    def _take_setup_hint(self) -> bool:
        """True for the first few lookups without a key (counted across restarts), then never."""
        if credentials.get_key(self.app.cfg["rewrites"]["api_key_env"]):
            return False
        flag = config.app_dir() / ".rewrites_hint"
        try:
            shown = int(flag.read_text(encoding="utf-8") or 0)
        except (OSError, ValueError):
            shown = 0
        if shown >= SETUP_HINTS:
            return False
        try:
            flag.write_text(str(shown + 1), encoding="utf-8")
        except OSError:
            pass
        return True

    def lookup_word(self, word: str) -> None:
        self.source.setPlainText(word)
        self.run_lookup(word)

    def copy_text(self, text: str) -> None:
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.flash(f"Copied “{text if len(text) < 40 else text[:37] + '…'}”")

    def flash(self, text: str) -> None:
        self.toast.setText(text)
        self._toast_timer.start()

    def _copy_column(self, index: int) -> None:
        cols = list(self._columns.values())
        if index < len(cols):
            self.copy_text(cols[index].main_text())

    # --- pronunciation ---
    def speak(self, text: str, lang: str) -> None:
        self._speaker.submit(self._speak, text, lang)

    def _speak(self, text: str, lang: str) -> None:
        """Worker thread: download (once) and play; failures come back as a toast."""
        try:
            speech.play(speech.fetch(self.app.http, text, lang, config.app_dir() / "tts"))
        except speech.SpeechError as e:
            self.speech_failed.emit(str(e))
        except Exception:  # noqa: BLE001 - never kill the worker
            self.speech_failed.emit("Couldn't play the pronunciation.")

    def _speak_column(self, index: int) -> None:
        cols = list(self._columns.values())
        if index < len(cols) and cols[index].can_speak():
            self.speak(cols[index].main_text(), cols[index].lang)

    # --- saved words and history ---
    def _set_star(self, on: bool, enabled: bool = True) -> None:
        self.star.blockSignals(True)
        self.star.setChecked(on)
        self.star.blockSignals(False)
        self.star.setText(ICON_STAR_ON if on else ICON_STAR)
        self.star.setEnabled(enabled)

    def _on_star(self, on: bool) -> None:
        if not self._text:
            return
        gloss, example = self._nav_column().current_meaning() if self._columns else ("", "")
        self.app.history.set_star(self._text, on, self._src, self._translations, gloss, _TAGS.sub("", example))
        self._set_star(on)
        short = self._text if len(self._text) < 30 else self._text[:27] + "…"
        self.flash(f"Saved “{short}”" if on else f"Removed “{short}” from saved")

    def open_history(self) -> None:
        """Saved words, then recent lookups. Picking one looks it up again (instant: it's cached)."""
        h = self.app.history
        saved = h.starred(MENU_ITEMS)
        recent = [e for e in h.recent(MENU_ITEMS + len(saved)) if not e.starred][:MENU_ITEMS]
        menu = QMenu(self)
        menu.setObjectName("history")
        for title, entries in (("SAVED", saved), ("RECENT", recent)):
            if not entries:
                continue
            menu.addAction(title).setEnabled(False)
            for e in entries:
                text = " ".join(e.text.split())
                text = text if len(text) <= 40 else text[:37].rstrip() + "…"
                tr = " ".join(e.translation().split())
                tr = tr if len(tr) <= 30 else tr[:27].rstrip() + "…"
                act = menu.addAction(f"{text}   →  {tr}" if tr else text)
                if e.gloss:
                    act.setToolTip(e.gloss)
                act.triggered.connect(lambda _=False, t=e.text: self.lookup_word(t))
        if not saved and not recent:
            menu.addAction("Nothing here yet. Your lookups will show up here.").setEnabled(False)
        elif recent:
            menu.addSeparator()
            menu.addAction("Clear recent lookups", self._clear_recent)
        menu.setToolTipsVisible(True)
        btn = self.history_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomRight()) - QPoint(menu.sizeHint().width(), 0))

    def _clear_recent(self) -> None:
        self.app.history.clear_recent()
        self.flash("Recent lookups cleared. Saved words were kept.")

    # --- lookup signals ---
    def _on_detected(self, gen: int, src: str) -> None:
        if gen == self._gen:
            self._src = src
            self.pill.setText(f"{L.name(src)} detected")

    def _on_translated(self, gen: int, lang: str, text: str, original: bool) -> None:
        if gen == self._gen and lang in self._columns:
            self._columns[lang].set_translation(text, original)
            self._translations[lang] = text

    def _on_details(self, gen: int, lang: str, data: dict) -> None:
        if gen == self._gen and lang in self._columns:
            col = self._columns[lang]
            col.set_details(data)
            if col.sense_count():
                self._show_sense(col)
                self._update_nav()

    # --- meanings ---
    def _sense_count(self) -> int:
        return max((c.sense_count() for c in self._columns.values()), default=0)

    def _nav_column(self):
        """The arrows live in the original word's column (or the first one if it has none)."""
        return next((c for lang, c in self._columns.items() if L.same(lang, self._src)), next(iter(self._columns.values())))

    def _update_nav(self) -> None:
        count = self._sense_count()
        host = self._nav_column()
        for col in self._columns.values():
            show = col is host and count >= 2
            col.nav.setVisible(show)
            if show:
                pos = next((c.sense_pos(self._sense_i) for c in self._columns.values() if c.sense_count()), "")
                col.nav.set_state(self._sense_i, count, pos)

    def _show_sense(self, col) -> None:
        sense = col.show_sense(self._sense_i)
        if sense:
            self.app.lookup.sense_synonyms(self._gen, col.lang, self._sense_i, sense, self._src)

    def _step_sense(self, step: int) -> None:
        self._go_sense(self._sense_i + step)

    def _go_sense(self, index: int) -> None:
        index = max(0, min(index, self._sense_count() - 1))
        if index == self._sense_i or self._sense_count() < 2:
            return
        self._sense_i = index
        for col in self._columns.values():
            self._show_sense(col)
        self._update_nav()

    def _open_meanings(self) -> None:
        """A list of every meaning (part of speech + start of the definition) to jump to."""
        count = self._sense_count()
        host = self._nav_column()
        if count < 2 or not host.nav.isVisible():
            return
        source = host if host.sense_count() else next(c for c in self._columns.values() if c.sense_count())
        menu = QMenu(self)
        menu.setObjectName("meanings")
        for i in range(count):
            gloss = source.sense_gloss(i)
            gloss = gloss if len(gloss) <= 60 else gloss[:57].rstrip() + "…"
            pos = source.sense_pos(i)
            act = menu.addAction(f"{i + 1}  ·  " + (f"{pos} · " if pos else "") + gloss)
            act.setCheckable(True)
            act.setChecked(i == self._sense_i)
            act.triggered.connect(lambda _=False, i=i: self._go_sense(i))
        label = host.nav.label
        menu.exec(label.mapToGlobal(label.rect().bottomLeft()))

    def _on_sense_synonyms(self, gen: int, lang: str, index: int, data: dict) -> None:
        if gen == self._gen and lang in self._columns:
            self._columns[lang].set_sense_synonyms(index, data)

    def _on_rewrites(self, gen: int, items: dict, model: str) -> None:
        if gen != self._gen:
            return
        for lang, col in self._columns.items():
            if lang in items:
                col.set_rewrites(items[lang])
        self.status.setText(self.status.text() + f" · rewrites by {model.split('/')[-1].replace(':free', '')}")

    def _on_rewrites_failed(self, gen: int, message: str) -> None:
        if gen != self._gen:
            return
        cols = list(self._columns.values())
        for i, col in enumerate(cols[:2]):
            if i == 0:
                col.rewrites.message(message)
            else:
                col.rewrites.clear()

    def _on_failed(self, gen: int, message: str) -> None:
        if gen != self._gen:
            return
        self.pill.hide()
        for col in self._columns.values():
            col.set_error(message)
        self.status.setText("")

    def _on_timing(self, gen: int, ms: int) -> None:
        if gen == self._gen:
            self.status.setText(f"Translated in {ms} ms")
            if self.app.cfg["history"]["enabled"]:
                self.app.history.add(self._text, self._src, self._translations)

    # --- window behaviour ---
    def event(self, e):
        if e.type() == QEvent.WindowDeactivate and self.app.cfg["ui"]["close_on_focus_loss"] and not self.pin.isChecked():
            QTimer.singleShot(150, self._hide_if_inactive)
        return super().event(e)

    def _hide_if_inactive(self) -> None:
        if QApplication.activePopupWidget():  # our meanings list is open
            return
        if not self.isActiveWindow() and not self.pin.isChecked():
            self.hide()

    def mousePressEvent(self, e):  # noqa: N802 - drag the popup by its header
        if e.button() == Qt.LeftButton and self.header.geometry().contains(self.card.mapFrom(self, e.position().toPoint())):
            handle = self.windowHandle()
            if handle and handle.startSystemMove():
                return
        super().mousePressEvent(e)

    def paintEvent(self, _):  # noqa: N802 - soft shadow without QGraphicsEffect (keeps scrolling fast)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.card.geometry())
        p.setPen(Qt.NoPen)
        for i in range(1, SHADOW):
            alpha = int(10 * (1 - i / SHADOW) ** 2)
            if not alpha:
                break
            p.setBrush(QColor(0, 0, 0, alpha))
            path = QPainterPath()
            path.addRoundedRect(rect.adjusted(-i, -i + 6, i, i + 6), 16 + i, 16 + i)
            p.drawPath(path)
