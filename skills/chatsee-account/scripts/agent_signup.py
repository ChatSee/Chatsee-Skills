#!/usr/bin/env python3
"""Create a ChatSee organisation + agent for this project, with no sign-up form.

    python agent_signup.py signup --org "<organisation>" --agent "<agent name>" --accept-terms [--api URL]
    python agent_signup.py check  [--api URL]
    python agent_signup.py suggest

suggest Prints default organisation and agent names for this project (no network), for the
        developer to accept or override.

signup  Calls ChatSee's agent sign-up. Writes CHATSEE_AGENT_ID, CHATSEE_TENANT_ID,
        CHATSEE_ENV, CHATSEE_SETUP_KEY and CHATSEE_API_URL to ./.env, makes sure .env is
        gitignored, and prints the claim link. The setup key is never printed.
        Refuses if ./.env already names a ChatSee agent (no second organisation).
check   Has ChatSee received this agent's conversations? Exit 0 healthy, 2 no events
        yet, 1 needs attention (expired, bad key, unreachable).

The API address: --api, else CHATSEE_API_URL in ./.env, else derived from the ChatSee
server URL in ./.mcp.json (https://host/mcp/ -> https://host/api). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ENV_FILE = Path(".env")
KEYS = ("CHATSEE_AGENT_ID", "CHATSEE_TENANT_ID", "CHATSEE_ENV", "CHATSEE_SETUP_KEY", "CHATSEE_API_URL")
# Local demo stack: MCP on 8001, API on 8000.
LOCAL_MCP_TO_API = {"127.0.0.1:8001": "http://127.0.0.1:8000", "localhost:8001": "http://127.0.0.1:8000"}


def read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_env(values: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [ln for ln in lines if ln.split("=", 1)[0].strip() not in values]
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("# ChatSee (created by the chatsee-account skill). Keep this file out of git.")
    lines += [f"{k}={v}" for k, v in values.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_gitignored() -> bool:
    gi = Path(".gitignore")
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if re.search(r"(?m)^\s*/?\.env\s*$", text):
        return False
    gi.write_text(text + ("" if not text or text.endswith("\n") else "\n") + ".env\n", encoding="utf-8")
    return True


def _mcp_json_candidates() -> list[Path]:
    """The project's .mcp.json first, then the one shipped with this skill's plugin.

    Installed as a plugin (Claude Code, Codex), the project has no .mcp.json: the ChatSee
    server comes from the plugin's own, a few folders above this script.
    """
    out = [Path(".mcp.json")]
    here = Path(__file__).resolve()
    out += [p / ".mcp.json" for p in list(here.parents)[2:6]]
    return out


def api_from_mcp_json() -> str | None:
    for f in _mcp_json_candidates():
        if not f.exists():
            continue
        try:
            servers = json.loads(f.read_text(encoding="utf-8")).get("mcpServers", {})
        except ValueError:
            continue
        for name, cfg in servers.items():
            url = (cfg or {}).get("url", "")
            if "chatsee" in name.lower() or "chatsee" in url:
                parts = urlsplit(url)
                if parts.netloc in LOCAL_MCP_TO_API:
                    return LOCAL_MCP_TO_API[parts.netloc]
                return f"{parts.scheme}://{parts.netloc}/api"
    return None


def resolve_api(arg: str | None) -> str:
    api = arg or read_env().get("CHATSEE_API_URL") or api_from_mcp_json()
    if not api:
        sys.exit("Can't tell which ChatSee to use: pass --api https://<host>/api (or add the ChatSee server to .mcp.json).")
    return api.rstrip("/")


def call(method: str, url: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except urllib.error.URLError as e:
        sys.exit(f"Can't reach ChatSee at {url}: {e.reason}")


def message(body: dict) -> str:
    m = body.get("message") or body.get("detail")
    if body.get("errors"):
        m = "; ".join(str(e.get("msg", "")).replace("Value error, ", "") for e in body["errors"])
    return m if isinstance(m, str) else json.dumps(body)[:300]


def nice_date(iso: str | None) -> str:
    """2026-11-19T11:52:54.953 -> 19 Nov 2026, 11:52 UTC (the raw text if it doesn't parse)."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "")[:19]).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return f"{iso} UTC"


def cmd_signup(a: argparse.Namespace) -> int:
    env = read_env()
    if env.get("CHATSEE_AGENT_ID"):
        print(f"This project is already connected to ChatSee (CHATSEE_AGENT_ID in .env). Not creating another organisation.")
        return 3
    if not a.accept_terms:
        sys.exit("The developer must accept ChatSee's Terms of Service and Privacy Policy first (--accept-terms).")
    api = resolve_api(a.api)
    status, body = call("POST", f"{api}/v1/connect/agent/signup", {
        "org_name": a.org, "agent_name": a.agent, "source": a.source, "accept_terms": True})
    if status == 429:
        sys.exit(f"ChatSee is limiting sign-ups from this network: {message(body)} Wait, then try once more (don't loop).")
    if status != 201:
        sys.exit(f"ChatSee sign-up failed (HTTP {status}): {message(body)}")
    write_env({**body["env"], "CHATSEE_API_URL": api})
    added = ensure_gitignored()
    print(f"Created ChatSee organisation '{body['org_name']}' (Free plan) with agent '{body['agent_name']}'.")
    print(f"  tenant_id   {body['tenant_id']}")
    print(f"  agent_id    {body['agent_id']}")
    print(f"  environment {body['environment']}")
    print(f"Saved to .env: {', '.join(KEYS)}" + (" (and added .env to .gitignore)" if added else " (.env is gitignored)"))
    print(f"Action required: claim this organisation by {nice_date(body['expires_at'])}. To claim it, "
          "open the claim link, enter your work email and set a password, then confirm the verification "
          "code ChatSee sends to that email. Organisations not claimed within 3 days are permanently "
          "deleted, together with their agent, account and all received conversations.")
    print("Claim link (show only to the developer; never write it to a file or commit):")
    print(body["claim_url"])
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    env = read_env()
    key = env.get("CHATSEE_SETUP_KEY")
    if not key:
        print("No CHATSEE_SETUP_KEY in .env: this project wasn't set up by the agent sign-up. "
              "Check the portal, or ask ChatSee via its MCP tools once signed in.")
        return 1
    status, body = call("GET", f"{resolve_api(a.api)}/v1/connect/agent/integration-check", token=key)
    if status != 200:
        print(f"Integration check failed (HTTP {status}): {message(body)}")
        return 1
    state = body["status"]
    claimed = "claimed" if body.get("claimed") else f"not yet claimed (claim by {nice_date(body.get('expires_at'))}; unclaimed organisations are permanently deleted)"
    print(f"status: {state}  events received: {body['events_received']}  last: {body.get('last_event_at') or '-'}  org: {claimed}")
    return {"healthy": 0, "no_events": 2}.get(state, 1)


_WORDS = ("Amber", "Bright", "Cedar", "Coral", "Lunar", "Maple", "Nova", "Orbit", "Pine", "Quartz", "Silver", "Swift")
_GENERIC = {"src", "app", "code", "project", "demo", "test", "tmp", "repo", "workspace", "documents", "desktop"}


def _title(name: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[-_\s.]+", name) if w)


def cmd_suggest(_: argparse.Namespace) -> int:
    """Default names, so the developer only has to say yes (or give their own)."""
    import random
    root = Path.cwd()
    words = [w for w in re.split(r"[-_\s.]+", root.name.lower()) if w]
    org = _title(root.name) if words and not set(words) <= _GENERIC else f"{random.choice(_WORDS)} {random.choice(_WORDS)}"
    if not org.lower().endswith(("org", "inc", "labs", "team")):
        org += " Org"
    # The agent under observation: a sub-folder holding agent-like code, else the project itself.
    bot = next((d.name for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith((".", "_"))
                and any((d / f).exists() for f in ("agent.py", "main.py", "app.py", "bot.py", "index.js", "index.ts"))), None)
    agent = _title(bot) if bot else _title(root.name) or "My"
    if "agent" not in agent.lower() and "bot" not in agent.lower():
        agent += " Agent"
    print(json.dumps({"org": org, "agent": agent}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signup")
    s.add_argument("--org", required=True)
    s.add_argument("--agent", default="My agent")
    # Only after the developer answered yes to the terms question (SKILL.md step 2), never assumed.
    s.add_argument("--accept-terms", action="store_true",
                   help="the developer explicitly said yes to ChatSee's Terms of Service and Privacy Policy")
    s.add_argument("--source", default="claude-code")
    s.add_argument("--api")
    c = sub.add_parser("check")
    c.add_argument("--api")
    sub.add_parser("suggest")
    a = p.parse_args()
    return {"signup": cmd_signup, "check": cmd_check, "suggest": cmd_suggest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
