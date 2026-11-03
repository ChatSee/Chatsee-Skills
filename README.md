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
> and you **sign in with your ChatSee account**; there is no ChatSee API key to set (your coding agent
> still needs its own sign-in or API key, as usual). `main` still targets
> gcp-demo with an MCP key until the sign-in release.

## What you get

Four skills, one MCP, one loop — **observe → ask what's wrong → fix the prompt → fix the code → repeat.**

| Skill | What it does |
|-------|--------------|
| 🛰️ **`telemetry-setup`** | Instrument your agent so each turn streams to the Guardian. |
| 🩹 **`remediation`** | Show remediations with their ChatSee status, approve the waiting ones, apply the Implemented ones. |
| 🛠️ **`structural-correction`** | Diagnose deeper *code* bugs and propose fixes. |
| 🔎 **`guardian-query`** | Ask the Guardian, in plain English, what's going wrong. |

Every step is **transparent and developer-invoked** — you ask, see the evidence, and approve the change. Nothing is applied silently.

> 💡 Ask *"what's my agent breaking?"* at the start of a session to see recent failures. (The
> automatic startup check needs a ChatSee API key, so it is off on this branch. See [Startup check](#-startup-check).)

---

## How the skills work

The plugin installs two things: the **ChatSee MCP server** (the connection, with six tools:
`list_my_agents`, `ask_guardian`, `list_remediations`, `approve_remediation`,
`get_remediations`, `apply_remediations`) and the **four
skills** (instructions that tell your coding agent how to do a whole job with those tools). A
single lookup such as *"list my ChatSee agents"* just calls a tool; a multi-step job follows a
skill.

**Signing in.** The first time the editor uses ChatSee, your browser opens on ChatSee: sign in,
click **Continue**, then **Allow**. The editor sees only the agents your ChatSee account can see.
This replaces the ChatSee API key only: your coding agent itself still needs its own sign-in or
API key (Claude account, OpenAI sign-in, Google sign-in or Gemini API key, GitHub Copilot access).

**The loop, end to end:**

1. **Create the agent in ChatSee** (portal: **Settings → Add agent**, type *interaction* +
   *custom*). That gives it its IDs. The skills can't create agents.
2. **`telemetry-setup`** adds the official `chatsee-ai` SDK to your agent's code. It gets the
   agent's `agent_id`, `tenant_id` and environment from your account via `list_my_agents` (no
   key), installs the SDK, writes them to the project's `.env` (and checks `.env` is
   gitignored), and wraps your agent's conversation loop so each turn (user message, tool calls,
   answer, errors) is sent to ChatSee. You review the change, then run your agent as normal.
   PII redaction is left off on dev and QA, which don't serve it yet.
3. **ChatSee analyses the conversations** (errors, clusters, suggested fixes). This takes from a
   few minutes to about 90 minutes.
4. **`guardian-query`** asks the Guardian, in plain English, what's going wrong: top error codes,
   clusters, anomalies, sentiment. Read-only. *"Nothing detected"* can mean the analysis hasn't
   finished, not that the agent is healthy.
5. **A person approves fixes.** Each remediation has the status the portal shows: Open,
   Proposed, In progress or **Implemented**. Approving (Approve & Apply) makes it Implemented. It needs the
   SRE or Admin role, in the portal or from your editor in the next step.
6. **`remediation`** lists the agent's remediations with their status and FM code
   (`list_remediations`). You choose: approve waiting ones one at a time, on your explicit yes
   (`approve_remediation`), then it adds every Implemented fix to your agent's system prompt as a
   marked block (showing you the diff first) and records them as applied in ChatSee
   (`apply_remediations`). Nothing Implemented means nothing is approved yet, not that the agent is
   healthy.
7. **`structural-correction`** handles failures a prompt change can't fix (cut-off replies, wrong
   or repeated tool calls, loops, failures that grow with conversation length): it asks the
   Guardian for evidence, finds the cause in your code and **proposes** a fix for you to approve.
   It needs no approval in ChatSee, and code fixes aren't reported back to ChatSee.

**Editors:** Claude Code (terminal and VS Code), Codex, Gemini CLI, GitHub Copilot (VS Code and
Copilot CLI) and Cursor. Cursor uses its own server address, `/mcp/cursor`, which the installer
sets for you.

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
- **Access to this GitHub repository.** It is private for now, so your GitHub account must be in
  the ChatSee organization, and `git` must be signed in to GitHub. Check with:
  ```bash
  git ls-remote https://github.com/ChatSee/Chatsee-Skills chatsee-dev
  ```
  One line ending in `refs/heads/chatsee-dev` means you're ready. Claude Code, Codex and Gemini
  fetch the branch themselves; only Cursor and Copilot need a clone:
  ```bash
  git clone -b chatsee-dev https://github.com/ChatSee/Chatsee-Skills.git
  ```

**Signing in:** the first time the editor uses the `chatsee` MCP, it opens your browser at
ChatSee. Log in, click **Continue**, then **Allow**, and the editor is connected. You can
remove access any time by clearing the editor's authentication for `chatsee`.

---

## Install

### 🟣 Claude Code

Run these **in your terminal**:

```bash
claude plugin marketplace add "ChatSee/Chatsee-Skills#chatsee-dev"
claude plugin install chatsee-skills@chatsee
```

