"""The local record of what was applied to an agent's prompt, and when.

Shared because there are two ways a fix gets applied and both must leave the same trail:
`apply_to_prompt.py` for the shapes it can edit mechanically, and Claude editing the prompt
directly for every other shape (a YAML key, a database row, a vendor console). The second
path is the general one, so the record cannot live inside the first script.

Written BEFORE the Guardian is told anything, so a failed acknowledgement still leaves
evidence of what actually landed.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime


def git_sha(cwd: str | None = None) -> str | None:
    """Short commit of the agent's repo, when there is one — provenance for the applied block."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def write(target: str, ids: list, confirmed: bool, **extra) -> str:
    """Append one entry to `.chatsee/applied.jsonl` beside `target`. Returns the file path.

    `target` is whatever was changed — a prompt file, a source file, or a plain description
    like "Copilot Studio topic: Order Status" when the prompt is not on disk at all. When it
    is not a real path the record lands beside the working directory instead, which is the
    best available answer for a prompt that lives somewhere else entirely.
    """
    entry = {
        # `.astimezone()` rather than `timezone.utc`: these files get copied into other
        # people's repos, where a linter targeting a newer Python rewrites `timezone.utc` into
        # `datetime.UTC` (3.11+) and the skill then fails to import on 3.9/3.10. This gives an
        # equally unambiguous offset-aware timestamp with nothing for a linter to modernise.
        "applied_at": datetime.now().astimezone().isoformat(),
        "target": target,
        "failure_memory_ids": ids,
        "chatsee_env": os.environ.get("CHATSEE_ENV"),
        "guardian_confirmed": confirmed,
    }
    if os.path.exists(target):
        entry["target_path"] = os.path.abspath(target)
        base = os.path.dirname(os.path.abspath(target))
    else:
        base = os.getcwd()
    entry["code_version"] = git_sha(base)
    entry.update(extra)

    d = os.path.join(base, ".chatsee")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "applied.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return path
