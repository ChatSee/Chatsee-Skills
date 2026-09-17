"""Client for the ChatSee Guardian MCP server (streamable HTTP) — used by skills 2, 3, 4.

Live only: requires CHATSEE_MCP_KEY and talks to the real Guardian.

Env (all required config comes from the environment — nothing is baked in):
  CHATSEE_MCP_KEY      MCP key (cs-live-…)                      REQUIRED
  CHATSEE_MCP_URL      MCP endpoint (e.g. https://…/mcp/)       REQUIRED
  CHATSEE_MCP_TIMEOUT  per-call seconds (default 300 — ask_guardian can tail past 120s)

There is deliberately NO default endpoint: a wrong-environment default is worse than a
clear error, because it silently answers about the wrong tenant's data.

Tools:
  ask_guardian(question, session_id=None)   -> {answer, session_id, tools_used, ...}
  get_remediations(mode)                     -> {skills_markdown, failure_memory_ids, total_rules}
  apply_remediations(ids, details)           -> confirmation  (STATE-CHANGING)

Errors are RAISED, never swallowed. Callers must let them propagate (or catch GuardianError
and exit non-zero) — a failed call must never look like "nothing to report".

Scope agent-specific questions with scope(agent, question): ask_guardian is tenant-scoped and
will otherwise answer about an arbitrary agent.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import os
import urllib.error
import urllib.request

import env_config

_PROTO = "2025-06-18"
_ids = itertools.count(1)


class GuardianError(RuntimeError):
    """Any failure talking to the Guardian. Callers should exit non-zero."""


class GuardianConfigError(GuardianError):
    """Missing or malformed local configuration (env vars)."""


class GuardianAuthError(GuardianError):
    """The key was rejected (401/403) — expired, revoked, or wrong environment."""


class GuardianUnavailable(GuardianError):
    """Transport failure or a server-side error (429/5xx, timeout, DNS)."""


# ---- config (read at call time, so tests and callers can set env freely) -----


def _key() -> str:
    env_config.load()
    k = os.environ.get("CHATSEE_MCP_KEY")
    if not k:
        raise GuardianConfigError(
            "CHATSEE_MCP_KEY not set, and no config file supplied it. Put it in `.env` at the "
            "project root, or point CHATSEE_ENV_FILE at the agent's env file (see .env.example)."
        )
    return k


def _url() -> str:
    env_config.load()
    u = os.environ.get("CHATSEE_MCP_URL")
    if not u:
        raise GuardianConfigError(
            "CHATSEE_MCP_URL not set, and no config file supplied it (see .env.example). "
            "There is no default: guessing the environment would query the wrong tenant."
        )
    return u


def _timeout() -> int:
    raw = os.environ.get("CHATSEE_MCP_TIMEOUT", "300")
    try:
        t = int(raw)
    except ValueError:
        raise GuardianConfigError(
            f"CHATSEE_MCP_TIMEOUT must be a whole number of seconds (got {raw!r})."
        ) from None
    if t <= 0:
        raise GuardianConfigError(f"CHATSEE_MCP_TIMEOUT must be positive (got {t}).")
    return t


# ---- public API -------------------------------------------------------------


def scope(agent: str, question: str) -> str:
    """Wrap a question so the Guardian answers for ONE named agent only.

    ask_guardian is tenant-scoped; with no agent named it silently picks one. Routing every
    agent-specific question through this is what keeps skills 3/4 from pulling other agents' data.
    """
    return (
        f'For the agent named "{agent}" ONLY. Use only this agent\'s data — do not '
        f"include, aggregate, compare, or mention any other agent. If this agent has no "
        f"relevant data, say so explicitly rather than substituting another agent.\n\n"
        f"{question}"
    )


def ask_guardian(question: str, session_id: str | None = None) -> dict:
    """Natural-language production insights. Scope agent-specific questions with scope()."""
    args = {"question": question}
    if session_id:
        args["session_id"] = session_id
    return _call("ask_guardian", args)


def get_remediations(mode: str = "pending") -> dict:
    """Approved fix-rules for this key's agent (resolved server-side). mode = pending | all."""
    if mode not in ("pending", "all"):
        raise GuardianConfigError(f"mode must be 'pending' or 'all' (got {mode!r}).")
    return _call("get_remediations", {"mode": mode})


