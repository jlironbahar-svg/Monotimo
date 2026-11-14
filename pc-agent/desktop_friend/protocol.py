"""Wire protocol constants. Mirrors shared/protocol.ts (kept in sync by tests/test_protocol_sync.py)."""

PROTOCOL_VERSION = 1
DEFAULT_PORT = 8765
PAIR_URL_SCHEME = "desktopfriend"

# Phone -> PC message types
CLIENT_TYPES = frozenset({"hello", "chat", "voice", "action", "screenshot", "config", "apps", "ping"})

# PC -> Phone message types
SERVER_TYPES = frozenset(
    {"welcome", "status", "transcript", "reply", "action_result", "screenshot", "config", "error", "apps", "pong"}
)

QUICK_ACTIONS = frozenset(
    {
        "point",
        "click",
        "scroll",
        "type",
        "keys",
        "shortcut",
        "open_app",
        "open_url",
        "web_search",
        "describe_screen",
        "cursor_home",
        "toggle_cursor",
    }
)

PC_STATES = frozenset({"idle", "transcribing", "thinking", "acting", "speaking"})
MOODS = frozenset({"happy", "excited", "curious", "proud", "sad", "sleepy"})
ERROR_CODES = frozenset(
    {"auth_failed", "bad_request", "protocol_mismatch", "not_configured", "upstream_error", "internal"}
)
