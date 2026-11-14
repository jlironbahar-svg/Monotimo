"""Transparent, click-through, always-on-top window that draws the AI's little blue cursor.

The overlay covers the primary screen. It never takes focus and lets every mouse event pass
through to the apps underneath, so the user's real cursor keeps working normally.
"""

from __future__ import annotations

import math
import random
import sys

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

from ..ui import HOME

# Arrow outline with the tip at (0, 0). Units are pixels before SCALE.
_ARROW = [(0, 0), (0, 23), (6, 17.5), (10.5, 27), (14.5, 25.2), (10, 16), (17.5, 16)]
SCALE = 1.35
PULSE_LIFE = 1.1
RIPPLE_LIFE = 0.45


def _ease_in_out(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def _bezier(a: QPointF, c: QPointF, b: QPointF, t: float) -> QPointF:
    u = 1 - t
    return QPointF(u * u * a.x() + 2 * u * t * c.x() + t * t * b.x(), u * u * a.y() + 2 * u * t * c.y() + t * t * b.y())


def arrow_polygon(origin: QPointF, scale: float = SCALE) -> QPolygonF:
    return QPolygonF([QPointF(origin.x() + x * scale, origin.y() + y * scale) for x, y in _ARROW])


def paint_cursor(p: QPainter, tip: QPointF, color: QColor, eyes_open: bool = True, scale: float = SCALE) -> None:
    """Draw the friendly blue arrow (shared with the tray icon)."""
    # soft shadow
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 55))
    p.drawPolygon(arrow_polygon(QPointF(tip.x() + 2.2, tip.y() + 3.0), scale))

    poly = arrow_polygon(tip, scale)
    grad = QLinearGradient(tip, QPointF(tip.x() + 10 * scale, tip.y() + 27 * scale))
    grad.setColorAt(0.0, color.lighter(145))
    grad.setColorAt(1.0, color.darker(115))
    p.setBrush(QBrush(grad))
    pen = QPen(QColor(255, 255, 255), max(1.6, 1.5 * scale))
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawPolygon(poly)

    # tiny face: two eyes and a blush, so it reads as a little character
    ex1 = QPointF(tip.x() + 3.6 * scale, tip.y() + 12.6 * scale)
    ex2 = QPointF(tip.x() + 7.6 * scale, tip.y() + 12.6 * scale)
    p.setPen(Qt.NoPen)
    if eyes_open:
        p.setBrush(QColor(255, 255, 255))
        for e in (ex1, ex2):
            p.drawEllipse(e, 1.55 * scale, 1.7 * scale)
        p.setBrush(QColor(16, 30, 70))
        for e in (ex1, ex2):
            p.drawEllipse(QPointF(e.x() + 0.25 * scale, e.y() + 0.3 * scale), 0.85 * scale, 0.95 * scale)
    else:
        p.setPen(QPen(QColor(255, 255, 255), 0.9 * scale, Qt.SolidLine, Qt.RoundCap))
        for e in (ex1, ex2):
            p.drawLine(QPointF(e.x() - 1.3 * scale, e.y()), QPointF(e.x() + 1.3 * scale, e.y()))
        p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 140, 180, 150))
    p.drawEllipse(QPointF(tip.x() + 5.6 * scale, tip.y() + 15.4 * scale), 1.3 * scale, 0.7 * scale)


class _Pulse:
    __slots__ = ("center", "t0", "life", "big")

    def __init__(self, center: QPointF, t0: float, life: float, big: bool):
        self.center, self.t0, self.life, self.big = center, t0, life, big


