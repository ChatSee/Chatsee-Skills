#!/usr/bin/env python3
"""Surface an agent's recent status (failures, health, error clusters) when a session starts.

Everything else in this repo is pull: the developer asks, the Guardian answers. This is the
one push — it runs from a `SessionStart` hook so a developer learns their agent has been
failing without having to think to ask. Classification is asynchronous and can land hours
after the traffic that caused it, so the moment a developer opens their editor is often the
first time the answer even exists.

    usage:  startup_check.py [--agent "<name>"] [--hours N] [--timeout S] [--stdout] [--only <keys>]
            keys:  failures, topcode, clusters, recent, severity, escalations   (reliable)
                   volume, health, sentiment, impact                            (arithmetic, opt-in)
            default set: failures, topcode, clusters, recent, severity, escalations
            fast preset: --only failures,topcode,escalations   (single-fact, snappiest)

Wiring (opt-in — see guardian-query/SKILL.md):

    "hooks": {"SessionStart": [{"hooks": [{"type": "command",
      "command": "python3 .claude/skills/guardian-query/scripts/startup_check.py"}]}]}

THREE RULES THIS SCRIPT BREAKS ON PURPOSE, because a session-start hook is not a skill script:

1. **It exits 0 even when the Guardian call fails.** Everywhere else a failed call must exit
   non-zero (CLAUDE.md § Errors are raised). Here a non-zero exit degrades every session in
   the repo, including sessions that have nothing to do with ChatSee. So failures are
   *reported* rather than *raised*.

2. **But it never fails silently.** A revoked key printing nothing would be exactly the bug
   that rule exists to prevent — "no output" would read as "your agent is fine". So an error
   prints one visible line naming the cause. Silence means one thing only: the Guardian was
   reached and had nothing to report.

3. **It bounds its own timeout** rather than inheriting `CHATSEE_MCP_TIMEOUT` (default 300s).
   Nothing that runs before a developer can type should be able to hang for five minutes.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import guardian_client as g  # noqa: E402  - after the sys.path insert above

# Long enough for a real agentic answer, short enough that a bad day doesn't stall the editor.
# Measured 2026-08-13 against a ChatSee environment: a 24h question took 19s, a 720h one took 99s. So the
# window size drives the latency, and 30s only fits because this asks about 24 hours.
DEFAULT_TIMEOUT = 30
DEFAULT_HOURS = 24

# The predefined STARTUP QUERY SET. Each entry is fired at session start and its answer combined
# into one block, so the questions a developer most often asks are already in the session context
# (instant to answer, no live call). They run in order, reusing ONE Guardian conversation so the
# follow-ups are cheaper than cold calls. Each is still a live call (~20s on a 24h window), so this
# trades a little startup latency for instant answers — the server-side cache (tracked separately)
# is what removes that latency. Trim the set at runtime with `--only <key>[,<key>]`.
STARTUP_QUERIES = (
    # reliable — about the error CODES and their grouping (the Guardian gets these right).
    # `failures` stays FIRST because it is the GATE (see GATE_KEY): a healthy agent goes silent after
    # this one call. `topcode`/`escalations` are FAST: single-fact, one-line answers, cheap to add.
    ("failures", "which error codes have been detected? Answer in at most 6 lines as "
                 "`CODE  name  count`, most frequent first."),
    ("topcode",  "which single error code is most frequent? One line only: `CODE  name  count`."),
    ("clusters", "what are the top 3 recurring error clusters or themes? One short line each, "
                 "naming the error codes they cover."),
    ("recent",   "which error codes were detected most recently? Newest first, one short line each."),
    ("severity", "which of the detected errors are the most severe or critical? Worst first, one "
                 "short line each with the code and why it matters."),
    ("escalations", "were there any escalations? One line: yes or no, with the count if yes."),
    # aggregate / arithmetic — the Guardian's numbers here are less reliable; opt-in via --only.
    # `volume` is fast (one line) but is still a count, so it stays opt-in with the other arithmetic.
    ("volume",   "how many failures in total, and across how many distinct error codes? One line."),
    ("health",   "give a one-line health summary: the overall error rate and whether there were escalations."),
    ("sentiment","how is user sentiment trending? Answer in one short line."),
    ("impact",   "which error codes affect the most conversations? Worst first, one short line each."),
)
_LABELS = {
    "topcode": "Top error", "failures": "Failures", "clusters": "Clusters", "recent": "Most recent",
    "severity": "Severity", "escalations": "Escalations", "volume": "Volume", "health": "Health",
    "sentiment": "Sentiment", "impact": "Impact",
}

# Default startup set — the full RELIABLE tier, so one session-start covers almost every code-based
# question a developer asks and each is then instant to answer from context (no live call). The
# trade is startup latency: each key is a live Guardian call run in sequence (they reuse one
# conversation, so follow-ups are cheaper than the cold gate call), and the server-side cache
# (tracked separately) is what removes that cost. The code-based queries `failures`, `topcode`,
# `clusters`, `recent`, `severity`, `escalations` are safe here; the arithmetic ones (`volume`,
# `health`, `sentiment`, `impact`) stay opt-in until the Guardian's counts are trusted.
#   Fast preset (single-fact, snappiest):  --only failures,topcode,escalations
#   Run any subset at will:                --only <key>,<key>
DEFAULT_KEYS = ("failures", "topcode", "clusters", "recent", "severity", "escalations")

# `failures` is the GATE: if it reports nothing, the agent is healthy and startup stays silent.
# It is asked with a NONE escape so 'no failures' is detectable; the softer queries are asked
# plainly, because offering them a NONE escape made the Guardian bail even when data existed.
GATE_KEY = "failures"
_PREAMBLE_GATE = (
    "In the last {hours} hours only, for this agent: {q} "
    "If nothing applies in that window, reply with exactly: NONE"
)
_PREAMBLE_PLAIN = (
    "For this agent in the last {hours} hours: {q} Answer concisely; do not reply NONE."
)

def _parse(argv: list[str]) -> tuple[str | None, int, int, bool, list]:
    """--agent / --hours / --timeout / --stdout / --only, env fallbacks. Unknown flags are an error."""
    g.env_config.load(announce=False)  # a hook must not print a [config] line every session
    agent = os.environ.get("CHATSEE_AGENT")
    hours, timeout = DEFAULT_HOURS, DEFAULT_TIMEOUT
    to_stdout = False

    queries = [q for q in STARTUP_QUERIES if q[0] in DEFAULT_KEYS]

    it = iter(argv)
    for a in it:
        if a == "--agent":
            agent = next(it, None)
        elif a == "--hours":
            hours = _positive_int(next(it, None), "--hours")
        elif a == "--timeout":
            timeout = _positive_int(next(it, None), "--timeout")
        elif a == "--stdout":
            to_stdout = True  # Codex SessionStart reads stdout -> context (exit 0), unlike Claude Code
        elif a == "--only":
            wanted = {k.strip() for k in (next(it, "") or "").split(",") if k.strip()}
            queries = [q for q in STARTUP_QUERIES if q[0] in wanted] or list(STARTUP_QUERIES)
        else:
            raise ValueError(f"unknown option {a!r}")
    return agent, hours, timeout, to_stdout, queries


def _positive_int(raw: str | None, flag: str) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(
            f"{flag} needs a whole number of {'hours' if 'hour' in flag else 'seconds'} (got {raw!r})"
        ) from None
    if value <= 0:
        raise ValueError(f"{flag} must be positive (got {value})")
    return value


def is_empty(answer: str) -> bool:
    """True when the Guardian's answer is essentially a 'nothing' reply, so that section is skipped.

    Anchored to the START of the answer. A health or cluster summary can legitimately contain a
    marker mid-sentence ("no escalations", "none escalated"), and matching a marker *anywhere*
    wrongly suppressed valid sections — so only an answer that *begins* with a nothing-marker (or
    is exactly one) counts as empty. A real list ("In the last 24h, three codes: …") survives.
    """
    text = answer.strip().lower()
    if not text:
        return True
    head = text.split("\n", 1)[0].strip().rstrip(".!:")
    if head in ("none", "n/a", "na", "nothing", "no", "no errors", "no failures", "no incidents"):
        return True
    return head.startswith((
        "no errors", "no error ", "no failures", "no failure ",
        "no incidents", "no incident ", "no data", "none detected", "none found",
    ))


def _clean(answer: str) -> str:
    """Strip portal-only affordances and collapse blank lines from a Guardian answer.

    The wording stays the Guardian's own — restating a result in our words is how real output
    starts looking staged, and the counts are the developer's evidence. Only portal affordances
    that mean nothing in a terminal are removed:

      `<redirect index="2">…`                                    (as query_guardian.py does)
      `— click here to view them *(records page — filter not applied)*`
    """
    body = re.sub(r"</?redirect[^>]*>", "", answer)
    body = re.sub(r"\s*[—-]?\s*click here to view (?:them|it)\s*\*?\([^)]*\)\*?", "", body, flags=re.I)
    return re.sub(r"\n{2,}", "\n", body).strip()


def render(blocks: list, agent: str, hours: int, limit: int = 1000) -> str:
    """Combine the startup query set's non-empty answers into one compact, labeled block.

    Live answers space each code onto its own line, which turned five codes into eleven lines —
    too tall for something shown before the developer has typed anything — so this stays terse.
    """
    lines = [f"[chatsee] {agent} — status in the last {hours}h:"]
    for key, ans in blocks:
        label = _LABELS.get(key, key.title())
        lines.append(f"• {label}: {ans}".replace("\n", "\n  "))
    body = "\n".join(lines)
    if len(body) > limit:
        cut = body.rfind("\n", 0, limit)
        body = (body[:cut] if cut > 0 else body[:limit]).rstrip() + "\n…"
    return body


def _emit(text: str, to_stdout: bool) -> None:
    """Surface a line to the developer, formatted per coding agent.

    Claude Code: plain text on stderr (caller returns exit 2 so SessionStart shows it; exit 0 discards it).
    Codex: a JSON envelope on stdout — Codex requires SessionStart hook output to be JSON and injects
    ``additionalContext`` into the session. Plain text triggers 'invalid session start JSON output'.
    """
    if to_stdout:
        # systemMessage -> shown VISIBLY to the developer in the Codex TUI (surfaced as a notice);
        # additionalContext -> fed to the model so it can also answer from it. Emit both.
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
            "systemMessage": text,
        }))
    else:
        print(text, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    try:
        agent, hours, timeout, to_stdout, queries = _parse(sys.argv[1:] if argv is None else argv)
    except ValueError as e:
        print(f"[chatsee] {e}", file=sys.stderr)
        return 0

    # Output plumbing differs per coding agent (see _emit):
    #   Claude Code    : plain text on stderr + exit 2 (exit 0 discards stderr).
    #   Codex (--stdout): JSON additionalContext on stdout + exit 0.
    surface_rc = 0 if to_stdout else 2

    # Not a ChatSee project, or not configured yet. Say nothing at all — a repo that has never
    # heard of ChatSee should not be nagged on every session start.
    if not os.environ.get("CHATSEE_MCP_KEY"):
        return 0

    # Configured, but we cannot tell which agent to ask about. Unscoped questions get answered
    # about an arbitrary agent on the tenant, so asking anyway would report a
    # different agent's status under this project's name. Worse than saying nothing.
    if not agent:
        _emit(
            "[chatsee] set CHATSEE_AGENT to see this agent's recent status at startup "
            "(unscoped questions answer about a different agent).",
            to_stdout,
        )
        return 0

    os.environ["CHATSEE_MCP_TIMEOUT"] = str(timeout)

    # Fire the startup query set in order, reusing ONE Guardian conversation so each follow-up is
    # cheaper than a cold call. `failures` is the gate (see GATE_KEY): if it reports nothing, the
    # agent is healthy and we stay silent rather than run the softer queries. Non-empty answers
    # are combined into one block.
    blocks: list = []
    session_id = os.environ.get("SESSION_ID") or None
    for key, q in queries:
        preamble = _PREAMBLE_GATE if key == GATE_KEY else _PREAMBLE_PLAIN
        try:
            resp = g.ask_guardian(g.scope(agent, preamble.format(hours=hours, q=q)), session_id=session_id)
        except g.GuardianError as e:
            # Rule 2: never let a broken call read as an all-clear. If the FIRST call fails the
            # Guardian is unreachable — report it. If a later one fails, keep what we have.
            if not blocks:
                _emit(f"[chatsee] could not check recent status: {e}", to_stdout)
                return surface_rc
            break
        session_id = resp.get("session_id") or session_id
        ans = resp.get("answer") or resp.get("raw") or ""
        if key == GATE_KEY and is_empty(ans):
            return 0  # healthy agent -> stay quiet entirely, skip the softer queries
        if not is_empty(ans):
            blocks.append((key, _clean(ans)))

    if not blocks:
        return 0  # nothing substantive to report -> stay quiet

    # Surface the combined block (see _emit for per-agent formatting).
    _emit(render(blocks, agent, hours), to_stdout)
    return surface_rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - a hook must not break the session, whatever happens
        print(f"[chatsee] startup check failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(0)
