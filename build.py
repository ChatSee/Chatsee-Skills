#!/usr/bin/env python3
"""Generate every platform bundle from the canonical `skills/` directory.

There is exactly one copy of the four skills — `skills/`. Everything else in this file is
either a config file written from a template, or a mirror of `skills/` at a path some host
insists on. Nothing here is hand-maintained, which is the point: four hand-kept copies of the
same skill is how they start disagreeing about how to call the Guardian.

Who reads what
--------------
  Claude Code (plugin)  .claude-plugin/plugin.json   -> ./skills/          (direct, no copy)
  Codex       (plugin)  .codex-plugin/plugin.json    -> ./skills/          (direct, no copy)
  Gemini CLI  (ext)     platforms/gemini/            -> its own skills/    MIRROR
  Claude Code (project) .claude/skills/                                    MIRROR
  Cursor      (project) .cursor/skills/                                    MIRROR
  Copilot     (repo)    .github/skills/ + .github/mcp.json                 MIRROR

Gemini gets its own directory rather than sharing the repo root. Sharing it meant Gemini
discovered Claude Code's `hooks/hooks.json` and ran it with `${CLAUDE_PLUGIN_ROOT}` never
expanded, so every Gemini session opened with a failed SessionStart hook.

Never edit a mirror: `--check` fails the build when one drifts.

The two things that change before publication
---------------------------------------------
`MCP_URL` and `AUTH_MODE`, below. They are variables and not typed into four config files by
hand, so switching the demo host for production, or `bearer-env` for `oauth`, is a one-line
edit plus a rebuild rather than an edit in four places that is easy to do in three.

Usage
-----
    python build.py            # write the bundles
    python build.py --check    # exit 1 if anything is stale (for CI)
"""

from __future__ import annotations

import argparse
import base64
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANONICAL = ROOT / "skills"

# ── The two things that change before we publish ────────────────────────────
MCP_URL = "https://dev-react.chatsee.ai/mcp/"  # dev, sign-in; main stays on gcp-demo + keys until release (CSA-4027)
AUTH_MODE = "oauth"  # sign in with ChatSee; no key in any generated config

VERSION = "1.0.0"
KEY_VAR = "CHATSEE_MCP_KEY"
AGENT_VAR = "CHATSEE_AGENT"
SERVER_NAME = "chatsee"

DESCRIPTION = (
    "Monitor your AI agent with ChatSee and fix its failures — prompt-level and code-level — "
    "from your coding agent. Telemetry setup, Guardian queries, remediations, and structural "
    "code fixes over one MCP, plus a startup check that surfaces recent failures."
)

# Hosts that will only read skills from a fixed path, so they get a copy of `skills/`.
MIRRORS = (".claude/skills", ".cursor/skills", "platforms/gemini/skills", ".github/skills")

STARTUP_SCRIPT = "skills/guardian-query/scripts/startup_check.py"


# ── auth ────────────────────────────────────────────────────────────────────
# Each host interpolates environment variables into config with its own syntax, and getting
# one wrong fails silently — the literal string is sent as the credential and the server just
# answers 401. Claude Code and Codex take ${VAR}; Cursor wants ${env:VAR}; Gemini takes $VAR.


def auth_headers(syntax: str) -> dict:
    """The Authorization header for one host, or nothing at all once we are on OAuth."""
    if AUTH_MODE == "oauth":
        # The client performs the OAuth flow after our 401 points it at the protected-resource
        # metadata. No credential belongs in a config file in that world.
        return {}
    ref = {"braced": "${%s}" % KEY_VAR, "cursor": "${env:%s}" % KEY_VAR, "bare": "$%s" % KEY_VAR}[syntax]
    return {"Authorization": f"Bearer {ref}"}


def write_json(rel: str, payload: dict, target: Path) -> None:
    path = target / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── mirrors ─────────────────────────────────────────────────────────────────


def sync_mirror(rel: str, target: Path) -> None:
    """Replace <target>/<rel> with an exact copy of `skills/`.

    Removed wholesale rather than merged: a skill deleted from the canonical tree has to
    disappear from the mirrors too, or a host keeps offering a skill that no longer exists.
    """
    dest = target / rel
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CANONICAL, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


# ── per-host config ─────────────────────────────────────────────────────────


def build_claude(target: Path) -> None:
    write_json(
        ".claude-plugin/plugin.json",
        {
            "name": "chatsee-skills",
            "displayName": "ChatSee Skills",
            "version": VERSION,
            "description": DESCRIPTION,
            "author": {"name": "ChatSee", "url": "https://chatsee.ai"},
            "homepage": "https://github.com/ChatSee/Chatsee-Skills",
            "repository": "https://github.com/ChatSee/Chatsee-Skills",
            "keywords": ["chatsee", "observability", "agent-reliability", "remediation", "guardian", "mcp"],
            "skills": "./skills/",
            "mcpServers": "./.mcp.json",
        },
        target,
    )
    write_json(
        ".mcp.json",
        {"mcpServers": {SERVER_NAME: {"type": "http", "url": MCP_URL, "headers": auth_headers("braced")}}},
        target,
    )
    write_json(
        "hooks/hooks.json",
        {
            "description": (
                "SessionStart hook: asks the Guardian for the agent's recent failures and surfaces "
                f"them. Needs {KEY_VAR} and {AGENT_VAR} in the environment; python must be on PATH."
            ),
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": f'python -u "${{CLAUDE_PLUGIN_ROOT}}/{STARTUP_SCRIPT}"'}]}
                ]
            },
        }
        if AUTH_MODE != "oauth"
        else OAUTH_NO_HOOK,
        target,
    )


