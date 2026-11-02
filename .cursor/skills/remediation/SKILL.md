---
name: remediation
description: Show an agent's ChatSee remediations with their portal status (Open, Proposed, In progress, Live), let the developer approve the ones waiting for approval, fold the approved (Live) rules into that agent's system prompt, then confirm them applied. The transparent, developer-invoked form of the closed loop, for prompt-level fixes. (Skill 2 of 4.)
---

# Remediation (skill 2)

Shows the agent's remediations as ChatSee shows them, lets the developer approve the ones
still waiting, and applies the approved rules to the target agent's **system prompt**:
transparent and developer-invoked, you see the diff before anything is written.
Wired to the real ChatSee Recommendations MCP server. Live only, there is no mock.

## First: is ChatSee connected?
Use the ChatSee MCP tools (`list_my_agents`, `list_remediations`, `approve_remediation`,
`get_remediations`, `apply_remediations`, `ask_guardian`). If they are missing, or a call
fails with an authentication error,
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
1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → ▶ 2 apply → 3 code fix
```

**This skill applies *approved* fixes, not detected errors.** Detection is automatic;
approval is a deliberate human decision, made in the ChatSee portal or here, by the developer,
one remediation at a time. An agent can carry dozens of incidents and still have nothing
approved.

## Use ChatSee's words for status
A remediation has a **status**, and it is the one the portal's Remediations screen shows.
Always use these words and the **FM code** (FM-004…), so the developer can find the same row
in the portal:

| Status (portal) | Means | What this skill offers (`next_step`) |
|---|---|---|
| **Open** | Logged; may or may not have a fix yet | Approve and apply, if it has a fix; otherwise nothing |
| **Proposed** | A fix is waiting for sign-off | Approve and apply |
| **In progress** | Being worked on, not signed off | Approve and apply |
| **Live** (stored as *implemented*) | Approved. The fix should be in effect | Apply, or nothing if it is already in the prompt |
| **Regressed** | Was Live, then marked as not working | Approve and apply again |

Two kinds are never applied to a prompt: a remediation **with no fix yet**, and a **Jira**
remediation (its work ships through the ticket). `list_remediations` marks both `none`.

**Approving = the portal's Approve & Apply.** It sets the status to **Live** in ChatSee, with
the same history and versioning as the portal button. It needs the **SRE or Admin** role, the
same as in the portal; `list_remediations` returns `can_approve` for the signed-in person.

**Nothing Live is not "healthy".** It means nothing is approved yet. Say how many are waiting
(Proposed, In progress, Open), and run **skill 4** to show what was actually detected.

## Which agent
**Signed in with ChatSee (the normal case):** pass `agent_name` to every remediation tool.
You can reach only agents the signed-in person is assigned, the same as in the portal. If
they have one agent, it is used automatically; if several, the tool returns their list:
call `list_my_agents` or ask which one, never guess.

**Using an API key instead:** the key is bound to one agent, so no name is passed, and
nothing can be approved (an approval needs a person): approve in the portal.

## Where the prompt lives is YOUR problem to solve, not the script's

**Every agent stores its prompt somewhere different, and you can read the codebase.** Find it,
edit it, verify it, acknowledge it. Do not tell a developer their prompt is in an unsupported
place — there is no such place, only places the shortcut script cannot handle mechanically.

Shapes you will meet, and all of them are fine:

| Where the prompt lives | How you apply the fix |
|---|---|
| A prose file (`.md`, `.txt`) | `apply_to_prompt.py` — shortcut below |
| A Python string literal | `apply_to_prompt.py` — shortcut below |
| A JS/TS template literal, a Go const, a Ruby heredoc | Edit it yourself, then the `apply_remediations` tool |
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
5. **Then acknowledge** with the `apply_remediations` tool, or the loop stays open and
   ChatSee still believes the fix was never applied.

### The shortcut

`apply_to_prompt.py` handles the two shapes that need no judgement — a prose file, and a
Python string literal (edited through the AST, re-parsed afterwards, write refused unless the
file still compiles and the variable still holds exactly the intended text). It does the
backup, the atomic write, the idempotent markers and the local record. The acknowledgement
stays with the `apply_remediations` tool. Use it when it fits; it is not the only door.

For Python it finds the variable by name — `SYSTEM_PROMPT`, `SYSTEM_MESSAGE`,
`SYSTEM_INSTRUCTIONS`, `INSTRUCTIONS`, `SYSTEM`, `PROMPT` — or `--var NAME`. A computed prompt
(f-string, concatenation) it refuses, because rewriting one could silently change what the
agent sends; that is a case for editing by hand.

## Tools, and the one script
Talk to ChatSee **through the MCP tools** — they use the connection the developer signed in
with, so nothing needs a key:

- `list_remediations(agent_name)` — every remediation with `fm_code`, `title`,
  `status_label`, `next_step`, `reason`, the rule text (`fix`) and `can_approve`.
  **Read-only**: call it as often as you like.
- `approve_remediation(failure_memory_id, agent_name)` — the portal's Approve & Apply for ONE
  remediation; it becomes **Live**. **State-changing, in the portal.** Only after the
  developer's explicit yes for that remediation (Steps, below).
- `get_remediations(mode, agent_name)` — the **Live** rules only, as `skills_markdown` (each
  rule labelled with its FM code) plus the `failure_memory_ids` you confirm later. `mode` is
  `all` (default) or `pending`.
- `apply_remediations(failure_memory_ids, details, agent_name)` — acknowledge rules that are
  now in the prompt. Refuses anything not Live. **State-changing.**

For the file edit itself, `scripts/apply_to_prompt.py` is still the shortcut for the two
mechanical shapes. Give it the rules you fetched rather than letting it fetch them:

- `scripts/apply_to_prompt.py <target> --rules-file <file> [--var NAME] [--write]` — save the
  `get_remediations` output to a file (e.g. `.chatsee/rules.json`) and pass it here. The
  script then only edits the file and never touches the network. **Dry-run by default**;
  `--write` applies. Confirm afterwards with `apply_remediations`.

**Only with an API key and no sign-in** do the older network-using scripts apply:
`fetch_remediation.py`, `apply_to_prompt.py … --confirm` (no `--rules-file`), and
`confirm_applied.py`. They read `CHATSEE_MCP_KEY`.

## Two separate states. Read this before interpreting any output.

1. **Status** (the portal's, table above): has a person approved it? Only **Live** may be applied.
2. **In the prompt or not** (`in_prompt`, from ChatSee's delivery record): has a coding agent
   put it in this agent's prompt? Behind it are three delivery states you may see in raw output:

| Delivery state | Means |
|---|---|
| **Created** | Approved, never fetched by a coding agent. |
| **Delivered** | Fetched. Says nothing about whether it was applied. |
| **Applied** | Confirmed in the agent's prompt (`in_prompt: true`). |

Delivery states are **not** portal statuses; never present "Delivered" or "Applied" as the
remediation's status. Fetching with `get_remediations` moves a rule `Created → Delivered`, so
its `pending` means *"never fetched"*, not *"waiting to be applied"*; this skill says **new**
instead and **defaults to `all`**. `list_remediations` changes nothing.

## Steps
1. **Show.** Call `list_remediations` (with `agent_name` if needed). Show a table, newest
   first: FM code · title · status (portal words) · what can be done (from `next_step`):
   - `apply`: "Live, ready to apply"
   - `done`: "Live, already in the prompt"
   - `approve_and_apply`: "<status>, needs approval"
   - `none`: the `reason` (no fix yet / Jira)

   Add one line of counts, e.g. "2 Live (1 already applied) · 1 Proposed · 1 Open, no fix".
2. **Let the developer choose.** Offer: apply the Live ones, and approve any of the
   `approve_and_apply` ones. If `can_approve` is false, say that approving needs an SRE or
   Admin (`approval_note`) and continue with the Live ones only.
3. **Approve one at a time, only on an explicit yes.** For each remediation the developer
   wants approved, show its `fix` text and ask: *"Approve FM-003 in ChatSee? It becomes Live."*
   Call `approve_remediation` only after a clear yes for **that** remediation. Never approve
   because the developer said "apply the fixes", never approve several on one vague yes, and
   never approve on your own initiative. Report each result; if one is refused, show the
   tool's message and carry on with the rest.
4. **Fetch the Live rules.** Call `get_remediations` with `mode: "all"`. The managed block in
   the prompt holds **every Live rule**, because Live means "in effect": the ones already
   applied stay, newly approved ones join. If the developer does not want a Live rule in
   effect, that is a decision for the portal (mark it Regressed), not something to drop
   silently here.
5. **Apply.** Save that output as JSON to `.chatsee/rules.json` beside the agent's code. Find
   the prompt. For a prose file or a Python literal, run
   `apply_to_prompt.py <prompt-file> --rules-file .chatsee/rules.json` and show the diff;
   nothing is written. For any other shape, edit by hand following the rules above. Then
   apply with `--write` (between `<!-- chatsee:failure-memory:start/end -->` markers;
   re-running replaces the block, never duplicates it). Each apply appends a record to
   `.chatsee/applied.jsonl`.
6. **Confirm.** Once the rules are truly in place, call `apply_remediations` with the
   `failure_memory_ids` and a note saying what changed.
   ⚠️ **State-changing:** records each one as in the prompt (`Applied`).
7. **Close.** Call `list_remediations` again and show the updated table, so the developer
   sees the same statuses the portal now shows.

## Closed-loop alignment
Approving sets the portal status to Live (`implemented`); applying moves the
`failure_memory`'s delivery record through `Created → Delivered → Applied` (`mcp_delivery`). The MCP `apply_remediations` tool and the SDK's
`POST /v1/api/closed-loop/acknowledge-remediations` are two doors to the same transition;
our marker block *is* the "inject the skill into the prompt" step it expects first.

## Notes & status
- Signed in with ChatSee, nothing is configured by hand. The API-key path alone reads
  `CHATSEE_MCP_KEY` and `CHATSEE_MCP_URL` (env, **no default** — a wrong-environment default
  would silently query the wrong tenant).
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
