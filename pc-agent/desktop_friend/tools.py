"""Everything the companion can *do* on the PC. Used by the LLM tool loop and by phone quick actions."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .automation import ActionOutcome, Automation, AutomationDisabled, AutomationUnavailable
from .groq_client import GroqError

log = logging.getLogger(__name__)

Progress = Callable[[str], Awaitable[None] | None]


@dataclass
class ToolResult:
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def for_llm(self) -> dict:
        return {"ok": self.ok, "result": self.detail, **self.data}


OS_NAME = "macOS" if sys.platform == "darwin" else ("Windows" if sys.platform.startswith("win") else "Linux")

# OpenAI-style function definitions understood by Groq.
TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "point_at",
            "description": "Look at the PC screen and move your blue cursor to point at an element, e.g. 'the save button'. Does NOT click.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "What to point at, described visually."}},
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Find an on-screen element and click it with the mouse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "What to click, described visually."},
                    "button": {"type": "string", "enum": ["left", "right"], "description": "Mouse button (default left)."},
                    "double": {"type": "boolean", "description": "Double-click (default false)."},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the window under your blue cursor (or the middle of the screen).",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                    "amount": {"type": "integer", "description": "How far, 1-20 (default 5)."},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text with the keyboard into whatever currently has focus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "press_enter": {"type": "boolean", "description": "Press Enter afterwards (default false)."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_keys",
            "description": "Press a key or shortcut. Use 'mod' for the main shortcut modifier (Ctrl on Windows/Linux, Cmd on macOS). Examples: ['mod','s'], ['alt','tab'], ['enter'].",
            "parameters": {
                "type": "object",
                "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application installed on the PC, e.g. 'notepad', 'calculator', 'spotify', 'chrome'.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website in the PC's default browser.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web: opens the results in the PC's browser and returns a short summary you can read back.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "look_at_screen",
            "description": "Take a screenshot of the PC and answer a question about what is visible.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "What you want to know about the screen."}},
                "required": ["question"],
            },
        },
    },
]


class ToolExecutor:
    def __init__(self, config, vision, automation: Automation, websearch, ui, sounds):
        self.cfg = config
        self.vision = vision
        self.auto = automation
        self.search = websearch
        self.ui = ui
        self.sounds = sounds

    async def _progress(self, progress: Progress | None, text: str) -> None:
        self.ui.set_status(text)
        if progress:
            r = progress(text)
            if asyncio.iscoroutine(r):
                await r

    def _need_vision(self) -> ToolResult | None:
        if not self.vision.groq.configured:
            return ToolResult(False, "I need a Groq API key before I can see the screen. Add one in Settings.")
        return None

    async def _locate(self, target: str, progress: Progress | None):
        await self._progress(progress, f"Looking for {target}…")
        return await self.vision.locate(target)

    # -- tools ----------------------------------------------------------
    async def point_at(self, target: str, progress: Progress | None = None) -> ToolResult:
        if err := self._need_vision():
            return err
        loc = await self._locate(target, progress)
        if not loc:
            self.sounds.play("error")
            return ToolResult(False, f"I couldn't find {target} on the screen.")
        await self._progress(progress, f"Pointing at {target}")
        duration = self.ui.point(loc.x, loc.y, target)
        await asyncio.sleep(duration)
        self.sounds.play("point")
        return ToolResult(True, f"Pointing at {loc.description or target}.", {"x": round(loc.x, 3), "y": round(loc.y, 3)})

    async def click(self, target: str, button: str = "left", double: bool = False, progress: Progress | None = None) -> ToolResult:
        if err := self._need_vision():
            return err
        if not self.cfg.allow_automation:
            return ToolResult(False, "Clicking is turned off on this PC (DF_ALLOW_AUTOMATION=false).")
        loc = await self._locate(target, progress)
        if not loc:
            self.sounds.play("error")
            return ToolResult(False, f"I couldn't find {target} on the screen.")
        await self._progress(progress, f"Clicking {target}")
        duration = self.ui.point(loc.x, loc.y, target)
        await asyncio.sleep(duration + 0.1)
        outcome = await self._auto(self.auto.click, loc.x, loc.y, "right" if button == "right" else "left", 2 if double else 1)
        if outcome.ok:
            self.ui.click_ripple(loc.x, loc.y)
            self.sounds.play("click")
            return ToolResult(True, f"Clicked {loc.description or target}.")
        return ToolResult(False, outcome.detail)

    async def scroll(self, direction: str, amount: int = 5, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, f"Scrolling {direction}")
        at = self.ui.cursor_position or (0.5, 0.5)
        outcome = await self._auto(self.auto.scroll, direction, amount, at)
        return ToolResult(outcome.ok, outcome.detail)

    async def type_text(self, text: str, press_enter: bool = False, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, "Typing…")
        self.sounds.play("action")
        outcome = await self._auto(self.auto.type_text, text, press_enter)
        return ToolResult(outcome.ok, outcome.detail)

    async def press_keys(self, keys: list[str] | str, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, "Pressing keys")
        outcome = await self._auto(self.auto.press_keys, keys)
        return ToolResult(outcome.ok, outcome.detail)

    async def open_app(self, name: str, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, f"Opening {name}")
        outcome = await asyncio.to_thread(self.auto.open_app, name)
        self.sounds.play("action" if outcome.ok else "error")
        return ToolResult(outcome.ok, outcome.detail)

    async def open_website(self, url: str, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, f"Opening {url}")
        outcome = await asyncio.to_thread(self.auto.open_url, url)
        self.sounds.play("action")
        return ToolResult(outcome.ok, outcome.detail)

    async def web_search(self, query: str, progress: Progress | None = None) -> ToolResult:
        await self._progress(progress, f"Searching the web for {query}")
        await asyncio.to_thread(self.auto.web_search_in_browser, query)
        self.sounds.play("action")
        summary = await self.search.summarize(query)
        return ToolResult(True, summary, {"opened_in_browser": True})

    async def look_at_screen(self, question: str = "", progress: Progress | None = None) -> ToolResult:
        if err := self._need_vision():
            return err
        await self._progress(progress, "Looking at your screen…")
        answer = await self.vision.describe(question or None)
        return ToolResult(True, answer)

    async def cursor_home(self, progress: Progress | None = None) -> ToolResult:
        self.ui.home()
        return ToolResult(True, "Blue cursor is back home.")

    async def toggle_cursor(self, progress: Progress | None = None) -> ToolResult:
        self.cfg.cursor_visible = not self.ui.visible
        self.ui.set_visible(self.cfg.cursor_visible)
        return ToolResult(True, "Blue cursor shown." if self.cfg.cursor_visible else "Blue cursor hidden.")

    # -- dispatch -------------------------------------------------------
    async def _auto(self, fn, *args) -> ActionOutcome:
        try:
            return await asyncio.to_thread(fn, *args)
        except (AutomationDisabled, AutomationUnavailable) as exc:
            return ActionOutcome(False, str(exc))
        except Exception as exc:  # pyautogui FailSafeException, display errors, ...
            name = type(exc).__name__
            if name == "FailSafeException":
                return ActionOutcome(False, "Stopped: you moved the mouse into a screen corner (safety stop).")
            log.exception("automation failed")
            return ActionOutcome(False, f"That didn't work ({name}: {exc}).")

    async def run(self, name: str, args: dict | None, progress: Progress | None = None) -> ToolResult:
        args = dict(args or {})
        try:
            if name == "point_at" or name == "point":
                return await self.point_at(str(args.get("target", "")).strip() or "it", progress)
            if name == "click":
                return await self.click(
                    str(args.get("target", "")).strip() or "it",
                    str(args.get("button", "left")),
                    bool(args.get("double", False)),
                    progress,
                )
            if name == "scroll":
                return await self.scroll(str(args.get("direction", "down")), int(args.get("amount") or 5), progress)
            if name in ("type_text", "type"):
                return await self.type_text(
                    str(args.get("text", "")), bool(args.get("press_enter", args.get("enter", False))), progress
                )
            if name in ("press_keys", "keys"):
                return await self.press_keys(args.get("keys") or [], progress)
            if name == "open_app":
                return await self.open_app(str(args.get("name", "")), progress)
            if name in ("open_website", "open_url"):
                return await self.open_website(str(args.get("url", "")), progress)
            if name == "web_search":
                return await self.web_search(str(args.get("query", "")), progress)
            if name in ("look_at_screen", "describe_screen"):
                return await self.look_at_screen(str(args.get("question", "")), progress)
            if name == "cursor_home":
                return await self.cursor_home(progress)
            if name == "toggle_cursor":
                return await self.toggle_cursor(progress)
            return ToolResult(False, f"Unknown tool {name!r}.")
        except GroqError as exc:
            log.warning("tool %s: %s", name, exc)
            if exc.is_model_missing:
                return ToolResult(False, f"The Groq vision model isn't available: {exc.message}. Update GROQ_VISION_MODEL in .env.")
            return ToolResult(False, f"My eyes aren't working right now ({exc.message}).")
        except (TypeError, ValueError) as exc:
            return ToolResult(False, f"Bad arguments for {name}: {exc}")
