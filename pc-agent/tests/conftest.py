import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_friend.config import Config  # noqa: E402


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    for key in ("GROQ_API_KEY", "ELEVENLABS_API_KEY", "DF_PORT", "DF_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text("DF_PORT=0\nDF_PC_SOUNDS=false\n")
    c = Config.load(env, create_if_missing=False)
    c.data_dir = tmp_path / "data"
    c.pc_name = "TestPC"
    return c
