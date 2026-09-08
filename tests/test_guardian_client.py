"""Tests for the Guardian client's error handling and SSE framing — no network.

These cover the bug that mattered most: a Guardian error used to be indistinguishable from
"your agent is fine". Every failure shape must now raise.

    ./.venv/bin/python -m pytest tests/ -q
"""

import json
import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "_shared")),
)
import guardian_client as g


def _ok(payload: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


# ---- _unwrap: every failure shape must raise -------------------------------


def test_success_returns_payload():
    assert g._unwrap("ask_guardian", _ok({"answer": "hi"})) == {"answer": "hi"}


def test_jsonrpc_error_raises():
    env = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "bad key"}}
    with pytest.raises(g.GuardianError, match="bad key"):
        g._unwrap("ask_guardian", env)


def test_mcp_tool_level_error_raises():
    env = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"isError": True, "content": [{"type": "text", "text": "agent not found"}]},
    }
    with pytest.raises(g.GuardianError, match="agent not found"):
        g._unwrap("ask_guardian", env)


def test_empty_payload_raises_rather_than_looking_like_no_issues():
    env = {"jsonrpc": "2.0", "id": 1, "result": {"content": []}}
    with pytest.raises(g.GuardianUnavailable):
        g._unwrap("get_remediations", env)


def test_missing_envelope_raises():
    with pytest.raises(g.GuardianUnavailable):
        g._unwrap("ask_guardian", None)


def test_non_json_text_is_returned_as_raw():
    env = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": "plain answer"}]},
    }
    assert g._unwrap("ask_guardian", env) == {"raw": "plain answer"}


# ---- _frame: SSE parsing ---------------------------------------------------


def test_picks_frame_matching_request_id_not_the_last_line():
    """Regression: keeping only the last `data:` line meant a trailing progress
    notification discarded the real answer."""
    body = (
        f"event: message\ndata: {json.dumps(_ok({'answer': 'real'}))}\n\n"
        'data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"p":90}}\n\n'
    )
    assert g._frame(body, 1)["result"]["content"][0]["text"] == json.dumps({"answer": "real"})


def test_handles_plain_json_response():
    assert g._frame(json.dumps(_ok({"answer": "x"})), 1)["id"] == 1


def test_falls_back_to_last_outcome_frame_when_id_absent():
    body = f"data: {json.dumps(_ok({'answer': 'y'}))}\n\n"
    assert g._frame(body, 999) is not None


def test_empty_body_returns_none():
    assert g._frame("", 1) is None


# ---- config: no silent wrong-environment default ---------------------------


def test_url_is_required(monkeypatch):
    monkeypatch.delenv("CHATSEE_MCP_URL", raising=False)
    with pytest.raises(g.GuardianConfigError, match="CHATSEE_MCP_URL"):
        g._url()


def test_key_is_required(monkeypatch):
    monkeypatch.delenv("CHATSEE_MCP_KEY", raising=False)
    with pytest.raises(g.GuardianConfigError, match="CHATSEE_MCP_KEY"):
        g._key()


def test_bad_timeout_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("CHATSEE_MCP_TIMEOUT", "soon")
    with pytest.raises(g.GuardianConfigError, match="whole number"):
        g._timeout()


def test_apply_remediations_refuses_empty_ids(monkeypatch):
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-x-y")
    monkeypatch.setenv("CHATSEE_MCP_URL", "https://example.invalid/mcp/")
    with pytest.raises(g.GuardianConfigError, match="no failure_memory_ids"):
        g.apply_remediations([])
