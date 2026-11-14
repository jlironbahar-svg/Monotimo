"""Render the overlay and pairing window off-screen (no display needed)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _blue_pixels(img, color):
    c = color
    hits = 0
    for x in range(0, img.width(), 2):
        for y in range(0, img.height(), 2):
            p = img.pixelColor(x, y)
            if p.alpha() > 200 and abs(p.blue() - c.blue()) < 60 and p.blue() > p.red() + 60:
                hits += 1
    return hits


def test_overlay_glides_and_draws(qapp):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor

    from desktop_friend.gui.overlay import CursorOverlay

    ov = CursorOverlay("#2F7BFF")
    ov.resize(800, 600)
    ov.glide_to(0.25, 0.5, "the save button", duration=0.01)
    import time

    time.sleep(0.08)  # durations are clamped to >= 50 ms
    ov._tick()
    assert abs(ov.pos_f.x() - 200) < 1 and abs(ov.pos_f.y() - 300) < 1
    img = ov.grab().toImage()
    assert _blue_pixels(img, QColor("#2F7BFF")) > 20
    ov.ripple(0.5, 0.5)
    ov.go_home(0.01)
    ov.close()


def test_pairing_window_builds(qapp, cfg):
    from desktop_friend.agent import Agent
    from desktop_friend.gui.pairing_window import PairingWindow

    agent = Agent(cfg)
    w = PairingWindow(agent)
    assert not w.qr.pixmap().isNull()
    w.device_event("Pixel", True)
    assert "Pixel" in w.status.text()
    w.device_event("Pixel", False)
    assert "Waiting" in w.status.text()
    w.close()
