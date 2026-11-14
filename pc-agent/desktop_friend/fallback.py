"""Rule-based intent router used when no Groq key is set or the LLM is unreachable."""

from __future__ import annotations

import re

_RULES: list[tuple[re.Pattern, callable]] = []


def _rule(pattern: str):
    def deco(fn):
        _RULES.append((re.compile(pattern, re.IGNORECASE), fn))
        return fn

    return deco


def _clean(s: str) -> str:
    return s.strip().strip(".!?").strip().strip('"').strip("'").strip()


@_rule(r"^(?:please\s+)?(?:search|google|look up)(?:\s+(?:the\s+)?(?:web|internet|online))?(?:\s+for)?\s+(?P<q>.+)$")
def _search(m):
    return "web_search", {"query": _clean(m.group("q"))}


@_rule(r"^(?:please\s+)?(?:point|show me)(?:\s+(?:at|to|where))?\s+(?P<t>.+)$")
def _point(m):
    return "point_at", {"target": _clean(m.group("t"))}


@_rule(r"^(?:please\s+)?(?P<kind>double[- ]?click|right[- ]?click|click|tap|press)\s+(?:on\s+)?(?P<t>.+)$")
def _click(m):
    kind = m.group("kind").lower().replace("-", " ")
    target = _clean(m.group("t"))
    if kind == "press" and (len(target.split()) <= 2 and ("+" in target or target.lower() in _KEYS)):
        return "press_keys", {"keys": re.split(r"[+\s]+", target.lower())}
    return "click", {"target": target, "double": kind.startswith("double"), "button": "right" if kind.startswith("right") else "left"}


@_rule(r"^(?:please\s+)?scroll\s+(?P<d>up|down|left|right)(?:\s+(?:by\s+)?(?P<n>\d+))?")
def _scroll(m):
    return "scroll", {"direction": m.group("d").lower(), "amount": int(m.group("n") or 5)}


@_rule(r"^(?:please\s+)?(?:type|write)\s+(?P<t>.+)$")
def _type(m):
    text = m.group("t").strip()
    enter = False
    for suffix in (" and press enter", " then press enter", " and hit enter"):
        if text.lower().endswith(suffix):
            text, enter = text[: -len(suffix)], True
    return "type_text", {"text": text.strip().strip('"').strip("'"), "press_enter": enter}


@_rule(r"^(?:please\s+)?(?:go to|open|visit)\s+(?P<u>(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/\S*)?)$")
def _url(m):
    return "open_website", {"url": m.group("u")}


@_rule(r"^(?:please\s+)?(?:open|launch|start|run)\s+(?P<a>.+)$")
def _app(m):
    return "open_app", {"name": _clean(m.group("a")).removeprefix("the ").removeprefix("my ")}


@_rule(r"(?:what(?:'s| is)\s+on\s+(?:my\s+|the\s+)?screen|describe\s+(?:my\s+|the\s+)?screen|what do you see)")
def _look(m):
    return "look_at_screen", {"question": "What is on my screen?"}


@_rule(r"^(?:come back|go home|cursor home|reset cursor)")
def _home(m):
    return "cursor_home", {}


_KEYS = {
    "enter", "return", "escape", "esc", "tab", "space", "backspace", "delete", "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown", "f5", "f11",
}


def route(text: str) -> tuple[str, dict] | None:
    t = text.strip()
    for pattern, fn in _RULES:
        m = pattern.search(t)
        if m:
            return fn(m)
    return None


HELP = (
    "I can do simple commands like 'open notepad', 'search the web for puppies', 'scroll down' or "
    "'type hello'. Add a Groq API key in Settings so I can really chat and see your screen!"
)
