#!/usr/bin/env python3
"""skill 4 — ask the ChatSee Guardian a natural-language question about production.

    usage:  query_guardian.py "your question"
            query_guardian.py --agent "<name>" "top error codes last 24h"   # scoped to one agent
            SESSION_ID=<id> query_guardian.py "and by topic?"               # follow-up

Name an agent (--agent or CHATSEE_AGENT) for agent-specific questions so the Guardian
answers about that agent only. Leave it off for tenant-wide questions ("what agents can
you see?", "overall anomalies this week?").
"""

import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import guardian_client as g  # noqa: E402  - after the sys.path insert above


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
    if not question:
        sys.exit('ask something, e.g.  query_guardian.py "top error codes in the last 24 hours"')

    q = g.scope(agent, question) if agent else question
    a = g.ask_guardian(q, os.environ.get("SESSION_ID") or None)

    answer = a.get("answer") or a.get("raw")
    if not answer:
        sys.exit(f"error: Guardian returned no answer. Payload keys: {sorted(a)}")
    print(re.sub(r"</?redirect[^>]*>", "", answer))  # strip UI anchors
    if a.get("clarification"):
        print(f"\n[clarification requested] {a['clarification']}")
    if a.get("session_id"):
        print(f"\n[session_id: {a['session_id']} — SESSION_ID=… for a follow-up]")


if __name__ == "__main__":
    try:
        main()
    except (
        g.GuardianError
    ) as e:  # typed: auth / unavailable / config — never a silent "(no answer)"
        sys.exit(f"error: {e}")
