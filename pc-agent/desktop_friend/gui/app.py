"""Qt application: GUI on the main thread, asyncio server on a background thread."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from ..agent import Agent
from ..config import Config
from ..console import print_pairing
from ..server import serve
from .bridge import QtBridge
from .overlay import CursorOverlay, paint_cursor
from .pairing_window import PairingWindow

log = logging.getLogger(__name__)


def make_icon(color: str) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    paint_cursor(p, QPointF(14, 6), QColor(color), scale=1.85)
    p.end()
    return QIcon(pix)


class ServerThread(threading.Thread):
    def __init__(self, agent: Agent, bridge: QtBridge):
        super().__init__(name="desktop-friend-server", daemon=True)
        self.agent = agent
        self.bridge = bridge
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_event: asyncio.Event | None = None
        self._ready = threading.Event()

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.stop_event = asyncio.Event()
        self._ready.set()
        try:
            self.loop.run_until_complete(serve(self.agent, self.stop_event))
        except OSError as exc:
            self.bridge.server_failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - surfaced to the user
            log.exception("server crashed")
            self.bridge.server_failed.emit(repr(exc))
        finally:
            self.loop.close()

    def stop(self) -> None:
        self._ready.wait(2)
        if self.loop and self.stop_event and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.stop_event.set)
        self.join(timeout=4)


def run_gui(cfg: Config) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Desktop Friend")
    app.setQuitOnLastWindowClosed(False)
    icon = make_icon(cfg.cursor_color)
    app.setWindowIcon(icon)

    bridge = QtBridge()
    agent = Agent(cfg, ui=bridge)
    overlay = CursorOverlay(cfg.cursor_color)
    window = PairingWindow(agent)

    # asyncio -> GUI wiring (queued across threads)
    bridge.point_sig.connect(lambda x, y, label, d: overlay.glide_to(x, y, label, d))
    bridge.click_sig.connect(overlay.ripple)
    bridge.home_sig.connect(overlay.go_home)
    bridge.visible_sig.connect(overlay.set_overlay_visible)
    bridge.status_sig.connect(window.set_activity)
    bridge.status_sig.connect(lambda text: overlay.flash_label(text, 3.0))
    bridge.pairing_sig.connect(window.set_pairing)
    bridge.config_sig.connect(window.refresh_keys)

    def on_device(name: str, connected: bool) -> None:
        window.device_event(name, connected)
        if connected:
            overlay.flash_label(f"Hi {name}!", 3.0)
            # The first time a phone connects, tuck the pairing window away.
            QTimer.singleShot(1800, window.hide)

    bridge.device_sig.connect(on_device)

    def toggle_cursor() -> None:
        agent.cfg.cursor_visible = not overlay.isVisible()
        bridge.set_visible(agent.cfg.cursor_visible)

    window.toggle_cursor_requested.connect(toggle_cursor)

    server = ServerThread(agent, bridge)

    def on_server_failed(message: str) -> None:
        QMessageBox.critical(
            None,
            "Desktop Friend",
            f"Couldn't start the server on port {cfg.port}:\n{message}\n\nIs Desktop Friend already running? "
            "Change DF_PORT in pc-agent/.env or run with --port.",
        )
        app.quit()

    bridge.server_failed.connect(on_server_failed)

    # tray icon (falls back to "closing the window quits" when there's no tray)
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon)
        tray.setToolTip("Desktop Friend")
        menu = QMenu()
        show_qr = QAction("Show pairing QR code", menu)
        show_qr.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
        cursor = QAction("Show / hide blue cursor", menu)
        cursor.triggered.connect(toggle_cursor)
        home = QAction("Send cursor home", menu)
        home.triggered.connect(lambda: overlay.go_home(0.6))
        quit_action = QAction("Quit Desktop Friend", menu)
        quit_action.triggered.connect(app.quit)
        for a in (show_qr, cursor, home):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: (window.show(), window.raise_()) if reason == QSystemTrayIcon.Trigger else None
        )
        tray.show()
        app._df_tray_menu = menu  # keep a reference
    else:
        app.setQuitOnLastWindowClosed(True)

    app.aboutToQuit.connect(server.stop)

    # Let Ctrl+C in the terminal quit the Qt loop.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(300)

    server.start()
    if cfg.cursor_visible:
        overlay.set_overlay_visible(True)
    window.show()

    print_pairing(agent)
    rc = app.exec()
    if tray:
        tray.hide()
    return rc
