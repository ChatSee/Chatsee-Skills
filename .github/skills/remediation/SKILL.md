---
name: remediation
description: Fetch the ChatSee Guardian's approved remediation rules for an agent and fold them into that agent's system prompt, then confirm them applied. The transparent, developer-invoked form of the closed loop, for prompt-level fixes. (Skill 2 of 4.)
---

# Remediation (skill 2)

Pulls the Guardian's approved fix-rules and applies them to the target agent's **system
prompt** — transparent and developer-invoked: you see the diff before anything is written.
Wired to the real ChatSee Recommendations MCP server (`_shared/guardian_client.py`).
Live only — there is no mock.

## Where this sits in the loop
```
1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → ▶ 2 apply → 3 code fix
```

**This skill reads *approved fixes*, not detected errors.** Detection is automatic; approval
is a deliberate human step in the ChatSee dashboard. An agent can carry dozens of incidents
and still have zero approved fixes.

**An empty result means nothing has been APPROVED — never that the agent is healthy.** The
Guardian's own wording for it (*"No failure memory entries for this agent"*) reads like an
all-clear and must not be relayed as one. When it comes back empty:
1. Run **skill 4** to show what was actually detected — lead with that, not with the emptiness.
2. Tell the developer which errors are worth approving, and that approval happens in the
   ChatSee dashboard. (For testing without the UI, the same two REST calls are
   `POST /v1/error_recommendations/fetch_recommendations` then `…/submit_applied_recommendations`.)
3. Re-run this skill once something is approved.

## Agent scoping is automatic
`get_remediations` resolves tenant + agent **server-side from `CHATSEE_MCP_KEY`** — the key
is bound to one agent, so no agent name is passed. (Contrast skill 3/4's `ask_guardian`,
which must be scoped by name.) To act on a different agent, use that agent's key.

## Where the prompt lives is YOUR problem to solve, not the script's

**Every agent stores its prompt somewhere different, and you can read the codebase.** Find it,
edit it, verify it, acknowledge it. Do not tell a developer their prompt is in an unsupported
place — there is no such place, only places the shortcut script cannot handle mechanically.

Shapes you will meet, and all of them are fine:

| Where the prompt lives | How you apply the fix |
|---|---|
| A prose file (`.md`, `.txt`) | `apply_to_prompt.py` — shortcut below |
| A Python string literal | `apply_to_prompt.py` — shortcut below |
| A JS/TS template literal, a Go const, a Ruby heredoc | Edit it yourself, then `confirm_applied.py` |
| A YAML/JSON/TOML key | Edit that key with a real parser, keeping the file valid |
| Assembled from fragments at runtime | Work out which fragment carries the system instructions; if genuinely ambiguous, ask |
| A database row, a CMS | Write it back through whatever the app already uses |
| A prompt-management service (Langfuse, PromptLayer, Braintrust) | Create a **new version** through their API — do not mutate one in place, that defeats their versioning |
| A vendor console (Copilot Studio, Agentforce, Bedrock) | Not on disk. Use their API, or hand the developer the exact text and where to paste it |

ChatSee is built for this: its own docs say injection is done by *"the customer's local
tooling"* and the MCP call is only the acknowledgement. **You are the local tooling.**

### Rules for editing by hand

1. **Keep the markers.** Wrap the rules in `<!-- chatsee:failure-memory:start … -->` /
   `<!-- chatsee:failure-memory:end -->`, or the nearest equivalent the format allows. They are
   what makes the next apply replace the block instead of stacking a second copy. If the format
   cannot carry them (a database column, a console text box), say so, and expect to replace the
   whole managed section by hand next time.
2. **Show the diff before writing.** Non-negotiable — this edits what the agent says to every
   customer.
3. **Verify the file still loads.** Re-parse the YAML, re-import the module, re-run the agent
   once. A prompt file that no longer parses takes the agent down.
4. **Back up first** if you are not editing something under version control.
5. **Then acknowledge** with `confirm_applied.py`, or the loop stays open and ChatSee still
   believes the fix was never applied.

### The shortcut

