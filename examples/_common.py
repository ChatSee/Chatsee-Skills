"""Shared config + auth for the REST test utilities (`onboard_agent.py`, `approve_fix.py`).

These talk to ChatSee's REST API rather than the Guardian MCP, so they cannot reuse
`guardian/guardian_client.py` — but they inherit its rule: **no invented endpoint default.**
A wrong host does not fail, it silently creates or approves against another environment's
tenant, which is worse than a clear error.
"""

import os
import sys
from urllib.parse import urlsplit

# Same config loading as the skills, so these utilities and the skills can never disagree about
# which agent they are pointed at. Without it `--agent-id` had to be passed by hand even though
# `.env` already named the agent.
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "_shared")),
)
import env_config  # noqa: E402  - after the sys.path insert above

env_config.load()


def api_base() -> str:
    """The REST API base URL, from config only — derived, never guessed.

    `CHATSEE_API_BASE` wins. Otherwise it is derived from `CHATSEE_MCP_URL`, which every
    generated env file already carries, so the two can never point at different environments.
    """
    if base := os.environ.get("CHATSEE_API_BASE"):
        return base.rstrip("/")
    mcp = os.environ.get("CHATSEE_MCP_URL")
    if not mcp:
        sys.exit(
            "no API endpoint configured: set CHATSEE_API_BASE, or CHATSEE_MCP_URL to derive it.\n"
            "  (source the agent's env file first — see .env.example)"
        )
    parts = urlsplit(mcp)
    if not parts.scheme or not parts.netloc:
        sys.exit(f"CHATSEE_MCP_URL is not a usable URL: {mcp!r}")
    return f"{parts.scheme}://{parts.netloc}/api"


def env_alias() -> str:
    """Environment alias the SDK should be pointed at (`dev`|`qa`|`demo`|`poc`, or a URL).

    Read from config rather than from `register_agent`'s response, which returns whatever
    `CHATSEE_ENV` happens to be set on the pod that served the call (see VALIDATION.md P1/P2).
    """
    alias = os.environ.get("CHATSEE_ENV")
    if not alias:
        sys.exit("set CHATSEE_ENV (dev|qa|demo|poc, or a full URL) — see .env.example")
    return alias


def get_token(explicit: str | None, base: str) -> str:
    """Dashboard bearer token.

    Prefers `--token`. Otherwise borrows the login helper from `register_agent_demo.py`, which
    is gitignored because it embeds an RSA private key and a password — which is exactly why
    those credentials are not duplicated here.
    """
    if explicit:
        return explicit

    import httpx

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from register_agent_demo import (
            DEFAULT_EMAIL,
            DEFAULT_PASSWORD,
            login,
        )
    except ImportError:
        sys.exit(
            "no --token given and register_agent_demo.py is not importable.\n"
            "Pass --token '<bearer>', or keep that script in the repo root (it is gitignored)."
        )
    email = os.environ.get("CHATSEE_LOGIN_EMAIL") or DEFAULT_EMAIL
    password = os.environ.get("CHATSEE_LOGIN_PASSWORD") or DEFAULT_PASSWORD
    with httpx.Client(base_url=base, timeout=60.0, verify=False) as c:
        return login(c, email, password)
