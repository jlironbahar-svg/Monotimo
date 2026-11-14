"""The agent must recover by itself when Groq retires a model (e.g. the Llama 4 vision model)."""
from PIL import Image

from desktop_friend.groq_client import GroqError
from desktop_friend.models import ModelResolver, is_unusable_model_error, rank_vision_candidates
from desktop_friend.vision import Vision

RETIRED = "meta-llama/llama-4-scout-17b-16e-instruct"


class AccountGroq:
    """Fake Groq account: `models` exist, `vision_ok` accept images, everything else 404s."""

    configured = True

    def __init__(self, models, vision_ok, chat_ok=None):
        self.models = models
        self.vision_ok = set(vision_ok)
        self.chat_ok = set(chat_ok or models)
        self.vision_calls = []

    async def list_models(self):
        return list(self.models)

    async def vision(self, model, prompt, jpeg, system=None, json_mode=False):
        self.vision_calls.append(model)
        if model not in self.models:
            raise GroqError(404, f"The model `{model}` has been decommissioned", "model_decommissioned")
        if model not in self.vision_ok:
            raise GroqError(400, "messages[1].content must be a string", "invalid_request_error")
        if "Find this element" in prompt:
            return '{"found": true, "x": 500, "y": 500, "description": "Save"}'
        return "Blue."

    async def chat(self, model, messages, tools=None, **kw):
        if model not in self.chat_ok:
            raise GroqError(404, f"The model `{model}` does not exist", "model_not_found")
        return {"role": "assistant", "content": "hi"}


class StubCapture:
    def grab(self):
        return Image.new("RGB", (1280, 800), "white")


def test_error_classification():
    assert is_unusable_model_error(GroqError(404, "nope", "model_not_found"))
    assert is_unusable_model_error(GroqError(400, "The model `x` has been decommissioned and is no longer supported", "invalid_request_error"))
    assert is_unusable_model_error(GroqError(400, "content must be a string", "x"), needs_images=True)
    assert not is_unusable_model_error(GroqError(400, "content must be a string", "x"))
    assert not is_unusable_model_error(GroqError(429, "slow down", "rate_limit"))
    assert not is_unusable_model_error(ValueError("x"))


def test_vision_ranking_prefers_known_then_hints():
    models = ["llama-3.3-70b-versatile", "whisper-large-v3", "acme/new-vl-9b", "meta-llama/llama-4-maverick-17b-128e-instruct"]
    ranked = rank_vision_candidates(models, exclude=set())
    assert ranked[:2] == ["meta-llama/llama-4-maverick-17b-128e-instruct", "acme/new-vl-9b"]
    assert "whisper-large-v3" not in ranked


async def test_retired_vision_model_is_replaced_and_saved(cfg):
    cfg.vision_model = RETIRED  # what the user's .env had
    groq = AccountGroq(models=["openai/gpt-oss-120b", "acme/new-vl-9b"], vision_ok=["acme/new-vl-9b"])
    resolver = ModelResolver(groq, cfg)
    vision = Vision(groq, lambda: cfg.vision_model, lambda: False, StubCapture(), models=resolver)
    res = await vision.locate("save button")
    assert res is not None and (round(res.x, 2), round(res.y, 2)) == (0.5, 0.5)
    assert cfg.vision_model == "acme/new-vl-9b"
    assert "GROQ_VISION_MODEL=acme/new-vl-9b" in cfg.env_path.read_text()
    # next call goes straight to the working model
    groq.vision_calls.clear()
    await vision.describe()
    assert groq.vision_calls == ["acme/new-vl-9b"]


async def test_text_only_models_are_skipped(cfg):
    cfg.vision_model = "auto"
    groq = AccountGroq(models=["llama-3.3-70b-versatile", "qwen/qwen3-vl-32b-instruct"], vision_ok=["qwen/qwen3-vl-32b-instruct"])
    resolver = ModelResolver(groq, cfg)
    assert await resolver.ensure("vision") == "qwen/qwen3-vl-32b-instruct"


async def test_no_vision_model_gives_clear_error(cfg):
    cfg.vision_model = RETIRED
    groq = AccountGroq(models=["llama-3.3-70b-versatile"], vision_ok=[])
    vision = Vision(groq, lambda: cfg.vision_model, lambda: False, StubCapture(), models=ModelResolver(groq, cfg))
    try:
        await vision.describe()
    except GroqError as exc:
        assert "no vision-capable" in exc.message
    else:
        raise AssertionError("expected GroqError")


async def test_startup_check_fixes_chat_and_stt(cfg):
    cfg.chat_model = "retired-chat"
    cfg.stt_model = "whisper-old"
    cfg.vision_model = "auto"
    groq = AccountGroq(models=["llama-3.3-70b-versatile", "whisper-large-v3", "groq/compound", "acme/vision-1"], vision_ok=["acme/vision-1"])
    await ModelResolver(groq, cfg).startup_check()
    assert (cfg.chat_model, cfg.stt_model, cfg.search_model, cfg.vision_model) == (
        "llama-3.3-70b-versatile", "whisper-large-v3", "groq/compound", "acme/vision-1",
    )


async def test_brain_heals_chat_model(cfg):
    from desktop_friend.brain import Brain

    cfg.chat_model = "retired-chat"
    groq = AccountGroq(models=["openai/gpt-oss-20b"], vision_ok=[])
    brain = Brain(cfg, groq, tools=None, models=ModelResolver(groq, cfg))
    assert (await brain.respond("hello", [])).text == "hi"
    assert cfg.chat_model == "openai/gpt-oss-20b"
