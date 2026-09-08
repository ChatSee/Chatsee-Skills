#!/usr/bin/env python3
"""Stand in for the human reviewer: turn a DETECTED error into an APPROVED fix.

ChatSee's loop has a person in the middle. After the platform detects errors it generates
suggested fixes ("recommendations"), and a human approves the ones worth shipping — which
creates the `failure_memory` record that skill 2 later pulls. Normally that approval happens
in the ChatSee dashboard; this script does it over the REST API instead, so the whole loop
can be exercised end to end without the UI.

    1. fetch_recommendations         → generates suggestions for an error code (if none yet)
    2. submit_applied_recommendations → approves them  → failure_memory (state: Created)

After this, skill 2 takes over:  get_remediations (→ Delivered) → apply → --confirm (→ Applied)

Auth: needs a dashboard bearer token. Either pass --token, or let this import the login
helper from `register_agent_demo.py` (gitignored — it carries the credentials, which is
exactly why they are not duplicated here).

    ./.venv/bin/python examples/approve_fix.py --agent-id <id> --code REA_18 [--count 1]
    ./.venv/bin/python examples/approve_fix.py --agent-id <id> --code REA_18 --list-only

⚠️  Creates real records. Point it at a DISPOSABLE agent.
"""

import argparse
import json
import os
import sys

import httpx
from _common import api_base, get_token

REC = "/v1/error_recommendations"


def post(client, path, token, payload):
    r = client.post(
        path,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )
    try:
        body = r.json()
    except ValueError:
        sys.exit(f"{path} → HTTP {r.status_code}, non-JSON body: {r.text[:300]}")
    if r.status_code != 200:
        sys.exit(f"{path} → HTTP {r.status_code}: {json.dumps(body)[:500]}")
    return body


def main() -> None:
    p = argparse.ArgumentParser(description="Approve a fix for a detected error (no UI).")
    p.add_argument(
        "--agent-id",
        default=os.environ.get("CHATSEE_AGENT_ID"),
        help="defaults to $CHATSEE_AGENT_ID",
    )
    p.add_argument("--code", required=True, help="errorcode_id, e.g. REA_18")
    p.add_argument("--count", type=int, default=1, help="error_count for this code")
    p.add_argument("--token", default=None, help="dashboard bearer token")
    p.add_argument("--title", default=None, help="failure-memory title (must be unique per agent)")
    p.add_argument("--max-recs", type=int, default=3, help="how many suggestions to approve")
    p.add_argument("--list-only", action="store_true", help="show suggestions, approve nothing")
    args = p.parse_args()
    if not args.agent_id:
        sys.exit("no agent: pass --agent-id or set CHATSEE_AGENT_ID (source your .env.<agent>)")

    base = api_base()
    token = get_token(args.token, base)
    print("[auth] ok")

    with httpx.Client(base_url=base, timeout=180.0, verify=False) as client:
        # ---- 1. suggestions (generated on demand if this error has none yet) ----
        print(f"[recommend] fetching suggestions for {args.code} (may generate — can be slow) ...")
        body = post(
            client,
            f"{REC}/fetch_recommendations",
            token,
            {"errorcode_id": args.code, "agent_id": args.agent_id, "error_count": args.count},
        )
        data = body.get("data") or {}
        current = data.get("current_recommendations") or []
        print(f"[recommend] {len(current)} suggestion(s) returned")
        for i, rec in enumerate(current, 1):
            desc = rec.get("recommendation_description") or rec.get("description") or str(rec)
            print(f"  {i}. {desc[:160]}")

        if not current:
            print("\nNo suggestions available for this error code — nothing to approve.")
            print(f"raw keys: {sorted(data)}")
            return
        if args.list_only:
            print("\n--list-only — nothing approved.")
            return

        # ---- 2. approve → creates the failure_memory skill 2 will pull ----
        chosen = current[: args.max_recs]
        title = args.title or f"Fix {args.code} (approved via API)"
        payload = {
            "errorcode_id": args.code,
            "agent_id": args.agent_id,
            "title": title,
            "error_count": args.count,
            "error_description": data.get("error_description") or f"Detected error {args.code}",
            "error_name": data.get("error_name") or args.code,
            "recommendations": [
                {
                    "recommendation_id": r.get("_id") or r.get("recommendation_id"),
                    "recommendation_description": r.get("recommendation_description")
                    or r.get("description", ""),
                    "is_modified_by_user": False,
                }
                for r in chosen
            ],
        }
        print(f"\n[approve] submitting {len(chosen)} recommendation(s) as {title!r} ...")
        body = post(client, f"{REC}/submit_applied_recommendations", token, payload)
        result = body.get("data") or {}
        print("[approve] ok — failure memory created")
        print(f"  applied_recommendation_id: {result.get('applied_recommendation_id')}")
        print(f"  jira: {result.get('jira_status', 'n/a')}")
        print("\nNext: skill 2 can now pull it —")
        print("  fetch_remediation.py all         # Created → Delivered")
        print("  apply_to_prompt.py <prompt.md> --mode all --write       # splice into the prompt")
        print("  ...then --confirm          # Delivered → Applied")


if __name__ == "__main__":
    main()
