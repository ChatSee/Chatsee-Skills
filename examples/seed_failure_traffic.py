#!/usr/bin/env python3
"""Send realistic FAILING conversations to a ChatSee agent, so the platform's own
classifier has something to find.

This is the enterprise-shaped test: instead of hand-creating a failure record in the
database, we make the agent actually misbehave and let ChatSee detect it. Each
conversation below reproduces a failure mode ChatSee's taxonomy already recognises —
observed live on a real monitored agent:

  SCO_07  Silent Error Ignore   — a tool call fails; the agent answers as if it didn't
  RES_13  Partial Answer        — a multi-part request; only some parts answered
  RES_05  Canned Response       — user pushes back; agent replies with boilerplate
  REA_15  Invalid Assumption    — agent states a cause the data doesn't support
  SCO_12  Intent Misclassification — agent answers a question that wasn't asked

No LLM is called: the Guardian classifies conversation *content*, so scripted
transcripts exercise the same path a misbehaving production agent would. That also
makes the corpus deterministic — the same failures every run, which is what you want
when you're testing whether detection works.

    CHATSEE_AGENT_ID=… CHATSEE_TENANT_ID=… CHATSEE_ENV=demo \
        ./.venv/bin/python examples/seed_failure_traffic.py [--dry-run]

⚠️  Sends real telemetry. Point it at a DISPOSABLE agent, never a customer's.
"""

import os
import sys

from chatsee import ChatseeTracker

SYSTEM = (
    "You are an audience-building assistant for a marketing team. Build customer segments "
    "from the requested targeting criteria. If a criterion is unavailable, say so explicitly."
)

# Each entry is one conversation: a list of turns.
# A turn is (user_message, bot_message, tool_calls) where a tool_call is
# (name, arguments, result, error) — error=None means it succeeded.
CONVERSATIONS = [
    # ---- SCO_07 Silent Error Ignore: the tool rejected a field, the user is never told ----
    (
        "SCO_07",
        [
            (
                "Build me an audience of EV buyers in California with household income over $150k.",
                "Here's your audience: 48,200 customers in California with household income over $150k.",
                [
                    (
                        "build_segment",
                        {
                            "region": "California",
                            "income_min": 150000,
                            "intent": "EV_auto_purchase_intent",
                        },
                        {"segment_size": 48200, "applied": ["region", "income_min"]},
                        "unsupported_field: EV_auto_purchase_intent",
                    )
                ],
            ),
        ],
    ),
    (
        "SCO_07",
        [
            (
                "I need a segment of lapsed subscribers who opened our EV newsletter.",
                "Done — 12,405 lapsed subscribers are in your segment.",
                [
                    (
                        "build_segment",
                        {"status": "lapsed", "engaged_with": "ev_newsletter"},
                        {"segment_size": 12405, "applied": ["status"]},
                        "unsupported_field: engaged_with",
                    )
                ],
            ),
        ],
    ),
    (
        "SCO_07",
        [
            (
                "Target households with a second vehicle and a home charger.",
                "Your audience is ready: 7,830 households.",
                [
                    (
                        "build_segment",
                        {"vehicles_min": 2, "has_home_charger": True},
                        {"segment_size": 7830, "applied": ["vehicles_min"]},
                        "unsupported_field: has_home_charger",
                    )
                ],
            ),
        ],
    ),
    # ---- RES_13 Partial Answer: multi-part request, only part delivered ----
    (
        "RES_13",
        [
            (
                "Give me the segment size, the average income, and the top three states.",
                "The segment contains 48,200 customers.",
                [("build_segment", {"region": "California"}, {"segment_size": 48200}, None)],
            ),
        ],
    ),
    (
        "RES_13",
        [
            (
                "Build the audience, then tell me the expected open rate and the best send time.",
                "I've built the audience — 22,140 customers.",
                [("build_segment", {"tier": "premium"}, {"segment_size": 22140}, None)],
            ),
        ],
    ),
    (
        "RES_13",
        [
            (
                "Compare the Spring and Holiday segments on size, income, and churn risk.",
                "Spring has 48,200 customers and Holiday has 31,050.",
                [
                    ("build_segment", {"campaign": "Spring"}, {"segment_size": 48200}, None),
                    ("build_segment", {"campaign": "Holiday"}, {"segment_size": 31050}, None),
                ],
            ),
        ],
    ),
    # ---- RES_05 Canned Response: user objects, agent replies with boilerplate ----
    (
        "RES_05",
        [
            (
                "Build an audience of EV buyers earning over $150k.",
                "Here's your audience: 48,200 customers.",
                [
                    (
                        "build_segment",
                        {"income_min": 150000, "intent": "EV_auto_purchase_intent"},
                        {"segment_size": 48200, "applied": ["income_min"]},
                        "unsupported_field: EV_auto_purchase_intent",
                    )
                ],
            ),
            (
                "This looks wrong — I asked for EV buyers and this is just everyone over $150k.",
                "This audience was generated based on the available criteria. Let me know if "
                "you'd like to refine it further.",
                [],
            ),
        ],
    ),
    (
        "RES_05",
        [
            (
                "The segment you built last time was missing my income filter.",
                "Segments are generated based on the available criteria. Please let me know if "
                "there is anything else I can help you with.",
                [],
            ),
        ],
    ),
    (
        "RES_05",
        [
            (
                "Why is this audience so much smaller than last week's?",
                "Audience sizes are generated based on the available criteria at the time of the "
                "request. Let me know if you'd like to refine it further.",
                [],
            ),
        ],
    ),
    # ---- REA_15 Invalid Assumption: states an unsupported cause ----
    (
        "REA_15",
        [
            (
                "Why did the segment shrink from 60k to 48k?",
                "The drop is because a large number of customers unsubscribed over the weekend.",
                [("build_segment", {"region": "California"}, {"segment_size": 48200}, None)],
            ),
        ],
    ),
    (
        "REA_15",
        [
            (
                "Our open rate fell this month. What happened?",
                "That's most likely because your competitors increased their email volume, which "
                "reduced attention in the inbox.",
                [],
            ),
        ],
    ),
    # ---- SCO_12 Intent Misclassification: answers a question that wasn't asked ----
    (
        "SCO_12",
        [
            (
                "Can you export the current segment to CSV?",
                "The current segment contains 48,200 customers with an average income of $162,000.",
                [("build_segment", {"region": "California"}, {"segment_size": 48200}, None)],
            ),
        ],
    ),
    (
        "SCO_12",
        [
            (
                "How do I share this audience with my colleague?",
                "Your audience has 22,140 customers and was built from the premium tier criteria.",
                [],
            ),
        ],
    ),
    (
        "SCO_12",
        [
            (
                "Delete the Holiday Teaser segment please.",
                "The Holiday Teaser segment contains 31,050 customers.",
                [("build_segment", {"campaign": "Holiday"}, {"segment_size": 31050}, None)],
            ),
        ],
    ),
]


