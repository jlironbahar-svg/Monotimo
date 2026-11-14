"""One WebSocket connection from a phone."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import secrets
import sys
from typing import Any

from aiohttp import WSMsgType, web

from .protocol import PROTOCOL_VERSION, QUICK_ACTIONS
from .tts import TTSError

log = logging.getLogger(__name__)

HELLO_TIMEOUT = 15
_EXT_FOR_MIME = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/flac": "flac",
}


class Session:
    def __init__(self, agent, ws: web.WebSocketResponse, remote: str):
        self.agent = agent
        self.ws = ws
        self.remote = remote
        self.id = secrets.token_hex(4)
        self.device_name = "Phone"
        self.history: list[dict] = []
        self._send_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._tts_warned = False

    # ------------------------------------------------------------------
    async def send(self, msg: dict) -> None:
        if self.ws.closed:
            return
        async with self._send_lock:
            try:
                await self.ws.send_str(json.dumps(msg))
            except (ConnectionResetError, RuntimeError) as exc:
                log.debug("send failed: %s", exc)

    async def error(self, code: str, message: str, msg_id: str | None = None) -> None:
        payload: dict[str, Any] = {"type": "error", "code": code, "message": message}
        if msg_id:
            payload["id"] = msg_id
        await self.send(payload)

    async def status(self, state: str, detail: str = "", msg_id: str | None = None) -> None:
        payload: dict[str, Any] = {"type": "status", "state": state}
        if detail:
            payload["detail"] = detail
        if msg_id:
            payload["id"] = msg_id
        await self.send(payload)

    # ------------------------------------------------------------------
    async def run(self) -> None:
        if not await self._handshake():
            await self.ws.close()
            return
        self.agent.connected[self.id] = self.device_name
        self.agent.ui.device_event(self.device_name, True)
        try:
            async for raw in self.ws:
                if raw.type == WSMsgType.TEXT:
                    await self._dispatch(raw.data)
                elif raw.type == WSMsgType.ERROR:
                    log.info("ws error from %s: %s", self.device_name, self.ws.exception())
                    break
        finally:
            for t in list(self._tasks):
                t.cancel()
            self.agent.connected.pop(self.id, None)
            self.agent.ui.device_event(self.device_name, False)

    async def _handshake(self) -> bool:
        try:
            raw = await self.ws.receive(timeout=HELLO_TIMEOUT)
        except asyncio.TimeoutError:
            return False
        if raw.type != WSMsgType.TEXT:
            return False
        try:
            hello = json.loads(raw.data)
        except ValueError:
            await self.error("bad_request", "First message must be JSON hello")
            return False
        if hello.get("type") != "hello":
            await self.error("bad_request", "First message must be hello")
            return False
        if int(hello.get("protocol", 0)) != PROTOCOL_VERSION:
            await self.error(
                "protocol_mismatch",
                f"PC speaks protocol v{PROTOCOL_VERSION}, phone sent v{hello.get('protocol')}. Update both apps.",
            )
            return False

        device_id = str(hello.get("deviceId") or "")[:80]
        self.device_name = str(hello.get("deviceName") or "Phone")[:64]
        if not device_id:
            await self.error("bad_request", "deviceId missing")
            return False

        pairing = self.agent.pairing
        if hello.get("deviceToken") and pairing.check_device_token(device_id, hello["deviceToken"]):
            token = hello["deviceToken"]
            first_time = False
        elif hello.get("pairToken") and pairing.check_pair_token(hello["pairToken"]):
            token = pairing.register_device(device_id, self.device_name)
            first_time = True
        else:
            await self.error("auth_failed", "This phone isn't paired with the PC (or the QR code changed). Scan the QR code again.")
            log.warning("rejected connection from %s (%s)", self.remote, self.device_name)
            return False

        w, h = await asyncio.to_thread(self.agent.automation.screen_size)
        await self.send(
            {
                "type": "welcome",
                "protocol": PROTOCOL_VERSION,
                "pcName": self.agent.cfg.pc_name,
                "platform": sys.platform,
                "deviceToken": token,
                "screen": {"width": w, "height": h},
                "config": self.agent.cfg.summary(),
            }
        )
        log.info("%s %s from %s", "paired" if first_time else "connected", self.device_name, self.remote)
        if first_time:
            self.agent.sounds.play("paired")
        return True

    # ------------------------------------------------------------------
    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _dispatch(self, data: str) -> None:
        try:
            msg = json.loads(data)
            mtype = msg["type"]
        except (ValueError, KeyError, TypeError):
            await self.error("bad_request", "Malformed message")
            return
        msg_id = str(msg.get("id") or "") or None

        if mtype == "ping":
            await self.send({"type": "pong", "t": msg.get("t", 0)})
        elif mtype == "config":
            changed = self.agent.cfg.update_from_phone(msg)
            if "DF_CURSOR_VISIBLE" in changed:
                self.agent.ui.set_visible(self.agent.cfg.cursor_visible)
            if changed:
                log.info("settings updated from phone: %s", ", ".join(changed))
                self.agent.ui.config_changed()
            await self.send({"type": "config", "id": msg_id, "config": self.agent.cfg.summary()})
        elif mtype == "chat":
            self._spawn(self._handle_chat(msg_id or "", str(msg.get("text", "")), bool(msg.get("speak", True))))
        elif mtype == "voice":
            self._spawn(self._handle_voice(msg_id or "", msg))
        elif mtype == "action":
            self._spawn(self._handle_action(msg_id or "", str(msg.get("action", "")), msg.get("args") or {}))
        elif mtype == "screenshot":
            self._spawn(self._handle_screenshot(msg_id or "", int(msg.get("maxWidth") or 900)))
        elif mtype == "hello":
            await self.error("bad_request", "Already connected", msg_id)
        else:
            await self.error("bad_request", f"Unknown message type {mtype!r}", msg_id)

    # ------------------------------------------------------------------
    async def _handle_voice(self, msg_id: str, msg: dict) -> None:
        if not self.agent.groq.configured:
            await self.error("not_configured", "Voice needs a Groq API key (Settings → AI keys). You can still type!", msg_id)
            return
        try:
            audio = base64.b64decode(msg.get("audio") or "", validate=False)
        except (binascii.Error, ValueError):
            await self.error("bad_request", "Audio is not valid base64", msg_id)
            return
        if len(audio) < 800:
            await self.send({"type": "reply", "id": msg_id, "text": "That was too short for me to hear! Hold the button while you talk.", "audioUrl": None, "mood": "curious", "actions": []})
            return
        mime = str(msg.get("mime") or "audio/m4a").lower()
        ext = _EXT_FOR_MIME.get(mime, "m4a")
        await self.status("transcribing", "Listening…", msg_id)
        try:
            text = await self.agent.groq.transcribe(self.agent.cfg.stt_model, audio, f"voice.{ext}", mime)
        except Exception as exc:
            log.warning("transcription failed: %s", exc)
            await self.status("idle")
            await self.error("upstream_error", f"I couldn't understand the recording ({exc}).", msg_id)
            return
        await self.send({"type": "transcript", "id": msg_id, "text": text})
        await self._handle_chat(msg_id, text, bool(msg.get("speak", True)))

    async def _handle_chat(self, msg_id: str, text: str, speak: bool) -> None:
        async def progress(detail: str) -> None:
            await self.status("acting" if not detail.startswith("Thinking") else "thinking", detail, msg_id)

        await self.status("thinking", "Thinking…", msg_id)
        try:
            async with self.agent.action_lock:
                result = await self.agent.brain.respond(text, self.history, progress)
        except Exception:
            log.exception("brain crashed")
            await self.status("idle")
            await self.error("internal", "Something went wrong on the PC. Check the agent's terminal for details.", msg_id)
            return
        audio_url = await self._speak(result.text, msg_id) if speak else None
        await self.send(
            {
                "type": "reply",
                "id": msg_id,
                "text": result.text,
                "audioUrl": audio_url,
                "mood": result.mood,
                "actions": result.actions,
            }
        )
        await self.status("idle")

    async def _speak(self, text: str, msg_id: str) -> str | None:
        if not self.agent.tts.configured:
            return None
        await self.status("speaking", "Warming up my voice…", msg_id)
        try:
            audio = await self.agent.tts.synthesize(text)
        except TTSError as exc:
            log.warning("TTS failed: %s", exc)
            if not self._tts_warned:
                self._tts_warned = True
                await self.error("upstream_error", f"ElevenLabs voice unavailable, using the phone's voice instead. ({exc})", msg_id)
            return None
        clip_id = self.agent.audio.put(audio)
        return f"/audio/{clip_id}.mp3"

    async def _handle_action(self, msg_id: str, action: str, args: dict) -> None:
        if action not in QUICK_ACTIONS:
            await self.error("bad_request", f"Unknown action {action!r}", msg_id)
            return
        if not isinstance(args, dict):
            args = {}

        async def progress(detail: str) -> None:
            await self.status("acting", detail, msg_id)

        await self.status("acting", action.replace("_", " "), msg_id)
        try:
            async with self.agent.action_lock:
                result = await self.agent.tools.run(action, args, progress)
        except Exception as exc:
            log.exception("action %s failed", action)
            result = None
            await self.error("internal", f"{action} failed: {exc}", msg_id)
        if result is not None:
            await self.send({"type": "action_result", "id": msg_id, "action": action, "ok": result.ok, "detail": result.detail})
        await self.status("idle")

    async def _handle_screenshot(self, msg_id: str, max_width: int) -> None:
        try:
            image, w, h = await self.agent.vision.thumbnail(max(240, min(max_width, 1600)))
        except Exception as exc:
            log.warning("screenshot failed: %s", exc)
            await self.error("internal", f"Couldn't capture the screen ({type(exc).__name__}). On macOS, allow Screen Recording.", msg_id)
            return
        await self.send({"type": "screenshot", "id": msg_id, "image": image, "width": w, "height": h})
