#!/usr/bin/env python3
"""skill 2 apply-step — write the Guardian's fix-rules INTO a target agent's prompt file.

Fetches the current rules and splices them into the prompt file between marker comments.
Idempotent: re-running REPLACES the managed block, never duplicates it.

SAFE BY DEFAULT: prints a diff and writes nothing unless you pass --write.

    usage:  apply_to_prompt.py <prompt_file> [--mode all|new] [--write] [--confirm]
            apply_to_prompt.py <prompt_file> --rules-file <saved get_remediations output> [--write]

    --rules-file  signed in with ChatSee, no key: take the rules from the get_remediations
               tool's output instead of fetching them. The script then never touches the
               network; confirm afterwards with the apply_remediations tool.

    --mode     which rules to apply (default: all — everything this agent's prompt should
               contain). `new` applies only never-downloaded rules, which is rarely what you
               want: merely LOOKING at a rule marks it downloaded, so `new` is usually empty
               by the time you apply. Defaulting to `new` made the obvious sequence
               (fetch, then apply) report "nothing to apply".
    --write    actually modify the file (default: dry-run, show the diff only)
    --confirm  after writing, tell the Guardian these were applied
               (STATE-CHANGING: moves them Delivered → Applied — only when you mean it)

Every write makes a `<file>.chatsee.bak` backup, is atomic (temp file + rename, so an
interrupted run cannot leave a half-written prompt), and appends a record to
`.chatsee/applied.jsonl` so there is a local, durable answer to "what was applied, when".
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_shared")))
import apply_record  # noqa: E402  - after the sys.path insert above
import guardian_client as g  # noqa: E402  - after the sys.path insert above

START = "<!-- chatsee:failure-memory:start (managed by the remediation skill) -->"
END = "<!-- chatsee:failure-memory:end -->"
MAX_BLOCK = 100_000  # refuse absurd payloads rather than paste them into a prompt

# Two prompt shapes are supported: a prose file, and a string literal in Python source.
# Everything else is refused rather than corrupted — an HTML comment is not a comment in
# JSON or YAML, and splicing one in breaks the file. (Verified: writing into a .py at file
# level produced `SyntaxError: unterminated string literal`, which is why the Python path
# edits the literal through the AST instead of appending to the file.)
UNSPLICEABLE = {
    ".js",
    ".mjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rb",
    ".java",
    ".rs",
    ".php",
    ".cs",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".xml",
    ".csv",
}

# Names a system prompt is usually bound to. Used only to find the variable when the
# developer has not named one with --var.
PROMPT_NAMES = (
    "SYSTEM_PROMPT",
    "SYSTEM_MESSAGE",
    "SYSTEM_INSTRUCTIONS",
    "INSTRUCTIONS",
    "SYSTEM",
    "PROMPT",
)


class ApplyError(RuntimeError):
    """A local, user-fixable problem — bad arguments or an unsafe target file."""


def _is_python(path: str) -> bool:
    return os.path.splitext(path)[1].lower() == ".py"


def _check_target(path: str) -> None:
    """Refuse a target the managed block would corrupt rather than annotate."""
    suffix = os.path.splitext(path)[1].lower()
    if suffix in UNSPLICEABLE:
        raise ApplyError(
            f"{path} is a {suffix} file. This script only edits the two shapes that need no "
            "judgement — a prose file, and a Python string literal — because an HTML comment "
            f"is not a comment in {suffix} and writing one would corrupt the file.\n"
            "  That is a limit of the SHORTCUT, not of the skill: edit this prompt yourself "
            "with a parser that understands the format, keep the chatsee markers so the next "
            "apply replaces rather than duplicates, verify the file still loads, then run\n"
            "    confirm_applied.py <failure_memory_id>... --note 'what you changed'\n"
            "  to close the loop. `fetch_remediation.py` gives you the rules and the ids."
        )


# ---- Python string-literal prompts -----------------------------------------


def _char_offset(lines: list, lineno: int, col: int) -> int:
    """Absolute character offset for an ast (lineno, col_offset) pair.

    `col_offset` is a **UTF-8 byte** offset into the line, not a character offset — decoding
    the byte prefix converts it. Getting this wrong silently misplaces the edit on any prompt
    containing a non-ASCII character, which most real prompts eventually do.
    """
    line = lines[lineno - 1]
    return sum(len(x) for x in lines[: lineno - 1]) + len(
        line.encode("utf-8")[:col].decode("utf-8")
    )


def find_prompt_literal(source: str, var: str | None = None):
    """Locate the system-prompt string literal. Returns (name, value, start, end).

    Only a module-level assignment of a plain string constant qualifies. An f-string or a
    concatenation is refused rather than guessed at: rewriting a computed prompt would
    silently change what the agent sends.
    """
    import ast  # noqa: PLC0415 - only needed on the Python path

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ApplyError(f"cannot parse the file as Python: {e}") from None

    lines = source.splitlines(keepends=True)
    found = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if var is not None and target.id != var:
            continue
        if var is None and target.id not in PROMPT_NAMES:
            continue
        if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            raise ApplyError(
                f"{target.id} is not a plain string literal (it looks computed). Move it to a "
                "prose file, or point --var at a variable that is a literal."
            )
        v = node.value
        found.append(
            (
                target.id,
                v.value,
                _char_offset(lines, v.lineno, v.col_offset),
                _char_offset(lines, v.end_lineno, v.end_col_offset),
            )
        )

    if not found:
        looked = f"--var {var}" if var else f"any of {', '.join(PROMPT_NAMES)}"
        raise ApplyError(
            f"no module-level system-prompt string literal found ({looked}).\n"
            "  Name it with --var <NAME>, or move the prompt into a .md/.txt file."
        )
    if len(found) > 1:
        names = ", ".join(n for n, _, _, _ in found)
        raise ApplyError(
            f"several candidate prompt variables ({names}) — name one with --var so this "
            "does not edit the wrong prompt."
        )
    return found[0]


def _py_literal(text: str) -> str:
    """Render `text` as a triple-quoted Python literal that round-trips exactly."""
    if not text.endswith("\n"):
        text += "\n"
    body = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""{body}"""'