class CursorOverlay(QWidget):
    def __init__(self, color: str = "#2F7BFF"):
        super().__init__(None)
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        if sys.platform.startswith("linux"):
            flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setWindowTitle("Desktop Friend cursor")

        self.color = QColor(color) if QColor(color).isValid() else QColor("#2F7BFF")
        self._clock = QElapsedTimer()
        self._clock.start()
        self._anim: tuple[QPointF, QPointF, QPointF, float, float, bool] | None = None
        self._pulses: list[_Pulse] = []
        self._label = ""
        self._label_until = 0.0
        self._next_blink = 3.0
        self._blink_until = 0.0
        self._last_dirty = QRectF()

        self._fit_to_screen()
        self.pos_f = self._home_point()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen.geometryChanged.connect(lambda _g: self._fit_to_screen())

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # -- geometry -------------------------------------------------------
    def _fit_to_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())

    def _to_local(self, x: float, y: float) -> QPointF:
        return QPointF(x * self.width(), y * self.height())

    def _home_point(self) -> QPointF:
        return self._to_local(*HOME)

    def _now(self) -> float:
        return self._clock.elapsed() / 1000.0

    # -- public slots (GUI thread) ---------------------------------------
    def glide_to(self, x: float, y: float, label: str = "", duration: float = 0.6, pulse: bool = True) -> None:
        target = self._to_local(x, y)
        start = QPointF(self.pos_f)
        # control point: a little arc above the straight line, for a playful hop
        mid = QPointF((start.x() + target.x()) / 2, (start.y() + target.y()) / 2)
        dist = math.hypot(target.x() - start.x(), target.y() - start.y())
        ctrl = QPointF(mid.x(), mid.y() - min(140.0, dist * 0.25))
        self._anim = (start, ctrl, target, self._now(), max(0.05, duration), pulse)
        if label:
            self.flash_label(label, duration + 2.5)

    def go_home(self, duration: float = 0.6) -> None:
        self.glide_to(*HOME, label="", duration=duration, pulse=False)

    def ripple(self, x: float, y: float) -> None:
        self._pulses.append(_Pulse(self._to_local(x, y), self._now(), RIPPLE_LIFE, big=False))

    def flash_label(self, text: str, seconds: float = 3.0) -> None:
        self._label = text if len(text) <= 48 else text[:47] + "…"
        self._label_until = self._now() + seconds

    def set_overlay_visible(self, visible: bool) -> None:
        if visible:
            self.show()
            self.raise_()
            self._exclude_from_capture()
            self._timer.start(16)
        else:
            self._timer.stop()
            self.hide()

    def _exclude_from_capture(self) -> None:
        """Windows 10 2004+: keep the overlay out of screenshots so the vision model never sees it."""
        if sys.platform.startswith("win"):
            try:
                import ctypes

                WDA_EXCLUDEFROMCAPTURE = 0x11
                ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), WDA_EXCLUDEFROMCAPTURE)
            except Exception:
                pass

    # -- animation ------------------------------------------------------
    def _bob(self, now: float) -> float:
        return 0.0 if self._anim else math.sin(now * 2.6) * 2.4

    def _cursor_rect(self, now: float) -> QRectF:
        tip = QPointF(self.pos_f.x(), self.pos_f.y() + self._bob(now))
        return QRectF(tip.x() - 4, tip.y() - 4, 30 * SCALE + 8, 38 * SCALE + 8)

    def _label_rect(self, now: float) -> QRectF:
        if not self._label or now > self._label_until:
            return QRectF()
        fm = QFontMetricsF(self._label_font())
        w = fm.horizontalAdvance(self._label) + 24
        h = fm.height() + 12
        x = self.pos_f.x() + 26 * SCALE
        y = self.pos_f.y() + 24 * SCALE + self._bob(now)
        if x + w > self.width() - 8:
            x = self.pos_f.x() - w - 10
        if y + h > self.height() - 8:
            y = self.pos_f.y() - h - 10
        return QRectF(x, y, w, h)

    def _dirty(self, now: float) -> QRectF:
        r = self._cursor_rect(now).united(self._label_rect(now))
        for pulse in self._pulses:
            rad = 64 if pulse.big else 30
            r = r.united(QRectF(pulse.center.x() - rad, pulse.center.y() - rad, rad * 2, rad * 2))
        return r

    def _tick(self) -> None:
        now = self._now()
        if self._anim:
            start, ctrl, end, t0, dur, pulse = self._anim
            t = (now - t0) / dur
            if t >= 1.0:
                self.pos_f = QPointF(end)
                self._anim = None
                if pulse:
                    self._pulses.append(_Pulse(QPointF(end), now, PULSE_LIFE, big=True))
                    self._pulses.append(_Pulse(QPointF(end), now + 0.22, PULSE_LIFE, big=True))
            else:
                self.pos_f = _bezier(start, ctrl, end, _ease_in_out(t))
        self._pulses = [p for p in self._pulses if now - p.t0 < p.life]
        if now >= self._next_blink:
            self._blink_until = now + 0.13
            self._next_blink = now + random.uniform(2.5, 5.5)

        dirty = self._dirty(now)
        self.update(dirty.united(self._last_dirty).toAlignedRect().adjusted(-3, -3, 3, 3))
        self._last_dirty = dirty

    # -- painting -------------------------------------------------------
    def _label_font(self) -> QFont:
        f = QFont()
        f.setPointSizeF(10.5)
        f.setBold(True)
        return f

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        now = self._now()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        for pulse in self._pulses:
            age = now - pulse.t0
            if age < 0:
                continue
            t = age / pulse.life
            max_r = 56 if pulse.big else 24
            radius = 6 + (max_r - 6) * (1 - (1 - t) ** 3)
            alpha = int(200 * (1 - t))
            c = QColor(self.color)
            c.setAlpha(alpha)
            p.setPen(QPen(c, 3.5 if pulse.big else 2.5))
            fill = QColor(self.color)
            fill.setAlpha(int(alpha * 0.18))
            p.setBrush(fill)
            p.drawEllipse(pulse.center, radius, radius)

        tip = QPointF(self.pos_f.x(), self.pos_f.y() + self._bob(now))
        paint_cursor(p, tip, self.color, eyes_open=now >= self._blink_until)

        rect = self._label_rect(now)
        if not rect.isNull():
            path = QPainterPath()
            path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            p.setBrush(self.color.darker(110))
            p.drawPath(path)
            p.setPen(QColor(255, 255, 255))
            p.setFont(self._label_font())
            p.drawText(rect, Qt.AlignCenter, self._label)
        p.end()
