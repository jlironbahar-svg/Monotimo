"""Configuration: `.env` file + environment variables, with write-back for settings changed from the phone."""

from __future__ import annotations

import logging
import os
import shutil
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, set_key

log = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
AGENT_DIR = PACKAGE_DIR.parent
DEFAULT_ENV_PATH = AGENT_DIR / ".env"
EXAMPLE_ENV_PATH = AGENT_DIR / ".env.example"

DEFAULTS: dict[str, str] = {
    "GROQ_API_KEY": "",
    "ELEVENLABS_API_KEY": "",
    "ELEVENLABS_VOICE_ID": "cgSgspJ2msm6clMCkdW9",
    "ELEVENLABS_MODEL_ID": "eleven_flash_v2_5",
    "GROQ_CHAT_MODEL": "openai/gpt-oss-120b",
    "GROQ_VISION_MODEL": "meta-llama/llama-4-scout-17b-16e-instruct",
    "GROQ_STT_MODEL": "whisper-large-v3-turbo",
    "GROQ_SEARCH_MODEL": "groq/compound-mini",
    "DF_HOST": "0.0.0.0",
    "DF_PORT": "8765",
    "DF_PC_NAME": "",
    "DF_CURSOR_COLOR": "#2F7BFF",
    "DF_CURSOR_VISIBLE": "true",
    "DF_PC_SOUNDS": "true",
    "DF_ALLOW_AUTOMATION": "true",
    "DF_RESTORE_MOUSE": "true",
    "DF_VISION_REFINE": "true",
    "DF_SEARCH_URL": "https://www.google.com/search?q={query}",
    "DF_DATA_DIR": "",
}


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'")


@dataclass
class Config:
    env_path: Path
    groq_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = DEFAULTS["ELEVENLABS_VOICE_ID"]
    elevenlabs_model_id: str = DEFAULTS["ELEVENLABS_MODEL_ID"]
    chat_model: str = DEFAULTS["GROQ_CHAT_MODEL"]
    vision_model: str = DEFAULTS["GROQ_VISION_MODEL"]
    stt_model: str = DEFAULTS["GROQ_STT_MODEL"]
    search_model: str = DEFAULTS["GROQ_SEARCH_MODEL"]
    host: str = "0.0.0.0"
    port: int = 8765
    pc_name: str = ""
    cursor_color: str = "#2F7BFF"
    cursor_visible: bool = True
    pc_sounds: bool = True
    allow_automation: bool = True
    restore_mouse: bool = True
    vision_refine: bool = True
    search_url: str = DEFAULTS["DF_SEARCH_URL"]
    data_dir: Path = field(default_factory=lambda: Path.home() / ".desktop-friend")
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, env_path: Path | None = None, create_if_missing: bool = True) -> "Config":
        env_path = Path(env_path) if env_path else DEFAULT_ENV_PATH
        if create_if_missing and not env_path.exists() and EXAMPLE_ENV_PATH.exists():
            try:
                shutil.copyfile(EXAMPLE_ENV_PATH, env_path)
                log.info("Created %s from .env.example", env_path)
            except OSError as exc:  # read-only install dir etc.
                log.warning("Could not create %s: %s", env_path, exc)

        file_values = {k: v for k, v in dotenv_values(env_path).items() if v is not None} if env_path.exists() else {}

        def get(key: str) -> str:
            # Real environment variables win over the file, the file wins over defaults.
            if key in os.environ and os.environ[key].strip():
                return _clean(os.environ[key])
            if key in file_values and file_values[key].strip():
                return _clean(file_values[key])
            return DEFAULTS[key]

        data_dir = get("DF_DATA_DIR")
        try:
            port = int(get("DF_PORT"))
        except ValueError:
            port = 8765

        return cls(
            env_path=env_path,
            groq_api_key=get("GROQ_API_KEY"),
            elevenlabs_api_key=get("ELEVENLABS_API_KEY"),
            elevenlabs_voice_id=get("ELEVENLABS_VOICE_ID"),
            elevenlabs_model_id=get("ELEVENLABS_MODEL_ID"),
            chat_model=get("GROQ_CHAT_MODEL"),
            vision_model=get("GROQ_VISION_MODEL"),
            stt_model=get("GROQ_STT_MODEL"),
            search_model=get("GROQ_SEARCH_MODEL"),
            host=get("DF_HOST"),
            port=port,
            pc_name=get("DF_PC_NAME") or socket.gethostname() or "My PC",
            cursor_color=get("DF_CURSOR_COLOR"),
            cursor_visible=_truthy(get("DF_CURSOR_VISIBLE")),
            pc_sounds=_truthy(get("DF_PC_SOUNDS")),
            allow_automation=_truthy(get("DF_ALLOW_AUTOMATION")),
            restore_mouse=_truthy(get("DF_RESTORE_MOUSE")),
            vision_refine=_truthy(get("DF_VISION_REFINE")),
            search_url=get("DF_SEARCH_URL"),
            data_dir=Path(data_dir).expanduser() if data_dir else Path.home() / ".desktop-friend",
        )

    # ------------------------------------------------------------------
    def persist(self, key: str, value: str) -> None:
        """Write a single setting back into the .env file (creating it if needed)."""
        with self._lock:
            try:
                self.env_path.parent.mkdir(parents=True, exist_ok=True)
                if not self.env_path.exists():
                    self.env_path.touch()
                set_key(str(self.env_path), key, value, quote_mode="never")
            except OSError as exc:
                log.error("Could not save %s to %s: %s", key, self.env_path, exc)

    def update_from_phone(self, changes: dict) -> list[str]:
        """Apply a ConfigUpdateMsg. Returns the list of changed setting names (never the values)."""
        changed: list[str] = []
        mapping = {
            "groqApiKey": ("groq_api_key", "GROQ_API_KEY"),
            "elevenLabsApiKey": ("elevenlabs_api_key", "ELEVENLABS_API_KEY"),
            "elevenLabsVoiceId": ("elevenlabs_voice_id", "ELEVENLABS_VOICE_ID"),
        }
        for msg_key, (attr, env_key) in mapping.items():
            if msg_key in changes and isinstance(changes[msg_key], str):
                value = changes[msg_key].strip()
                if attr == "elevenlabs_voice_id" and not value:
                    value = DEFAULTS["ELEVENLABS_VOICE_ID"]
                if value != getattr(self, attr):
                    setattr(self, attr, value)
                    self.persist(env_key, value)
                    changed.append(env_key)
        bool_mapping = {"cursorVisible": ("cursor_visible", "DF_CURSOR_VISIBLE"), "pcSounds": ("pc_sounds", "DF_PC_SOUNDS")}
        for msg_key, (attr, env_key) in bool_mapping.items():
            if msg_key in changes and isinstance(changes[msg_key], bool):
                if changes[msg_key] != getattr(self, attr):
                    setattr(self, attr, changes[msg_key])
                    self.persist(env_key, "true" if changes[msg_key] else "false")
                    changed.append(env_key)
        return changed

    def summary(self) -> dict:
        """PcConfigSummary sent to the phone. Never includes secret values."""
        return {
            "hasGroqKey": bool(self.groq_api_key),
            "hasElevenLabsKey": bool(self.elevenlabs_api_key),
            "elevenLabsVoiceId": self.elevenlabs_voice_id,
            "cursorVisible": self.cursor_visible,
            "pcSounds": self.pc_sounds,
            "automationEnabled": self.allow_automation,
            "models": {
                "chat": self.chat_model,
                "vision": self.vision_model,
                "stt": self.stt_model,
                "tts": self.elevenlabs_model_id,
            },
        }

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir
