"""UiBridge implementation that hops from the asyncio thread to the Qt GUI thread via queued signals."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..ui import UiBridge


class QtBridge(QObject, UiBridge):
    point_sig = Signal(float, float, str, float)
    click_sig = Signal(float, float)
    home_sig = Signal(float)
    visible_sig = Signal(bool)
    status_sig = Signal(str)
    pairing_sig = Signal(str)
    device_sig = Signal(str, bool)
    config_sig = Signal()
    server_failed = Signal(str)

    def __init__(self):
        QObject.__init__(self)
        UiBridge.__init__(self)

    def _emit_point(self, x, y, label, duration):
        self.point_sig.emit(x, y, label, duration)

    def _emit_click(self, x, y):
        self.click_sig.emit(x, y)

    def _emit_home(self, duration):
        self.home_sig.emit(duration)

    def _emit_visible(self, visible):
        self.visible_sig.emit(visible)

    def _emit_status(self, text):
        self.status_sig.emit(text)

    def _emit_pairing(self, url):
        self.pairing_sig.emit(url)

    def _emit_device(self, name, connected):
        self.device_sig.emit(name, connected)

    def _emit_config(self):
        self.config_sig.emit()
