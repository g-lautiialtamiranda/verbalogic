"""VerbaLogic entry point: tray icon, global hotkey, config watching, wiring."""
from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
import threading
from pathlib import Path

import httpx
from PySide6.QtCore import QFileSystemWatcher, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import config, credentials, startup
from .cache import Cache
from .capture import _OWN_PROCESSES, Capture, grab_selection
from .history import History
from .hotkey import HotkeyError, HotkeyListener
from .keys import KeyCombo, parse_combo
from .lookup import Lookup
from .providers.llm import ChatClient, LLMError
from .rewrites import build_prompt, parse_rewrites
from .ui.icon import make_icon, make_pixmap
from .ui.popup import Popup
from .ui.settings import SettingsDialog
from .ui.theme import stylesheet

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
INSTANCE_KEY = f"VerbaLogic-{os.environ.get('USERNAME', 'user')}"


class VerbaLogicApp(QObject):
    captured = Signal(object)

    def __init__(self, qapp: QApplication, *, with_hotkey: bool = True):
        super().__init__()
        self.qapp = qapp
        self.cfg, warnings = config.load()
        self.http = httpx.Client(
            timeout=httpx.Timeout(8.0, connect=4.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self.cache = Cache(config.app_dir() / "cache.sqlite")
        self.lookup = Lookup(self.http, self.cache, self)
        self.history = History(config.app_dir() / "history.sqlite", self.cfg["history"]["size"])
        self._apply_style()
        self.popup = Popup(self)
        self.settings: SettingsDialog | None = None

        self.tray = QSystemTrayIcon(make_icon(self.cfg["ui"]["accent"]), self)
        self.tray.activated.connect(self._on_tray_activated)
        self._build_tray_menu()
        self.tray.show()

        self.hotkeys = HotkeyListener(self._on_hotkey)
        self.captured.connect(self._on_captured)
        if with_hotkey:
            self.hotkeys.start_and_wait()
            self._register_hotkey()

        self._watcher = QFileSystemWatcher([str(config.ensure_file())], self)
        self._reload_timer = QTimer(self, singleShot=True, interval=300, timeout=self._on_file_changed)
        self._watcher.fileChanged.connect(lambda _: self._reload_timer.start())

        self._sync_startup()
        threading.Thread(target=self._prewarm, daemon=True).start()
        if with_hotkey:  # a real run, not a test: make sure VerbaLogic is in the Start menu
            icon = self._icon_file()
            threading.Thread(target=startup.ensure_menu_shortcut, args=(icon,), daemon=True).start()
        for w in warnings:
            self.notify("Config problem", w, warn=True)
        self._first_run_hint()

    # --- setup helpers ---
    def _icon_file(self) -> Path:
        """The app icon as an .ico for Windows shortcuts (made once, on the UI thread)."""
        path = config.app_dir() / "verbalogic.ico"
        if not path.exists():
            make_pixmap(self.cfg["ui"]["accent"], 256).save(str(path), "ICO")
        return path

    def _apply_style(self) -> None:
        self.qapp.setStyleSheet(stylesheet(self.cfg["ui"]))

    def _prewarm(self) -> None:
        """Open the TLS connections now so the first lookup is fast."""
        try:
            self.http.head("https://clients5.google.com/translate_a/t", timeout=4)
        except httpx.HTTPError:
            pass

    def _first_run_hint(self) -> None:
        flag = config.app_dir() / ".welcomed"
        if not flag.exists():
            flag.write_text("1", encoding="utf-8")
            self.notify("VerbaLogic is running", f"Select text anywhere and press {self._hotkey_label()}.")

    def _hotkey_label(self) -> str:
        return parse_combo(self.cfg["hotkey"]["open"]).pretty()

    def notify(self, title: str, message: str, warn: bool = False) -> None:
        logging.info("%s: %s", title, message)
        icon = QSystemTrayIcon.Warning if warn else QSystemTrayIcon.Information
        self.tray.showMessage(title, message, icon, 6000)

    # --- tray ---
    def _build_tray_menu(self) -> None:
        menu = QMenu()
        self._open_action = QAction(f"Open VerbaLogic ({self._hotkey_label()})", menu)
        self._open_action.triggered.connect(lambda: self.popup.present(""))
        history = QAction("Saved and recent lookups…", menu)
        history.triggered.connect(self._open_history)
        settings = QAction("Settings…", menu)
        settings.triggered.connect(self.open_settings)
        open_file = QAction("Open config file", menu)
        open_file.triggered.connect(lambda: os.startfile(config.ensure_file()))
        self._startup_action = QAction("Start with Windows", menu, checkable=True)
        self._startup_action.setChecked(self.cfg["startup"]["start_with_windows"])
        self._startup_action.toggled.connect(lambda on: config.save({"startup": {"start_with_windows": on}}))
        quit_ = QAction("Quit", menu)
        quit_.triggered.connect(self.quit)
        for a in (self._open_action, history, settings, open_file):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self._startup_action)
        menu.addSeparator()
        menu.addAction(quit_)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(f"VerbaLogic: select text and press {self._hotkey_label()}")

    def _open_history(self) -> None:
        self.popup.present("")
        QTimer.singleShot(0, self.popup.open_history)

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.popup.present("")

    # --- hotkey ---
    def _register_hotkey(self) -> bool:
        try:
            self.hotkeys.set_hotkey(self.cfg["hotkey"]["open"])
            return True
        except (HotkeyError, ValueError) as e:
            self.notify("Shortcut not available", f"{e} Open Settings from the tray icon to choose another.", warn=True)
            return False

    def _on_hotkey(self, combo: KeyCombo) -> None:
        """Runs on the hotkey thread: copy the selection there, then hand over to the UI thread."""
        self.captured.emit(grab_selection(self.cfg, combo))

    def _on_captured(self, cap: Capture) -> None:
        if cap.app in _OWN_PROCESSES and self.popup.isVisible():
            self.popup.hide()  # the shortcut toggles the popup when it already has focus
            return
        note = ""
        if cap.keystroke != "none" and not cap.fresh and cap.text:
            note = "Nothing new was copied; showing what was already on the clipboard."
        self.popup.present(cap.text, note)

    # --- settings / config ---
    def open_settings(self, tab: str | None = None) -> None:
        if self.settings and self.settings.isVisible():
            if tab:
                self.settings.show_tab(tab)
            self.settings.raise_()
            self.settings.activateWindow()
            return
        self.popup.hide()
        self.hotkeys.unregister()  # so the shortcut can be recorded instead of firing
        self.settings = SettingsDialog(self)
        self.settings.setWindowIcon(make_icon(self.cfg["ui"]["accent"]))
        self.settings.finished.connect(lambda _: self._register_hotkey())
        if tab:
            self.settings.show_tab(tab)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _on_file_changed(self) -> None:
        path = str(config.config_path())
        if path not in self._watcher.files() and os.path.exists(path):
            self._watcher.addPath(path)  # editors that replace the file drop the watch
        self.reload_config()

    def reload_config(self) -> None:
        old_hotkey = self.cfg["hotkey"]["open"]
        self.cfg, warnings = config.load()
        self.history.size = self.cfg["history"]["size"]
        self._apply_style()
        self.popup.rebuild()
        self.tray.setIcon(make_icon(self.cfg["ui"]["accent"]))
        self._build_tray_menu()
        dialog_open = self.settings is not None and self.settings.isVisible()
        if self.cfg["hotkey"]["open"] != old_hotkey and not dialog_open and self.hotkeys.is_alive():
            self._register_hotkey()
        self._sync_startup()
        for w in warnings:
            self.notify("Config problem", w, warn=True)

    def _sync_startup(self) -> None:
        want = self.cfg["startup"]["start_with_windows"]
        if want != startup.is_enabled():
            if not startup.set_enabled(want, self._icon_file() if want else None):
                self.notify("Start with Windows", "Couldn't create the startup shortcut.", warn=True)
        self._startup_action.blockSignals(True)
        self._startup_action.setChecked(startup.is_enabled())
        self._startup_action.blockSignals(False)

    def test_rewrites(self, models: list[str]) -> tuple[str, str]:
        rw = self.cfg["rewrites"]
        client = ChatClient(self.http, rw["base_url"], models or rw["models"], credentials.get_key(rw["api_key_env"]), rw["timeout_seconds"])
        text = "I can't make it to the meeting tomorrow"
        data, model = client.complete_json(build_prompt(text, "en", ["es"], 1, rw["spanish_variant"]))
        items = parse_rewrites(data, text, ["es"], 1).get("es") or []
        if not items:
            raise LLMError(f"{model} answered, but not in the expected format.")
        first = items[0]
        return model, first.text or next(iter(first.variants.values()))

    def quit(self) -> None:
        self.hotkeys.stop()
        self.tray.hide()
        self.qapp.quit()


def _setup_logging() -> None:
    log = config.app_dir() / "verbalogic.log"
    if log.exists() and log.stat().st_size > 1_000_000:
        log.unlink()
    logging.basicConfig(
        filename=str(log), level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sys.excepthook = lambda *exc: logging.error("Unhandled error", exc_info=exc)


def _already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"open")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(prog="verbalogic")
    parser.add_argument("--open", action="store_true", help="open the popup right away (the Start menu entry uses this)")
    parser.add_argument("--show", metavar="TEXT", help="open the popup with this text (for testing)")
    parser.add_argument("--screenshot", metavar="PNG", help="with --show: save a screenshot after a few seconds and quit")
    parser.add_argument("--wait", type=float, default=5.0, help="seconds before the screenshot")
    args = parser.parse_args()

    _setup_logging()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VerbaLogic")
    except (AttributeError, OSError):
        pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("VerbaLogic")
    qapp.setQuitOnLastWindowClosed(False)

    dev = args.show is not None
    if not dev and _already_running():
        return
    app = VerbaLogicApp(qapp, with_hotkey=not dev)
    qapp.setWindowIcon(make_icon(app.cfg["ui"]["accent"]))

    if not dev:
        server = QLocalServer(app)
        QLocalServer.removeServer(INSTANCE_KEY)
        server.listen(INSTANCE_KEY)
        server.newConnection.connect(lambda: (server.nextPendingConnection(), app.popup.present("")))
        if args.open:
            QTimer.singleShot(200, lambda: app.popup.present(""))
    else:
        QTimer.singleShot(200, lambda: app.popup.present(args.show))
        if args.screenshot:
            def shoot():
                app.popup.pin.setChecked(True)
                app.popup.grab().save(args.screenshot)
                qapp.quit()
            QTimer.singleShot(int(args.wait * 1000), shoot)
    sys.exit(qapp.exec())
