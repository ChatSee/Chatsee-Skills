---
name: guardian-query
description: Ask the ChatSee Guardian, in plain English from Claude Code, what's happening in production for a monitored agent — top error codes, error clusters, anomalies, sentiment. Read-only, developer-driven. Name an agent to scope the answer to it. (Skill 4 of 4.)
---

# Guardian query (skill 4)

Lets a developer ask the Guardian — from Claude Code, without the ChatSee portal — what's
happening in production. Read-only.

**Skill 3 vs. skill 4 (same data, different driver):** skill 4 = the *developer* asks and
reads; skill 3 = *Claude* consumes the same data and proposes fixes.

## First: is ChatSee connected?
Use the ChatSee MCP tools (`list_my_agents`, `ask_guardian`, `list_remediations`, `get_remediations`,
`apply_remediations`). If they are missing, or a call fails with an authentication error,
**stop and tell the developer to sign in**, then retry:
- Claude Code: `/mcp` → the ChatSee server → **Authenticate**
- Gemini CLI: `/mcp auth chatsee`
- Codex: `codex mcp login <server name>`, then restart Codex
- Cursor / VS Code: the ChatSee entry in the MCP settings → **Connect** / **Start**

**Never search for API keys, `.env` files, environment variables or config files to get
around a missing sign-in,** and never read files outside the project. The key-based scripts
described below are only for CI setups where a key was deliberately provided.

## Where this sits in the loop
```
1 telemetry → [ChatSee classifies] → ▶ 4 ask → [a human approves] → 2 apply → 3 code fix
```

**If it reports nothing detected:** classification has not finished yet (see skill 1) or the
agent has no telemetry. Not evidence of a healthy agent.

**Detecting an error does not create a fix.** Between this skill and skill 2 sits a human
approval step: a person (SRE or Admin) reviews ChatSee's suggested fix and approves it,
which makes it **Implemented**. That happens in the portal (Remediations → Approve & Apply) or in
skill 2, one remediation at a time on the developer's explicit yes. Nothing bridges the two
automatically, and that gate is deliberate: skill 2 rewrites a production system prompt.
So when the developer wants something fixed:
- **prompt-level** → skill 2: it shows each remediation's status (Open, Proposed,
  In progress, Implemented), lets them approve the waiting ones, and applies the Implemented ones
- **code-level** → skill 3, which needs no approval because it only proposes

Say which of the two you are recommending and why, rather than jumping straight to a fix.

## How to ask — call the MCP tool, don't run a script
Use the ChatSee MCP tools directly. They travel on the connection the developer signed
in with, so nothing needs a key:

- `list_my_agents` — which agents this person can see. Call it first when you're unsure
  which agent they mean.
- `ask_guardian(question, agent_name)` — the question, scoped to one agent by name.

Scoping follows the signed-in person's ChatSee permissions, exactly as the dashboard
does. A non-admin with several agents must name one; if they don't, the tool returns
their agent list — pick the one they meant and ask again rather than guessing. Admins
may omit `agent_name` to ask about the whole organization.

## Steps
1. If the agent isn't obvious, call `list_my_agents`.
2. Call `ask_guardian` with the question and `agent_name`.
3. Present the answer concisely. Pass the returned `session_id` back to `ask_guardian`
   to ask a follow-up in the same Guardian conversation.
4. To fix something: hand off to skill 2 (prompt-level) or skill 3 (structural).

**Only if the tools aren't available** (an API-key setup with no sign-in), fall back to
`query_guardian.py [--agent "<name>"] "<question>"`, which reads `CHATSEE_MCP_KEY`.

## The startup check — the one thing here that isn't pull

`scripts/startup_check.py` surfaces the agent's **last 24 hours** of failures when a session
starts, so a developer finds out without having to think to ask. Classification is
asynchronous and often lands hours after the traffic that caused it, so opening the editor is
frequently the first moment the answer exists at all.

**Opt-in** — add to `.claude/settings.json`:

```json
{"hooks": {"SessionStart": [{"hooks": [{
  "type": "command",
  "command": "python3 .claude/skills/guardian-query/scripts/startup_check.py",
  "async": true, "timeout": 60,
  "statusMessage": "Checking ChatSee for recent failures"}]}]}}
```

**`async: true` is the important part** — a Guardian answer takes ~20s and a blocking hook
would stall every session start behind it. Async runs it in the background instead.

### Reading its output

| What you see | What it means |
|---|---|
| nothing | The Guardian was reached and reported no failures in 24h. **The only silent case.** |
| `[chatsee] <agent> — failures in the last 24h: …` | Real findings. Offer to dig in — that's this skill; or hand to skill 2/3 to fix. |
| `[chatsee] could not check recent failures: …` | The call failed. Say so; don't let it read as an all-clear. |
| `[chatsee] set CHATSEE_AGENT …` | Configured but unscoped, so it refused to ask. Unscoped questions get answered about a *different* agent. |

**Don't re-run it on a whim.** If the developer wants more detail, `query_guardian.py` is the
right tool — the startup line is a notice, not the investigation.

**Tuning:** `--hours N` widens the window, `--timeout S` the deadline. Latency scales with the
window — measured 19s for 24h and 99s for 720h — so a wide window needs a matching timeout.

## What it can answer (verified live)
- **List agents** ("what agents can you see?") — paginated; identify a target by name.
- **Top error codes** ("top error codes last 24h") — codes + human names + counts.
- **Anomalies / quality** ("unusual patterns last 7 days") — error rate, escalations.
- **Sentiment** ("how is sentiment trending?").
- **Follow-ups** via `SESSION_ID=…`.

## Status
**Live-tested ✓** — lists the tenant's agents, and a scoped query returns only that agent's
codes and counts. Verified on agents in two separate tenants, including one created from
scratch for the test. Answers may carry `<redirect index="…">` UI anchors; the script strips
them.

⚠️ **The Guardian's own arithmetic is unreliable** — it has reported "1 interaction received"
for an agent with 16, and "4 structural patterns" followed by a list of 3. Error codes and counts have held up; interaction totals and self-reported tallies
have not. Quote the codes; sanity-check the totals before repeating them.
