"""Minimal async client for the Groq OpenAI-compatible REST API (chat, tools, vision, Whisper)."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Callable

import httpx

log = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        super().__init__(f"Groq {status}: {message}")
        self.status = status
        self.code = code or ""
        self.message = message

    @property
    def is_model_missing(self) -> bool:
        return self.status == 404 or self.code in {"model_not_found", "model_decommissioned"}


class GroqClient:
    def __init__(self, api_key_getter: Callable[[], str], timeout: float = 60.0, base_url: str = GROQ_BASE_URL):
        self._key = api_key_getter
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))

    @property
    def configured(self) -> bool:
        return bool(self._key())

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        key = self._key()
        if not key:
            raise GroqError(401, "GROQ_API_KEY is not set", "not_configured")
        headers = {"Authorization": f"Bearer {key}"}
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._http.request(method, f"{self._base}{path}", headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(0.6 * (attempt + 1))
                continue
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                retry_after = resp.headers.get("retry-after")
                try:
                    delay = min(float(retry_after), 5.0) if retry_after else 0.8 * (attempt + 1)
                except ValueError:
                    delay = 0.8 * (attempt + 1)
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 400:
                code, message = None, resp.text[:500]
                try:
                    err = resp.json().get("error", {})
                    code, message = err.get("code") or err.get("type"), err.get("message", message)
                except ValueError:
                    pass
                raise GroqError(resp.status_code, message, code)
            return resp.json()
        raise GroqError(0, f"network error talking to Groq: {last_exc}", "network")

    # ------------------------------------------------------------------
    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.6,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> dict:
        """Returns the assistant `message` dict (may contain `tool_calls`)."""
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        data = await self._request("POST", "/chat/completions", json=body)
        return data["choices"][0]["message"]

    async def vision(self, model: str, prompt: str, jpeg: bytes, system: str | None = None, json_mode: bool = False) -> str:
        b64 = base64.b64encode(jpeg).decode("ascii")
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        )
        msg = await self.chat(model, messages, temperature=0.1, max_tokens=400, json_mode=json_mode)
        return (msg.get("content") or "").strip()

    async def transcribe(self, model: str, audio: bytes, filename: str = "voice.m4a", mime: str = "audio/m4a") -> str:
        files = {"file": (filename, audio, mime)}
        data = {"model": model, "response_format": "json", "temperature": "0"}
        result = await self._request("POST", "/audio/transcriptions", files=files, data=data)
        return (result.get("text") or "").strip()

    async def list_models(self) -> list[str]:
        data = await self._request("GET", "/models")
        return sorted(m.get("id", "") for m in data.get("data", []))
