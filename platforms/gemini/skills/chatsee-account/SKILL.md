---
name: chatsee-account
description: Create a new ChatSee account (a ChatSee organisation, also called a tenant, on the Free plan) from the editor and connect the editor to it in one sign-in. Use when a developer asks to sign up for ChatSee, create a ChatSee account, organisation, workspace or tenant, or says they don't have a ChatSee account yet. Not for developers who already have an account and just need to sign in. (Skill 0, before the other four.)
---

# Create a ChatSee account (skill 0)

The developer gets a new ChatSee organisation (tenant) on the Free plan, and the editor
is signed in to it in the same pass. Nothing is created by you directly: the developer
fills in the sign-up page in their browser. Your job is to send them to the right page
and pick up once they are connected.

## 1. Already connected?
Call `list_my_agents`.
- **It works:** the editor is already signed in to a ChatSee organisation (its `tenant_id`
  is in the answer). Tell the developer, and stop unless they want a *second*, separate
  organisation. For that they first sign out of the current one: Claude Code `/mcp` →
  the ChatSee server → **Clear authentication**. Then continue below.
- **The tool is missing or fails with an authentication error:** not signed in yet. Continue.

## 2. Mark this browser for sign-up
Open the sign-up link in the developer's default browser. It is on the same site as the
ChatSee MCP server: take the host from the ChatSee server URL in the project's `.mcp.json`
(or the editor's MCP settings) and add `/api/v1/connect/signup-intent`.

| ChatSee MCP URL | Sign-up link |
|---|---|
| `https://dev-react.chatsee.ai/mcp/` | `https://dev-react.chatsee.ai/api/v1/connect/signup-intent` |
| `https://qa.chatsee.ai/mcp/` | `https://qa.chatsee.ai/api/v1/connect/signup-intent` |

```bash
python -m webbrowser "<sign-up link>"
```
If that fails, use `start "" "<link>"` (Windows), `open "<link>"` (macOS) or
`xdg-open "<link>"` (Linux). **Always also print the link**, so the developer can open it
themselves. The page only says "go back to your editor"; it sets a mark in that browser
that lasts 15 minutes.

Don't ask for, or type, their name, email or password anywhere. They enter those on the
ChatSee page.

## 3. Ask the developer to sign in from the editor
Only the developer can start the editor's sign-in. Tell them, in the same browser:
- Claude Code: `/mcp` → the ChatSee server → **Authenticate**
- Gemini CLI: `/mcp auth chatsee`
- Codex: `codex mcp login <server name>`, then restart Codex
- Cursor / VS Code: the ChatSee entry in the MCP settings → **Connect** / **Start**

What they will see: the **ChatSee sign-up page** (not sign-in) → name, work email,
organisation, password → a 6-digit code by email → **Create account and continue** →
**Allow**. Then the browser returns to the editor, connected to the new organisation.

If the browser shows **"Continue as <someone>"** instead, that browser is already signed in
to an existing ChatSee account. To create a new one they sign out there ("Not you? Switch
account"), then run this skill again. If the mark expired (more than 15 minutes), the
normal sign-in page opens; its **Create an account** link at the bottom leads to the same
sign-up.

## 4. Confirm and carry on
When the developer says they are done, call `list_my_agents` again. A new organisation has
**0 agents** and a `tenant_id`. Tell them it worked, then offer the next step:
- create their first agent (`create_agent`), or
- instrument an existing agent so its conversations reach ChatSee (skill 1, telemetry-setup).

**Never search for API keys, `.env` files or credentials to get around a missing sign-in**,
and never read files outside the project.
