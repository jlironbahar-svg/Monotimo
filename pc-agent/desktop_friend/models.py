"""Self-healing Groq model selection.

Groq retires models from time to time (that's what broke "point at ..." when the Llama 4 vision
model was removed). Instead of asking the user to edit .env, the agent:

1. on startup, checks the configured models against the account's live model list, and
2. whenever a call fails because a model is gone or can't take images, finds a working
   replacement, saves it to .env, and retries.

Any setting can also be "auto" to always pick automatically.
"""

from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image

from .groq_client import GroqClient, GroqError

log = logging.getLogger(__name__)

# Known-good choices, best first. Unknown future models are still found by the keyword hints below.
VISION_PREFERRED = [
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-vl-235b-a22b-instruct",
    "qwen/qwen3-vl-32b-instruct",
    "qwen/qwen2.5-vl-72b-instruct",
    "moonshotai/kimi-vl-a3b-instruct",
    "google/gemma-3-27b-it",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]
VISION_HINTS = ("vision", "-vl", "vl-", "/vl", "llava", "pixtral", "llama-4", "maverick", "scout", "gemma-3", "omni", "multimodal")

CHAT_PREFERRED = [
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
]
STT_PREFERRED = ["whisper-large-v3-turbo", "whisper-large-v3", "distil-whisper-large-v3-en"]
SEARCH_PREFERRED = ["groq/compound-mini", "groq/compound"]

NON_CHAT = ("whisper", "tts", "playai", "orpheus", "guard", "embed", "compound", "allam")

SETTING = {
    "vision": ("vision_model", "GROQ_VISION_MODEL"),
    "chat": ("chat_model", "GROQ_CHAT_MODEL"),
    "stt": ("stt_model", "GROQ_STT_MODEL"),
    "search": ("search_model", "GROQ_SEARCH_MODEL"),
}


def is_unusable_model_error(exc: Exception, needs_images: bool = False) -> bool:
    """True when the error means "this model can't do the job", so another model might."""
    if not isinstance(exc, GroqError):
        return False
    if exc.is_model_missing or exc.code in {"model_terminated", "model_not_active"}:
        return True
    msg = (exc.message or "").lower()
    if exc.status in (400, 404) and ("decommission" in msg or "does not exist" in msg or "not found" in msg or "no longer supported" in msg):
        return True
    if needs_images and exc.status == 400 and any(w in msg for w in ("image", "vision", "multimodal", "content must be a string", "image_url")):
        return True
    return False


def _tiny_jpeg() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), (47, 123, 255))
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def rank_vision_candidates(models: list[str], exclude: set[str]) -> list[str]:
    available = [m for m in models if m not in exclude]
    ordered = [m for m in VISION_PREFERRED if m in available]
    ordered += [m for m in available if m not in ordered and any(h in m.lower() for h in VISION_HINTS)]
    # last resort: any other chat model (some accept images without saying so in the name)
    ordered += [m for m in available if m not in ordered and not any(n in m.lower() for n in NON_CHAT)]
    return ordered


def pick_first(models: list[str], preferred: list[str], must_contain: str | None = None, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    for m in preferred:
        if m in models and m not in exclude:
            return m
    for m in models:
        if m in exclude:
            continue
        low = m.lower()
        if must_contain and must_contain in low:
            return m
        if must_contain is None and not any(n in low for n in NON_CHAT):
            return m
    return None


class ModelResolver:
    MAX_VISION_TRIES = 10

    def __init__(self, groq: GroqClient, config, on_change=None):
        self.groq = groq
        self.cfg = config
        self.on_change = on_change  # called with (kind, model) after a switch
        self._lock = asyncio.Lock()
        self._bad: dict[str, set[str]] = {k: set() for k in SETTING}
        self._models: list[str] | None = None

    def current(self, kind: str) -> str:
        return getattr(self.cfg, SETTING[kind][0])

    def _set(self, kind: str, model: str) -> None:
        attr, env_key = SETTING[kind]
        old = getattr(self.cfg, attr)
        setattr(self.cfg, attr, model)
        self.cfg.persist(env_key, model)
        log.warning("Groq %s model %r is not usable; switched to %r (saved to .env)", kind, old, model)
        if self.on_change:
            self.on_change(kind, model)

    async def available_models(self, refresh: bool = False) -> list[str]:
        if self._models is None or refresh:
            self._models = await self.groq.list_models()
        return self._models

    async def _vision_works(self, model: str) -> bool:
        try:
            await self.groq.vision(model, "What colour is this image? Answer in one word.", _tiny_jpeg())
            return True
        except GroqError as exc:
            log.info("vision candidate %s rejected: %s", model, exc.message[:120])
            return False

    async def fix(self, kind: str, failed: str | None = None) -> str | None:
        """Find a working replacement for `kind`. Returns the new model or None."""
        async with self._lock:
            current = self.current(kind)
            if failed and failed != current and current != "auto":
                return current  # someone else already fixed it while we waited
            if failed:
                self._bad[kind].add(failed)
            try:
                models = await self.available_models(refresh=True)
            except GroqError as exc:
                log.warning("could not list Groq models: %s", exc)
                return None
            exclude = set(self._bad[kind])
            if kind == "vision":
                for candidate in rank_vision_candidates(models, exclude)[: self.MAX_VISION_TRIES]:
                    if await self._vision_works(candidate):
                        self._set(kind, candidate)
                        return candidate
                    self._bad[kind].add(candidate)
                return None
            if kind == "chat":
                choice = pick_first(models, CHAT_PREFERRED, exclude=exclude)
            elif kind == "stt":
                choice = pick_first(models, STT_PREFERRED, must_contain="whisper", exclude=exclude)
            else:
                choice = pick_first(models, SEARCH_PREFERRED, must_contain="compound", exclude=exclude)
            if choice:
                self._set(kind, choice)
            return choice

    async def ensure(self, kind: str) -> str:
        """Return a usable model id, resolving "auto" (or a missing model) first."""
        model = self.current(kind)
        if model and model != "auto":
            return model
        fixed = await self.fix(kind, failed=None)
        if not fixed:
            raise GroqError(404, f"No Groq {kind} model is available on this account.", "model_not_found")
        return fixed

    async def startup_check(self) -> None:
        """Replace configured models that no longer exist. Runs in the background; never raises."""
        if not self.groq.configured:
            return
        try:
            models = await self.available_models(refresh=True)
        except Exception as exc:  # offline, bad key, ...
            log.info("model check skipped: %s", exc)
            return
        for kind in SETTING:
            model = self.current(kind)
            if model == "auto" or model not in models:
                if model != "auto":
                    log.warning("Configured Groq %s model %r is not on your account any more", kind, model)
                try:
                    await self.fix(kind, failed=None if model == "auto" else model)
                except Exception:  # keep going with the other kinds
                    log.exception("could not pick a %s model", kind)
