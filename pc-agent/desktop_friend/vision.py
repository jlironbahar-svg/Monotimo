"""Screen capture + Groq vision: describe the screen and locate UI elements for the blue cursor.

All coordinates handed to the rest of the agent are *normalized* (0..1) relative to the
primary monitor, so they map cleanly onto the Qt overlay (logical pixels) and onto
pyautogui (which may use physical or logical pixels depending on OS / DPI scaling).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .groq_client import GroqClient

log = logging.getLogger(__name__)

LOCATE_SYSTEM = (
    "You are a precise GUI grounding assistant. You look at screenshots of a computer desktop and "
    "return the exact location of the requested on-screen element as JSON."
)

LOCATE_PROMPT = """The screenshot has a faint coordinate grid. Numbers along the TOP edge are X positions and numbers along the LEFT edge are Y positions, both from 0 to 1000 (0,0 is the top-left corner, 1000,1000 the bottom-right).

Find this element: "{target}"

Ignore the small blue arrow cursor with a white outline; it is the assistant's own pointer.
Reply with ONLY a JSON object, no other text:
{{"found": true or false, "x": <0-1000>, "y": <0-1000>, "description": "<what you found, max 12 words>"}}
x and y must be the CENTER of the element. If it is not visible, use "found": false."""

DESCRIBE_SYSTEM = (
    "You are looking at the user's computer screen through a screenshot. Be concrete: name the apps, "
    "windows, and the important text you can read. Never invent things you cannot see."
)


@dataclass
class LocateResult:
    x: float  # normalized 0..1
    y: float  # normalized 0..1
    description: str
    refined: bool = False


class ScreenCapture:
    """Grabs the primary monitor with mss. Each call creates its own mss instance (thread safe)."""

    def grab(self) -> Image.Image:
        import mss  # imported lazily: needs a display

        with mss.mss() as sct:
            monitor = getattr(sct, "primary_monitor", None)
            if not monitor:
                monitors = sct.monitors[1:] or sct.monitors
                monitor = next((m for m in monitors if m.get("left") == 0 and m.get("top") == 0), monitors[0])
            shot = sct.grab(monitor)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def resize_max(img: Image.Image, max_width: int) -> Image.Image:
    if img.width <= max_width:
        return img
    h = round(img.height * max_width / img.width)
    return img.resize((max_width, h), Image.LANCZOS)


def to_jpeg(img: Image.Image, quality: int = 80) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def annotate_grid(img: Image.Image, divisions: int = 10) -> Image.Image:
    """Overlay a labelled 0-1000 grid so the vision model has rulers to read coordinates from."""
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    w, h = base.size
    font = _font(max(11, min(w, h) // 55))
    for i in range(1, divisions):
        x = round(w * i / divisions)
        y = round(h * i / divisions)
        draw.line([(x, 0), (x, h)], fill=(255, 0, 140, 70), width=1)
        draw.line([(0, y), (w, y)], fill=(255, 0, 140, 70), width=1)
    for i in range(0, divisions):
        label = str(i * 1000 // divisions)
        x = round(w * i / divisions)
        y = round(h * i / divisions)
        # X labels along the top; Y labels down the left edge (the shared "0" corner only once)
        positions = [(x + 3, 2)] if i == 0 else [(x + 3, 2), (2, y + 3)]
        for pos in positions:
            bbox = draw.textbbox(pos, label, font=font)
            draw.rectangle([bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1], fill=(255, 255, 255, 200))
            draw.text(pos, label, fill=(200, 0, 110, 255), font=font)
    return Image.alpha_composite(base, layer).convert("RGB")


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_point(text: str) -> tuple[bool, float, float, str] | None:
    """Parse the model's JSON answer into (found, x01, y01, description)."""
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    found = data.get("found", True)
    if isinstance(found, str):
        found = found.strip().lower() == "true"
    try:
        x, y = float(data.get("x")), float(data.get("y"))
    except (TypeError, ValueError):
        return (False, 0.0, 0.0, str(data.get("description", ""))) if found is False else None
    if 0 <= x <= 1 and 0 <= y <= 1 and (isinstance(data.get("x"), float) or isinstance(data.get("y"), float)):
        x01, y01 = x, y  # model answered in 0..1 instead of 0..1000
    else:
        x01, y01 = x / 1000.0, y / 1000.0
    x01 = min(max(x01, 0.0), 1.0)
    y01 = min(max(y01, 0.0), 1.0)
    return bool(found), x01, y01, str(data.get("description", ""))[:120]


def crop_box(width: int, height: int, cx: float, cy: float, frac: float = 0.3, min_w: int = 360, min_h: int = 240):
    """Pixel crop box (left, top, right, bottom) around a normalized point, clamped to the image."""
    bw = min(width, max(int(width * frac), min_w))
    bh = min(height, max(int(height * frac), min_h))
    left = int(cx * width - bw / 2)
    top = int(cy * height - bh / 2)
    left = min(max(left, 0), width - bw)
    top = min(max(top, 0), height - bh)
    return left, top, left + bw, top + bh


class Vision:
    def __init__(self, groq: GroqClient, model_getter, refine_getter, capture: ScreenCapture | None = None):
        self.groq = groq
        self._model = model_getter
        self._refine = refine_getter
        self.capture = capture or ScreenCapture()

    async def grab(self) -> Image.Image:
        return await asyncio.to_thread(self.capture.grab)

    async def screen_size(self) -> tuple[int, int]:
        img = await self.grab()
        return img.size

    async def thumbnail(self, max_width: int = 900) -> tuple[str, int, int]:
        img = resize_max(await self.grab(), max_width)
        return base64.b64encode(to_jpeg(img, 70)).decode("ascii"), img.width, img.height

    async def describe(self, question: str | None = None) -> str:
        img = resize_max(await self.grab(), 1280)
        prompt = (question or "What is on my screen right now?") + " Answer in at most 3 short sentences."
        return await self.groq.vision(self._model(), prompt, to_jpeg(img, 80), system=DESCRIBE_SYSTEM)

    async def _ask_point(self, img: Image.Image, target: str):
        jpeg = to_jpeg(annotate_grid(img), 82)
        text = await self.groq.vision(self._model(), LOCATE_PROMPT.format(target=target), jpeg, system=LOCATE_SYSTEM)
        log.debug("vision answer for %r: %s", target, text)
        return parse_point(text)

    async def locate(self, target: str, image: Image.Image | None = None) -> LocateResult | None:
        full = image or await self.grab()
        first = await self._ask_point(resize_max(full, 1280), target)
        if not first or not first[0]:
            return None
        _, x, y, desc = first
        result = LocateResult(x, y, desc)
        if not self._refine():
            return result

        # Pass 2: zoom into the area around the first guess for a precise point.
        box = crop_box(full.width, full.height, x, y)
        crop = full.crop(box)
        if crop.width < 1024:
            scale = 1024 / crop.width
            crop = crop.resize((1024, round(crop.height * scale)), Image.LANCZOS)
        try:
            second = await self._ask_point(crop, target)
        except Exception as exc:  # refinement is best-effort
            log.info("refine pass failed: %s", exc)
            return result
        if second and second[0]:
            _, lx, ly, desc2 = second
            left, top, right, bottom = box
            ax = left + lx * (right - left)
            ay = top + ly * (bottom - top)
            return LocateResult(ax / full.width, ay / full.height, desc2 or desc, refined=True)
        return result
