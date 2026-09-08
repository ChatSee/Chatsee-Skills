# ChatSee skills — Codex wrapper

ChatSee's skills work across coding agents. The capability is the same everywhere (the ChatSee
**MCP** tools); each coding agent just needs a wrapper in **its own format**:

| Coding agent | Wrapper | Location |
|---|---|---|
| Claude Code | `.claude/skills/` (SKILL.md + scripts) | repo root |
| **Codex** | **`AGENTS.md`** | **this folder** |

## Install (Codex)
1. Copy `AGENTS.md` into your agent's repo (repo root, or the folder you launch Codex from —
   Codex reads `AGENTS.md` from the working directory and up the tree).
2. Wire the ChatSee MCP once:
   ```bash
   codex mcp add chatsee --url https://gcp-demo.chatsee.ai/mcp/ --bearer-token-env-var CHATSEE_MCP_KEY
   ```
3. Create `.env` with `CHATSEE_MCP_URL`, `CHATSEE_MCP_KEY`, and (for skill 1)
   `CHATSEE_AGENT_ID` / `CHATSEE_TENANT_ID` / `CHATSEE_ENV`. **Add `.env` to `.gitignore`.**
4. `cd` into the repo and run `codex`. Then just talk:
   - "What's wrong with my agent?"          → guardian-query
   - "Pull and apply the remediations"      → remediation
   - "Find and fix the code bug in X"       → structural-correction
   - "Set up ChatSee telemetry"             → telemetry-setup

Same 4 skills as Claude Code, same Guardian — different wrapper format. Adding another agent
(Cursor, Kimi, …) is just another small wrapper over the same MCP.
