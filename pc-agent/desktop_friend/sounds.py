"""Tiny synthesized sound effects (no binary assets) + a non-blocking cross-platform player."""

from __future__ import annotations

import io
import logging
import math
import random
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

log = logging.getLogger(__name__)

RATE = 22050


def _env(i: int, n: int, attack: float = 0.01, release: float = 0.25) -> float:
    t = i / RATE
    dur = n / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = min(1.0, (dur - t) / release) if release > 0 else 1.0
    return max(0.0, min(a, r))


def _tone(freqs: list[tuple[float, float]], dur: float, vol: float = 0.5, harmonics=(1.0, 0.25, 0.1)) -> list[float]:
    """freqs: list of (start_time, frequency) steps."""
    n = int(dur * RATE)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = freqs[0][1]
        for start, freq in freqs:
            if t >= start:
                f = freq
        phase += 2 * math.pi * f / RATE
        s = sum(h * math.sin(phase * (k + 1)) for k, h in enumerate(harmonics))
        out.append(s * vol * _env(i, n, 0.005, min(0.12, dur / 2)))
    return out


def _sweep(f0: float, f1: float, dur: float, vol: float = 0.5) -> list[float]:
    n = int(dur * RATE)
    out, phase = [], 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * (i / n)
        phase += 2 * math.pi * f / RATE
        out.append(math.sin(phase) * vol * _env(i, n, 0.004, dur * 0.6))
    return out


def _mix(*tracks: tuple[float, list[float]]) -> list[float]:
    """tracks: (offset_seconds, samples)."""
    length = max(int(off * RATE) + len(s) for off, s in tracks)
    out = [0.0] * length
    for off, s in tracks:
        o = int(off * RATE)
        for i, v in enumerate(s):
            out[o + i] += v
    return out


def _wav(samples: list[float]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples))
    return buf.getvalue()


def synth_all() -> dict[str, bytes]:
    random.seed(7)
    return {
        # "bip-boop" when the blue cursor arrives at its target
        "point": _wav(_mix((0, _tone([(0, 880)], 0.09, 0.35)), (0.08, _tone([(0, 1320)], 0.14, 0.32)))),
        # soft tick for a click
        "click": _wav(_tone([(0, 1800)], 0.035, 0.35, harmonics=(1.0, 0.4))),
        # happy arpeggio when a phone pairs
        "paired": _wav(
            _mix(
                (0.00, _tone([(0, 523.25)], 0.12, 0.3)),
                (0.09, _tone([(0, 659.25)], 0.12, 0.3)),
                (0.18, _tone([(0, 783.99)], 0.12, 0.3)),
                (0.27, _tone([(0, 1046.5)], 0.25, 0.3)),
            )
        ),
        # rising "wheee" when typing / acting
        "action": _wav(_sweep(500, 1100, 0.16, 0.3)),
        # gentle "uh-oh"
        "error": _wav(_mix((0, _tone([(0, 494)], 0.14, 0.3)), (0.13, _tone([(0, 370)], 0.22, 0.3)))),
    }


class SoundPlayer:
    def __init__(self, cache_dir: Path, enabled_getter):
        self._dir = Path(cache_dir) / "sounds"
        self._enabled = enabled_getter
        self._files: dict[str, Path] = {}
        self._linux_cmd = None
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            for name, data in synth_all().items():
                path = self._dir / f"{name}.wav"
                if not path.exists() or path.stat().st_size != len(data):
                    path.write_bytes(data)
                self._files[name] = path
        except OSError as exc:
            log.warning("sound effects unavailable: %s", exc)
        if sys.platform.startswith("linux"):
            for cmd in (["paplay"], ["pw-play"], ["aplay", "-q"]):
                if shutil.which(cmd[0]):
                    self._linux_cmd = cmd
                    break

    def play(self, name: str) -> None:
        if not self._enabled():
            return
        path = self._files.get(name)
        if not path:
            return
        try:
            if sys.platform.startswith("win"):
                import winsound

                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self._linux_cmd:
                subprocess.Popen([*self._linux_cmd, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # sound is decoration; never fail an action because of it
            log.debug("could not play %s: %s", name, exc)