def apply_remediations(failure_memory_ids: list[str], details: str = "") -> dict:
    """Confirm applied (Delivered → Applied). STATE-CHANGING — call only when truly applied."""
    if not failure_memory_ids:
        raise GuardianConfigError(
            "apply_remediations called with no failure_memory_ids — refusing to send an empty "
            "acknowledgement (it would move nothing and hide the fact that nothing was applied)."
        )
    return _call(
        "apply_remediations",
        {"failure_memory_ids": failure_memory_ids, "details": details},
    )


# ---- MCP plumbing (streamable HTTP + SSE) -----------------------------------


def _call(tool: str, arguments: dict) -> dict:
    """Call an MCP tool. Raises GuardianError on any failure — never returns a blank success."""
    timeout = _timeout()
    session = _open_session(timeout)
    req_id = next(_ids)
    envelope, _ = _post(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        session,
        timeout,
        req_id,
    )
    return _unwrap(tool, envelope)


def _unwrap(tool: str, envelope: dict | None) -> dict:
    """Turn a JSON-RPC envelope into the tool's payload, raising on every error shape."""
    if not envelope:
        raise GuardianUnavailable(f"{tool}: empty response from the Guardian (no JSON-RPC frame).")

    if "error" in envelope:  # JSON-RPC level failure
        err = envelope["error"] or {}
        raise GuardianError(
            f"{tool}: Guardian returned error {err.get('code', '?')}: "
            f"{err.get('message', 'unknown error')}"
        )

    result = envelope.get("result")
    if result is None:
        raise GuardianUnavailable(f"{tool}: response had neither 'result' nor 'error'.")

    content = result.get("content") or []
    text = "".join(b.get("text", "") for b in content if isinstance(b, dict))

    if result.get("isError"):  # MCP tool-level failure
        raise GuardianError(f"{tool}: {text.strip() or 'tool reported an error with no detail'}")

    if not text.strip():
        raise GuardianUnavailable(f"{tool}: Guardian returned an empty payload.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return payload if isinstance(payload, dict) else {"raw": text, "value": payload}


def _open_session(timeout: int) -> str | None:
    init_id = next(_ids)
    _, session = _post(
        {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTO,
                "capabilities": {},
                "clientInfo": {"name": "chatsee-skill", "version": "0.4"},
            },
        },
        None,
        timeout,
        init_id,
    )
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session, timeout, None)
    return session


def _post(body: dict, session: str | None, timeout: int, want_id: int | None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {_key()}",
        "MCP-Protocol-Version": _PROTO,
    }
    if session:
        headers["mcp-session-id"] = session

    req = urllib.request.Request(_url(), data=json.dumps(body).encode(), headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8", "replace")
        new_session = resp.headers.get("mcp-session-id") or session
    except urllib.error.HTTPError as e:
        detail = ""
        # body may be unreadable; the status still matters
        with contextlib.suppress(Exception):
            detail = e.read().decode("utf-8", "replace")[:300].strip()
        if e.code in (401, 403):
            raise GuardianAuthError(
                f"Guardian rejected the key (HTTP {e.code}). Check CHATSEE_MCP_KEY and that "
                f"CHATSEE_MCP_URL points at the environment that issued it. {detail}"
            ) from None
        if e.code == 429 or e.code >= 500:
            raise GuardianUnavailable(f"Guardian unavailable (HTTP {e.code}). {detail}") from None
        raise GuardianError(f"Guardian request failed (HTTP {e.code}). {detail}") from None
    except urllib.error.URLError as e:
        raise GuardianUnavailable(f"could not reach the Guardian at {_url()}: {e.reason}") from None
    except TimeoutError:
        raise GuardianUnavailable(
            f"Guardian timed out after {timeout}s — raise CHATSEE_MCP_TIMEOUT if this is a slow query."
        ) from None

    return _frame(raw, want_id), new_session


def _frame(raw: str, want_id: int | None) -> dict | None:
    """Pick our JSON-RPC frame out of the response body.

    The server may stream Server-Sent Events, where progress notifications arrive alongside
    the real result. Matching on the request id is what stops a trailing progress frame from
    being mistaken for the answer.
    """
    frames = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk:
                try:
                    frames.append(json.loads(chunk))
                except json.JSONDecodeError:
                    continue
    if not frames:  # plain application/json response
        text = raw.strip()
        if not text:
            return None
        try:
            frames = [json.loads(text)]
        except json.JSONDecodeError:
            return None

    if want_id is not None:
        for f in frames:
            if isinstance(f, dict) and f.get("id") == want_id:
                return f
    for f in reversed(frames):  # otherwise: last frame that actually carries an outcome
        if isinstance(f, dict) and ("result" in f or "error" in f):
            return f
    return frames[-1] if frames else None
