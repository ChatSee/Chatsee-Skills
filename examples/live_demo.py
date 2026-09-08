#!/usr/bin/env python3
"""Live end-to-end run of the four skills against the REAL ChatSee Guardian.

Runs each skill, scoped to the agent in $CHATSEE_AGENT. Output streams step by step
(each Guardian call takes ~10-60s — ask_guardian is agentic).

Exits non-zero if ANY step fails, and says which. A step that errors must never be
reported as a completed loop.

    set -a && source .env.<agent> && set +a && ./.venv/bin/python examples/live_demo.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
AGENT = os.environ.get("CHATSEE_AGENT", "")
PROMPT_FILE = os.environ.get(
    "CHATSEE_PROMPT_FILE", os.path.join(ROOT, "examples", "sample_agent", "PROMPT.md")
)

for _v in (
    "CHATSEE_MCP_KEY",
    "CHATSEE_MCP_URL",
    "CHATSEE_AGENT",
    "CHATSEE_AGENT_ID",
    "CHATSEE_TENANT_ID",
):
    if not os.environ.get(_v):
        sys.exit(f"{_v} not set — run `source .env` first (see .env.example).")

failures: list[str] = []
skipped: list[str] = []


def run(step: str, *args) -> None:
    """Run a step, inheriting stdout so it streams. Record (don't raise on) failure."""
    result = subprocess.run([PY, *args], cwd=ROOT)
    if result.returncode != 0:
        failures.append(step)
        print(f"  ✗ {step} FAILED (exit {result.returncode})", flush=True)


def skip(step: str, why: str) -> None:
    """A step we deliberately did not run. Never counted as a pass — or as a failure."""
    skipped.append(step)
    print(f"  ⊘ {step} SKIPPED — {why}", flush=True)


def banner(step: str, title: str) -> None:
    print(f"\n{'=' * 72}\n  {step} — {title}\n{'=' * 72}", flush=True)


def main() -> None:
    print("ChatSee agent self-improvement — LIVE loop", flush=True)
    print(f"agent under observation: {AGENT}\n(each Guardian call takes ~10-60s)", flush=True)

    banner("OBSERVE  (skill 1)", "the agent reports a turn to the Guardian")
    # No stub fallback: there is nothing worth reporting from a canned turn, so a missing key
    # is a SKIP, stated as one. A skipped step must never read as a pass.
    if os.environ.get("ANTHROPIC_API_KEY"):
        run(
            "skill 1 telemetry",
            ".claude/skills/telemetry-setup/assets/instrumented_agent.py",
            "how many Python files are tracked in this project?",
        )
    else:
        skip("skill 1 telemetry", "ANTHROPIC_API_KEY not set — the agent needs its own model")

    banner("ASK  (skill 4)", "what's going wrong in production?")
    run(
        "skill 4 query",
        ".claude/skills/guardian-query/scripts/query_guardian.py",
        "--agent",
        AGENT,
        "Top 3 error codes with counts?",
    )

    banner("REMEDIATE  (skill 2)", "fetch the Guardian's approved prompt-fixes")
    run("skill 2 fetch", ".claude/skills/remediation/scripts/fetch_remediation.py", "all")

    banner(
        "APPLY  (skill 2)",
        f"splice them into a prompt — DRY RUN, {os.path.basename(PROMPT_FILE)} not modified",
    )
    run(
        "skill 2 apply (dry run)",
        ".claude/skills/remediation/scripts/apply_to_prompt.py",
        PROMPT_FILE,
        "--mode",
        "all",
    )

    banner("CORRECT  (skill 3)", "the agent's deeper, code-level failures")
    run(
        "skill 3 structural",
        ".claude/skills/structural-correction/scripts/pull_insights.py",
        "--agent",
        AGENT,
    )

    print(f"\n{'=' * 72}", flush=True)
    if skipped:
        print(f"  skipped: {', '.join(skipped)}", flush=True)
    if failures:
        print(f"  INCOMPLETE — {len(failures)} step(s) failed: {', '.join(failures)}", flush=True)
        print(f"{'=' * 72}", flush=True)
        sys.exit(1)
    print("  Loop: observe → ask → remediate(prompt, dry run) → correct(code).", flush=True)
    print(f"{'=' * 72}", flush=True)


if __name__ == "__main__":
    main()
