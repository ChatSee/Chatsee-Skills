#!/usr/bin/env python3
"""skill 3 — pull ONE agent's structural failures from the Guardian for Claude to analyze.

Asks the Guardian which of a *named* agent's recurring failures look structural
(context-window/truncation, tool-wiring, control-flow, memory growth) rather than
prompt-fixable. Claude then reads the answer, locates the cause in that agent's code, and
PROPOSES a fix. This script only fetches the evidence — the diagnosis is Claude's job.

The agent name is REQUIRED. ask_guardian is tenant-scoped (32+ agents here); with no
agent named it silently answers about some other agent — the bug this skill used to have.

    usage:  pull_insights.py --agent "<agent name>" ["custom structural question"]
            CHATSEE_AGENT="<agent name>" pull_insights.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import guardian_client as g  # noqa: E402  - after the sys.path insert above

_STRUCTURAL_Q = (
    "Which of this agent's recurring failures look STRUCTURAL — context-window/truncation, "
    "tool-wiring, control-flow, or memory-growth problems — rather than fixable by a prompt "
    "change? For each, give the error code + count and the likely code-level cause."
)


def _parse(argv):
    g.env_config.load()  # fill CHATSEE_AGENT from the project config if the shell lacks it
    agent = os.environ.get("CHATSEE_AGENT")
    rest = []
    it = iter(argv)
    for a in it:
        if a == "--agent":
            agent = next(it, None)
        else:
            rest.append(a)
    return agent, " ".join(rest).strip()


def main() -> None:
    agent, question = _parse(sys.argv[1:])
    if not agent:
        sys.exit(
            "error: name the agent to analyze.\n"
            '  pull_insights.py --agent "<agent name>"   (or set CHATSEE_AGENT)\n'
            "  (without an agent the Guardian answers about the wrong one — see skill 3 docs)"
        )

    a = g.ask_guardian(g.scope(agent, question or _STRUCTURAL_Q))
    answer = a.get("answer") or a.get("raw")
    if not answer:
        sys.exit(f"error: Guardian returned no answer. Payload keys: {sorted(a)}")
    print(re.sub(r"</?redirect[^>]*>", "", answer))  # strip UI anchors


if __name__ == "__main__":
    try:
        main()
    except (
        g.GuardianError
    ) as e:  # typed: auth / unavailable / config — never a silent "(no answer)"
        sys.exit(f"error: {e}")
