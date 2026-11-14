"""Terminal output shared by the headless and GUI modes."""

from __future__ import annotations

from . import __version__

BANNER = r"""
  ____            _    _                 _____     _                _
 |  _ \  ___  ___| | _| |_ ___  _ __   |  ___| __(_) ___ _ __   __| |
 | | | |/ _ \/ __| |/ / __/ _ \| '_ \  | |_ | '__| |/ _ \ '_ \ / _` |
 | |_| |  __/\__ \   <| || (_) | |_) | |  _|| |  | |  __/ | | | (_| |
 |____/ \___||___/_|\_\\__\___/| .__/  |_|  |_|  |_|\___|_| |_|\__,_|
                               |_|
"""


def print_pairing(agent) -> None:
    """Banner + terminal QR code + pairing link (also used for "enter the code instead" on the phone)."""
    from .pairing import qr_matrix_ascii

    url = agent.pairing_url()
    print(BANNER)
    print(f"  Desktop Friend v{__version__} on {agent.cfg.pc_name}")
    print(f"  Listening on {', '.join(f'{h}:{agent.cfg.port}' for h in agent.hosts)}")
    print("\n  Scan this QR code with the Desktop Friend app:\n")
    print(qr_matrix_ascii(url))
    print(f"  (or open http://localhost:{agent.cfg.port}/ on this PC for a bigger QR code)")
    print(f"  Pairing URL: {url}\n")
    keys = []
    keys.append("Groq: " + ("set" if agent.cfg.groq_api_key else "MISSING"))
    keys.append("ElevenLabs: " + ("set" if agent.cfg.elevenlabs_api_key else "MISSING (phone voice will be used)"))
    print("  " + " | ".join(keys) + "\n")
