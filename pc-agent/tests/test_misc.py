import io
import wave

from desktop_friend.automation import looks_like_url, normalize_keys, normalize_url
from desktop_friend.config import Config
from desktop_friend.sounds import synth_all
from desktop_friend.tts import AudioCache, clean_for_speech
from desktop_friend.websearch import parse_ddg_html


def test_keys():
    import sys

    mod = "command" if sys.platform == "darwin" else "ctrl"
    assert normalize_keys(["Mod", "S"]) == [mod, "s"]
    assert normalize_keys("ctrl+shift+Escape") == ["ctrl", "shift", "esc"]
    assert normalize_keys(["Return"]) == ["enter"]


def test_urls():
    assert looks_like_url("youtube.com") and looks_like_url("https://x.org/a")
    assert not looks_like_url("notepad") and not looks_like_url("visual studio code")
    assert normalize_url("example.com") == "https://example.com"


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nGROQ_API_KEY=\nDF_PORT=9999\n")
    c = Config.load(env, create_if_missing=False)
    assert c.port == 9999 and c.groq_api_key == ""
    changed = c.update_from_phone({"groqApiKey": " gsk_abc ", "elevenLabsVoiceId": "", "cursorVisible": False, "bogus": 1})
    assert set(changed) == {"GROQ_API_KEY", "DF_CURSOR_VISIBLE"}  # empty voice id resets to the default (unchanged)
    again = Config.load(env, create_if_missing=False)
    assert again.groq_api_key == "gsk_abc" and again.cursor_visible is False
    assert "# comment" in env.read_text()


def test_env_var_overrides_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GROQ_CHAT_MODEL=from-file\n")
    monkeypatch.setenv("GROQ_CHAT_MODEL", "from-env")
    assert Config.load(env, create_if_missing=False).chat_model == "from-env"


def test_sounds_are_valid_wavs():
    for name, data in synth_all().items():
        with wave.open(io.BytesIO(data)) as w:
            assert w.getnchannels() == 1 and w.getframerate() == 22050 and w.getnframes() > 100, name


def test_speech_cleanup_and_cache():
    assert clean_for_speech("**Hi** there 🐶! See https://x.com") == "Hi there ! See a link"
    cache = AudioCache(max_items=2)
    a, b, c = cache.put(b"a"), cache.put(b"b"), cache.put(b"c")
    assert cache.get(a) is None and cache.get(c) == b"c"


def test_ddg_parser():
    page = '<a class="result__a" href="#">Paris <b>weather</b></a> ... <a class="result__snippet">Sunny, 21&deg;C</a>'
    assert parse_ddg_html(page) == [("Paris weather", "Sunny, 21°C")]


async def test_no_display_gives_friendly_error(cfg, monkeypatch):
    import builtins

    from desktop_friend.automation import Automation
    from desktop_friend.tools import ToolExecutor
    from desktop_friend.ui import NullBridge

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pyautogui":
            raise KeyError("DISPLAY")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    tools = ToolExecutor(cfg, None, Automation(cfg), None, NullBridge(), type("S", (), {"play": lambda *_: None})())
    result = await tools.run("scroll", {"direction": "down"})
    assert not result.ok and "can't reach the desktop" in result.detail


def test_lan_addresses_is_bounded(monkeypatch):
    import time

    from desktop_friend import netinfo

    def slow_getaddrinfo(*a, **k):
        time.sleep(5)
        return []

    monkeypatch.setattr(netinfo.socket, "getaddrinfo", slow_getaddrinfo)
    start = time.monotonic()
    assert netinfo.lan_addresses()  # always returns at least one address
    assert time.monotonic() - start < 3
