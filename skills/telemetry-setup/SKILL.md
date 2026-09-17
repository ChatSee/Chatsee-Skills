---
name: telemetry-setup
description: Instrument a deployed AI agent's code so each of its user interactions (prompt, answer, tool calls) streams to the ChatSee Guardian, using the official chatsee-ai SDK. Use when a developer wants their production agent monitored by ChatSee, or says telemetry/tracing/monitoring is not set up. This edits the agent's own source; the subject is its real end-user conversations, not the Claude Code session. (Skill 1 of 4.)
---

# Telemetry setup (skill 1)

**This skill edits the developer's agent code.** It finds the agent's turn loop and adds four
SDK calls so every real conversation is reported to ChatSee, where the Guardian analyzes it and
skills 2–4 can act on it.

**Subject = the agent's real end-user conversations**, never the Claude Code session.

## Where this sits in the loop
```
▶ 1 telemetry → [ChatSee classifies] → 4 ask → [a human approves] → 2 apply → 3 code fix
```

Nothing downstream exists until this is done and traffic has flowed.

## What you are installing

Four calls, wrapped around one turn of the agent's existing loop:

```python
from chatsee import ChatseeTracker

tracker = ChatseeTracker(agent_id=AGENT_ID, tenant_id=TENANT_ID,
                         api_base_url=CHATSEE_ENV, verify_ssl=True)

tracker.start_turn(user_message=user_msg, system_prompt=system_prompt,
                   metadata={"model": model, "code_version": git_sha})
tracker.log_tool_call(tool_name, tool_input, result=tool_result)   # once per tool call
tracker.log_exception(exc)                                         # on failure
tracker.end_turn(bot_message=answer)                               # POSTs the turn
```

Auth is the **`agent_id` + `tenant_id`** themselves — there is no key. Sending fails **open**:
if ChatSee is unreachable the agent keeps serving users.

## Steps

1. **Find the turn loop.** Locate where a user message enters and a final response leaves —
   the function handling one exchange. In a raw SDK agent that is the `while` loop around
   `messages.create`; in a framework it is the handler or callback that returns the reply. If
   there are several entry points, instrument the one real users hit.

2. **Install the SDK** into the interpreter *the agent* runs on:
   `python -m pip install chatsee-ai`. (Skills 2/3/4 need nothing — standard library only.)

3. **Read the agent's config, don't invent it.** `agent_id`, `tenant_id` and the environment
   come from the agent's own configuration. **Never write a default environment** — a plausible
   guess silently ships production traffic to the wrong ChatSee, and is invisible in whichever
   environment the default happens to match.

   ⚠️ **Check `.env` is gitignored before you finish.** Onboarding drops a `.env` at the project
   root containing a **live MCP key**, and a repo that has never needed one has no rule for it.
   Add `.env` to `.gitignore` if it is missing — this is the single easiest way for a customer
   to leak a credential on their first commit. If the agent has no way to read `.env` yet,
   `python-dotenv` is the normal choice; don't make the developer export variables by hand.

   **Two config files, and the split matters.** Anything identifying *this* agent goes in the
   project's `.env`. Anything true of the *machine* — most often the model API key the agent
   calls — goes in `~/.config/chatsee/agent.env`, which every project on the machine shares:

   ```python
   load_dotenv()  # ./.env — this agent's identity
   load_dotenv(os.path.join(os.path.expanduser("~"), ".config", "chatsee", "agent.env"))
   ```

   `load_dotenv` never overrides an already-set value, so project beats machine-wide and a real
   exported variable beats both. **Do not tell the developer to export the model key in their
   shell**: anything started from that shell inherits it, including Claude Code, which redirects
   their subscription billing to that key. A file the agent reads does not have that problem.
   The skills' own loader reads the same two files, and **refuses** agent identity from the
   machine-wide one — a global default for "which agent this is" would point every project at
   one agent.

4. **Wrap the loop** with the four calls above. Construct the tracker once per process or
   session, not per turn.

