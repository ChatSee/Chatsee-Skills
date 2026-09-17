"""Keep the unit tests hermetic now that the client can fall back to a config file.

`guardian/env_config.py` fills in absent CHATSEE_* variables from `.env` at the project root.
That is what lets Claude Code run the skills with no special shell — but it would also let a
developer's real `.env` leak into these tests, so `test_key_is_required` would pass or fail
depending on whose machine it ran on.

Every test therefore points the loader at a file that does not exist, and resets its
one-shot memo so ordering cannot matter.
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills", "_shared")),
)
import env_config  # noqa: E402  - after the sys.path insert above


@pytest.fixture(autouse=True)
def _isolate_env_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATSEE_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    # Also redirect the machine-wide file, or a real ~/.config/chatsee/agent.env on the
    # developer's machine would leak into these tests.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(env_config, "_done", False)
    monkeypatch.setattr(env_config, "_loaded_from", [])