def splice_python(source: str, block: str, var: str | None = None) -> str:
    """Return `source` with the managed block inside its prompt literal.

    The edit is verified before it is returned: the result must still parse, and the variable
    must still hold exactly the text we intended. A prompt is what the agent says to every
    customer — a corrupted one is worse than a failed apply.
    """
    name, value, start, end = find_prompt_literal(source, var)
    updated_value = _splice(value, block)
    if updated_value == value:
        return source

    new_source = source[:start] + _py_literal(updated_value) + source[end:]

    check_name, check_value, _, _ = find_prompt_literal(new_source, name)
    if check_name != name or check_value.rstrip("\n") != updated_value.rstrip("\n"):
        raise ApplyError(
            "internal: rewriting the prompt literal did not round-trip — refusing to write. "
            "Please report this with the prompt that triggered it."
        )
    return new_source


def _splice(text: str, block: str) -> str:
    """Insert or replace the managed block; never touch anything outside the markers.

    Raises on malformed marker state rather than guessing, because guessing here destroys
    the user's prompt: a stray START with no END used to make the next run delete everything
    between them.
    """
    n_start, n_end = text.count(START), text.count(END)
    if n_start > 1 or n_end > 1:
        raise ApplyError(
            f"file has {n_start} start and {n_end} end markers — expected at most one of each. "
            "Fix the file by hand (or delete the managed block) before re-applying."
        )
    if n_start != n_end:
        raise ApplyError(
            "file has an unbalanced chatsee managed block "
            f"({n_start} start / {n_end} end marker). Repair it by hand before re-applying."
        )
    if n_start == 1:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        return head + block + tail
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + block + "\n"


def _parse(argv):
    """Return (path, mode, write, confirm, var, rules_file). Unknown flags are an error."""
    path, mode, write, confirm, var, rules_file = None, "all", False, False, None, None
    it = iter(argv)
    for a in it:
        if a == "--rules-file":
            rules_file = next(it, None)
            if not rules_file:
                raise ApplyError("--rules-file needs a path to the get_remediations output")
        elif a == "--mode":
            raw = next(it, None)
            # "new" is our word for the server's "pending" — see the docstring.
            mode = {"all": "all", "new": "pending", "pending": "pending"}.get(raw)
            if mode is None:
                raise ApplyError(f"--mode must be 'all' (default) or 'new' (got {raw!r})")
        elif a == "--var":
            var = next(it, None)
            if not var:
                raise ApplyError("--var needs a variable name, e.g. --var SYSTEM_PROMPT")
        elif a == "--write":
            write = True
        elif a == "--confirm":
            confirm = True
        elif a.startswith("--"):
            raise ApplyError(f"unknown option {a!r}. See --help / the docstring for usage.")
        elif path is None:
            path = a
        else:
            raise ApplyError(f"unexpected extra argument {a!r} (one prompt file at a time).")
    return path, mode, write, confirm, var, rules_file


