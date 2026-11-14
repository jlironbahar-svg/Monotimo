import json

import pytest

from desktop_friend.agent import Agent
from desktop_friend.server import create_app

from fakes import FakeAutomation, FakeGroq, FakeSearch, FakeVision, SilentSounds, tool_call


class FakeTTS:
    configured = True

    async def synthesize(self, text):
        return b"ID3fake-mp3"

    async def close(self):
        pass


@pytest.fixture
def agent(cfg, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("desktop_friend.tools.asyncio.sleep", no_sleep)
    a = Agent(cfg)
    a.groq = FakeGroq([tool_call("point_at", {"target": "save"}), {"role": "assistant", "content": "There it is!"}])
    a.brain.groq = a.groq
    a.tools.vision = FakeVision(a.groq)
    a.vision = a.tools.vision
    a.automation = a.tools.auto = FakeAutomation()
    a.tools.search = FakeSearch()
    a.sounds = a.tools.sounds = SilentSounds()
    a.tts = FakeTTS()
    return a


async def _pair(client, agent, device="d1"):
    ws = await client.ws_connect("/ws")
    await ws.send_json({"type": "hello", "protocol": 1, "deviceId": device, "deviceName": "Pixel", "pairToken": agent.pairing.pair_token})
    welcome = await ws.receive_json()
    assert welcome["type"] == "welcome", welcome
    return ws, welcome


async def _until(ws, kind):
    seen = []
    while True:
        m = await ws.receive_json(timeout=5)
        seen.append(m)
        if m["type"] == kind:
            return m, seen


async def test_health_and_local_qr(aiohttp_client, agent):
    client = await aiohttp_client(create_app(agent))
    r = await client.get("/health")
    assert (await r.json())["protocol"] == 1
    r = await client.get("/qr.png")  # test client connects from 127.0.0.1
    assert r.status == 200 and (await r.read()).startswith(b"\x89PNG")
    r = await client.get("/")
    assert "Desktop Friend" in await r.text()


async def test_pair_chat_and_audio(aiohttp_client, agent):
    client = await aiohttp_client(create_app(agent))
    ws, welcome = await _pair(client, agent)
    assert welcome["screen"] == {"width": 1920, "height": 1080}
    assert welcome["config"]["hasGroqKey"] is False  # summary reflects config, not the fake
    assert "groq_api_key" not in json.dumps(welcome)

    await ws.send_json({"type": "chat", "id": "m1", "text": "point at save"})
    reply, seen = await _until(ws, "reply")
    states = [m["state"] for m in seen if m["type"] == "status"]
    assert states[0] == "thinking" and "acting" in states and "speaking" in states
    assert reply["text"] == "There it is!" and reply["mood"] == "proud"
    assert reply["audioUrl"].startswith("/audio/")
    audio = await client.get(reply["audioUrl"])
    assert audio.status == 200 and await audio.read() == b"ID3fake-mp3"
    assert (await client.get("/audio/notarealclip.mp3")).status == 404

    # reconnect with the device token
    await ws.close()
    ws2 = await client.ws_connect("/ws")
    await ws2.send_json({"type": "hello", "protocol": 1, "deviceId": "d1", "deviceName": "Pixel", "deviceToken": welcome["deviceToken"]})
    assert (await ws2.receive_json())["type"] == "welcome"


async def test_rejects_bad_auth_and_protocol(aiohttp_client, agent):
    client = await aiohttp_client(create_app(agent))
    ws = await client.ws_connect("/ws")
    await ws.send_json({"type": "hello", "protocol": 1, "deviceId": "x", "deviceName": "?", "pairToken": "guess"})
    assert (await ws.receive_json())["code"] == "auth_failed"
    ws = await client.ws_connect("/ws")
    await ws.send_json({"type": "hello", "protocol": 99, "deviceId": "x", "deviceName": "?", "pairToken": agent.pairing.pair_token})
    assert (await ws.receive_json())["code"] == "protocol_mismatch"
    ws = await client.ws_connect("/ws")
    await ws.send_json({"type": "chat", "text": "skip hello"})
    assert (await ws.receive_json())["code"] == "bad_request"


async def test_quick_actions_screenshot_config_ping(aiohttp_client, agent, cfg):
    client = await aiohttp_client(create_app(agent))
    ws, _ = await _pair(client, agent)
    await ws.send_json({"type": "action", "id": "a1", "action": "open_app", "args": {"name": "Spotify"}})
    res, _ = await _until(ws, "action_result")
    assert res == {"type": "action_result", "id": "a1", "action": "open_app", "ok": True, "detail": "opened Spotify"}
    await ws.send_json({"type": "action", "id": "a2", "action": "rm_rf", "args": {}})
    err, _ = await _until(ws, "error")
    assert err["code"] == "bad_request"
    await ws.send_json({"type": "screenshot", "id": "s1"})
    shot, _ = await _until(ws, "screenshot")
    assert shot["width"] == 320 and shot["image"] == "aGVsbG8="
    await ws.send_json({"type": "ping", "t": 42})
    assert (await _until(ws, "pong"))[0]["t"] == 42
    await ws.send_json({"type": "config", "id": "c1", "groqApiKey": "gsk_test123", "pcSounds": True})
    conf, _ = await _until(ws, "config")
    assert conf["config"]["hasGroqKey"] is True and conf["config"]["pcSounds"] is True
    assert "gsk_test123" not in json.dumps(conf)
    assert "GROQ_API_KEY=gsk_test123" in cfg.env_path.read_text()


async def test_voice_requires_key_and_transcribes(aiohttp_client, agent, cfg):
    import base64

    client = await aiohttp_client(create_app(agent))
    agent.groq._configured = False
    ws, _ = await _pair(client, agent)
    audio = base64.b64encode(b"\x00" * 4000).decode()
    await ws.send_json({"type": "voice", "id": "v1", "audio": audio, "mime": "audio/m4a"})
    err, _ = await _until(ws, "error")
    assert err["code"] == "not_configured"
    cfg.groq_api_key = "gsk_x"
    agent.groq._configured = True
    await ws.send_json({"type": "voice", "id": "v2", "audio": audio, "mime": "audio/m4a"})
    transcript, _ = await _until(ws, "transcript")
    assert transcript["text"] == "point at the save button"
    reply, _ = await _until(ws, "reply")
    assert reply["id"] == "v2"


async def test_apps_list_and_shortcut(aiohttp_client, agent):
    client = await aiohttp_client(create_app(agent))
    ws, _ = await _pair(client, agent)
    await ws.send_json({"type": "apps", "id": "l1"})
    msg, _ = await _until(ws, "apps")
    assert msg == {"type": "apps", "id": "l1", "apps": ["Claude", "Spotify", "Visual Studio Code"]}
    await ws.send_json({"type": "action", "id": "k1", "action": "shortcut", "args": {"name": "screenshot"}})
    res, _ = await _until(ws, "action_result")
    assert res["ok"] and ("shortcut", "screenshot") in agent.automation.calls
