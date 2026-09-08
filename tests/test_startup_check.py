"""Unit tests for the session-start failure check. Pure functions only — no network.

The two that carry weight are `is_empty` (deciding when a session start stays quiet) and
`main`'s guard rails, because both failure modes are silent by construction: if `is_empty`
is too eager the developer never sees a real failure, and if the script exits non-zero it
degrades every session in the repo.
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", ".claude", "skills", "guardian-query", "scripts"
        )
    ),
)
import startup_check as s  # noqa: E402  - after the sys.path insert above

# ---- is_empty ---------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "NONE",
        "none",
        "  NONE  ",
        "",
        "   ",
        "No errors detected for this agent.",
        "No error incidents in the last 24 hours.",
    ],
)
def test_empty_answers_keep_the_session_quiet(answer):
    assert s.is_empty(answer) is True


@pytest.mark.parametrize(
    "answer",
    [
        "EXE_19  Identical Tool Loop  12",
        "EXE_19  Identical Tool Loop  12\nREA_26  Post-Conclusion Spinning  7",
    ],
)
def test_real_findings_are_never_treated_as_empty(answer):
    assert s.is_empty(answer) is False


def test_a_long_answer_mentioning_no_errors_is_not_empty():
    """The Guardian prefaces real findings with negatives, and swallowing those is the
    expensive failure: the developer is told nothing while the agent is on fire."""
    answer = (
        "No errors were detected in the previous week. However, in the last 24 hours "
        "the following codes appeared for this agent and are worth attention:\n"
        "EXE_19  Identical Tool Loop  12\n"
        "REA_26  Post-Conclusion Spinning  7\n"
        "EXE_22  Termination Blindness  2"
    )
    assert s.is_empty(answer) is False


# ---- summarize --------------------------------------------------------------


def test_summary_names_the_agent_and_window_and_keeps_the_guardians_words():
    out = s.summarize("EXE_19  Identical Tool Loop  12", "Acme Support Agent", 24)
    assert "Acme Support Agent" in out
    assert "24h" in out
    assert "EXE_19  Identical Tool Loop  12" in out


def test_summary_strips_portal_redirect_anchors():
    out = s.summarize('<redirect index="2">EXE_19</redirect> 12', "A", 24)
    assert "redirect" not in out
    assert "EXE_19" in out


def test_summary_truncates_at_a_line_boundary():
    body = "\n".join(f"CODE_{i}  some failure name  {i}" for i in range(80))
    out = s.summarize(body, "A", 24, limit=100)
    assert out.endswith("…")
    assert len(out) < 250
    # a trimmed line would strand a half-written code in front of the developer
    for line in out.splitlines()[1:-1]:
        assert line.startswith("CODE_")


def test_short_answers_are_not_truncated():
    out = s.summarize("EXE_19  Identical Tool Loop  12", "A", 24)
    assert "…" not in out


# ---- argument parsing -------------------------------------------------------


def test_defaults_are_24_hours_and_a_bounded_timeout(monkeypatch):
    monkeypatch.setenv("CHATSEE_AGENT", "Configured Agent")
    agent, hours, timeout = s._parse([])
    assert (agent, hours) == ("Configured Agent", 24)
    assert 0 < timeout <= 60, "a session-start hook must not be able to hang for minutes"


def test_flags_override_the_environment(monkeypatch):
    monkeypatch.setenv("CHATSEE_AGENT", "From Env")
    agent, hours, timeout = s._parse(["--agent", "From Flag", "--hours", "6", "--timeout", "5"])
    assert (agent, hours, timeout) == ("From Flag", 6, 5)


@pytest.mark.parametrize(
    "argv",
    [["--nope"], ["--hours", "0"], ["--hours", "-1"], ["--hours", "many"], ["--timeout", "0"]],
)
def test_bad_arguments_raise_rather_than_degrade_silently(argv):
    with pytest.raises(ValueError):
        s._parse(argv)


# ---- main: the guard rails --------------------------------------------------


def test_unconfigured_repo_prints_nothing_at_all(monkeypatch, capsys):
    """A repo that has never heard of ChatSee must not be nagged on every session start."""
    monkeypatch.delenv("CHATSEE_MCP_KEY", raising=False)
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    assert s.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_key_without_agent_says_so_instead_of_asking_unscoped(monkeypatch, capsys):
    """Unscoped questions get answered about an arbitrary agent, so printing another
    agent's failures under this project's name would be worse than saying nothing."""
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.delenv("CHATSEE_AGENT", raising=False)
    assert s.main([]) == 0
    assert "CHATSEE_AGENT" in capsys.readouterr().err


def test_guardian_failure_is_reported_and_still_exits_zero(monkeypatch, capsys):
    """The two rules together: never break the session, never look like a clean bill of
    health. A revoked key that printed nothing would be the exact bug this guards."""
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.setenv("CHATSEE_AGENT", "Acme Support Agent")

    def _boom(*_args, **_kwargs):
        raise s.g.GuardianAuthError("Guardian rejected the key (HTTP 401).")

    monkeypatch.setattr(s.g, "ask_guardian", _boom)

    assert s.main([]) == 0
    err = capsys.readouterr().err
    assert "could not check recent failures" in err
    assert "401" in err


def test_findings_are_printed_to_stderr_so_stdout_stays_clean(monkeypatch, capsys):
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.setenv("CHATSEE_AGENT", "Acme Support Agent")
    monkeypatch.setattr(
        s.g, "ask_guardian", lambda *_a, **_k: {"answer": "EXE_19  Identical Tool Loop  12"}
    )

    assert s.main([]) == 0
    captured = capsys.readouterr()
    assert "EXE_19" in captured.err
    assert captured.out == ""


def test_no_findings_means_no_output(monkeypatch, capsys):
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.setenv("CHATSEE_AGENT", "Acme Support Agent")
    monkeypatch.setattr(s.g, "ask_guardian", lambda *_a, **_k: {"answer": "NONE"})

    assert s.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_question_is_scoped_to_the_named_agent(monkeypatch):
    """Scoping is load-bearing: BRIEF.md §4 records the Guardian answering about a different
    agent entirely when the question named none."""
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.setenv("CHATSEE_AGENT", "Acme Support Agent")
    seen = {}

    def _capture(question, *_a, **_k):
        seen["q"] = question
        return {"answer": "NONE"}

    monkeypatch.setattr(s.g, "ask_guardian", _capture)
    s.main([])

    assert "Acme Support Agent" in seen["q"]
    assert "24 hours" in seen["q"]


def test_timeout_is_clamped_for_the_hook_not_inherited_from_the_long_default(monkeypatch):
    """CHATSEE_MCP_TIMEOUT defaults to 300s. Nothing that runs before a developer can type
    should be able to hang that long."""
    monkeypatch.setenv("CHATSEE_MCP_KEY", "cs-test-key")
    monkeypatch.setenv("CHATSEE_AGENT", "Acme Support Agent")
    monkeypatch.setenv("CHATSEE_MCP_TIMEOUT", "300")
    monkeypatch.setattr(s.g, "ask_guardian", lambda *_a, **_k: {"answer": "NONE"})

    s.main([])
    assert int(os.environ["CHATSEE_MCP_TIMEOUT"]) <= 60


def test_summary_strips_portal_click_here_anchors():
    """Live answers carry `— click here to view them *(records page — filter not applied)*`
    on every line. It is a portal affordance and pure noise in a terminal."""
    answer = (
        "EXE_19  Identical Tool Loop  **8** — click here to view them "
        "*(records page — filter not applied)*"
    )
    out = s.summarize(answer, "A", 24)
    assert "click here" not in out
    assert "filter not applied" not in out
    assert "EXE_19  Identical Tool Loop  **8**" in out


def test_summary_collapses_blank_lines_between_entries():
    """The Guardian double-spaces every code; five codes became eleven lines on screen."""
    answer = "EXE_19  loop  8\n\nREA_18  evidence  6\n\nREA_26  spinning  4"
    body = s.summarize(answer, "A", 24).splitlines()[1:]
    assert body == ["EXE_19  loop  8", "REA_18  evidence  6", "REA_26  spinning  4"]
