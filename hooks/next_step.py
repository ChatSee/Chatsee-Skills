#!/usr/bin/env python3
"""Claude Code SessionStart hook: tell the developer the one next step for ChatSee.

Installing the plugin can't ask questions, so the first session after it does: a developer
who just installed ChatSee Skills sees what to say next instead of having to read docs.

- Project not connected yet  -> "Say: set up ChatSee" (asks for the org and agent names).
- Connected by agent sign-up -> claimed or not, and the deletion date if not.
- Anything goes wrong        -> print nothing. A start-up hint must never break a session.

Standard library only; one network call at most (3 s), to the project's own ChatSee.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path


def read_env(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    f = root / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def nice_date(iso: str | None) -> str:
    """2026-11-19T11:52:54.953 -> 19 Nov 2026, 11:52 UTC (the raw text if it doesn't parse)."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "")[:19]).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return f"{iso} UTC"


def claim_state(env: dict[str, str]) -> dict | None:
    api, key = env.get("CHATSEE_API_URL"), env.get("CHATSEE_SETUP_KEY")
    if not (api and key):
        return None
    req = urllib.request.Request(f"{api.rstrip('/')}/v1/connect/agent/integration-check",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read() or b"{}")


def main() -> None:
    try:
        cwd = json.loads(sys.stdin.read() or "{}").get("cwd")
    except ValueError:
        cwd = None
    root = Path(cwd or os.getcwd())
    env = read_env(root)

    if not env.get("CHATSEE_AGENT_ID"):
        msg = ("ChatSee Skills is installed. Next step: say \"set up ChatSee\". Claude will create a free "
               "ChatSee organisation for this project, asking you to confirm each name, and connect your "
               "agent under observation. Already have a ChatSee account? Run /mcp, select chatsee, then "
               "Authenticate.")
        ctx = ("ChatSee Skills is installed but this project is not connected to ChatSee yet. If the "
               "developer asks to set up ChatSee, says yes/next/go ahead to this hint, or asks what to do "
               "next, use the chatsee-account skill (it asks for the names and the terms, one question at a time).")
    else:
        try:
            state = claim_state(env)
        except Exception:
            state = None
        if state and not state.get("claimed"):
            msg = (f"ChatSee: action required. Please claim this project's organisation by "
                   f"{nice_date(state.get('expires_at'))}: open the claim link, enter your work email and set a "
                   f"password, then confirm the verification code ChatSee sends to that email. Unclaimed "
                   f"organisations are permanently deleted, together with their agent and all received "
                   f"conversations ({state.get('events_received', 0)} received so far).")
            ctx = ("The project's ChatSee organisation is unclaimed. Remind the developer to claim it before "
                   "using guardian-query, remediation or structural-correction; reading data needs the claim.")
        else:
            msg = ("ChatSee is connected for this project. Try: \"What are the top errors for my agent?\" "
                   "(First time? Run /mcp, select chatsee, then Authenticate.)")
            ctx = "This project is connected to ChatSee (CHATSEE_AGENT_ID in .env)."

    print(json.dumps({"systemMessage": msg,
                      "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
