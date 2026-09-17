"""A real agent, instrumented with skill 1 — the pattern to copy into your own agent.

Real in every respect that matters: it calls Claude, Claude decides whether to use the tool,
the tool returns facts computed from the actual repository, and the answer is composed from
what came back. Nothing is canned — there is no stub model, no fixture data, and no
pre-written answer. What it demonstrates is the four instrumentation calls:

    start_turn(...) → log_tool_call(...) → end_turn(...)          (+ log_exception on failure)

Everything else here is an ordinary agent, and is meant to be replaced by yours.

Config — all from the environment, or from `.env` at the project root:
    ANTHROPIC_API_KEY                                     required (this agent's own model)
    CHATSEE_AGENT_ID / CHATSEE_TENANT_ID / CHATSEE_ENV    required (who to report to)
    CHATSEE_PROMPT_FILE   system prompt path. Skill 2 writes remediation rules INTO this file,
                          which is why the prompt lives in a file and not in this source.
    CLAUDE_MODEL          defaults to a small fast model; any model id works.

Run — the question is an argument, so nothing about the conversation is baked in:

    python instrumented_agent.py "how many Python files are in this project?"
"""

from __future__ import annotations

import os
import subprocess
import sys

import anthropic
from chatsee import ChatseeTracker

# Fill in any config not already exported, from `.env` at the project root. A deployed agent
# gets its config from its own environment — DELETE THESE THREE LINES when you copy this file.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import env_config  # noqa: E402  - after the sys.path insert above

env_config.load()

DEFAULT_MODEL = "claude-haiku-4-5"

TOOLS = [
    {
        "name": "inspect_repo",
        "description": (
            "Get facts about the repository the agent is running in: file counts by "
            "extension, total tracked files, and recent commit subjects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "extension": {
                    "type": "string",
                    "description": "File extension to count, without the dot, e.g. 'py'.",
                },
                "commits": {
                    "type": "integer",
                    "description": "How many recent commit subjects to return (0 for none).",
                },
            },
        },
    }
]


