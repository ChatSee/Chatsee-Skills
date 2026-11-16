---
name: chatsee-account
description: Set up ChatSee for a developer who has no ChatSee account, entirely from the editor - creates a ChatSee organisation (tenant) on the Free plan with an agent, wires the developer's bot to stream its conversations, confirms data is arriving, and hands over a claim link. Use when a developer asks to set up ChatSee, sign up for ChatSee, create a ChatSee account, organisation, workspace or tenant, or says they don't have a ChatSee account yet. Not for developers who already have an account and just need to sign in. (Skill 0, before the other four.)
---

# Set up ChatSee with no account (skill 0)

The developer gets a ChatSee organisation on the Free plan and an agent, and their bot
starts streaming conversations to it, **without leaving the editor and without a sign-up
form**. ChatSee creates the organisation with no owner; the developer claims it later with
a link (email + 6-digit code, about 30 seconds). This is how Raindrop and Axiom onboard
from coding agents.

Until it is claimed the organisation can only **receive** conversations. Nobody can read
them (no dashboard, no Guardian answers, no remediations) until a verified person owns it.
Unclaimed organisations are deleted after 72 hours.

## 1. Already set up?
- If the project's `.env` has `CHATSEE_AGENT_ID`, it is already connected: say so and stop.
  Don't create a second organisation.
- If the ChatSee MCP tools work (`list_my_agents` answers), the developer already has an
  account: use it (offer `create_agent` and skill 1, telemetry-setup) and stop.

## 2. Ask two things, then create it
Ask the developer, in one message:
- **What should the organisation be called?** (suggest their company or project name)
- **Do you accept ChatSee's [Terms of Service](https://www.chatsee.ai/terms-of-service) and
  [Privacy Policy](https://www.chatsee.ai/privacy-policy)?** Only continue on a clear yes.

Name the agent after their bot or repo (for example "Returns Bot"); mention the name you chose.
From the project root, run:

```bash
python <this skill>/scripts/agent_signup.py signup --org "<organisation>" --agent "<agent name>" --accept-terms
```

It picks the ChatSee address from the ChatSee server in `.mcp.json` (pass
`--api https://<host>/api` if there is none). It writes `CHATSEE_AGENT_ID`,
`CHATSEE_TENANT_ID`, `CHATSEE_ENV`, `CHATSEE_SETUP_KEY` and `CHATSEE_API_URL` to `.env`,
makes sure `.env` is gitignored, and prints the **claim link**. It never prints the setup key.

On HTTP 429 it says how long to wait: wait once and retry once, never loop.

**Never ask for, or type, a password or email in the chat.** None is needed here.

## 3. Stream the bot's conversations
Follow skill 1 (**telemetry-setup**) to add the four ChatSee SDK calls to the developer's
bot. The ids are already in `.env`, so skill 1 uses them and doesn't need a sign-in.
As skill 1 says: offer to run the bot, don't just run it (it calls their model and tools).

If the developer has no bot yet, skill 1's reference agent works as a first one.

## 4. Confirm data is arriving
After the bot has handled at least one conversation, wait about 30 seconds and run:

```bash
python <this skill>/scripts/agent_signup.py check
```

`status: healthy` with a count means ChatSee is receiving it (exit 0). `no_events` (exit 2)
means nothing has arrived yet: check the bot actually ran and that `.env` is loaded by it.
The check shows counts only, never conversation content.

## 5. Hand over the claim link
Show the claim link **in the chat only** (never write it to a file, commit or log): whoever
opens it first and confirms an email owns the organisation. Tell the developer:

> "ChatSee is receiving your bot's conversations. Open this link within 3 days to claim
> your organisation: enter your work email and the code we send. Then you can see what
> ChatSee finds."

## 6. After they claim
Reading data needs the developer's own sign-in, once:
- Claude Code: `/mcp` → the ChatSee server → **Authenticate** → **Continue** → **Allow**
  (the claim already signed the browser in, so no password).
- Gemini CLI: `/mcp auth chatsee` · Codex: `codex mcp login <server name>`, then restart ·
  Cursor / VS Code: the ChatSee entry in the MCP settings → **Connect** / **Start**.

Then skills 2-4 work: ask the Guardian (guardian-query), review fixes (remediation), code
fixes (structural-correction). Failures appear a few minutes to about an hour after the
conversations, so "no errors yet" right after setup is normal.

**Never search for API keys, credentials or other `.env` files to get around a missing
sign-in,** and never read files outside the project.