`apply_to_prompt.py` handles the two shapes that need no judgement — a prose file, and a
Python string literal (edited through the AST, re-parsed afterwards, write refused unless the
file still compiles and the variable still holds exactly the intended text). It does the
backup, the atomic write, the idempotent markers, the local record and the acknowledgement in
one step. Use it when it fits; it is not the only door.

For Python it finds the variable by name — `SYSTEM_PROMPT`, `SYSTEM_MESSAGE`,
`SYSTEM_INSTRUCTIONS`, `INSTRUCTIONS`, `SYSTEM`, `PROMPT` — or `--var NAME`. A computed prompt
(f-string, concatenation) it refuses, because rewriting one could silently change what the
agent sends; that is a case for editing by hand.

## Scripts
- `scripts/fetch_remediation.py [all|new]` — show the approved rules. Default `all`.
- `scripts/apply_to_prompt.py <target> [--mode all|new] [--var NAME] [--write] [--confirm]` —
  the shortcut. **Dry-run by default**; `--write` applies, `--confirm` acknowledges.
- `scripts/confirm_applied.py <id>… --note "what you changed" [--target <where>]` — acknowledge
  a fix **you** applied. This is the general path and works regardless of where the prompt
  lives. Both scripts write the same `.chatsee/applied.jsonl` record.

## A fix has ONE state. Read this before interpreting any output.

| State | Means |
|---|---|
| **Created** | A human approved it in the dashboard. Nobody has downloaded it yet. |
| **Delivered** | It has been downloaded. Says nothing about whether it was applied. |
| **Applied** | The developer confirmed it is in the agent's prompt. |
| **Rejected** | Declined in the dashboard. |

There is no separate "marked" concept — the Guardian's `"Skill marked as Applied."` is just
its wording for "the state is now Applied".

⚠️ **Downloading a rule changes its state** (`Created → Delivered`). There is no way to look
without marking it delivered. So the server's `pending` really means *"never downloaded"*, not
*"waiting to be applied"* — a rule stops being pending the moment you read it, even though
nothing has been applied. This skill therefore says **`new`** instead of `pending`, and
**defaults everything to `all`**.

**Two different empty results — do not confuse them:**
- *"No pending remediations."* → nothing **new**. There may be plenty already downloaded;
  re-run with `all`.
- *"No failure memory entries for this agent."* → nothing has been **approved** at all. This
  is the one that needs a human in the dashboard.

## Steps
1. `fetch_remediation.py` — show every approved rule (add `new` for only the undownloaded ones).
2. `apply_to_prompt.py <agent-prompt-file>` — review the diff. Nothing is written.
3. Re-run with `--write` to apply between `<!-- chatsee:failure-memory:start/end -->` markers
   (re-running replaces the block, never duplicates it). Each apply appends a record to
   `.chatsee/applied.jsonl`.
4. Once the rules are truly in place, add `--confirm` to acknowledge.
   ⚠️ **State-changing:** moves each failure memory `Delivered → Applied` on the Guardian.

## Closed-loop alignment
Applying a fix moves a `failure_memory` through `Created → Delivered → Applied`
(`mcp_delivery`). The MCP `apply_remediations` tool and the SDK's
`POST /v1/api/closed-loop/acknowledge-remediations` are two doors to the same transition;
our marker block *is* the "inject the skill into the prompt" step it expects first.

## Notes & status
- Key in `CHATSEE_MCP_KEY` (env), endpoint `CHATSEE_MCP_URL` (env, **no default** — a
  wrong-environment default would silently query the wrong tenant).
- **Live-tested ✓, loop closed** — the full `Created → Delivered → Applied` transition has
  run on two agents in two separate tenants, confirmed by the applied id leaving the pending
  set on a re-fetch (not merely a 200 response). Transcript:
  `tests/fixtures/closed_loop_live.md`; full write-up in `VALIDATION.md`.
- Every apply appends a record to `.chatsee/applied.jsonl` **beside the prompt file**, so the
  history lives in the agent's own repo regardless of where the command was run from.
- The SDK's alternative REST door (`POST /v1/closed-loop/acknowledge-remediations`) is now
  **routed and live** — it was a 404 until `ChatSee-Api` PR #1904 landed. This skill still uses
  the MCP `apply_remediations` tool, which has always been the working path; the REST door
  matters for anyone following the SDK's own documentation.
