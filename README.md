<div align="center">

# ChatSee Skills

**Monitor your AI agent — and fix its failures — without leaving your coding agent.**

Detect prompt-level and code-level failures in a deployed AI agent through ChatSee's **Guardian**,
then remediate them in place. Installs into **Claude Code**, **Codex**, **Gemini CLI**, **Cursor** and **GitHub Copilot** over a single MCP.

[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-6C4BF6)](#-claude-code)
[![Codex](https://img.shields.io/badge/Codex-plugin-10A37F)](#-codex)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-extension-4285F4)](#-gemini-cli)
[![Cursor](https://img.shields.io/badge/Cursor-skills_+_MCP-333333)](#-cursor)
[![GitHub Copilot](https://img.shields.io/badge/GitHub_Copilot-skills_+_MCP-24292F?logo=github&logoColor=white)](#-github-copilot)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](#prerequisites)
[![MCP](https://img.shields.io/badge/protocol-MCP-000000)](#prerequisites)
[![Site](https://img.shields.io/badge/chatsee.ai-000000)](https://chatsee.ai)

</div>

---

> **Branch `chatsee-dev`: the ChatSee dev environment.** The MCP is `https://dev-react.chatsee.ai/mcp/`
> and you **sign in with your ChatSee account**; there is no API key to set. `main` still targets
> gcp-demo with an MCP key until the sign-in release.

## What you get

Four skills, one MCP, one loop — **observe → ask what's wrong → fix the prompt → fix the code → repeat.**

| Skill | What it does |
|-------|--------------|
| 🛰️ **`telemetry-setup`** | Instrument your agent so each turn streams to the Guardian. |
| 🩹 **`remediation`** | Pull the Guardian's approved prompt-fixes and apply them. |
| 🛠️ **`structural-correction`** | Diagnose deeper *code* bugs and propose fixes. |
| 🔎 **`guardian-query`** | Ask the Guardian, in plain English, what's going wrong. |

Every step is **transparent and developer-invoked** — you ask, see the evidence, and approve the change. Nothing is applied silently.

> 💡 Ask *"what's my agent breaking?"* at the start of a session to see recent failures. (The
> automatic startup check needs an API key, so it is off on this branch. See [Startup check](#-startup-check).)

---

## Prerequisites

Before installing, make sure you have:

- **A ChatSee account on dev**: you can log in at <https://dev-react.chatsee.ai>. The editor
  sees only the agents that account can see.
- **Python 3.9+**: the skills carry their own scripts; skills 2/3/4 need **no third-party packages**.
- **The `chatsee-ai` SDK**: only needed for `telemetry-setup` (skill 1):
  ```bash
  pip install chatsee-ai
  ```
- **This branch, cloned locally** (the install steps below point at the clone):
  ```bash
  git clone -b chatsee-dev https://github.com/ChatSee/Chatsee-Skills.git
  ```

**Signing in:** the first time the editor uses the `chatsee` MCP, it opens your browser at
ChatSee. Log in, click **Continue**, then **Allow**, and the editor is connected. You can
remove access any time by clearing the editor's authentication for `chatsee`.

---

## Install

### 🟣 Claude Code

Run these **inside Claude Code** (start it with `claude`, then type the commands at the prompt),
using the path of your clone:

```text
/plugin marketplace add /path/to/Chatsee-Skills
/plugin install chatsee-skills@chatsee
```

Restart when prompted. Then sign in: `/mcp` → **chatsee** → **Authenticate**. `/mcp` should
show `chatsee ✔ connected`, and *"list my ChatSee agents"* should list your agents.

### 🟢 Codex

Run these **in your terminal** (Codex **v0.117+**):

```bash
codex plugin marketplace add /path/to/Chatsee-Skills
codex plugin add chatsee-skills@chatsee
codex plugin list        # should show chatsee-skills — installed, enabled
codex mcp login chatsee  # opens the browser to sign in with ChatSee
```

Open a Codex session; the skills and the `chatsee` MCP tools load automatically.

### 🔵 Gemini CLI

Requires Gemini CLI **v0.26+** (hooks). From the repo root:

```bash
gemini extensions link platforms/gemini --consent
gemini extensions list      # should show 1 MCP server and 4 agent skills
```

Then sign in from inside Gemini: `/mcp auth chatsee`. Confirm with `/mcp`; you want
`chatsee … Connected`.

### ⚫ Cursor

Requires Cursor **2.4+** (agent skills). Cursor has no plugin bundle format, so the skills and
the connection install separately:

```bash
cp -R /path/to/ChatSee-Skills/.cursor/skills  <your-repo>/.cursor/skills
```

For the MCP server, add this to **`~/.cursor/mcp.json`** (or copy the repo's `.cursor/mcp.json`).
There is no key in it:

```json
{ "mcpServers": { "chatsee": { "url": "https://dev-react.chatsee.ai/mcp/" } } }
```

Restart Cursor fully, then open **Settings → MCP**: `chatsee` shows **Needs login**. Click it
to sign in with ChatSee.

### 🐙 GitHub Copilot

Copilot has two surfaces with different setups.

**Copilot code review / cloud agent** — the skills live in the repository, so they arrive when
the repo does:

```bash
cp -R /path/to/ChatSee-Skills/.github/skills  <your-repo>/.github/skills
```

An administrator then adds the MCP server (`https://dev-react.chatsee.ai/mcp/`) under
**Settings → Copilot → MCP servers**. There is no one-click bundle for Copilot; this half is
configured in GitHub, not from a file.

**Copilot CLI** — personal skills go in `~/.copilot/skills/`, and a project `.mcp.json` or
`.github/mcp.json` is honoured:

```bash
cp -R /path/to/ChatSee-Skills/skills/* ~/.copilot/skills/
```

> ⚠️ **Unverified.** `.github/mcp.json` is generated with an inferred remote-server schema.
> GitHub documents the *local* shape (`"type": "local"` with `command`/`args`/`tools`) and does
> not publish the remote one, and this has not been run against a real Copilot CLI install.
> Confirm before relying on it.

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
| `.github/` | GitHub Copilot | generated mirror + config |

```bash
python build.py            # regenerate every bundle
python build.py --check    # fail if any bundle is stale (CI)
```

Gemini gets its own directory rather than sharing the repo root: sharing it meant Gemini
discovered Claude Code's `hooks/hooks.json` and ran it with `${CLAUDE_PLUGIN_ROOT}` never
expanded, so every session opened with a failed SessionStart hook.

---

## 🚀 Startup check

> **Off on the `chatsee-dev` branch.** The startup script calls the Guardian with an MCP key,
> and this branch signs in instead, so no session-start hook is installed. Ask in the session
> instead (*"what's my agent breaking?"*). The script below still works if you set a key yourself.

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

On this branch the MCP connection needs **no configuration**: the URL is in the plugin, and
you sign in through the browser. The variables below are optional.

| Variable | Used by | Purpose |
|----------|---------|---------|
| `CHATSEE_AGENT` | skills 3/4 | agent name to scope queries to (**quote it** — names have spaces) |
| `CHATSEE_MCP_KEY` / `CHATSEE_MCP_URL` | standalone scripts only | only for running the skills' Python scripts outside an editor; not used by the plugin |
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
