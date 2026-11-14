"""The window with the pairing QR code, connection status and key status."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..pairing import qr_png_bytes

STYLE = """
QWidget#root { background: #EEF4FF; }
QFrame#card { background: white; border-radius: 22px; }
QLabel { color: #1B2A4A; }
QLabel#title { font-size: 24px; font-weight: 800; }
QLabel#subtitle { font-size: 13px; color: #51607d; }
QLabel#addr { font-size: 13px; color: #51607d; }
QLabel#status { font-size: 14px; font-weight: 700; padding: 8px 14px; border-radius: 14px; background: #FFF4D6; color: #8A5A00; }
QLabel#status[connected="true"] { background: #DDF7E6; color: #146B34; }
QLabel#keys { font-size: 12px; color: #51607d; }
QLabel#activity { font-size: 12px; color: #2F7BFF; }
QPushButton { background: #2F7BFF; color: white; border: none; border-radius: 14px; padding: 9px 16px; font-weight: 700; }
QPushButton:hover { background: #1F66E5; }
QPushButton#secondary { background: #E3ECFF; color: #1B2A4A; }
QPushButton#secondary:hover { background: #D3E0FF; }
"""


class PairingWindow(QWidget):
    toggle_cursor_requested = Signal()

    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.setObjectName("root")
        self.setWindowTitle("Desktop Friend — pair your phone")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)

        card = QFrame(objectName="card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(10)

        title = QLabel("🐶 Desktop Friend", objectName="title", alignment=Qt.AlignCenter)
        subtitle = QLabel(
            "Open the Desktop Friend app on your phone and scan this code.\nPhone and PC must be on the same Wi-Fi.",
            objectName="subtitle",
            alignment=Qt.AlignCenter,
        )
        subtitle.setWordWrap(True)
        self.qr = QLabel(alignment=Qt.AlignCenter)
        self.qr.setMinimumSize(300, 300)
        self.qr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.addr = QLabel(objectName="addr", alignment=Qt.AlignCenter)
        self.addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status = QLabel("Waiting for your phone…", objectName="status", alignment=Qt.AlignCenter)
        self.activity = QLabel("", objectName="activity", alignment=Qt.AlignCenter)
        self.keys = QLabel(objectName="keys", alignment=Qt.AlignCenter)
        self.keys.setWordWrap(True)

        new_qr = QPushButton("New QR code")
        new_qr.setToolTip("Make a fresh pairing code. Phones that are already paired stay paired.")
        new_qr.clicked.connect(self._rotate)
        forget = QPushButton("Unpair phones", objectName="secondary")
        forget.clicked.connect(self._forget)
        cursor_btn = QPushButton("Show/hide cursor", objectName="secondary")
        cursor_btn.clicked.connect(self.toggle_cursor_requested.emit)
        buttons = QHBoxLayout()
        buttons.addWidget(new_qr)
        buttons.addWidget(cursor_btn)
        buttons.addWidget(forget)

        for w in (title, subtitle, self.qr, self.addr, self.status, self.activity, self.keys):
            lay.addWidget(w)
        lay.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.addWidget(card)

        self._devices: dict[str, int] = {}
        self.set_pairing(agent.pairing_url())
        self.refresh_keys()

    # -- slots ----------------------------------------------------------
    def set_pairing(self, url: str) -> None:
        pix = QPixmap()
        pix.loadFromData(qr_png_bytes(url, box_size=10), "PNG")
        self.qr.setPixmap(pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.FastTransformation))
        hosts = self.agent.hosts
        extra = f"  (also {', '.join(hosts[1:3])})" if len(hosts) > 1 else ""
        self.addr.setText(f"<b>{self.agent.cfg.pc_name}</b> · {hosts[0]}:{self.agent.cfg.port}{extra}")

    def device_event(self, name: str, connected: bool) -> None:
        self._devices[name] = max(0, self._devices.get(name, 0) + (1 if connected else -1))
        online = [n for n, c in self._devices.items() if c > 0]
        if online:
            self.status.setText("Connected to " + ", ".join(online) + " ✓")
            self.status.setProperty("connected", "true")
        else:
            self.status.setText("Waiting for your phone…")
            self.status.setProperty("connected", "false")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_activity(self, text: str) -> None:
        self.activity.setText(text)

    def refresh_keys(self) -> None:
        cfg = self.agent.cfg
        groq = "✓" if cfg.groq_api_key else "✗ missing"
        eleven = "✓" if cfg.elevenlabs_api_key else "✗ missing (phone voice used)"
        hint = "" if cfg.groq_api_key and cfg.elevenlabs_api_key else "<br>Add keys in the phone app (Settings) or in pc-agent/.env"
        self.keys.setText(f"Groq {groq} &nbsp;·&nbsp; ElevenLabs {eleven}{hint}")

    def _rotate(self) -> None:
        self.agent.refresh_hosts()
        self.agent.rotate_pairing()

    def _forget(self) -> None:
        answer = QMessageBox.question(
            self,
            "Unpair phones",
            "Unpair every phone? They will need to scan a new QR code.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.agent.pairing.forget_devices()
            self.agent.rotate_pairing()

    def showEvent(self, event) -> None:  # noqa: N802
        self.agent.refresh_hosts()
        super().showEvent(event)
