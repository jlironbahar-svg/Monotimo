"""Command line entry point:  python -m desktop_friend [--headless] [--check] ..."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import signal
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .console import print_pairing

log = logging.getLogger("desktop_friend")

def _setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
        except (AttributeError, ValueError):
            pass


def _prompt_for_keys(cfg: Config) -> None:
    """First run convenience: ask for missing keys in an interactive terminal and save them to .env."""
    if not sys.stdin or not sys.stdin.isatty():
        return
    if cfg.groq_api_key and cfg.elevenlabs_api_key:
        return
    print("\nSome API keys are missing. Paste them now, or press Enter to skip")
    print("(you can also set them later from the phone app: Settings -> AI keys).\n")
    try:
        if not cfg.groq_api_key:
            key = getpass.getpass("  Groq API key (gsk_..., input hidden): ").strip()
            if key:
                cfg.groq_api_key = key
                cfg.persist("GROQ_API_KEY", key)
        if not cfg.elevenlabs_api_key:
            key = getpass.getpass("  ElevenLabs API key (input hidden): ").strip()
            if key:
                cfg.elevenlabs_api_key = key
                cfg.persist("ELEVENLABS_API_KEY", key)
    except (EOFError, KeyboardInterrupt):
        print()
    print()


async def _check(cfg: Config) -> int:
    """Validate keys and model names against the live APIs."""
    from .groq_client import GroqClient, GroqError
    from .tts import ElevenLabsTTS

    ok = True
    print(f"Config file: {cfg.env_path}")
    groq = GroqClient(lambda: cfg.groq_api_key)
    if not cfg.groq_api_key:
        print("  Groq:        NOT SET  (chat, vision, voice input disabled; simple commands still work)")
        ok = False
    else:
        from .models import SETTING, ModelResolver

        try:
            models = set(await groq.list_models())
            print(f"  Groq:        key ok ({len(models)} models available)")
            before = {kind: getattr(cfg, attr) for kind, (attr, _env) in SETTING.items()}
            await ModelResolver(groq, cfg).startup_check()  # swaps retired/"auto" models and saves to .env
            for kind, (attr, _env) in SETTING.items():
                model = getattr(cfg, attr)
                if model in models:
                    note = "ok" if model == before[kind] else f"ok (switched from {before[kind]!r}, saved to .env)"
                else:
                    note = "NOT AVAILABLE - no working replacement found"
                    ok = False
                print(f"    {kind:<7} {model:<48} {note}")
            if not ok:
                print("  Models on your account:\n    " + "\n    ".join(sorted(models)))
        except GroqError as exc:
            print(f"  Groq:        FAILED  {exc}")
            ok = False
    await groq.close()

    tts = ElevenLabsTTS(lambda: cfg.elevenlabs_api_key, lambda: cfg.elevenlabs_voice_id, lambda: cfg.elevenlabs_model_id)
    try:
        status = await tts.check()
    except Exception as exc:
        status = f"FAILED {exc}"
    print(f"  ElevenLabs:  {status}")
    ok &= status.startswith("ok")
    await tts.close()
    return 0 if ok else 1


def run_headless(cfg: Config) -> int:
    from .agent import Agent
    from .server import serve

    async def main() -> int:
        agent = Agent(cfg)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):  # Windows
                pass
        started = asyncio.Event()
        task = asyncio.create_task(serve(agent, stop, started))
        done, _ = await asyncio.wait({task, asyncio.create_task(started.wait())}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            task.result()  # re-raise startup error
        print_pairing(agent)
        await task
        return 0

    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        log.error("Could not start the server on port %s: %s. Is Desktop Friend already running? Try --port.", cfg.port, exc)
        return 2


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    parser = argparse.ArgumentParser(prog="desktop-friend", description="Desktop Friend PC agent")
    parser.add_argument("--headless", action="store_true", help="no overlay or windows; QR code in the terminal only")
    parser.add_argument("--check", action="store_true", help="validate API keys and model names, then exit")
    parser.add_argument("--port", type=int, help="override DF_PORT")
    parser.add_argument("--env", type=Path, help="path to the .env file (default: pc-agent/.env)")
    parser.add_argument("--new-pairing", action="store_true", help="generate a new pairing QR code (old QR stops working)")
    parser.add_argument("--forget-devices", action="store_true", help="unpair all phones")
    parser.add_argument("--no-prompt", action="store_true", help="don't ask for missing API keys on start")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "PIL", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    cfg = Config.load(args.env)
    if args.port:
        cfg.port = args.port

    if args.check:
        return asyncio.run(_check(cfg))

    if args.new_pairing or args.forget_devices:
        from .pairing import PairingStore

        store = PairingStore(cfg.ensure_data_dir() / "pairing.json")
        if args.new_pairing:
            store.rotate_pair_token()
            print("New pairing QR code generated.")
        if args.forget_devices:
            store.forget_devices()
            print("All phones unpaired.")

    if not args.no_prompt:
        _prompt_for_keys(cfg)

    headless = args.headless or os.environ.get("DF_HEADLESS", "").lower() in {"1", "true", "yes"}
    if not headless:
        try:
            from .gui.app import run_gui
        except ImportError as exc:
            log.warning("GUI unavailable (%s); running headless. Install PySide6-Essentials for the blue cursor overlay.", exc)
            headless = True
        else:
            return run_gui(cfg)
    return run_headless(cfg)


if __name__ == "__main__":
    sys.exit(main())
