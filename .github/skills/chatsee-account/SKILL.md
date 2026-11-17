---
name: chatsee-account
description: Set up ChatSee for a developer who has no ChatSee account, entirely from the editor - creates a ChatSee organisation (tenant) on the Free plan with an agent, wires the developer's bot to stream its conversations, confirms data is arriving, and hands over a claim link. Use when a developer asks to set up ChatSee, sign up for ChatSee, create a ChatSee account, organisation, workspace or tenant, or says they don't have a ChatSee account yet. Not for developers who already have an account and just need to sign in. (Skill 0, before the other four.)
---

# Set up ChatSee with no account (skill 0)

The developer gets a ChatSee organisation on the Free plan and an agent, and their bot
starts streaming conversations to it, **without leaving the editor and without a sign-up
form**. ChatSee creates the organisation with no owner; the developer claims it later with
a link (work email, a password and the 6-digit code, about 30 seconds). This is how Raindrop and Axiom onboard
from coding agents.

Until it is claimed the organisation can only **receive** conversations. Nobody can read
them (no dashboard, no Guardian answers, no remediations) until a verified person owns it.
**An unclaimed organisation is permanently deleted after 3 days: the organisation, its agent,
its account and every conversation it received.** Say this in plain words every time you
mention the claim link, with the date.

## How to talk to the developer: a conversation, not a manual
Most developers arrive knowing nothing about ChatSee. Never paste a wall of instructions.
Do one stage at a time, say in one line what just happened, and **end every message with
the single recommended next step** as a yes/no question. Keep messages short.

## 1. Already set up?
- If the project's `.env` has `CHATSEE_AGENT_ID`, it is already connected: say so and stop.
  Don't create a second organisation.
- If the ChatSee MCP tools work (`list_my_agents` answers), the developer already has an
  account: use it (offer `create_agent` and skill 1, telemetry-setup) and stop.

## 2. Suggest names, ask for the terms (always), then create it
Don't make the developer invent names. Get defaults with:

```bash
python <this skill>/scripts/agent_signup.py suggest
```

Use names the developer already gave instead of the defaults. Then ask **one** message and
wait for the answer, **even when the developer has already given names or said "set up
ChatSee"**:

> I'll create a free ChatSee organisation **<org>** with the agent **<agent>**
> (say if you want different names).
> Do you accept ChatSee's [Terms of Service](https://www.chatsee.ai/terms-of-service) and
> [Privacy Policy](https://www.chatsee.ai/privacy-policy)? (yes / no)

- Asking for a ChatSee account, naming the organisation, or saying "go ahead" is **not**
  acceptance. Only an explicit yes to *this* question is. Never assume it, never answer it
  for them, and never pass `--accept-terms` without it. On no, stop: nothing is created.
- If they answer with new names, use them; a yes with no names keeps the defaults.

From the project root, run:

```bash
python <this skill>/scripts/agent_signup.py signup --org "<organisation>" --agent "<agent name>" --accept-terms
```

It picks the ChatSee address from the ChatSee server in `.mcp.json` (pass
`--api https://<host>/api` if there is none). It writes `CHATSEE_AGENT_ID`,
`CHATSEE_TENANT_ID`, `CHATSEE_ENV`, `CHATSEE_SETUP_KEY` and `CHATSEE_API_URL` to `.env`,
makes sure `.env` is gitignored, and prints the **claim link** and its deadline. It never
prints the setup key.

Then reply in two or three lines: created (names, Free plan), the 3-day deletion warning
with the date, and the next step as a question (step 3).

On HTTP 429 it says how long to wait: wait once and retry once, never loop.

**Never ask for, or type, a password or email in the chat.** None is needed here; the
developer chooses their password on ChatSee's claim page.

## 3. Stream the bot's conversations (ask first)
This edits the developer's own code, so **ask before touching it**, even straight after
step 2: name the file you would change, for example *"Shall I add ChatSee monitoring to
returns-bot/agent.py?"*, and wait for a yes. On no, stop here and just give the claim link
(step 5). On yes, follow skill 1 (**telemetry-setup**) to add the four ChatSee SDK calls to
the developer's bot. The ids are already in `.env`, so skill 1 uses them and doesn't need a sign-in.
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

> "ChatSee is receiving your bot's conversations. Open this link to claim your
> organisation: enter your work email, choose a password and enter the code we send.
> **If it isn't claimed by <date>, the organisation, its agent, its account and all its
> conversations are permanently deleted.** Once claimed, you can see what ChatSee finds."

Then recommend the next step: *"Once you've claimed it, shall I connect Claude Code to your
organisation so you can ask what ChatSee found?"* (step 6).

## 6. After they claim
Reading data needs the developer's own sign-in, once:
- Claude Code: `/mcp` → the ChatSee server → **Authenticate** → **Continue** → **Allow**
  (the claim already signed the browser in, so no password prompt).
- The ChatSee portal: sign in with the email and password chosen when claiming.
- Gemini CLI: `/mcp auth chatsee` · Codex: `codex mcp login <server name>`, then restart ·
  Cursor / VS Code: the ChatSee entry in the MCP settings → **Connect** / **Start**.

Then recommend one thing to try, for example *"Ask me: what are the top errors for
<agent>?"*. Skills 2-4 work from here: ask the Guardian (guardian-query), review fixes (remediation), code
fixes (structural-correction). Failures appear a few minutes to about an hour after the
conversations, so "no errors yet" right after setup is normal.

**Never search for API keys, credentials or other `.env` files to get around a missing
sign-in,** and never read files outside the project.
