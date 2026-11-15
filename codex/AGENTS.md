# ChatSee skills for Codex

This is the **Codex wrapper** for the ChatSee skills — the counterpart to the Claude Code
`.claude/skills/` package. It gives Codex the **same 5 skills** over the **same ChatSee MCP**
(`list_my_agents`, `create_agent`, `ask_guardian`, `get_remediations`, `apply_remediations`).
Install the wrapper for your agent; the capability is identical, only the format differs per
coding agent. (The Codex plugin, `.codex-plugin/plugin.json`, loads the full skills from
`skills/` directly; this file is the short version for repos that use `AGENTS.md` only.)

```
▶ 0 account → 1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → 2 apply → 3 code fix
```

**Connecting:** the developer signs in with their own ChatSee account — no API key:
`codex mcp login <server name>`, then restart Codex. The tools then see only the agents that
person may reach. **Never ask the user for a tenant id or agent id**: call `list_my_agents`.
(Older setups used a `cs-live-…` key in `CHATSEE_MCP_KEY`; that still works where configured.)

---

## Skill 0 — chatsee-account  ("create a ChatSee account / tenant / organisation")
For developers with **no ChatSee account yet**. Nothing is created by you: they fill in
ChatSee's sign-up page in the browser.
1. Call `list_my_agents`. If it works, they already have an organisation — tell them and stop.
2. Open the sign-up page: the ChatSee MCP URL's host + `/connect/signup`
   (`https://dev-react.chatsee.ai/mcp/` → `https://dev-react.chatsee.ai/connect/signup`) with
   `python -m webbrowser "<page>"`, and **always print the link** too. They enter name, work
   email, organisation, password and the emailed 6-digit code, and land on **"Your ChatSee
   account is ready"**. They keep that tab open. Never ask for or type their details yourself.
3. Ask them to run `codex mcp login <server name>` and restart Codex. The browser is already
   signed in, so they click **Continue**, then **Allow**.
4. Call `list_my_agents` again (a new organisation has 0 agents), then offer `create_agent`
   or skill 1.

## Skill 1 — telemetry-setup  ("set up ChatSee telemetry / monitoring")
Instrument the developer's **agent code** so each real user turn streams to ChatSee. This edits
the agent's own source — the subject is its **real end-user conversations**, not this Codex session.
1. **Find the turn loop** — where a user message enters and the final reply leaves (the `while`
   around `messages.create`, or the framework handler).
2. **Install the SDK** into the interpreter the agent runs on: `python -m pip install chatsee-ai`.
3. **Wrap one turn** with four calls (read `agent_id`/`tenant_id`/env from the agent's config —
   **never invent the environment**):
   ```python
   from chatsee import ChatseeTracker
   tracker = ChatseeTracker(agent_id=AGENT_ID, tenant_id=TENANT_ID,
                            api_base_url=CHATSEE_ENV, verify_ssl=True)
   tracker.start_turn(user_message=user_msg, system_prompt=system_prompt)
   tracker.log_tool_call(tool_name, tool_input, result=tool_result)  # per tool call
   tracker.log_exception(exc)                                        # on failure
   tracker.end_turn(bot_message=answer)                              # POSTs the turn
   ```
   Auth is the `agent_id` + `tenant_id` themselves — no key for telemetry; it fails **open**
   (if ChatSee is unreachable the agent keeps serving users).
   Get `agent_id` / `tenant_id` from `list_my_agents` (or `create_agent` for a new agent).
4. **Ensure `.env` is gitignored** — if the agent keeps ids or keys in `.env`, add it to
   `.gitignore` if missing.

## Skill 2 — remediation  ("pull / apply the fixes")
1. Call `chatsee.get_remediations` with `mode="pending"` (use `"all"` for a full resync) and
   show the returned markdown rules.
2. Apply those rules to the agent's **prompt / instructions / guardrails** in this repo.
3. Call `chatsee.apply_remediations` with the `failure_memory_ids` from step 1 and a short
   `details` note of what you changed.

## Skill 3 — structural-correction  ("diagnose / fix the code bug")
Some failures are in the **code**, not the prompt.
1. Call `chatsee.ask_guardian` to get the exact failing behavior + the offending messages.
2. **Read the relevant source file(s)**, locate the real bug, and **propose the precise code
   change** (show a diff and explain why it fixes the error).
3. Only edit code the user approves.
*(A "report the code fix back to ChatSee" tool is not enabled in every environment yet — stop
after proposing/applying the fix if it isn't present.)*

## Skill 4 — guardian-query  ("what's wrong / errors / clusters / health / sentiment")
Call `chatsee.ask_guardian` with a clear, specific question (e.g. "top error codes and clusters
for my agent"). Summarize plainly. Reuse the same `session_id` for follow-ups.

---

## Fix decision rule (prompt fix vs code fix)
When the user asks you to **fix** a detected failure, decide the fix type this way:
1. Call `get_remediations` (`mode="pending"`).
2. **If it returns a remediation** → an approved **prompt-level** fix exists. Apply that rule to
   the agent's prompt/instructions, then call `apply_remediations` with the `failure_memory_ids`.
   (Skill 2 — the prompt fix.)
3. **If it returns nothing** ("No pending remediations") → there is no approved prompt fix, so do a
   **code-level** fix: call `ask_guardian` for the error, trace it to the agent's code, find the
   bug, and propose the fix. (Skill 3 — the code fix.)

In short: **prompt fix when a failure memory / remediation exists; otherwise a code-level fix
driven by the Guardian's detected error.**

## Style
- Be transparent: say which ChatSee tool you're calling and why, show the evidence, let the user
  approve changes. (Coding agents adopt guidance they can see, not covert instructions.)
- Guardian calls take 10–60s (agentic) — that's normal; wait for the result.
- If a Guardian answer says "no errors", telemetry may still be processing — say so rather than
  assuming the agent is clean.
