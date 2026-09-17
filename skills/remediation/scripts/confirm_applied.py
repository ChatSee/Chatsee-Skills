#!/usr/bin/env python3
"""skill 2 — tell the Guardian a fix is now in the agent's prompt. Closes the loop.

Use this **after applying a fix yourself**, when the prompt lives somewhere
`apply_to_prompt.py` cannot mechanically edit: a YAML key, a database row, a prompt-management
service, a vendor console, a template assembled at runtime. Find the prompt, make the change,
verify it, then acknowledge here.

This is the general path. `apply_to_prompt.py` is a shortcut for the two shapes that can be
edited safely without judgement (a prose file, a Python string literal) and acknowledges on
its own; everything else comes through here.

    confirm_applied.py <failure_memory_id> [...] --note "what you changed" [--target <where>]

    --note    required. What you changed and where — this is what a human reads later when
              asking "was this actually done, and to what?"
    --target  what was modified: a path, or a description like
              "Copilot Studio topic: Order Status". Defaults to the note.

⚠️ STATE-CHANGING: moves each failure memory Delivered → Applied on the Guardian. Only run it
once the change is genuinely live — acknowledging a fix you have not applied makes ChatSee's
record wrong in the one direction nobody checks.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import apply_record  # noqa: E402  - after the sys.path insert above
import guardian_client as g  # noqa: E402  - after the sys.path insert above


def _parse(argv):
    ids, note, target = [], None, None
    it = iter(argv)
    for a in it:
        if a == "--note":
            note = next(it, None)
        elif a == "--target":
            target = next(it, None)
        elif a.startswith("--"):
            sys.exit(f"unknown option {a!r}. See the docstring for usage.")
        else:
            ids.append(a)
    if not ids:
        sys.exit(__doc__)
    if not note:
        sys.exit("--note is required: say what you changed and where.")
    return ids, note, target or note


def main() -> None:
    ids, note, target = _parse(sys.argv[1:])

    # Record first. If the Guardian call then fails, there is still local evidence of what was
    # applied — the opposite order would lose it exactly when it matters.
    path = apply_record.write(target, ids, confirmed=False, note=note)

    resp = g.apply_remediations(ids, note)
    apply_record.write(target, ids, confirmed=True, note=note)

    print(json.dumps(resp, indent=2)[:800])
    results = resp.get("results") or []
    ok = [r for r in results if r.get("success")]
    print(f"\n{len(ok)}/{len(ids)} acknowledged. Local record: {path}")
    if len(ok) != len(ids):
        sys.exit("some ids were not acknowledged — see the results above")


if __name__ == "__main__":
    try:
        main()
    except g.GuardianError as e:
        sys.exit(f"error: {e}")