def _git(*args: str) -> str:
    """Run git in the repo this file lives in. Returns '' on any failure — the tool reports
    what it can rather than crashing the agent."""
    try:
        out = subprocess.run(
            ["git", "-C", os.path.dirname(os.path.abspath(__file__)), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def inspect_repo(extension: str = "", commits: int = 0) -> dict:
    """The agent's one tool. Every number it returns is computed now, from the real tree."""
    # `:/` anchors the pathspec at the repo root — without it git scopes ls-files to the
    # directory it was run in, which is this asset's folder, and every count comes back as 1.
    tracked = [p for p in _git("ls-files", "--", ":/").splitlines() if p]
    result: dict = {"tracked_files": len(tracked)}

    if extension:
        ext = "." + extension.lstrip(".")
        result["extension"] = ext
        result["matching_files"] = sum(1 for p in tracked if p.endswith(ext))

    if commits and commits > 0:
        subjects = _git("log", f"-{min(commits, 20)}", "--format=%s").splitlines()
        result["recent_commits"] = [s for s in subjects if s]

    if not tracked:
        result["note"] = "not a git repository, or git unavailable — counts are empty"
    return result


def code_version() -> str | None:
    """The agent's own commit — the fix boundary a regression check needs."""
    return os.environ.get("CHATSEE_CODE_VERSION") or _git("rev-parse", "--short", "HEAD").strip()


def load_system_prompt() -> str:
    """From a FILE, because that file is what skill 2 splices remediation rules into — a fix
    applied there reaches this agent on its next run with no code change."""
    raw = os.environ.get("CHATSEE_PROMPT_FILE")
    if not raw:
        sys.exit(
            "set CHATSEE_PROMPT_FILE to this agent's system-prompt file.\n"
            "  It must be a real file: skill 2 writes approved remediation rules into it."
        )
    # A relative path in `.env` is relative to the project, not to wherever this was launched.
    path = env_config.resolve(raw)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError as e:
        sys.exit(f"could not read CHATSEE_PROMPT_FILE at {path}: {e}")
    if not text:
        sys.exit(f"CHATSEE_PROMPT_FILE at {path} is empty — an agent needs a system prompt.")
    return text


def run_turn(
    tracker: ChatseeTracker,
    client: anthropic.Anthropic,
    model: str,
    system: str,
    user_msg: str,
) -> str:
    """One user→assistant exchange, tool calls included, reported to ChatSee as one turn.

    THIS is the pattern skill 1 installs. The three tracker calls below are the whole of it.
    """
    tracker.start_turn(
        user_message=user_msg,
        system_prompt=system,
        # metadata is free — the SDK forwards it verbatim — and it is what later makes
        # "did this start when we changed model / shipped that commit?" answerable.
        metadata={"model": model, "code_version": code_version()},
    )
    messages: list = [{"role": "user", "content": user_msg}]

    try:
        while True:
            resp = client.messages.create(
                model=model, max_tokens=4096, system=system, tools=TOOLS, messages=messages
            )
            if resp.stop_reason == "refusal":
                answer = "(the model declined this request)"
                break

            messages.append({"role": "assistant", "content": resp.content})
            tool_uses = [b for b in resp.content if b.type == "tool_use"]

            if not tool_uses:
                answer = "".join(b.text for b in resp.content if b.type == "text").strip()
                break

            results = []
            for tu in tool_uses:
                out = inspect_repo(**tu.input)
                print(f"  ↳ tool: inspect_repo({tu.input}) -> {out}")
                tracker.log_tool_call("inspect_repo", tu.input, result=out)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(out)})
            messages.append({"role": "user", "content": results})
    except Exception as e:
        # Report the failure and still end the turn — a broken turn is data the Guardian wants,
        # and telemetry must never mask the agent's own error.
        tracker.log_exception(e)
        tracker.end_turn(bot_message=f"(error: {e})")
        raise

    tracker.end_turn(bot_message=answer)  # POSTs the whole turn to ChatSee
    return answer


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        sys.exit(f'usage: {os.path.basename(sys.argv[0])} "<what to ask the agent>"')

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set — this agent calls a model of its own.")
    agent_id = os.environ.get("CHATSEE_AGENT_ID")
    tenant_id = os.environ.get("CHATSEE_TENANT_ID")
    env = os.environ.get("CHATSEE_ENV")  # no default — a wrong guess reports to the wrong tenant
    if not (agent_id and tenant_id and env):
        sys.exit("set CHATSEE_AGENT_ID, CHATSEE_TENANT_ID and CHATSEE_ENV.")

    model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
    system = load_system_prompt()

    # verify_ssl=True explicitly — the SDK defaults it to False and suppresses the warning,
    # which is not something to inherit silently into a production agent.
    tracker = ChatseeTracker(
        agent_id=agent_id,
        tenant_id=tenant_id,
        api_base_url=env,
        verify_ssl=True,
    )

    print(f"USER: {question}")
    try:
        answer = run_turn(tracker, anthropic.Anthropic(), model, system, question)
    except anthropic.AuthenticationError:
        sys.exit("ANTHROPIC_API_KEY was rejected — this agent's own model key is invalid.")
    except anthropic.NotFoundError:
        sys.exit(f"model {model!r} not available to this key — set CLAUDE_MODEL to one that is.")
    except anthropic.APIError as e:
        # The turn has already been reported to ChatSee with the exception attached by run_turn;
        # a stack trace here would only bury that.
        sys.exit(f"the agent's model call failed: {e}")
    print(f"ASSISTANT: {answer}")

    # end_turn fails open (never breaks the agent); on success the API assigns a session_id.
    if tracker.session_id:
        print(f"\n✓ ChatSee accepted the interaction (session_id={tracker.session_id})")
    else:
        sys.exit("\n✗ ChatSee did not confirm — check the ids, CHATSEE_ENV, and connectivity")


if __name__ == "__main__":
    main()
