# Install ChatSee Skills in Claude Code

This guide connects **Claude Code** to ChatSee on the **QA environment** and installs the four
ChatSee skills. It covers both ways of using Claude Code:

- **[A. Claude Code in a terminal](#a-claude-code-in-a-terminal)** (cmd, PowerShell, macOS or Linux)
- **[B. Claude Code in VS Code](#b-claude-code-in-vs-code)** (the Claude Code extension)

Both share the same settings, so a plugin installed one way also appears in the other.
**You never need an API key:** you sign in with your ChatSee account in the browser.

Time needed: about 10 minutes.

---

## Before you start

| You need | How to check |
|---|---|
| A **ChatSee QA account** | You can log in at <https://qa.chatsee.ai> |
| **Claude Code**, signed in to your Claude account | `claude --version` prints a version (terminal), or the Claude Code extension is installed (VS Code) |
| **Git**, signed in to GitHub | `git --version` prints a version |
| **Access to the ChatSee Skills repository** (private for now) | See the check below |
| **Python 3.9+** (the skills' helper scripts use it) | `python --version` |

**Check repository access** (the same command works in cmd, PowerShell and macOS/Linux):

```
git ls-remote https://github.com/ChatSee/Chatsee-Skills chatsee-qa
```

✅ One line ending in `refs/heads/chatsee-qa` means you're ready.
❌ `Repository not found` means your GitHub account isn't in the ChatSee organization yet. Ask the
ChatSee team for access.

> Don't have Claude Code yet? Terminal: in **PowerShell** run `irm https://claude.ai/install.ps1 | iex`,
> then open a new terminal and run `claude` once to sign in. VS Code: install the **Claude Code**
> extension (publisher: Anthropic) from the Extensions view and sign in when it asks.

---

## A. Claude Code in a terminal

### Step 1: Install the ChatSee Skills plugin

Run these two commands. They are the same in **cmd**, **PowerShell** and **macOS/Linux**:

```
claude plugin marketplace add "ChatSee/Chatsee-Skills#chatsee-qa"
claude plugin install chatsee-skills@chatsee
```

✅ You should see `Successfully added marketplace: chatsee` and
`Successfully installed plugin: chatsee-skills@chatsee (scope: user)`.

`#chatsee-qa` selects the QA version. Without it you would get a different environment.

![Step 1: the two install commands and their success messages](images/claude-code/a1-install.png)

### Step 2: Start Claude Code in your project

Go to the folder of the project you want to work on (for example your AI agent's code) and start
Claude Code:

```
cd <your project folder>
claude
```

Claude Code shows **"1 MCP server needs authentication · run /mcp"**. That's the ChatSee server
waiting for you to sign in. Type `/mcp` and press Enter.

![Step 2: the needs-authentication notice and /mcp](images/claude-code/a2-start.png)

### Step 3: Sign in to ChatSee

1. In **Manage MCP servers**, select **plugin:chatsee-skills:chatsee** (marked *needs authentication*)
   and press Enter.

   ![Step 3.1: the ChatSee server in the MCP list](images/claude-code/a3-mcp-list.png)

2. Choose **1. Authenticate** and press Enter.

   ![Step 3.2: Authenticate](images/claude-code/a3-authenticate.png)

3. Your browser opens on ChatSee. **Leave Claude Code on this screen** until you finish in the
   browser. If the browser doesn't open, press `c` to copy the address shown and paste it into
   your browser.

   ![Step 3.3: Claude Code waiting while you sign in](images/claude-code/a3-browser-opens.png)

4. If ChatSee asks you to sign in, log in with your **ChatSee QA account** (email and password,
   Google or GitHub).

   ![Step 3.4: the ChatSee sign-in page](images/claude-code/a3-login.png)

5. On **Continue to Claude Code**, check the account shown under *Signed in as* and click
   **Continue**. (Wrong account? Click **Switch account**.)

   ![Step 3.5: Continue to Claude Code](images/claude-code/a3-continue.png)

6. On **Allow Claude Code?**, check the permissions and click **Allow**:
   - Ask the Guardian about your agents' conversations and errors
   - See the approved fixes for your agents
   - Mark fixes as applied to your agents
   - Stay connected when you're not using it

   ![Step 3.6: Allow Claude Code?](images/claude-code/a3-allow.png)

7. The browser shows **Authentication successful**. Close the tab and return to Claude Code.

   ![Step 3.7: Authentication successful](images/claude-code/a3-success.png)

✅ Claude Code shows **Authentication successful. Connected to plugin:chatsee-skills:chatsee.**

![Step 3: connected](images/claude-code/a3-connected.png)

### Step 4: Check it works

Ask Claude Code:

```
list my ChatSee agents
```

✅ It lists the agents your ChatSee account can see, with the environment `qa`. (Approve the
ChatSee tool call if Claude Code asks.)

![Step 4: the agent list](images/claude-code/a4-agents.png)

**You're set up.** Go to [Using the skills](#using-the-skills).

---

## B. Claude Code in VS Code

> In the VS Code Claude Code panel, plugins are managed from a screen (**Manage plugins**), not
> with typed `/plugin …` commands.

### Step 1: Open your project and the Claude Code panel

**File → Open Folder…** and choose your project folder. Open the Claude Code panel (the Claude
icon at the top right of the editor).

### Step 2: Open Manage plugins

In the Claude Code chat box, type `/plu` and choose **Manage plugins** from the list.

![Step 2: Manage plugins in the slash-command list](images/claude-code/b1-plugins-command.png)

### Step 3: Add the ChatSee marketplace

1. Open the **Marketplaces** tab.
2. In the *GitHub repo, URL, or path…* box, type:

   ```
   ChatSee/Chatsee-Skills#chatsee-qa
   ```

3. Click **Add**.

   ![Step 3: adding the marketplace](images/claude-code/b2-marketplace-add.png)

✅ **chatsee** appears in the list (*GitHub: ChatSee/Chatsee-Skills*).

![Step 3: marketplace added](images/claude-code/b2-marketplace-added.png)

### Step 4: Install the plugin

1. Open the **Plugins** tab. Under *Available*, find **chatsee-skills** and click **Install**.

   ![Step 4: chatsee-skills in the plugin list](images/claude-code/b3-install.png)

   The *Source* link under the plugin may show `…/tree/main/`. That's only a display link: the
   plugin comes from the `chatsee-qa` branch you added in step 3.

2. ✅ It moves to *Installed* as **chatsee-skills@chatsee**, switched on, with *Scope: project*
   (it's installed for this project folder) and the **chatsee** server listed under it.

   ![Step 4: installed](images/claude-code/b3-installed.png)

3. Close Manage plugins and type `/reload-plugins` in the chat box.

### Step 5: Sign in to ChatSee

1. Type `/mcp`. Under *MCP servers*, **plugin:chatsee-skills:chatsee** shows **⚠ Needs Auth**.
   Select it.

   ![Step 5.1: the ChatSee server needs authentication](images/claude-code/b4-mcp-menu.png)

2. In the **MCP servers** panel, select **plugin:chatsee-skills:chatsee** again, then click
   **Authenticate**.

   ![Step 5.2: MCP servers panel](images/claude-code/b4-needs-auth.png)

3. VS Code asks **"Do you want Code to open the external website?"** for `auth-qa.chatsee.ai`.
   Click **Open**.

   ![Step 5.3: allow VS Code to open the sign-in page](images/claude-code/b4-open-browser.png)

4. In the browser: log in if asked → **Continue** → **Allow** → *Authentication successful*. These
   are the same screens as [A, step 3](#step-3-sign-in-to-chatsee).
5. ✅ Back in VS Code, the server shows **✓ Connected**.

   ![Step 5.5: connected](images/claude-code/b4-connected.png)

Sign in from VS Code even if you already signed in from a terminal: the two may not share the
sign-in.

### Step 6: Check it works

Ask in the panel: `list my ChatSee agents`. ✅ Claude calls **list_my_agents** and lists your
agents, with the environment `qa`.

![Step 6: the agent list in VS Code](images/claude-code/b5-agents.png)

> Prefer commands? If you have the Claude Code CLI, you can instead run the two commands from
> [A, step 1](#step-1-install-the-chatsee-skills-plugin) in VS Code's terminal (that installs for
> your user, in every project), then `/reload-plugins` in the panel and continue from step 5.

---

## Using the skills

Just ask in plain English. Claude Code picks the right skill.

| Skill | What it does | Try asking |
|---|---|---|
| **telemetry-setup** | Adds the ChatSee SDK to your agent so its conversations are sent to ChatSee | `set up ChatSee telemetry for this agent, it's <agent name>` |
| **guardian-query** | Asks the ChatSee Guardian what's going wrong in production | `what is <agent name> breaking this week?` |
| **remediation** | Fetches the approved fixes and applies them to your agent's system prompt | `get the approved fixes for <agent name> and apply them to the system prompt` |
| **structural-correction** | Finds code-level causes of failures and proposes a fix for you to approve | `find the code-level cause of <problem> in <file> and propose a fix` |

Notes:
- The agent must already exist in ChatSee (portal: **Settings → Add agent**). `telemetry-setup` gets
  its IDs from your account automatically; no keys are needed.
- New conversations take a while (minutes, sometimes longer) to be analysed before the Guardian and
  remediations reflect them.
- Every change to your code is shown to you first. Nothing is applied silently.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| `Repository not found` when adding the marketplace | Your GitHub account needs access to the ChatSee organization, and `git` must be signed in. Rerun the access check above |
| `Cannot add marketplace "chatsee": its source doesn't match…` | You installed ChatSee Skills before from another environment. Run `claude plugin marketplace remove chatsee`, then step 1 again |
| `/mcp` doesn't list **chatsee** | Restart Claude Code (or `/reload-plugins` in VS Code), and check `claude plugin list` shows `chatsee-skills` enabled |
| After **Allow**, the browser shows **"This site can't be reached"** on `localhost` | Claude Code had stopped waiting. If it still shows **`URL >`**, copy the whole address from the browser and paste it there. Otherwise choose **Authenticate** again and finish in the browser without leaving that screen |
| The browser says **you're signed in as a different user** | Log in to <https://qa.chatsee.ai> with the account you want (or clear cookies for `auth-qa.chatsee.ai`), then **Authenticate** again |
| The browser says **this request has expired** | You took more than about 30 minutes or reused an old page. Close it and choose **Authenticate** again |
| `list my ChatSee agents` returns nothing | Your account has no agents, or none assigned to you. Check in the ChatSee portal |
| Anything asks you for an **API key** | That shouldn't happen. Check you used `#chatsee-qa` in step 1, and report it |

---

## Update, disconnect or uninstall

```
claude plugin marketplace update chatsee                 # fetch the latest version...
claude plugin update chatsee-skills@chatsee              # ...and update the installed plugin
claude mcp logout "plugin:chatsee-skills:chatsee"        # disconnect from ChatSee
claude plugin uninstall chatsee-skills@chatsee           # remove the plugin
claude plugin marketplace remove chatsee                 # remove the marketplace
```

You can also disconnect from `/mcp` → **chatsee** → **Clear authentication** (terminal and VS Code).
In VS Code you can remove the plugin from **Manage plugins → Plugins** (the bin icon).
