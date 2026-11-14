"""The companion's brain: Groq tool-calling loop with a rule-based fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from . import fallback
from .groq_client import GroqClient, GroqError
from .tools import OS_NAME, TOOL_SCHEMAS, Progress, ToolExecutor, ToolResult

log = logging.getLogger(__name__)

MAX_STEPS = 6
HISTORY_LIMIT = 12

SYSTEM_PROMPT = """You are "Desktop Friend", a cheerful, cute puppy companion who lives in the user's phone and is connected to their {os} computer named "{pc}".
You can see the PC screen and control it with tools: you have your own little blue cursor to point at things, and you can click, scroll, type, press shortcuts, open apps and websites, and search the web.

How to behave:
- Use tools whenever the user asks you to do or look at something on the PC. Never claim you did something without calling a tool.
- "Point at X" means use point_at (do not click). "Click X" means click. "Search the web for X" means web_search.
- For multi-step tasks call tools one after another (for example open_app, then type_text).
- If a tool fails, say so honestly and kindly, and suggest what the user could try.
- Your reply is spoken out loud by a text-to-speech voice: keep it to 1-2 short sentences (under 40 words), warm and playful, like an eager puppy. No markdown, no lists, no emojis, no URLs.
- When web_search returns a summary, tell the user the key facts briefly.
"""


@dataclass
class BrainResult:
    text: str
    mood: str = "happy"
    actions: list[dict] = field(default_factory=list)


def _mood_for(actions: list[dict]) -> str:
    if not actions:
        return "happy"
    if any(not a["ok"] for a in actions):
        return "sad"
    tools = {a["tool"] for a in actions}
    if tools & {"web_search", "look_at_screen"}:
        return "curious"
    if tools & {"point_at", "click", "type_text", "press_keys", "open_app", "open_website", "scroll"}:
        return "proud"
    return "happy"


def _log_entry(tool: str, result: ToolResult) -> dict:
    return {"tool": tool, "ok": result.ok, "detail": result.detail[:300]}


def _fallback_reply(tool: str, result: ToolResult) -> str:
    if not result.ok:
        return result.detail
    if tool == "web_search":
        return f"I opened the search on your PC. Here's what I found: {result.detail}"
    if tool == "look_at_screen":
        return result.detail
    friendly = {
        "point_at": "Right there!",
        "click": "Click! Done.",
        "open_app": "Opening it now!",
        "open_website": "Here you go!",
        "type_text": "All typed up!",
        "press_keys": "Pressed it!",
        "scroll": "Scrolling!",
        "cursor_home": "Back to my spot!",
    }
    return friendly.get(tool, "Done!")


class Brain:
    def __init__(self, config, groq: GroqClient, tools: ToolExecutor):
        self.cfg = config
        self.groq = groq
        self.tools = tools

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(os=OS_NAME, pc=self.cfg.pc_name)

    async def respond(self, text: str, history: list[dict], progress: Progress | None = None) -> BrainResult:
        text = text.strip()
        if not text:
            return BrainResult("I didn't catch that. Could you say it again?", "curious")

        if not self.groq.configured:
            return await self._fallback(text, progress)

        try:
            result = await self._llm_loop(text, history, progress)
        except GroqError as exc:
            log.warning("LLM failed: %s", exc)
            routed = fallback.route(text)
            if routed:
                return await self._fallback(text, progress)
            if exc.status == 401:
                return BrainResult("My Groq key doesn't seem to work. Could you check it in Settings?", "sad")
            if exc.is_model_missing:
                return BrainResult(
                    f"The Groq model {self.cfg.chat_model} isn't available. Please update GROQ_CHAT_MODEL on the PC.", "sad"
                )
            if exc.status == 429:
                return BrainResult("Whoa, I'm out of breath. Groq says we hit a rate limit, try again in a moment!", "sleepy")
            return BrainResult("Oops, my brain hiccuped. Can you try that again?", "sad")

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": result.text})
        del history[:-HISTORY_LIMIT]
        return result

    async def _llm_loop(self, text: str, history: list[dict], progress: Progress | None) -> BrainResult:
        messages: list[dict] = [{"role": "system", "content": self.system_prompt()}, *history, {"role": "user", "content": text}]
        actions: list[dict] = []
        retried = False
        step = 0
        while step < MAX_STEPS:
            step += 1
            try:
                msg = await self.groq.chat(self.cfg.chat_model, messages, tools=TOOL_SCHEMAS)
            except GroqError as exc:
                # Groq returns 400 tool_use_failed when the model emits a malformed call; one retry usually fixes it.
                if exc.code == "tool_use_failed" and not retried:
                    retried = True
                    continue
                raise
            calls = msg.get("tool_calls") or []
            if not calls:
                reply = (msg.get("content") or "").strip() or "Done!"
                return BrainResult(reply, _mood_for(actions), actions)

            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be an object")
                except ValueError as exc:
                    result = ToolResult(False, f"Invalid arguments: {exc}")
                else:
                    log.info("tool call: %s %s", name, args)
                    result = await self.tools.run(name, args, progress)
                actions.append(_log_entry(name, result))
                messages.append({"role": "tool", "tool_call_id": call.get("id", name), "content": json.dumps(result.for_llm())})
            if progress:
                r = progress("Thinking…")
                if hasattr(r, "__await__"):
                    await r

        return BrainResult("I did as much as I could! Want me to keep going?", _mood_for(actions), actions)

    async def _fallback(self, text: str, progress: Progress | None) -> BrainResult:
        routed = fallback.route(text)
        if not routed:
            return BrainResult(fallback.HELP, "curious")
        tool, args = routed
        result = await self.tools.run(tool, args, progress)
        actions = [_log_entry(tool, result)]
        return BrainResult(_fallback_reply(tool, result), _mood_for(actions), actions)
