"""Tests for the config-file fallback that lets the skills run without a special shell.

The load-bearing invariant is **the environment always wins**. Loading a file over an
already-set variable is the bug that made a query about a brand-new agent return a different
agent's 151 incidents (VALIDATION.md F1), so it is pinned first and hardest.

    ./.venv/bin/python -m pytest tests/ -q
"""

import os
import sys

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "_shared")),
)
import env_config as e  # noqa: E402  - after the sys.path insert above


def _write(tmp_path, body: str) -> str:
    p = tmp_path / "agent.env"
    p.write_text(body, encoding="utf-8")
    return str(p)


def _fresh(monkeypatch, path: str):
    """Point the loader at `path` as the PROJECT file, with its memo cleared.

    conftest already redirects XDG_CONFIG_HOME to an empty temp dir, so the machine-wide
    file is absent unless a test writes one deliberately.
    """
    monkeypatch.setenv("CHATSEE_ENV_FILE", path)
    monkeypatch.setattr(e, "_done", False)
    monkeypatch.setattr(e, "_loaded_from", [])


def _write_user_config(tmp_path, body: str) -> str:
    """Create the machine-wide file inside the temp XDG root conftest set up."""
    d = tmp_path / "xdg" / "chatsee"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "agent.env"
    p.write_text(body, encoding="utf-8")
    return str(p)


# ---- the environment always wins (F1) --------------------------------------


