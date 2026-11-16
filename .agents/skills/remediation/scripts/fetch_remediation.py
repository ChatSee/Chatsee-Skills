#!/usr/bin/env python3
"""skill 2 — fetch the Guardian's approved fix-rules for this agent.

Rules come back as ready-to-apply markdown plus the failure_memory_ids you later confirm.
The agent is resolved server-side from CHATSEE_MCP_KEY, so no agent name is needed here.

    usage:  fetch_remediation.py [all|new]      (default: all)

    all   every approved rule for this agent — what its prompt should contain. THE DEFAULT,
          because "what should be in the prompt" is almost always the question.
    new   only rules that have never been downloaded ("pending", server-side).

⚠️ **Fetching is not a read-only operation.** Any rule you download moves Created → Delivered
on the Guardian. So `new` is self-consuming: look once and it is empty next time, even though
you have applied nothing. That is why the default here is `all` — `new` used to be the default
and made the obvious sequence (look, then apply) report "nothing to apply".
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import guardian_client as g  # noqa: E402  - after the sys.path insert above

# Our vocabulary → the server's. "new" says what the mode does; "pending" reads as
# "waiting to be applied", which is not what it means.
MODES = {"all": "all", "new": "pending", "pending": "pending"}


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg not in MODES:
        sys.exit(f"unknown mode {arg!r} — use 'all' (default) or 'new'.")
    r = g.get_remediations(MODES[arg])
    md = r.get("skills_markdown", "").strip()
    if md:
        print(md)
        return
    # Empty is not an error (exit 0), and the Guardian's own wording is what gets reported —
    # no editorialising here. What an empty result MEANS, and where to go next, is SKILL.md's
    # job. stdout stays empty so `> rules.md` yields an empty file rather than prose.
    print(r.get("message", "(no rules)"), file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except g.GuardianError as e:  # typed: auth / unavailable / config — never silently "no rules"
        sys.exit(f"error: {e}")
