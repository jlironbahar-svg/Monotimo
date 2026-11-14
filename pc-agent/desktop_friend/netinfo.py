"""Find the LAN addresses the phone can reach this PC on."""

from __future__ import annotations

import ipaddress
import socket


def _primary_ipv4() -> str | None:
    """IP of the interface that holds the default route. No packets are actually sent."""
    for probe in ("10.255.255.255", "8.8.8.8", "192.168.1.1"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((probe, 1))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("0."):
                return ip
        except OSError:
            continue
        finally:
            s.close()
    return None


def _usable(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.version == 4 and not (addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified)


def _score(ip: str) -> int:
    """Prefer typical home Wi-Fi ranges over VPN / container bridges."""
    if ip.startswith("192.168."):
        return 0
    if ip.startswith("10."):
        return 1
    if ip.startswith("172."):
        second = int(ip.split(".")[1])
        # 172.17-172.19 are usually Docker/WSL bridges, push them to the back
        return 3 if 17 <= second <= 19 else 2
    return 4


def lan_addresses(bind_host: str = "0.0.0.0") -> list[str]:
    """Candidate addresses, best first. If the server is bound to a specific IP only that one is returned."""
    if bind_host not in ("0.0.0.0", "", "::"):
        return [bind_host]

    found: list[str] = []
    primary = _primary_ipv4()
    if primary and _usable(primary):
        found.append(primary)

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _usable(ip) and ip not in found:
                found.append(ip)
    except OSError:
        pass

    if not found:
        return ["127.0.0.1"]
    head, rest = found[:1], sorted(found[1:], key=_score)
    return head + rest
