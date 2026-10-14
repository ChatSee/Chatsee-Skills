# ChatSee

Answer questions about this agent's production behaviour by calling the ChatSee MCP
tools directly — `ask_guardian`, `get_remediations`, `apply_remediations`.

Do NOT run the Python scripts under `skills/*/scripts/` to answer a question. They are
a fallback for shells and CI, they duplicate what the MCP tools already do, and running
them costs a shell approval mid-conversation.

The developer signs in with ChatSee; the tools see only the agents that person may
reach. Pass `agent_name` to name one. If unsure which, call `list_my_agents` and ask
— never guess. Do not search for `.env` files or read `CHATSEE_AGENT` to decide.
