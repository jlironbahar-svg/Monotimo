"""The Python constants must match shared/protocol.ts (the source of truth)."""
import re
from pathlib import Path

from desktop_friend import protocol

TS = (Path(__file__).resolve().parents[2] / "shared" / "protocol.ts").read_text()


def _types_of(union: str) -> set[str]:
    block = re.search(rf"export type {union} =([^;]+);", TS).group(1)
    names = re.findall(r"\b(\w+Msg)\b", block)
    out = set()
    for name in names:
        body = re.search(rf"export interface {name} \{{(.*?)\n\}}", TS, re.S).group(1)
        out.add(re.search(r"type: '(\w+)'", body).group(1))
    return out


def _string_union(name: str) -> set[str]:
    block = re.search(rf"export type {name} =([^;]+);", TS).group(1)
    block = re.sub(r"//[^\n]*", "", block)  # ignore example values in comments
    return set(re.findall(r"'(\w+)'", block))


def test_message_types_match():
    assert _types_of("ClientMessage") == set(protocol.CLIENT_TYPES)
    assert _types_of("ServerMessage") == set(protocol.SERVER_TYPES)


def test_enums_match():
    assert _string_union("QuickAction") == set(protocol.QUICK_ACTIONS)
    assert _string_union("PcState") == set(protocol.PC_STATES)
    assert _string_union("Mood") == set(protocol.MOODS)
    assert _string_union("ErrorCode") == set(protocol.ERROR_CODES)


def test_constants_match():
    assert f"PROTOCOL_VERSION = {protocol.PROTOCOL_VERSION};" in TS
    assert f"DEFAULT_PORT = {protocol.DEFAULT_PORT};" in TS
    assert f"PAIR_URL_SCHEME = '{protocol.PAIR_URL_SCHEME}';" in TS
