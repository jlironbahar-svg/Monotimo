"""Test doubles for Groq, vision and automation."""
import json

from desktop_friend.automation import ActionOutcome
from desktop_friend.groq_client import GroqError
from desktop_friend.vision import LocateResult


class FakeGroq:
    def __init__(self, replies=None, configured=True):
        self.replies = list(replies or [])
        self.calls = []
        self._configured = configured

    @property
    def configured(self):
        return self._configured

    async def chat(self, model, messages, tools=None, **kw):
        self.calls.append({"model": model, "messages": [dict(m) for m in messages], "tools": tools})
        if not self.replies:
            return {"role": "assistant", "content": "Done!"}
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def transcribe(self, model, audio, filename="voice.m4a", mime="audio/m4a"):
        return "point at the save button"

    async def close(self):
        pass


def tool_call(name, args, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}],
    }


class FakeVision:
    def __init__(self, groq, point=(0.25, 0.5)):
        self.groq = groq
        self.point = point
        self.located = []

    async def locate(self, target):
        self.located.append(target)
        if self.point is None:
            return None
        return LocateResult(self.point[0], self.point[1], f"the {target}")

    async def describe(self, question=None):
        return "A text editor with a Save button."

    async def thumbnail(self, max_width=900):
        return "aGVsbG8=", 320, 200


class FakeAutomation:
    def __init__(self):
        self.calls = []

    def click(self, x, y, button="left", clicks=1):
        self.calls.append(("click", round(x, 3), round(y, 3), button, clicks))
        return ActionOutcome(True, "clicked")

    def scroll(self, direction, amount=5, at=None):
        self.calls.append(("scroll", direction, amount, at))
        return ActionOutcome(True, f"scrolled {direction} {amount}")

    def type_text(self, text, enter=False):
        self.calls.append(("type", text, enter))
        return ActionOutcome(True, f"typed {len(text)} characters")

    def press_keys(self, keys):
        self.calls.append(("keys", keys))
        return ActionOutcome(True, "pressed")

    def open_app(self, name):
        self.calls.append(("open_app", name))
        return ActionOutcome(True, f"opened {name}")

    def open_url(self, url):
        self.calls.append(("open_url", url))
        return ActionOutcome(True, f"opened {url}")

    def web_search_in_browser(self, query):
        self.calls.append(("search", query))
        return ActionOutcome(True, "searched")

    def screen_size(self):
        return 1920, 1080


class FakeSearch:
    async def summarize(self, query):
        return f"Top result about {query}."


class SilentSounds:
    def __init__(self):
        self.played = []

    def play(self, name):
        self.played.append(name)


__all__ = ["FakeGroq", "FakeVision", "FakeAutomation", "FakeSearch", "SilentSounds", "tool_call", "GroqError"]


def _fake_run_shortcut(self, name):
    self.calls.append(("shortcut", name))
    return ActionOutcome(True, name)


def _fake_installed_apps(self):
    return ["Claude", "Spotify", "Visual Studio Code"]


FakeAutomation.run_shortcut = _fake_run_shortcut
FakeAutomation.installed_apps = _fake_installed_apps
