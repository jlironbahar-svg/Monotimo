"""Pairing secrets, device tokens and the QR payload.

Flow
----
1. The PC keeps a *pairing token* (shown in the QR code). It survives restarts so an
   already-printed QR keeps working, and can be rotated from the pairing window.
2. A phone that scans the QR sends ``hello{pairToken}``. The PC answers with a fresh,
   random *device token* and stores only its SHA-256 hash.
3. Later connections send ``hello{deviceToken}``. Rotating the pairing token does not
   log out devices that are already paired; "Forget devices" does.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .protocol import PAIR_URL_SCHEME, PROTOCOL_VERSION

log = logging.getLogger(__name__)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class Device:
    device_id: str
    name: str
    token_hash: str
    created: float
    last_seen: float


class PairingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.pair_token: str = ""
        self.devices: dict[str, Device] = {}
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        data: dict = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text("utf-8"))
            except (OSError, ValueError) as exc:
                log.warning("Pairing file %s unreadable (%s); starting fresh", self.path, exc)
        self.pair_token = data.get("pair_token") or secrets.token_urlsafe(18)
        for dev_id, d in (data.get("devices") or {}).items():
            try:
                self.devices[dev_id] = Device(
                    device_id=dev_id,
                    name=d.get("name", "Phone"),
                    token_hash=d["token_hash"],
                    created=float(d.get("created", 0)),
                    last_seen=float(d.get("last_seen", 0)),
                )
            except (KeyError, TypeError, ValueError):
                continue
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pair_token": self.pair_token,
            "devices": {
                d.device_id: {
                    "name": d.name,
                    "token_hash": d.token_hash,
                    "created": d.created,
                    "last_seen": d.last_seen,
                }
                for d in self.devices.values()
            },
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), "utf-8")
        tmp.replace(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    # -- tokens ---------------------------------------------------------
    def rotate_pair_token(self) -> str:
        with self._lock:
            self.pair_token = secrets.token_urlsafe(18)
            self._save()
            return self.pair_token

    def forget_devices(self) -> None:
        with self._lock:
            self.devices.clear()
            self._save()

    def check_pair_token(self, token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(str(token), self.pair_token)

    def register_device(self, device_id: str, name: str) -> str:
        """Issue a new device token for a phone that presented a valid pairing token."""
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self.devices[device_id] = Device(device_id, name[:64] or "Phone", _hash(token), now, now)
            self._save()
        return token

    def check_device_token(self, device_id: str, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            dev = self.devices.get(device_id)
            if dev is None or not hmac.compare_digest(dev.token_hash, _hash(str(token))):
                return False
            dev.last_seen = time.time()
            self._save()
            return True

    def any_device_token(self, token: str | None) -> bool:
        """Used to authorise HTTP audio downloads (token passed as ?t=)."""
        if not token:
            return False
        h = _hash(str(token))
        return any(hmac.compare_digest(d.token_hash, h) for d in self.devices.values())


def pairing_url(hosts: list[str], port: int, token: str, pc_name: str) -> str:
    """The string encoded in the QR code."""
    return (
        f"{PAIR_URL_SCHEME}://pair?v={PROTOCOL_VERSION}"
        f"&h={quote(','.join(hosts), safe=',')}"
        f"&p={port}"
        f"&t={quote(token, safe='')}"
        f"&n={quote(pc_name, safe='')}"
    )


def qr_matrix_ascii(data: str) -> str:
    """Render a QR code with Unicode half blocks for terminals."""
    import io

    import qrcode

    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    return buf.getvalue()


def qr_png_bytes(data: str, box_size: int = 10) -> bytes:
    import io

    import qrcode

    qr = qrcode.QRCode(border=2, box_size=box_size, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1B2A4A", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
