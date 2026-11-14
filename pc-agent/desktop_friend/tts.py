"""ElevenLabs text-to-speech + a small in-memory cache served over HTTP to the phone."""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections import OrderedDict
from typing import Callable

import httpx

log = logging.getLogger(__name__)

ELEVEN_BASE_URL = "https://api.elevenlabs.io/v1"

_EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f000-\U0001f2ff\U0000fe0f\U0000200d]+", flags=re.UNICODE
)


def clean_for_speech(text: str) -> str:
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"[*_`#>]+", "", text)  # markdown
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url)
    text = re.sub(r"https?://\S+", "a link", text)
    return re.sub(r"\s+", " ", text).strip()


class TTSError(Exception):
    pass


class ElevenLabsTTS:
    def __init__(
        self,
        api_key_getter: Callable[[], str],
        voice_getter: Callable[[], str],
        model_getter: Callable[[], str],
        base_url: str = ELEVEN_BASE_URL,
    ):
        self._key = api_key_getter
        self._voice = voice_getter
        self._model = model_getter
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))

    @property
    def configured(self) -> bool:
        return bool(self._key())

    async def close(self) -> None:
        await self._http.aclose()

    async def synthesize(self, text: str) -> bytes:
        key = self._key()
        if not key:
            raise TTSError("ELEVENLABS_API_KEY is not set")
        spoken = clean_for_speech(text)[:1200]
        if not spoken:
            raise TTSError("nothing to say")
        url = f"{self._base}/text-to-speech/{self._voice()}"
        body = {
            "text": spoken,
            "model_id": self._model(),
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.45, "use_speaker_boost": True},
        }
        try:
            resp = await self._http.post(
                url,
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": key, "accept": "audio/mpeg"},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise TTSError(f"network error talking to ElevenLabs: {exc}") from exc
        if resp.status_code >= 400:
            detail = resp.text[:300]
            try:
                d = resp.json().get("detail")
                if isinstance(d, dict):
                    detail = d.get("message") or d.get("status") or detail
                elif isinstance(d, str):
                    detail = d
            except ValueError:
                pass
            raise TTSError(f"ElevenLabs {resp.status_code}: {detail}")
        return resp.content

    async def check(self) -> str:
        """Validate the key; returns a short human readable status."""
        key = self._key()
        if not key:
            return "not set"
        resp = await self._http.get(f"{self._base}/voices/{self._voice()}", headers={"xi-api-key": key})
        if resp.status_code == 200:
            return f"ok (voice: {resp.json().get('name', self._voice())})"
        if resp.status_code == 401:
            return "INVALID key (401). Note: a 20-character value is usually a *voice ID*, not an API key."
        if resp.status_code in (400, 404):
            return f"key looks valid but voice id {self._voice()!r} was not found"
        return f"unexpected response {resp.status_code}: {resp.text[:120]}"


class AudioCache:
    """Short-lived store for synthesized replies, keyed by an unguessable id."""

    def __init__(self, max_items: int = 40, ttl: float = 15 * 60):
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._max = max_items
        self._ttl = ttl

    def put(self, audio: bytes) -> str:
        self._evict()
        clip_id = secrets.token_urlsafe(12)
        self._items[clip_id] = (time.monotonic(), audio)
        return clip_id

    def get(self, clip_id: str) -> bytes | None:
        self._evict()
        item = self._items.get(clip_id)
        return item[1] if item else None

    def _evict(self) -> None:
        now = time.monotonic()
        for k in [k for k, (t, _) in self._items.items() if now - t > self._ttl]:
            del self._items[k]
        while len(self._items) > self._max:
            self._items.popitem(last=False)
