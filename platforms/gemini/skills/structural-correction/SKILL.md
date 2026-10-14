---
name: structural-correction
description: Diagnose a monitored agent's deeper, code-level failures (context-window handling, tool wiring, control flow, memory growth) from the ChatSee Guardian's data, then propose a code fix for developer approval. For failures a prompt tweak can't fix — the counterpart to skill 2 (prompt-level). Always scoped to one named agent. (Skill 3 of 4.)
---

# Structural correction (skill 3)

Skill 2 applies *prompt-level* fixes; skill 4 *surfaces* insights to a human; skill 3 has
**Claude** read the Guardian's data for **one agent** and fix **structural** problems a
prompt can't — context-window/memory handling, tool-wiring, control-flow bugs.

## First: is ChatSee connected?
Use the ChatSee MCP tools (`list_my_agents`, `ask_guardian`, `get_remediations`,
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
1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → 2 apply → ▶ 3 code fix
```

**Runs independently of the approval step** — it reads detected failures directly, so it
works as soon as classification lands. Nothing needs approving first.

⚠️ **The loop does not close here.** Skill 2 acknowledges its fixes back to the Guardian
(`Delivered → Applied`); this skill has no equivalent, so a code fix is invisible to ChatSee
and there is **no regression tracking for code changes**. State that plainly when handing a
fix over — do not imply the loop is closed for structural work.

## Always scope to one named agent (this is load-bearing)
The Guardian sees every agent on the tenant. Asked without an agent, it can **silently answer
about a different one** — a bug this skill once had. So every question names the agent:

- **Signed in with ChatSee (the normal case):** call the `ask_guardian` tool with
  `agent_name`. The server checks that the person may see that agent and scopes the
  question to it. Don't know the name? Call `list_my_agents`; if it lists several, ask
  which one — never pick for them.
- **Using an API key instead:** the key is bound to one agent, so the scope is fixed.
  `scripts/pull_insights.py --agent "<name>"` is the key-only fallback; it reads
  `CHATSEE_MCP_KEY`.

## Steps
1. **Pull** structural insights for the agent with `ask_guardian(question, agent_name)`.
   Ask for structural signatures specifically, e.g. *"Which failures in the last 7 days
   point at code rather than the prompt — truncated replies, failures that grow with
   conversation length, wrong or repeated tool calls, loops that don't end? Give error
   codes, counts and example sessions."* Follow up with narrower questions to drill in.
   The Guardian can take a minute or two when the window has little data.
2. **Triage strictly** — most failures are NOT structural. **Route on the failure's
   signature, never on its error-code prefix**: the code space is undocumented, and the same
   prefix appears on both kinds (the live demo agent's `SCO_07`/`REA_26` are structural,
   while `RES_13`/`RES_05` are prompt-fixable). Claim *structural* only when the behaviour
   points at code — replies truncated mid-sentence, failures that scale with conversation
   length, the wrong tool called, a loop that won't terminate. Anything fixable by telling
   the model to behave differently is **prompt-level → hand to skill 2**. When unsure,
   prefer skill 2.
3. **Locate** the cause in the agent's code.
4. **Propose a fix** as a concrete edit, citing the Guardian evidence.
5. **Apply only with developer approval** (propose-only by default).

## Tools, and the fallback script
`ask_guardian` fetches the Guardian's view of one agent. That is all it does — the diagnosis,
locating the cause in the code, and writing the fix are Claude's job, working from the
developer's actual repository. It uses the connection the developer signed in with, so no
key is needed.

`scripts/pull_insights.py` does the same fetch for the API-key path only.

## Status
**Live-tested ✓** — a scoped call returns *only* that agent's structural failures, and an
agent-less call refuses instead of leaking another agent's data. Verified on organic data:
on a fresh agent it identified *"REA_18 Evidence Disregard — error-handling logic doesn't
halt execution when tools return errors"*, which was exactly the planted defect.

Still Claude-driven and **propose-only**: nothing reports a code fix back to the Guardian.

## Open with the team
- How far should "autonomous" go — propose-only vs. auto-apply for structural fixes?
- A hard agent filter: `ask_guardian` scopes by name in the NL prompt (strong, not a
  guaranteed filter). A structured per-agent endpoint would be more robust.
