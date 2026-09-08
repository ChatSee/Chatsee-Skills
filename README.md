# ChatSee — Claude Code skills for agent self-improvement

Four **Claude Code skills** that let a developer improve a monitored **deployed** AI agent
using ChatSee's **Guardian**, without leaving their editor:

1. **`telemetry-setup`** — instrument the agent so each turn streams to the Guardian.
2. **`remediation`** — pull the Guardian's approved prompt-fixes and apply them.
3. **`structural-correction`** — Claude diagnoses deeper *code* bugs and proposes fixes.
4. **`guardian-query`** — ask the Guardian, in plain English, what's going wrong.

**The loop:** observe → ask what's wrong → remediate the prompt → correct the code → repeat.

Every step is **transparent and developer-invoked** — the developer asks, sees the evidence,
and approves the change. That is deliberate: a coding agent adopts guidance it can see and
judge, and refuses instructions covertly injected into its context, so the fixes are surfaced
rather than silently applied.

👉 Full detail, architecture, and live-test results: **[`BRIEF.md`](BRIEF.md)**.

## Install (into your own agent's repo)

Copy one directory in, add one config file, open Claude Code. That is the whole install.

```bash
cp -R /path/to/ChatSee-Skills/.claude/skills  <your-repo>/.claude/skills
```

Then create `.env` at your repo root with the ids and key ChatSee gave you — see
[`.env.example`](.env.example) for the full list — and **add `.env` to `.gitignore`**: it holds
a live key.

```bash
cd <your-repo> && claude
```

The skills carry their own shared client in `_shared/`, need **no third-party packages** for
skills 2/3/4, and run on **Python 3.9+**. Only skill 1 needs the `chatsee-ai` SDK, installed
into whatever interpreter your agent runs on. Start Claude Code from the repo the skills live
in — that is how it discovers them.

**Optional third step — recent failures on startup.** Add this to `.claude/settings.json` and
each session begins by telling you what your agent broke in the last 24 hours. It is the only
part of the install that is not a file copy, and the only part that pushes rather than waits
to be asked:

```json
{"hooks": {"SessionStart": [{"hooks": [{
  "type": "command",
  "command": "python3 .claude/skills/guardian-query/scripts/startup_check.py",
  "async": true, "timeout": 60}]}]}}
```

It runs in the background, so it never delays a session, and it stays silent unless there is
something to say. Detail in `guardian-query/SKILL.md`.

Everything runs **live against the real ChatSee Guardian** — there is no mock.

## Run it

Just talk to Claude — see **[`DEMO.md`](DEMO.md)** for the six things to ask. `RUN.md` lists the
underlying commands if you would rather drive them yourself.

**Scope, honestly:** skills 1, 2, and 4 run end to end. Skill 3 is **propose-only** — it
pulls the code-level failures and Claude drafts a fix, but nothing reports that fix back to
the Guardian, so there is no regression tracking yet. The loop is closed for *prompt* fixes
and open for *code* fixes. See [`ASSESSMENT.md`](ASSESSMENT.md) for the full gap list.

Guardian calls take ~10–60s (`ask_guardian` is agentic).

## Machine-wide config — one place for the model key

Test agents need a model API key. **Do not export it in your shell.** Anything launched from
that shell inherits it, including Claude Code, which redirects subscription billing to that key.

Put it in `~/.config/chatsee/agent.env` instead (mode `0600`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Every project's skills read it as a fallback, and any agent can too:

```python
load_dotenv()                                                   # ./.env — this agent
load_dotenv(os.path.expanduser("~/.config/chatsee/agent.env"))  # machine-wide secrets
```

**Precedence, highest first:** real environment variables → the project's `.env` →
`~/.config/chatsee/agent.env`. So a per-project override always wins, and the machine-wide file
only fills gaps.

**The machine-wide file may not identify an agent.** `CHATSEE_AGENT_ID`, `CHATSEE_TENANT_ID`,
`CHATSEE_MCP_KEY` and `CHATSEE_AGENT` are refused from it, with a warning. A global default for
*which agent this is* would silently point every project at one agent — the same class of bug as
`VALIDATION.md` F1, one level up. Machine-wide holds what is true of the machine; the project
holds what is true of the agent.

## Config (env only — never hardcode keys)

| Var | Used by | Purpose |
|-----|---------|---------|
| `CHATSEE_MCP_KEY` | skills 2/3/4 | Guardian MCP key (`cs-live-…`), bound to one agent |
| `CHATSEE_MCP_URL` | skills 2/3/4 | MCP endpoint (e.g. `https://gcp-demo.chatsee.ai/mcp/`) |
| `CHATSEE_AGENT` | skills 3/4 | agent name to scope queries to (**quote it** — names have spaces) |
| `CHATSEE_MCP_TIMEOUT` | skills 2/3/4 | per-call seconds (default 300) |
| `CHATSEE_AGENT_ID` / `CHATSEE_TENANT_ID` / `CHATSEE_ENV` | skill 1 | the agent's IDs + environment (`dev`\|`qa`\|`demo`\|`poc`) |

## Layout

```
.claude/skills/<name>/         the four skills (SKILL.md + thin scripts) — the product
.claude/skills/_shared/          guardian_client.py + env_config.py, shared by all four skills
examples/live_demo.py          the full loop, live (all four skills in sequence)
examples/sample_agent/         fixture with a structural bug + skill-3 PROPOSED_FIX.md
```

## Notes
- Python 3.9+ (the skills are pinned to it so they run in any repo). No secrets committed; keys live in `.env` (gitignored). Every commit is secret-scanned.
- Skill 1 uses the official `chatsee-ai` SDK (keyless); skills 2/3/4 use the Guardian MCP.
