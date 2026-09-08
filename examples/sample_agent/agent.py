"""A small custom support agent — with a deliberate STRUCTURAL bug.

The bug: `history` grows without bound, and every turn sends the ENTIRE history to the
model. Long conversations blow past the context window → the model's replies get
truncated / the agent terminates early. This is a *code-level* problem a prompt tweak
cannot fix — exactly what skill 3 (structural-correction) targets, as opposed to skill 2
(prompt-level).

(The model call is faked; this is a fixture for demonstrating skill 3.)
"""


class SupportAgent:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history: list[dict] = []

    def turn(self, user_msg: str) -> str:
        self.history.append({"role": "user", "content": user_msg})

        # BUG (structural): the full, unbounded history is sent every turn.
        messages = [{"role": "system", "content": self.system_prompt}, *self.history]

        reply = self._call_model(messages)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _call_model(self, messages: list[dict]) -> str:
        # Real implementation would call the LLM API with `messages`.
        # If len(messages) is large, the real call would truncate / error.
        return "(reply)"
