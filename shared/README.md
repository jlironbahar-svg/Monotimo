# Shared protocol

[`protocol.ts`](protocol.ts) is the contract between the phone app and the PC agent. The app imports it directly
(Metro bundles `../shared` via `mobile-app/metro.config.js`). The PC agent mirrors the message names in
`pc-agent/desktop_friend/protocol.py`, and `pc-agent/tests/test_protocol_sync.py` keeps the two in sync.

## Pairing

The QR code encodes `desktopfriend://pair?v=1&h=<ip1>,<ip2>&p=<port>&t=<pairToken>&n=<pcName>`.
Scanning it with the system camera also opens the app (the `desktopfriend` URL scheme).

## Session

```
phone                                         PC
  │── ws://ip:port/ws ───────────────────────▶│
  │── hello {deviceId, pairToken | deviceToken}▶│  first message, within 15 s
  │◀──────────── welcome {deviceToken, config}─│  phone stores deviceToken, drops pairToken
  │── chat {id, text} ────────────────────────▶│
  │◀─ status {thinking} · status {acting, "Looking for the save button…"} ─│
  │◀─ reply {id, text, mood, actions[], audioUrl} ─────────────────────────│
  │── GET /audio/<id>.mp3 ────────────────────▶│  ElevenLabs voice, played on the phone
  │── voice {id, audio(base64 m4a)} ──────────▶│  → transcript {text} → … → reply
  │── action {id, action, args} ──────────────▶│  quick actions, no LLM → action_result
  │── screenshot {id} ────────────────────────▶│  → screenshot {image(base64 jpeg)}
  │── config {groqApiKey?, …} ────────────────▶│  → config {summary without secrets}
  │── ping ──▶ pong                            │  every 15 s
```

Errors arrive as `error {code, message, id?}`. `auth_failed` and `protocol_mismatch` mean the phone must re-pair or
update. The connection is closed after either.
