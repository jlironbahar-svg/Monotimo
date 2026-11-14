import pytest

from desktop_friend.brain import Brain
from desktop_friend.groq_client import GroqError
from desktop_friend.tools import ToolExecutor
from desktop_friend.ui import NullBridge

from fakes import FakeAutomation, FakeGroq, FakeSearch, FakeVision, SilentSounds, tool_call


def make(cfg, replies=None, configured=True, point=(0.25, 0.5)):
    groq = FakeGroq(replies, configured)
    vision = FakeVision(groq, point)
    auto = FakeAutomation()
    ui = NullBridge()
    sounds = SilentSounds()
    tools = ToolExecutor(cfg, vision, auto, FakeSearch(), ui, sounds)
    return Brain(cfg, groq, tools), groq, vision, auto, ui, sounds


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("desktop_friend.tools.asyncio.sleep", no_sleep)


async def test_point_tool_loop(cfg):
    brain, groq, vision, auto, ui, sounds = make(
        cfg, [tool_call("point_at", {"target": "save button"}), {"role": "assistant", "content": "It's right there!"}]
    )
    history = []
    result = await brain.respond("Point at the save button", history)
    assert result.text == "It's right there!"
    assert result.mood == "proud"
    assert result.actions == [{"tool": "point_at", "ok": True, "detail": "Pointing at the save button."}]
    assert vision.located == ["save button"]
    assert ui.cursor_position == (0.25, 0.5)
    assert auto.calls == [], "pointing must never click"
    assert "point" in sounds.played
    # tool result was fed back to the model with the matching id
    tool_msgs = [m for m in groq.calls[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["tool_call_id"] == "call_1"
    assert history[-1] == {"role": "assistant", "content": "It's right there!"}


async def test_click_moves_cursor_then_clicks(cfg):
    brain, _, _, auto, ui, sounds = make(
        cfg, [tool_call("click", {"target": "OK", "double": True}), {"role": "assistant", "content": "Clicked!"}], point=(0.6, 0.4)
    )
    result = await brain.respond("double click OK", [])
    assert auto.calls == [("click", 0.6, 0.4, "left", 2)]
    assert ui.cursor_position == (0.6, 0.4)
    assert result.actions[0]["ok"]
    assert "click" in sounds.played


async def test_click_not_found(cfg):
    brain, *_ = make(cfg, [tool_call("click", {"target": "unicorn"}), {"role": "assistant", "content": "Can't see it"}], point=None)
    result = await brain.respond("click the unicorn", [])
    assert result.mood == "sad"
    assert result.actions[0] == {"tool": "click", "ok": False, "detail": "I couldn't find unicorn on the screen."}


async def test_automation_disabled(cfg):
    cfg.allow_automation = False
    brain, _, _, auto, _, _ = make(cfg, [tool_call("click", {"target": "OK"}), {"role": "assistant", "content": "nope"}])
    result = await brain.respond("click OK", [])
    assert auto.calls == []
    assert not result.actions[0]["ok"]


async def test_scroll_uses_blue_cursor_position(cfg):
    brain, _, _, auto, ui, _ = make(cfg, [tool_call("scroll", {"direction": "down", "amount": 3}), {"role": "assistant", "content": "ok"}])
    await brain.respond("scroll down", [])
    assert auto.calls == [("scroll", "down", 3, (0.5, 0.5))], "cursor at home -> scroll middle of the screen"
    ui.point(0.2, 0.3)
    brain.groq.replies = [tool_call("scroll", {"direction": "up"}), {"role": "assistant", "content": "ok"}]
    await brain.respond("scroll up", [])
    assert auto.calls[-1] == ("scroll", "up", 5, (0.2, 0.3))


async def test_multi_step_and_bad_arguments(cfg):
    bad = tool_call("type_text", {"text": "x"})
    bad["tool_calls"][0]["function"]["arguments"] = "{not json"
    brain, _, _, auto, _, _ = make(
        cfg,
        [tool_call("open_app", {"name": "notepad"}), bad, tool_call("type_text", {"text": "hi", "press_enter": True}, "c3"),
         {"role": "assistant", "content": "Typed it!"}],
    )
    result = await brain.respond("open notepad and type hi", [])
    assert [a["ok"] for a in result.actions] == [True, False, True]
    assert auto.calls == [("open_app", "notepad"), ("type", "hi", True)]


async def test_web_search_reads_back(cfg):
    brain, groq, _, auto, _, _ = make(cfg, [tool_call("web_search", {"query": "weather paris"}), {"role": "assistant", "content": "Sunny!"}])
    result = await brain.respond("search the web for weather paris", [])
    assert ("search", "weather paris") in auto.calls
    assert result.mood == "curious"
    assert "Top result about weather paris" in groq.calls[1]["messages"][-1]["content"]


async def test_tool_use_failed_is_retried(cfg):
    brain, groq, *_ = make(cfg, [GroqError(400, "bad tool", "tool_use_failed"), {"role": "assistant", "content": "Hi!"}])
    assert (await brain.respond("hello", [])).text == "Hi!"
    assert len(groq.calls) == 2


async def test_no_key_uses_rule_router(cfg):
    brain, groq, _, auto, _, _ = make(cfg, configured=False)
    result = await brain.respond("open calculator", [])
    assert auto.calls == [("open_app", "calculator")]
    assert groq.calls == []
    result = await brain.respond("point at the save button", [])
    assert "Groq API key" in result.text
    result = await brain.respond("tell me a joke", [])
    assert "Groq API key" in result.text


async def test_llm_outage_falls_back(cfg):
    brain, _, _, auto, _, _ = make(cfg, [GroqError(503, "down")])
    result = await brain.respond("scroll down", [])
    assert auto.calls[0][0] == "scroll"
    brain.groq.replies = [GroqError(401, "bad key")]
    result = await brain.respond("how are you", [])
    assert "key" in result.text.lower()


async def test_history_is_bounded(cfg):
    brain, *_ = make(cfg)
    history = []
    for i in range(20):
        await brain.respond(f"hi {i}", history)
    assert len(history) == 12