def send(conversations, agent_id: str, tenant_id: str, env: str) -> int:
    sent = 0
    for i, (code, turns) in enumerate(conversations, 1):
        # A fresh tracker per conversation → the server assigns a distinct session,
        # exactly as separate end-user conversations would arrive.
        tracker = ChatseeTracker(
            agent_id=agent_id, tenant_id=tenant_id, api_base_url=env, verify_ssl=True
        )
        for user_msg, bot_msg, tools in turns:
            tracker.start_turn(
                user_message=user_msg,
                system_prompt=SYSTEM,
                metadata={"model": "seed-corpus", "seeded_failure_mode": code},
            )
            for name, args, result, error in tools:
                tracker.log_tool_call(name, args, result=result, error=error)
            tracker.end_turn(bot_message=bot_msg)
            sent += 1
        status = "✓" if tracker.session_id else "✗ not confirmed"
        print(f"  [{i:2}/{len(conversations)}] {code}  {len(turns)} turn(s)  {status}")
    return sent


def main() -> None:
    dry = "--dry-run" in sys.argv[1:]
    agent_id = os.environ.get("CHATSEE_AGENT_ID")
    tenant_id = os.environ.get("CHATSEE_TENANT_ID")
    env = os.environ.get("CHATSEE_ENV")  # no default — a wrong guess seeds the wrong tenant
    if not (agent_id and tenant_id and env):
        sys.exit("set CHATSEE_AGENT_ID, CHATSEE_TENANT_ID and CHATSEE_ENV first")

    modes = sorted({c for c, _ in CONVERSATIONS})
    turns = sum(len(t) for _, t in CONVERSATIONS)
    print(
        f"{len(CONVERSATIONS)} conversations / {turns} turns across {len(modes)} failure "
        f"modes: {', '.join(modes)}"
    )
    print(f"target: agent {agent_id} on {env}")

    if dry:
        print("\nDRY RUN — nothing sent.")
        return

    print()
    sent = send(CONVERSATIONS, agent_id, tenant_id, env)
    print(
        f"\n{sent} turns sent. ChatSee's classifier decides what (if anything) it flags — "
        f"give it time, then ask the Guardian about this agent."
    )


if __name__ == "__main__":
    main()
