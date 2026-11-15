---
name: chatsee-account
description: Create a new ChatSee account (a ChatSee organisation, also called a tenant, on the Free plan) from the editor, then connect the editor to it. Use when a developer asks to sign up for ChatSee, create a ChatSee account, organisation, workspace or tenant, or says they don't have a ChatSee account yet. Not for developers who already have an account and just need to sign in. (Skill 0, before the other four.)
---

# Create a ChatSee account (skill 0)

The developer gets a new ChatSee organisation (tenant) on the Free plan, then connects
the editor to it. Nothing is created by you directly: the developer fills in ChatSee's
sign-up page in their browser. Your job is to open that page and pick up afterwards.

## 1. Already connected?
Call `list_my_agents`.
- **It works:** the editor is already signed in to a ChatSee organisation (its `tenant_id`
  is in the answer). Tell the developer, and stop unless they want a *second*, separate
  organisation. For that they first sign out of the current one: Claude Code `/mcp` →
  the ChatSee server → **Clear authentication**. Then continue below.
- **The tool is missing or fails with an authentication error:** not signed in yet. Continue.

## 2. Open the ChatSee sign-up page
It is on the same site as the ChatSee MCP server: take the host from the ChatSee server
URL in the project's `.mcp.json` (or the editor's MCP settings) and add `/connect/signup`.

| ChatSee MCP URL | Sign-up page |
|---|---|
| `https://dev-react.chatsee.ai/mcp/` | `https://dev-react.chatsee.ai/connect/signup` |
| `https://qa.chatsee.ai/mcp/` | `https://qa.chatsee.ai/connect/signup` |

```bash
python -m webbrowser "<sign-up page>"
```
If that fails, use `start "" "<page>"` (Windows), `open "<page>"` (macOS) or
`xdg-open "<page>"` (Linux). **Always also print the link**, so the developer can open it
themselves.

Tell them what happens there: name, work email, organisation and password → a 6-digit
code by email → **Create account and continue**. The page then says **"Your ChatSee
account is ready"**. They should keep that tab open and come back here.

Don't ask for, or type, their name, email or password anywhere. They enter those on the
ChatSee page.

## 3. Connect the editor
When they say the account is ready, ask them to sign in from the editor. Only the
developer can start this:
- Claude Code: `/mcp` → the ChatSee server → **Authenticate**
- Gemini CLI: `/mcp auth chatsee`
- Codex: `codex mcp login <server name>`, then restart Codex
- Cursor / VS Code: the ChatSee entry in the MCP settings → **Connect** / **Start**

The browser already has them signed in, so they only click **Continue**, then **Allow**.
If it asks for a password instead (for example the sign-up tab was closed), they sign in
with the email and password they just chose.

## 4. Confirm and carry on
Call `list_my_agents` again. A new organisation has **0 agents** and a `tenant_id`. Tell
them it worked, then offer the next step:
- create their first agent (`create_agent`), or
- instrument an existing agent so its conversations reach ChatSee (skill 1, telemetry-setup).

**Never search for API keys, `.env` files or credentials to get around a missing sign-in**,
and never read files outside the project.
