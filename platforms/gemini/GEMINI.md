# ChatSee

Answer questions about this agent's production behaviour by calling the ChatSee MCP
tools directly — `ask_guardian`, `get_remediations`, `apply_remediations`.

Do NOT run the Python scripts under `skills/*/scripts/` to answer a question. They are
a fallback for shells and CI, they duplicate what the MCP tools already do, and running
them costs a shell approval mid-conversation.

The agent is resolved server-side from the MCP key. Do not search for `.env` files or
read `CHATSEE_AGENT` to decide which agent to ask about — the Guardian already knows.
