<div align="center">

# ChatSee Skills

**Monitor your AI agent — and fix its failures — without leaving your coding agent.**

Detect prompt-level and code-level failures in a deployed AI agent through ChatSee's **Guardian**,
then remediate them in place. Installs into **Claude Code**, **Codex**, **Gemini CLI** and **Cursor** over a single MCP.

[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-6C4BF6)](#-claude-code)
[![Codex](https://img.shields.io/badge/Codex-plugin-10A37F)](#-codex)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-extension-4285F4)](#-gemini-cli)
[![Cursor](https://img.shields.io/badge/Cursor-skills_+_MCP-333333)](#-cursor)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](#prerequisites)
[![MCP](https://img.shields.io/badge/protocol-MCP-000000)](#prerequisites)
[![Site](https://img.shields.io/badge/chatsee.ai-000000)](https://chatsee.ai)

</div>

---

## What you get

Four skills, one MCP, one loop — **observe → ask what's wrong → fix the prompt → fix the code → repeat.**

| Skill | What it does |
|-------|--------------|
| 🛰️ **`telemetry-setup`** | Instrument your agent so each turn streams to the Guardian. |
| 🩹 **`remediation`** | Pull the Guardian's approved prompt-fixes and apply them. |
| 🛠️ **`structural-correction`** | Diagnose deeper *code* bugs and propose fixes. |
| 🔎 **`guardian-query`** | Ask the Guardian, in plain English, what's going wrong. |

Every step is **transparent and developer-invoked** — you ask, see the evidence, and approve the change. Nothing is applied silently.

> 💡 **On session start**, the plugin surfaces what your agent broke recently — no need to think to ask. See [Startup check](#-startup-check).

---

## Prerequisites

Before installing, make sure you have:

- **Python 3.9+** — the skills carry their own client; skills 2/3/4 need **no third-party packages**.
- **A ChatSee MCP key** — `cs-live-…`, bound to one agent. Ask the ChatSee team.
- **The `chatsee-ai` SDK** — only needed for `telemetry-setup` (skill 1):
  ```bash
  pip install chatsee-ai
  ```

Set the key as an environment variable so the plugin's MCP can read it (never commit it):

```bash
# macOS / Linux
export CHATSEE_MCP_KEY="cs-live-<tenant>-<secret>"
export CHATSEE_AGENT="Your Agent Name"          # quote it — names have spaces
```
```powershell
# Windows (PowerShell) — persists across sessions
setx CHATSEE_MCP_KEY "cs-live-<tenant>-<secret>"
setx CHATSEE_AGENT   "Your Agent Name"
```

See the full variable list in [Configuration](#configuration).

---

## Install

### 🟣 Claude Code

Run these **inside Claude Code** (start it with `claude`, then type the commands at the prompt):

```text
/plugin marketplace add ChatSee/Chatsee-Skills
/plugin install chatsee-skills@chatsee
```

Restart when prompted. Confirm with `/plugin` → the skills and the `chatsee` MCP server should show as active.

<sub>Private repo? Claude Code uses your existing `git` authentication, so no extra step is needed.</sub>

### 🟢 Codex

Run these **in your terminal** (Codex **v0.117+**):

```bash
codex plugin marketplace add ChatSee/Chatsee-Skills
codex plugin add chatsee-skills@chatsee
codex plugin list        # should show chatsee-skills — installed, enabled
```

Open a Codex session — the skills and the `chatsee` MCP tools (`ask_guardian`, `get_remediations`, `apply_remediations`) load automatically.

### 🔵 Gemini CLI

Requires Gemini CLI **v0.26+** (hooks). From the repo root:

```bash
gemini extensions link platforms/gemini --consent
gemini extensions list      # should show 1 MCP server and 4 agent skills
```

Gemini prompts for your key and agent name at install — it is the only host that collects
the credential for you rather than assuming you exported it.

> **Known Gemini CLI bug:** the prompt can report `Setting "…" updated` while saving nothing,
> after which `extensions list` shows `[not set]` and the MCP tools never appear. If that
> happens, write the values directly to
> `~/.gemini/extensions/chatsee-skills/.env`:
>
> ```
> CHATSEE_MCP_KEY=cs-live-…
> CHATSEE_AGENT=Your Agent Name
> ```
>
> Then confirm with `gemini mcp list` — you want `chatsee … Connected`.

### ⚫ Cursor

Requires Cursor **2.4+** (agent skills). Cursor has no plugin bundle format, so the skills and
the connection install separately:

```bash
cp -R /path/to/ChatSee-Skills/.cursor/skills  <your-repo>/.cursor/skills
```

For the MCP server, put your key in **`~/.cursor/mcp.json`** (global, not the repo — the repo
copy is tracked and would commit a live credential):

```json
{ "mcpServers": { "chatsee": {
    "url": "https://gcp-demo.chatsee.ai/mcp/",
    "headers": { "Authorization": "Bearer cs-live-…" } } } }
```

> **Why the key is written in full here:** Cursor does not expand `${env:VAR}` inside headers
> for *remote* MCP servers — it sends the literal string and the server answers 401. The
> generated `.cursor/mcp.json` uses the documented form so it starts working when Cursor fixes
> this; until then, use the global file above, or an `mcp-remote` stdio shim.

Restart Cursor fully — it reads the global config at startup.

<details>
<summary><b>Manual install (any editor, no plugin system)</b></summary>

Copy the skills into your agent's repo and add a `.env`:

```bash
cp -R /path/to/ChatSee-Skills/skills  <your-repo>/.claude/skills
```

Create `.env` at your repo root (see [`.env.example`](.env.example)), **add it to `.gitignore`**, then start your coding agent from that repo — that's how it discovers the skills.
</details>

---

## Repository layout

`skills/` is the **only** hand-edited copy of the four skills. Everything else is generated by
[`build.py`](build.py):

| Path | Host | |
|---|---|---|
| `skills/` | — | **canonical source — edit here** |
| `.claude-plugin/` + `.mcp.json` + `hooks/` | Claude Code | reads `./skills/` directly |
| `.codex-plugin/` + `marketplace.json` | Codex | reads `./skills/` directly |
| `platforms/gemini/` | Gemini CLI | own directory + skills copy |
| `.claude/skills/` | Claude Code (project) | generated mirror |
| `.cursor/` | Cursor | generated mirror + config |

```bash
python build.py            # regenerate every bundle
python build.py --check    # fail if any bundle is stale (CI)
```

Gemini gets its own directory rather than sharing the repo root: sharing it meant Gemini
discovered Claude Code's `hooks/hooks.json` and ran it with `${CLAUDE_PLUGIN_ROOT}` never
expanded, so every session opened with a failed SessionStart hook.

---

## 🚀 Startup check

On every session start, the plugin runs a **predefined startup query set** against the Guardian and surfaces your agent's recent status — so you learn it's been failing without having to ask.

- **Default set (6 queries):** `failures` · `topcode` · `clusters` · `recent` · `severity` · `escalations` — covers almost every code-based question, and each answer is then **instant** to reuse during the session.
- **Stays silent when healthy:** `failures` is the gate — if there's nothing to report, startup prints nothing.
- **Fast preset** for a snappy start: single-fact queries only.

```bash
# fast preset — snappiest start
python skills/guardian-query/scripts/startup_check.py --only failures,topcode,escalations

# any subset, any window
python skills/guardian-query/scripts/startup_check.py --only severity,impact --hours 168
```

| Tier | Keys | Notes |
|------|------|-------|
| **Reliable** (default) | `failures` `topcode` `clusters` `recent` `severity` `escalations` | code-based; trusted |
| **Arithmetic** (opt-in) | `volume` `health` `sentiment` `impact` | counts less reliable — enable with `--only` |

> The startup set runs live Guardian calls in sequence, so a wider default trades a little startup latency for instant in-session answers. Full detail in [`guardian-query/SKILL.md`](skills/guardian-query/SKILL.md).

---

## Usage

Just talk to your coding agent:

- *"What's my agent breaking today?"*
- *"Pull the latest remediations and apply them."*
- *"Why is error code E-402 happening?"*

See **[`DEMO.md`](DEMO.md)** for a scripted walkthrough, and **[`RUN.md`](RUN.md)** for the underlying commands.

Guardian calls take **~10–60s** (`ask_guardian` is agentic). Narrow questions and shorter windows answer faster; the startup set pre-fetches the common ones so they're instant.

---

## Configuration

Env only — **never hardcode keys.**

| Variable | Used by | Purpose |
|----------|---------|---------|
| `CHATSEE_MCP_KEY` | skills 2/3/4 | Guardian MCP key (`cs-live-…`), bound to one agent |
| `CHATSEE_MCP_URL` | skills 2/3/4 | MCP endpoint (e.g. `https://gcp-demo.chatsee.ai/mcp/`) |
| `CHATSEE_AGENT` | skills 3/4 | agent name to scope queries to (**quote it** — names have spaces) |
| `CHATSEE_MCP_TIMEOUT` | skills 2/3/4 | per-call seconds (default 300) |
| `CHATSEE_AGENT_ID` / `CHATSEE_TENANT_ID` / `CHATSEE_ENV` | skill 1 | the agent's IDs + environment (`dev`\|`qa`\|`demo`\|`poc`) |

**Model API keys** belong in `~/.config/chatsee/agent.env` (mode `0600`) — **not** your shell, or Claude Code inherits it and redirects subscription billing. Precedence, highest first: real env vars → project `.env` → machine-wide file.

---

## Scope, honestly

Skills **1, 2, and 4 run end to end.** Skill 3 (`structural-correction`) is **propose-only** — it pulls code-level failures and drafts a fix, but nothing reports that fix back to the Guardian yet, so there's no regression tracking. The loop is **closed for prompt fixes, open for code fixes.** Full gap list in [`ASSESSMENT.md`](ASSESSMENT.md).

Everything runs **live against the real ChatSee Guardian** — there is no mock.

---

## Learn more

| Doc | What's in it |
|-----|--------------|
| [`BRIEF.md`](BRIEF.md) | Architecture, design rationale, live-test results |
| [`DEMO.md`](DEMO.md) | Scripted demo — the things to ask |
| [`ASSESSMENT.md`](ASSESSMENT.md) | Honest gap analysis |
| [`VALIDATION.md`](VALIDATION.md) | Test evidence |

<div align="center">
<sub>Built by <a href="https://chatsee.ai">ChatSee</a> · No secrets committed — keys live in env, never in the repo.</sub>
</div>