# The startup hook reads CHATSEE_MCP_KEY and has nothing to do after an OAuth sign-in (a
# hook cannot use the editor's MCP connection), so OAuth builds ship it switched off.
OAUTH_NO_HOOK = {
    "description": "No session-start hook: it needs an API key, and this build signs in with ChatSee.",
    "hooks": {},
}


def build_codex(target: Path) -> None:
    write_json(
        ".codex-plugin/plugin.json",
        {
            "name": "chatsee-skills",
            "version": VERSION,
            "description": DESCRIPTION,
            "author": {"name": "ChatSee", "url": "https://chatsee.ai"},
            "homepage": "https://github.com/ChatSee/Chatsee-Skills",
            "repository": "https://github.com/ChatSee/Chatsee-Skills",
            "keywords": ["chatsee", "observability", "agent-reliability", "remediation", "guardian", "mcp"],
            "skills": "./skills/",
            "mcpServers": "./.mcp.json",
            "interface": {
                "displayName": "ChatSee Skills",
                "shortDescription": "Detect and fix your AI agent's failures from your coding agent.",
                "category": "Developer Tools",
            },
        },
        target,
    )
    write_json(
        "marketplace.json",
        {
            "name": "chatsee",
            "interface": {"displayName": "ChatSee Skills"},
            "plugins": [
                {
                    "name": "chatsee-skills",
                    "source": {"source": "local", "path": "./"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Developer Tools",
                }
            ],
        },
        target,
    )


def build_gemini(target: Path) -> None:
    """Gemini reads `skills/` beside its manifest, in its own directory.

    `settings` is not optional decoration: Gemini filters out every environment variable an
    extension did not declare, so an undeclared CHATSEE_MCP_KEY never reaches the MCP call and
    the server answers 401 with nothing in the config visibly wrong.
    """
    # Gemini loads this every session. Without it, Gemini follows the skills' prose literally
    # and shells out to the scripts — which needs a shell approval mid-conversation, duplicates
    # the MCP call it already made, and makes it look slow beside Claude Code, which reaches for
    # the tool unprompted.
    gemini_context = (
        "# ChatSee\n\n"
        "Answer questions about this agent's production behaviour by calling the ChatSee MCP\n"
        "tools directly — `ask_guardian`, `get_remediations`, `apply_remediations`.\n\n"
        "Do NOT run the Python scripts under `skills/*/scripts/` to answer a question. They are\n"
        "a fallback for shells and CI, they duplicate what the MCP tools already do, and running\n"
        "them costs a shell approval mid-conversation.\n\n"
        + (
            "The developer signs in with ChatSee; the tools see only the agents that person may\n"
            "reach. Pass `agent_name` to name one. If unsure which, call `list_my_agents` and ask\n"
            "— never guess. Do not search for `.env` files or read `CHATSEE_AGENT` to decide.\n"
            if AUTH_MODE == "oauth"
            else "The agent is resolved server-side from the MCP key. Do not search for `.env` files or\n"
            "read `CHATSEE_AGENT` to decide which agent to ask about — the Guardian already knows.\n"
        )
    )
    ctx = target / "platforms" / "gemini" / "GEMINI.md"
    ctx.parent.mkdir(parents=True, exist_ok=True)
    ctx.write_text(gemini_context, encoding="utf-8")
    manifest = {
        "name": "chatsee-skills",
        "version": VERSION,
        "description": DESCRIPTION,
        "contextFileName": "GEMINI.md",
        "mcpServers": {SERVER_NAME: {"httpUrl": MCP_URL, "headers": auth_headers("bare"), "timeout": 600000}},
        "hooks": {} if AUTH_MODE == "oauth" else {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python ${{extensionPath}}${{/}}{STARTUP_SCRIPT} --stdout",
                        }
                    ],
                }
            ]
        },
    }
    if AUTH_MODE != "oauth":
        manifest["settings"] = [
            {
                "name": "ChatSee MCP key",
                "description": "Your ChatSee MCP key, from the agent's page in the ChatSee dashboard.",
                "envVar": KEY_VAR,
                "sensitive": True,
            },
            {
                "name": "ChatSee agent name",
                "description": "Which monitored agent this project is. Scopes every skill and the startup check.",
                "envVar": AGENT_VAR,
                "sensitive": False,
            },
        ]
    write_json("platforms/gemini/gemini-extension.json", manifest, target)


