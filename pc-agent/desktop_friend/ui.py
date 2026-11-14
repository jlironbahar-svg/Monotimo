"""Thread-safe facade between the asyncio agent and whatever draws on the desktop.

The asyncio side calls these methods. The Qt implementation (gui/bridge.py) forwards them to
the GUI thread with queued signals; NullBridge just logs (headless mode / tests).
Coordinates are normalized 0..1 on the primary screen.
"""

from __future__ import annotations

import logging
import math

log = logging.getLogger(__name__)

HOME = (0.955, 0.90)  # where the blue cursor "sits" when idle (bottom-right corner)


class UiBridge:
    def __init__(self) -> None:
        self._last = HOME
        self.visible = True
        self.at_home = True

    # -- helpers --------------------------------------------------------
    def travel_time(self, x: float, y: float) -> float:
        lx, ly = self._last
        dist = math.hypot(x - lx, y - ly)
        return round(min(1.0, max(0.35, 0.3 + dist * 0.75)), 3)

    @property
    def cursor_position(self) -> tuple[float, float] | None:
        """Where the blue cursor points right now, or None if it is resting at home."""
        return None if self.at_home else self._last

    # -- public API (called from the asyncio thread) ---------------------
    def point(self, x: float, y: float, label: str = "") -> float:
        """Glide the blue cursor to (x, y) and pulse. Returns the animation duration in seconds."""
        duration = self.travel_time(x, y)
        self._last = (x, y)
        self.at_home = False
        self._emit_point(x, y, label, duration)
        return duration

    def click_ripple(self, x: float, y: float) -> None:
        self._emit_click(x, y)

    def home(self) -> float:
        duration = self.travel_time(*HOME)
        self._last = HOME
        self.at_home = True
        self._emit_home(duration)
        return duration

    def set_visible(self, visible: bool) -> None:
        self.visible = visible
        self._emit_visible(visible)

    def set_status(self, text: str) -> None:
        self._emit_status(text)

    def pairing_changed(self, url: str) -> None:
        self._emit_pairing(url)

    def device_event(self, name: str, connected: bool) -> None:
        self._emit_device(name, connected)

    def config_changed(self) -> None:
        self._emit_config()

    # -- overridden by implementations -----------------------------------
    def _emit_point(self, x, y, label, duration):  # pragma: no cover - trivial
        log.info("[cursor] point -> (%.3f, %.3f) %s", x, y, label)

    def _emit_click(self, x, y):  # pragma: no cover
        log.info("[cursor] click ripple at (%.3f, %.3f)", x, y)

    def _emit_home(self, duration):  # pragma: no cover
        log.info("[cursor] home")

    def _emit_visible(self, visible):  # pragma: no cover
        log.info("[cursor] visible=%s", visible)

    def _emit_status(self, text):  # pragma: no cover
        log.debug("[status] %s", text)

    def _emit_pairing(self, url):  # pragma: no cover
        log.debug("[pairing] %s", url)

    def _emit_device(self, name, connected):  # pragma: no cover
        log.info("[device] %s %s", name, "connected" if connected else "disconnected")

    def _emit_config(self):  # pragma: no cover
        pass


class NullBridge(UiBridge):
    """Headless: nothing is drawn, everything is logged."""