5. **Leave the system prompt where it is.** Skill 2 edits a string literal in Python source
   in place, through the AST, so a prompt does not have to be moved into a file first — do not
   restructure someone's agent as a precondition for using the product.

   Mention the file option only as a *preference*, and only if it is genuinely useful to them:
   a prompt in a `.md`/`.txt` file can be changed without a code deploy, which matters if
   non-engineers edit it or if shipping code is slow. If they are happy with the literal,
   that works.

   (Prompts held in a database, a prompt-management service, or a vendor console are not
   supported yet — those need writing back through that system's own API.)

6. **Offer to verify — do not just run their agent.** Wiring up telemetry is not the same
   request as *executing* the agent, and running one is not a free or side-effect-free act:
   it spends money on their model provider, puts a real interaction into their ChatSee data,
   and **fires their agent's tools for real** — which might send an email, charge a card, or
   write to a production database. You cannot tell from the code whether it is safe.

   So finish the edit, then say what you would run and what it will touch, and let them
   decide. Run it yourself only if they say yes, or if they already asked you to test it.
   Handing them the one command to run is a perfectly good outcome.

   What to look for when it is run: a successful send assigns `tracker.session_id`. **No
   `session_id` means it did not land** — check the ids and the environment. That is the only
   immediate signal in the whole loop, so it is worth getting, which is why you offer rather
   than skip it silently.

7. **Then set expectations and stop.** Classification is asynchronous with no progress
   indicator: observed between ~2 minutes and ~90. Until it finishes the Guardian answers
   *"no errors have been detected"*, which is indistinguishable from a broken integration.
   **Do not re-instrument on the strength of that answer** — if `session_id` came back, the
   transport works. Say so, and give the rough wait.

## Details that matter

⚠️ **`verify_ssl` defaults to `False`** and the SDK suppresses the warning, so TLS
certificates go unchecked on real prompt traffic. Always pass `verify_ssl=True` explicitly.
Pass `redaction_enabled=True` to have the SDK strip PII first. (Confirmed by execution on
both `0.10.0` and the current published `0.12.1` — this is not a version that got fixed.)

**Always send `metadata`.** A free-form dict the SDK forwards verbatim, and it costs nothing.
At minimum `model` and `code_version` (a git sha): without them "did this start when we
switched models / shipped that build?" is unanswerable, because the payload has no model,
token or version fields of its own. *(Unverified: whether the backend persists and can filter
on metadata — open with the team.)*

`api_base_url` takes an environment alias (`dev`|`qa`|`demo`|`poc`) or a full URL.

## Reference implementation

`assets/instrumented_agent.py` is a **complete working instrumented agent** — real model call,
real tool-use loop, real tool, system prompt from a file, all four tracker calls in place. Two
uses:

- **The pattern** to mirror when editing the developer's agent.
- **A fallback** when there is no agent to instrument yet — a fresh repo, or proving the pipe
  works before touching production. The question is an argument:
  `python assets/instrumented_agent.py "<question>"`. Needs `ANTHROPIC_API_KEY` and
  `CHATSEE_PROMPT_FILE`.

Nothing in it is canned — no stub model, no fixture data, no pre-written answer. There is
deliberately no stubbed variant: a canned agent proves only that a POST succeeds, and a
`session_id` from a real turn is the thing worth having.

## Getting the ids

ChatSee portal → **Settings → Add agent** → name it, type **interaction** + **custom** → Add.
The ids are minted there. (`POST /v1/agents/register_agent` does the same over REST, for a
developer who would rather script it.)

⚠️ The portal's "Connect Source" snippet passes `user_id`/`tenant_name`/`api_key` and
**crashes when copy-pasted** — `tenant_name` and `api_key` are not parameters of
`ChatseeTracker`. Follow this skill, not that snippet: `agent_id` + `tenant_id` are the only
required arguments.

`user_id` is version-dependent — rejected by `0.10.0`, accepted by `0.12.1` — so don't lead
with it when reporting the bug. The portal is also passing the **agent** id into it, which
would label every interaction's end user as the agent.

The Node tab is worse than wrong: it imports `"chatsee"` from npm, and **no such package
exists** (`chatsee` and `chatsee-ai` both 404 there). The SDK is Python-only. A TypeScript or
Go agent has to POST `/v1/api/process_interaction` directly.

## Status

**Live-tested ✓** — this instrumentation has sent real agent turns and received a
server-assigned `session_id`, on agents in two separate tenants, including one created from
scratch. Live only; there is no mock. Traffic sent this way was then classified by ChatSee on
its own, surfaced by skill 4, and drove a fix through to `Applied`.

**Portable ✓** — every file under `.claude/skills/` compiles and runs on Python 3.9, verified
in a bare repo containing nothing but the skills, a `.env`, and a prompt file.

## Open with the team

The portal/response SDK snippet (`user_id`/`tenant_name`/`api_key`) does not match the
published SDK (keyless `agent_id`+`tenant_id`). Which is the intended contract — will the
package add api_key auth, or should the snippet be keyless? (SDK-vs-OTLP is settled: SDK.)

One follow-up from checking this against the real package on 2026-08-13:
- **Is a TypeScript SDK planned?** The portal's Node tab imports a package that does not
  exist on npm. If not, that tab should point at `/v1/api/process_interaction`.

## Which SDK version this skill is written against

**`0.12.1`** — our pin, and what `pip install chatsee-ai` gives you today. Everything
version-specific above was verified by executing against it, and
`tests/test_sdk_contract.py` re-checks those claims on every test run, so they fail loudly
rather than going quietly stale (they drifted once already: `user_id` was rejected by
`0.10.0` and is accepted by `0.12.1`).

That test only fires when the pin moves, so it cannot tell you a newer SDK exists. If a
version-specific claim here starts to matter, check PyPI by hand.

`0.12.1` added two optional arguments worth using — both backward-compatible:
- `start_turn(..., user_id=...)` — attribute a turn to a real end user, so the portal's
  Users view shows something better than an anonymous id.
- `log_tool_call(..., duration_ms=...)` — per-tool latency, which the interaction payload
  otherwise has no field for at all.
