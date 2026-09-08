# ChatSee skills for Codex

This is the **Codex wrapper** for the ChatSee skills — the counterpart to the Claude Code
`.claude/skills/` package. It gives Codex the **same 4 skills** over the **same ChatSee MCP**
(`ask_guardian`, `get_remediations`, `apply_remediations`). Install the wrapper for your agent;
the capability is identical, only the format differs per coding agent.

```
▶ 1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → 2 apply → 3 code fix
```

**Config (from `.env`, never hardcode keys):**
- `CHATSEE_MCP_URL` — MCP endpoint (e.g. `https://gcp-demo.chatsee.ai/mcp/`) — used by skills 2/3/4
- `CHATSEE_MCP_KEY` — `cs-live-…` key, bound to one agent — used by skills 2/3/4
- `CHATSEE_AGENT_ID`, `CHATSEE_TENANT_ID`, `CHATSEE_ENV` (`dev|qa|demo|poc`) — used by skill 1
- The agent identity is resolved automatically from the MCP key — **never ask the user for a
  tenant id or agent id when using the MCP tools.**

---

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
4. **Ensure `.env` is gitignored** — onboarding drops a `.env` with a live MCP key; add it to
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