def build_copilot(target: Path) -> None:
    """GitHub Copilot: skills at `.github/skills/`, MCP at `.github/mcp.json`.

    Copilot has two surfaces and they do not share paths. Copilot **code review** and the cloud
    agent read `.github/skills/` from the repository, with the MCP server configured by an
    administrator in repository settings rather than from a file. Copilot **CLI** reads personal
    skills from `~/.copilot/skills/` and honours a project `.mcp.json` or `.github/mcp.json`.

    ⚠️ UNVERIFIED: the remote-server schema below is inferred. GitHub documents the *local*
    shape (`"type": "local"` with `command`/`args`/`tools`) and does not publish the remote one,
    and Copilot CLI was not installed when this was written, so it has never been run. Treat it
    as a starting point: install the CLI, confirm, and correct here. Three config bugs in this
    repo came from schemas that were written but not exercised — do not assume this one is right.
    """
    sync_mirror(".github/skills", target)
    write_json(
        ".github/mcp.json",
        {
            "mcpServers": {
                SERVER_NAME: {
                    "type": "http",
                    "url": MCP_URL,
                    "headers": auth_headers("braced"),
                    "tools": ["*"],
                }
            }
        },
        target,
    )


def cursor_server_config() -> dict:
    return {"url": MCP_URL, "headers": auth_headers("cursor")}


def build_cursor(target: Path) -> None:
    """Cursor takes the skills mirror plus its own MCP and hook config.

    Two host quirks are baked in here rather than left to a reader of the README:
    the hook event is `sessionStart` (camelCase — every other host capitalises it), and
    Cursor does not resolve ${env:...} inside headers for *remote* servers. The config is
    written the documented way regardless, so it starts working the day Cursor fixes it;
    until then the README's fallbacks apply.
    """
    write_json(".cursor/mcp.json", {"mcpServers": {SERVER_NAME: cursor_server_config()}}, target)
    write_json(
        ".cursor/hooks.json",
        {
            "version": 1,
            "hooks": {} if AUTH_MODE == "oauth" else {
                # The startup check makes live Guardian calls, so it gets a ceiling rather than
                # being allowed to hold the session open. Not failClosed: a Guardian that is slow
                # or down must not stop the developer from working.
                "sessionStart": [{"command": f"python {STARTUP_SCRIPT} --stdout", "timeout": 30}],
            },
        },
        target,
    )


def cursor_deeplink() -> str:
    """The 'Add to Cursor' button target: base64 of the server config, per Cursor's docs."""
    blob = json.dumps(cursor_server_config(), separators=(",", ":")).encode("utf-8")
    return (
        "cursor://anysphere.cursor-deeplink/mcp/install"
        f"?name={SERVER_NAME}&config={base64.urlsafe_b64encode(blob).decode()}"
    )


BUILDERS = (build_claude, build_codex, build_gemini, build_cursor, build_copilot)


def build(target: Path) -> None:
    for rel in MIRRORS:
        sync_mirror(rel, target)
    for builder in BUILDERS:
        builder(target)


# ── drift check ─────────────────────────────────────────────────────────────


def differences(a: Path, b: Path, rel: str = "") -> list[str]:
    """Every path under `rel` that differs between two trees."""
    cmp = filecmp.dircmp(a, b)
    out = [f"{rel}/{n}" for n in (*cmp.left_only, *cmp.right_only, *cmp.diff_files)]
    for sub in cmp.common_dirs:
        out += differences(a / sub, b / sub, f"{rel}/{sub}")
    return out


def check() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        build(fresh)
        stale: list[str] = []
        for rel in MIRRORS:
            live = ROOT / rel
            if not live.exists():
                stale.append(f"{rel} (missing)")
            else:
                stale += differences(fresh / rel, live, rel)
        for rel in (
            ".claude-plugin/plugin.json",
            ".mcp.json",
            "hooks/hooks.json",
            ".codex-plugin/plugin.json",
            "marketplace.json",
            "platforms/gemini/gemini-extension.json",
            ".cursor/mcp.json",
            ".cursor/hooks.json",
            ".github/mcp.json",
        ):
            live = ROOT / rel
            if not live.exists() or live.read_bytes() != (fresh / rel).read_bytes():
                stale.append(rel)

    if stale:
        print("Generated bundles are stale — run `python build.py`:", file=sys.stderr)
        for s in sorted(set(stale)):
            print(f"  {s}", file=sys.stderr)
        return 1
    print("All generated bundles are up to date.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if any bundle is stale")
    args = ap.parse_args()

    if args.check:
        return check()

    build(ROOT)
    print(f"Built from {CANONICAL.relative_to(ROOT)}/  (MCP_URL={MCP_URL}, AUTH_MODE={AUTH_MODE})")
    for rel in MIRRORS:
        print(f"  mirror  {rel}/")
    for rel in (".claude-plugin", ".codex-plugin", "platforms/gemini", ".cursor", ".github"):
        print(f"  config  {rel}")
    print(f"\nAdd to Cursor:\n  {cursor_deeplink()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
