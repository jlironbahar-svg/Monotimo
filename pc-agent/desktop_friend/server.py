"""HTTP + WebSocket server (aiohttp)."""

from __future__ import annotations

import asyncio
import base64
import html
import logging

from aiohttp import web

from .pairing import qr_png_bytes
from .protocol import PROTOCOL_VERSION
from .session import Session

log = logging.getLogger(__name__)

AGENT_KEY = web.AppKey("agent", object)

_LOCAL = {"127.0.0.1", "::1", "localhost"}


def _is_local(request: web.Request) -> bool:
    return (request.remote or "") in _LOCAL


async def ws_handler(request: web.Request) -> web.StreamResponse:
    agent = request.app[AGENT_KEY]
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=24 * 1024 * 1024)
    await ws.prepare(request)
    session = Session(agent, ws, request.remote or "?")
    await session.run()
    return ws


async def health(request: web.Request) -> web.Response:
    agent = request.app[AGENT_KEY]
    return web.json_response({"ok": True, "app": "desktop-friend", "protocol": PROTOCOL_VERSION, "pcName": agent.cfg.pc_name})


async def audio(request: web.Request) -> web.Response:
    """Synthesized replies. The clip id is a 96-bit random value handed only to the paired phone."""
    agent = request.app[AGENT_KEY]
    clip = agent.audio.get(request.match_info["clip"])
    if clip is None:
        raise web.HTTPNotFound()
    return web.Response(body=clip, content_type="audio/mpeg", headers={"Cache-Control": "no-store"})


async def qr_png(request: web.Request) -> web.Response:
    if not _is_local(request):
        raise web.HTTPForbidden(text="The pairing QR code is only shown on the PC itself.")
    agent = request.app[AGENT_KEY]
    return web.Response(body=qr_png_bytes(agent.pairing_url()), content_type="image/png", headers={"Cache-Control": "no-store"})


async def index(request: web.Request) -> web.Response:
    agent = request.app[AGENT_KEY]
    if not _is_local(request):
        return web.Response(text="Desktop Friend is running. Open this page on the PC itself to see the pairing QR code.")
    agent.refresh_hosts()
    url = agent.pairing_url()
    b64 = base64.b64encode(qr_png_bytes(url, box_size=8)).decode()
    devices = ", ".join(html.escape(n) for n in agent.connected.values()) or "none yet"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Desktop Friend</title>
<meta http-equiv="refresh" content="20">
<style>body{{font-family:system-ui,sans-serif;background:#EEF4FF;color:#1B2A4A;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;border-radius:24px;padding:32px 40px;box-shadow:0 10px 40px #2F7BFF22;text-align:center;max-width:420px}}
h1{{margin:0 0 4px}}p{{color:#51607d}}img{{width:300px;height:300px;image-rendering:pixelated}}code{{background:#EEF4FF;padding:2px 6px;border-radius:6px}}</style></head>
<body><div class="card"><h1>Desktop Friend</h1><p>Scan with the Desktop Friend app on your phone</p>
<img alt="pairing QR code" src="data:image/png;base64,{b64}"><p><b>{html.escape(agent.cfg.pc_name)}</b> &middot; <code>{html.escape(agent.hosts[0])}:{agent.cfg.port}</code></p>
<p>Connected phones: {devices}</p></div></body></html>"""
    return web.Response(text=page, content_type="text/html")


def create_app(agent) -> web.Application:
    app = web.Application(client_max_size=24 * 1024 * 1024)
    app[AGENT_KEY] = agent
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/qr.png", qr_png)
    app.router.add_get(r"/audio/{clip:[A-Za-z0-9_\-]+}.mp3", audio)
    app.router.add_get("/ws", ws_handler)
    return app


async def serve(agent, stop: asyncio.Event, started: asyncio.Event | None = None) -> None:
    """Run until `stop` is set. Raises OSError if the port is taken."""
    app = create_app(agent)
    runner = web.AppRunner(app, access_log=None, handle_signals=False)
    await runner.setup()
    site = web.TCPSite(runner, agent.cfg.host, agent.cfg.port)
    try:
        await site.start()
    except OSError:
        await runner.cleanup()
        raise
    log.info("listening on %s:%s (LAN: %s)", agent.cfg.host, agent.cfg.port, ", ".join(agent.hosts))
    agent.ui.pairing_changed(agent.pairing_url())
    if started:
        started.set()
    try:
        await stop.wait()
    finally:
        await runner.cleanup()
        await agent.close()