def test_never_overrides_an_exported_variable(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_MCP_KEY=from-file\n")
    monkeypatch.setenv("CHATSEE_MCP_KEY", "from-shell")
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_MCP_KEY"] == "from-shell"


def test_fills_only_the_absent_variables(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_MCP_KEY=from-file\nCHATSEE_MCP_URL=https://file/mcp/\n")
    monkeypatch.setenv("CHATSEE_MCP_KEY", "from-shell")
    monkeypatch.delenv("CHATSEE_MCP_URL", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_MCP_KEY"] == "from-shell"
    assert os.environ["CHATSEE_MCP_URL"] == "https://file/mcp/"


def test_empty_value_in_file_does_not_mask_a_missing_variable(monkeypatch, tmp_path):
    # A blank entry must not count as "supplied" — the caller should still get the clear
    # "not set" error rather than an empty key reaching the Guardian as a 401.
    path = _write(tmp_path, "CHATSEE_MCP_KEY=\n")
    monkeypatch.delenv("CHATSEE_MCP_KEY", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert "CHATSEE_MCP_KEY" not in os.environ


# ---- parsing ---------------------------------------------------------------


def test_strips_quotes_so_agent_names_with_spaces_survive(monkeypatch, tmp_path):
    path = _write(tmp_path, 'CHATSEE_AGENT="Frictionless Test Agent"\n')
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "Frictionless Test Agent"


def test_ignores_comments_and_blank_lines(monkeypatch, tmp_path):
    path = _write(tmp_path, "# a comment\n\n  \nCHATSEE_AGENT=x\n")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "x"


def test_keeps_equals_signs_inside_values(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_MCP_KEY=cs-demo-abc-x=y=z\n")
    monkeypatch.delenv("CHATSEE_MCP_KEY", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_MCP_KEY"] == "cs-demo-abc-x=y=z"


# ---- absence and idempotence -----------------------------------------------


def test_missing_file_is_not_an_error(monkeypatch, tmp_path):
    _fresh(monkeypatch, str(tmp_path / "nope.env"))
    assert e.load(announce=False) is None


def test_reports_the_file_it_used(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_AGENT=x\n")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    assert e.load(announce=False) == path


def test_second_call_does_not_reload(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_AGENT=first\n")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    # Rewrite the file and call again: the memo means the change is not picked up mid-process,
    # so config cannot shift underneath a running command.
    with open(path, "w", encoding="utf-8") as f:
        f.write("CHATSEE_AGENT=second\n")
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "first"


# ---- the machine-wide file (~/.config/chatsee/agent.env) --------------------


def test_user_config_supplies_a_machine_wide_secret(monkeypatch, tmp_path):
    """The point of the file: one ANTHROPIC_API_KEY usable by every test agent."""
    _write_user_config(tmp_path, "ANTHROPIC_API_KEY=from-user-config\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _fresh(monkeypatch, str(tmp_path / "no-project.env"))
    e.load(announce=False)
    assert os.environ["ANTHROPIC_API_KEY"] == "from-user-config"


def test_project_file_beats_user_config(monkeypatch, tmp_path):
    path = _write(tmp_path, "ACME_MODEL=from-project\n")
    _write_user_config(tmp_path, "ACME_MODEL=from-user-config\n")
    monkeypatch.delenv("ACME_MODEL", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["ACME_MODEL"] == "from-project"


def test_environment_beats_both(monkeypatch, tmp_path):
    path = _write(tmp_path, "ACME_MODEL=from-project\n")
    _write_user_config(tmp_path, "ACME_MODEL=from-user-config\n")
    monkeypatch.setenv("ACME_MODEL", "from-shell")
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["ACME_MODEL"] == "from-shell"


def test_user_config_cannot_supply_agent_identity(monkeypatch, tmp_path):
    """F1, one level up: a machine-wide agent id would point every project at one agent."""
    _write_user_config(
        tmp_path,
        "CHATSEE_MCP_KEY=cs-demo-global\nCHATSEE_AGENT_ID=deadbeefdeadbeefdeadbeef\n"
        "CHATSEE_TENANT_ID=cafecafecafecafecafecafe\nCHATSEE_AGENT=Someone Elses Agent\n",
    )
    for k in e.AGENT_SCOPED:
        monkeypatch.delenv(k, raising=False)
    _fresh(monkeypatch, str(tmp_path / "no-project.env"))
    e.load(announce=False)
    for k in e.AGENT_SCOPED:
        assert k not in os.environ, f"{k} must not come from the machine-wide file"


def test_project_file_may_supply_agent_identity(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_AGENT=Acme Support Agent\n")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "Acme Support Agent"


def test_both_sources_combine(monkeypatch, tmp_path):
    """The real arrangement: agent identity from the project, model key machine-wide."""
    path = _write(tmp_path, "CHATSEE_AGENT=Acme Support Agent\n")
    _write_user_config(tmp_path, "ANTHROPIC_API_KEY=k\n")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "Acme Support Agent"
    assert os.environ["ANTHROPIC_API_KEY"] == "k"


def test_user_config_path_honours_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "elsewhere"))
    assert e.user_config_path() == str(tmp_path / "elsewhere" / "chatsee" / "agent.env")


# ---- inline comments -------------------------------------------------------


def test_strips_the_comment_after_a_quoted_value(monkeypatch, tmp_path):
    """Regression: `.env.example`'s commented placeholder parsed as value + comment, so the
    agent name echoed back to the developer was the entire line."""
    path = _write(tmp_path, 'CHATSEE_AGENT="Acme Support Agent"   # QUOTE it — names have spaces\n')
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "Acme Support Agent"


def test_strips_the_comment_after_an_unquoted_value(monkeypatch, tmp_path):
    path = _write(tmp_path, "CHATSEE_MCP_TIMEOUT=300   # ask_guardian is agentic\n")
    monkeypatch.delenv("CHATSEE_MCP_TIMEOUT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_MCP_TIMEOUT"] == "300"


def test_a_hash_inside_a_value_is_not_a_comment(monkeypatch, tmp_path):
    """Secrets contain '#'. Cutting at the first one would silently truncate a key."""
    path = _write(tmp_path, "CHATSEE_MCP_KEY=cs-demo-abc-se#cret\n")
    monkeypatch.delenv("CHATSEE_MCP_KEY", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_MCP_KEY"] == "cs-demo-abc-se#cret"


def test_a_hash_inside_a_quoted_value_survives(monkeypatch, tmp_path):
    path = _write(tmp_path, 'CHATSEE_AGENT="Agent #2"\n')
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    _fresh(monkeypatch, path)
    e.load(announce=False)
    assert os.environ["CHATSEE_AGENT"] == "Agent #2"