def _load_rules_file(rules_file: str) -> dict:
    """Read rules saved from the get_remediations MCP tool.

    This is how the script works when the developer signed in with ChatSee rather than
    setting a key. The sign-in lives inside the editor and never reaches a script, so the
    editor fetches the rules over its own connection, saves the tool's JSON output, and
    hands the file here. The script then only does the local, deterministic part — the
    splice — and never touches the network.
    """
    try:
        with open(rules_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise ApplyError(f"could not read rules from {rules_file}: {exc}") from exc
    if not isinstance(data, dict):
        raise ApplyError(f"{rules_file} is not the JSON object get_remediations returns")
    if data.get("error"):
        raise ApplyError(f"get_remediations returned an error: {data['error']}")
    return data


def _record(path: str, ids: list, mode: str, digest: str, confirmed: bool) -> None:
    """Append a durable local record — the same trail `confirm_applied.py` writes, so the two
    apply paths are indistinguishable to whoever reads the history later."""
    apply_record.write(path, ids, confirmed, mode=mode, block_sha256=digest)


def _write_atomic(path: str, content: str) -> None:
    """Back up, then replace via a same-directory temp file so a crash can't truncate."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            prev = f.read()
        with open(path + ".chatsee.bak", "w", encoding="utf-8") as f:
            f.write(prev)
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".chatsee-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main() -> None:
    path, mode, write, confirm, var, rules_file = _parse(sys.argv[1:])
    if not path:
        sys.exit(__doc__)
    if confirm and not write:
        raise ApplyError(
            "--confirm requires --write (never acknowledge a fix that wasn't applied)."
        )
    if confirm and rules_file:
        # With --rules-file the script has no connection of its own to confirm over.
        # The editor confirms instead, through the apply_remediations tool.
        raise ApplyError(
            "--confirm can't be used with --rules-file. After --write, confirm through the "
            "apply_remediations tool with the failure_memory_ids printed below."
        )
    # Before any network call: refusing early means a bad target costs nothing and cannot
    # leave a fix half-delivered.
    _check_target(path)

    r = _load_rules_file(rules_file) if rules_file else g.get_remediations(mode)
    md, ids = r.get("skills_markdown", ""), r.get("failure_memory_ids", [])
    if not md.strip():
        print(f"No {mode} remediations — nothing to apply. File untouched.")
        return
    if len(md) > MAX_BLOCK:
        raise ApplyError(f"remediation payload is {len(md)} chars (limit {MAX_BLOCK}) — refusing.")
    if START in md or END in md:
        raise ApplyError(
            "the Guardian's payload contains our managed-block markers — refusing to splice, "
            "as it would corrupt the block on the next run."
        )
    if not ids:
        print(
            "warning: the Guardian returned rules but no failure_memory_ids — "
            "nothing can be acknowledged, so --confirm will not be possible.",
            file=sys.stderr,
        )

    original = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            original = f.read()

    block = f"{START}\n{md.strip()}\n{END}"
    if _is_python(path):
        if not original:
            raise ApplyError(f"{path} does not exist — cannot find a prompt literal in it.")
        updated = splice_python(original, block, var)
    else:
        if var:
            raise ApplyError("--var only applies to a Python source file.")
        updated = _splice(original, block)

    if updated == original:
        # The rules are already in the file. That is still a valid state to acknowledge —
        # returning here used to make `--confirm` silently do nothing on a re-run, so a fix
        # you HAD applied could never be reported as applied.
        print(f"{path} is already up to date — no change.")
        if confirm and write and ids:
            resp = g.apply_remediations(ids, f"already present in {os.path.basename(path)}")
            print(f"Confirmed with Guardian: {json.dumps(resp)[:300]}")
        return

    diff = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"{path} (current)",
            tofile=f"{path} (after apply)",
        )
    )

    if not write:
        sys.stdout.writelines(diff)
        print(
            f"\nDRY RUN — {path} not modified. Re-run with --write to apply {len(ids)} rule set(s)."
        )
        return

    _write_atomic(path, updated)
    digest = hashlib.sha256(block.encode()).hexdigest()[:16]
    verb = "replaced managed block in" if START in original else "added managed block to"
    print(f"Applied {len(ids)} rule set(s) — {verb} {path}")
    print(f"backup: {path}.chatsee.bak   block sha256: {digest}")
    print(f"failure_memory_ids: {ids}")
    _record(path, ids, mode, digest, confirmed=False)

    if confirm and ids:
        resp = g.apply_remediations(
            ids, f"applied to {os.path.basename(path)} via apply_to_prompt.py"
        )
        _record(path, ids, mode, digest, confirmed=True)
        print(f"Confirmed with Guardian: {json.dumps(resp)[:300]}")
    elif rules_file:
        print("(not confirmed — call the apply_remediations tool with the ids above to close the loop)")
    else:
        print("(not confirmed — re-run with --confirm to mark these applied on the Guardian)")


if __name__ == "__main__":
    try:
        main()
    except (ApplyError, g.GuardianError) as e:
        sys.exit(f"error: {e}")
