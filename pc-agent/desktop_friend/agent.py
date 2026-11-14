"""Wires all services together. One Agent per running PC app."""

from __future__ import annotations

import asyncio
import logging

from .automation import Automation
from .brain import Brain
from .config import Config
from .groq_client import GroqClient
from .models import ModelResolver
from .netinfo import lan_addresses
from .pairing import PairingStore, pairing_url
from .sounds import SoundPlayer
from .tools import ToolExecutor
from .tts import AudioCache, ElevenLabsTTS
from .ui import NullBridge, UiBridge
from .vision import ScreenCapture, Vision
from .websearch import WebSearcher

log = logging.getLogger(__name__)


class Agent:
    def __init__(self, config: Config, ui: UiBridge | None = None, capture: ScreenCapture | None = None):
        self.cfg = config
        self.ui = ui or NullBridge()
        data_dir = config.ensure_data_dir()

        self.pairing = PairingStore(data_dir / "pairing.json")
        self.groq = GroqClient(lambda: self.cfg.groq_api_key)
        self.models = ModelResolver(self.groq, config, on_change=lambda _kind, _model: self.ui.config_changed())
        self.tts = ElevenLabsTTS(
            lambda: self.cfg.elevenlabs_api_key,
            lambda: self.cfg.elevenlabs_voice_id,
            lambda: self.cfg.elevenlabs_model_id,
        )
        self.audio = AudioCache()
        self.sounds = SoundPlayer(data_dir, lambda: self.cfg.pc_sounds)
        self.vision = Vision(self.groq, lambda: self.cfg.vision_model, lambda: self.cfg.vision_refine, capture, models=self.models)
        self.automation = Automation(config)
        self.search = WebSearcher(self.groq, lambda: self.cfg.search_model, models=self.models)
        self.tools = ToolExecutor(config, self.vision, self.automation, self.search, self.ui, self.sounds)
        self.brain = Brain(config, self.groq, self.tools, models=self.models)
        self.hosts = lan_addresses(config.host)
        # Only one thing at a time may drive the mouse/keyboard, whichever phone asked.
        self.action_lock = asyncio.Lock()
        self.connected: dict[str, str] = {}  # session id -> device name
        self.ui.visible = config.cursor_visible

    def pairing_url(self) -> str:
        return pairing_url(self.hosts, self.cfg.port, self.pairing.pair_token, self.cfg.pc_name)

    def rotate_pairing(self) -> str:
        self.pairing.rotate_pair_token()
        url = self.pairing_url()
        self.ui.pairing_changed(url)
        return url

    def refresh_hosts(self) -> None:
        """Wi-Fi changes (new network, new DHCP lease) change our IP; refresh before showing a QR."""
        hosts = lan_addresses(self.cfg.host)
        if hosts != self.hosts:
            self.hosts = hosts
            self.ui.pairing_changed(self.pairing_url())

    async def close(self) -> None:
        await self.groq.close()
        await self.tts.close()