(`#chatsee-dev` selects this branch. Inside the Claude Code CLI the same commands work as
`/plugin marketplace add …`; in the **VS Code** extension, use `/plugins` → **Marketplaces** →
add `ChatSee/Chatsee-Skills#chatsee-dev`, then **Plugins** → install **chatsee-skills**.)

Start `claude` (or reopen the VS Code panel), then sign in: `/mcp` → **chatsee** →
**Authenticate**. `/mcp` should show `chatsee ✔ connected`, and *"list my ChatSee agents"*
should list your agents.

> **Switching between ChatSee environments** (for example dev and QA, or an older key-based
> install)? Claude Code and Codex remember where the `chatsee` marketplace came from and refuse
> a different source. Remove it first: `claude plugin marketplace remove chatsee` /
> `codex plugin marketplace remove chatsee`, then add the new branch.

### 🟢 Codex

Run these **in your terminal** (Codex **v0.117+**):

```bash
codex plugin marketplace add ChatSee/Chatsee-Skills@chatsee-dev
codex plugin add chatsee-skills@chatsee
codex plugin list        # should show chatsee-skills — installed, enabled
codex mcp login chatsee  # opens the browser to sign in with ChatSee
```

Open a Codex session; the skills and the `chatsee` MCP tools load automatically.

> **Windows 10:** Codex uses Windows' own TLS, which has no TLS 1.3. The dev server must also
> accept TLS 1.2, or Codex can't connect at all.

### 🔵 Gemini CLI

Requires Gemini CLI **v0.26+**:

While the repository is private, install from a clone. Gemini's own `git clone` doesn't use
your saved GitHub login, so it can't fetch a private repo itself:

```bash
git clone -b chatsee-dev https://github.com/ChatSee/Chatsee-Skills.git
gemini extensions install ./Chatsee-Skills --consent
gemini extensions list      # should show 1 MCP server and 4 agent skills
```

Once the repository is public, this one command replaces the three above (answer **Y** when
it offers to `git clone` after looking for a release):

```bash
gemini extensions install https://github.com/ChatSee/Chatsee-Skills --ref chatsee-dev --consent
```

Then sign in from inside Gemini: `/mcp auth chatsee`. Confirm with `/mcp`; you want
`chatsee … Connected`.

### ⚫ Cursor and 🐙 GitHub Copilot (VS Code)

These editors have no plugin installer, so the repository includes one. In a terminal (cmd,
PowerShell or a macOS/Linux shell), go to **your own project folder** and run:

```bash
git clone -b chatsee-dev https://github.com/ChatSee/Chatsee-Skills.git
python Chatsee-Skills/install.py copilot      # or: python Chatsee-Skills/install.py cursor
```

It copies the four skills into the project and adds a `chatsee` server to the editor's MCP
file (`.vscode/mcp.json` or `.cursor/mcp.json`), keeping any servers already there. If you
cloned somewhere else, point it at the project instead: `python <clone>/install.py copilot
--project <your project folder>`. Afterwards the `Chatsee-Skills` folder can be deleted, or
left out of version control.

**Copilot (VS Code):** open the project in VS Code, open `.vscode/mcp.json` and click
**Start** above `"chatsee"`. VS Code asks to sign in; the browser opens ChatSee → **Continue**
→ **Allow**. Then use Copilot Chat in **Agent** mode: *"list my ChatSee agents"*.

**Cursor:** open the project in Cursor, then **Settings → MCP**: `chatsee` shows **Disabled**.
Click it, check the project source is switched on and click **Authenticate**. The browser opens
ChatSee → **Continue** → **Allow** → *Authorization complete*. Back in Cursor, `chatsee` shows
**6 tools enabled**; ask in the Agent chat: *"list my ChatSee agents"*.

Copilot's other surfaces:

**Copilot code review / cloud agent** — the skills live in the repository, so they arrive when
the repo does:

```bash
cp -R /path/to/ChatSee-Skills/.github/skills  <your-repo>/.github/skills
```

An administrator then adds the MCP server (`https://dev-react.chatsee.ai/mcp/`) under
**Settings → Copilot → MCP servers**. There is no one-click bundle for Copilot; this half is
configured in GitHub, not from a file.

**Copilot CLI** (the `copilot` command) installs this repository as a plugin: the four skills
plus the `chatsee` MCP server. It can't pick a branch from GitHub, so add the marketplace from a
clone of this branch (pass the clone's full path: a relative path is read as a GitHub repo name):

```bash
git clone -b chatsee-dev https://github.com/ChatSee/Chatsee-Skills.git
copilot plugin marketplace add "$PWD/Chatsee-Skills"   # a FULL path; Windows cmd: "%CD%\Chatsee-Skills"
copilot plugin install chatsee-skills@chatsee     # "Installed 4 skills"
copilot mcp list                                  # Plugin servers: chatsee (http)
```

Then start `copilot` and ask *"list my ChatSee agents"*; it opens the browser to sign in with
ChatSee the first time.

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
| `.codex-plugin/` | Codex | reads `./skills/` directly; shares `.claude-plugin/marketplace.json` |
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
expanded, so every session opened with a failed SessionStart hook. The sign-in build (this
branch) has no hooks, so it also writes `gemini-extension.json` and `GEMINI.md` at the root,
which is what lets `gemini extensions install <repo> --ref chatsee-dev` work.

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
