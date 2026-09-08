"""Tests for skill 2's splice/parse logic — the two pure functions that can destroy a
user's prompt file. No network: these exercise local behaviour only.

    ./.venv/bin/python -m pytest tests/ -q
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "remediation", "scripts")
    ),
)
import apply_to_prompt as a

BLOCK = f"{a.START}\nRULES\n{a.END}"


# ---- _splice ---------------------------------------------------------------


def test_appends_when_no_markers():
    out = a._splice("You are helpful.\n", BLOCK)
    assert out.startswith("You are helpful.")
    assert BLOCK in out


def test_replaces_in_place_and_is_idempotent():
    once = a._splice("HEAD\n", BLOCK)
    twice = a._splice(once, BLOCK)
    assert once == twice, "re-applying must replace the managed block, not duplicate it"
    assert twice.count(a.START) == 1


def test_preserves_text_on_both_sides_of_the_block():
    original = f"BEFORE\n{a.START}\nold\n{a.END}\nAFTER\n"
    out = a._splice(original, BLOCK)
    assert "BEFORE" in out and "AFTER" in out
    assert "old" not in out


def test_orphan_start_marker_raises_instead_of_deleting_content():
    """Regression: an unbalanced marker used to append a second block, and the NEXT run
    then permanently deleted everything between the two starts."""
    original = f"KEEP THIS LINE\n{a.START}\ndangling\n"
    with pytest.raises(a.ApplyError, match="unbalanced"):
        a._splice(original, BLOCK)


def test_duplicate_markers_raise():
    original = f"{a.START}\nx\n{a.END}\n{a.START}\ny\n{a.END}\n"
    with pytest.raises(a.ApplyError, match="expected at most one"):
        a._splice(original, BLOCK)


# ---- _parse ----------------------------------------------------------------


def test_flags_before_positional():
    assert a._parse(["--mode", "all", "f.md"]) == ("f.md", "all", False, False, None)


def test_flags_after_positional():
    assert a._parse(["f.md", "--mode", "all", "--write"]) == ("f.md", "all", True, False, None)


def test_write_defaults_to_false_so_a_bare_run_is_a_dry_run():
    _path, _mode, write, confirm, _var = a._parse(["f.md"])
    assert (write, confirm) == (False, False)


def test_var_is_parsed_for_the_python_path():
    assert a._parse(["agent.py", "--var", "SYSTEM"])[4] == "SYSTEM"


def test_var_without_a_name_is_an_error():
    with pytest.raises(a.ApplyError, match="--var needs"):
        a._parse(["agent.py", "--var"])


def test_mode_defaults_to_all_not_pending():
    """Regression: defaulting to "pending" made the obvious sequence do nothing.

    Fetching a rule moves it Created -> Delivered, so merely LOOKING at the new rules leaves
    "pending" empty — and `apply_to_prompt.py f.md` then reported "nothing to apply" for an
    agent that had approved fixes waiting.
    """
    assert a._parse(["f.md"])[1] == "all"


def test_new_is_accepted_as_the_friendly_name_for_pending():
    # Our vocabulary is "new"; the server's wire value is still "pending".
    assert a._parse(["f.md", "--mode", "new"])[1] == "pending"


def test_unknown_mode_is_rejected():
    with pytest.raises(a.ApplyError, match="--mode"):
        a._parse(["f.md", "--mode", "everything"])


def test_unknown_flag_is_an_error_not_silently_ignored():
    """Regression: --dry-run was silently ignored, so it performed a REAL write."""
    with pytest.raises(a.ApplyError, match="unknown option"):
        a._parse(["--dry-run", "f.md"])


def test_invalid_mode_is_an_error_not_a_silent_downgrade():
    with pytest.raises(a.ApplyError, match="--mode"):
        a._parse(["f.md", "--mode", "bogus"])


def test_second_positional_is_an_error():
    with pytest.raises(a.ApplyError, match="extra argument"):
        a._parse(["a.md", "b.md"])


# ---- target safety ---------------------------------------------------------


def test_allows_prose_prompt_files():
    for path in ("PROMPT.md", "system_prompt.txt", "prompt", "/abs/path/PROMPT.MD"):
        a._check_target(path)  # must not raise


# ---- Python string-literal prompts -----------------------------------------

PY_SRC = '''import os

SYSTEM_PROMPT = """You are a support bot.

Be brief — customers are busy."""

def go():
    return SYSTEM_PROMPT
'''


def _py_block(body="RULES"):
    return f"{a.START}\n{body}\n{a.END}"


def test_splices_into_the_literal_not_the_file():
    out = a.splice_python(PY_SRC, _py_block())
    import ast

    ast.parse(out)  # the whole point: the file must still be valid Python
    _name, value, _s, _e = a.find_prompt_literal(out)
    assert a.START in value and "RULES" in value
    assert "def go():" in out  # nothing outside the literal was touched


def test_literal_splice_is_idempotent():
    once = a.splice_python(PY_SRC, _py_block())
    assert a.splice_python(once, _py_block()) == once


def test_replacing_rules_does_not_duplicate_the_block():
    once = a.splice_python(PY_SRC, _py_block("V1"))
    twice = a.splice_python(once, _py_block("V2"))
    assert twice.count(a.START) == 1
    assert "V1" not in twice and "V2" in twice


def test_non_ascii_prompt_is_not_mangled():
    """ast column offsets are UTF-8 BYTE offsets; treating them as characters misplaces the
    edit on any prompt containing a non-ASCII character."""
    _name, value, _s, _e = a.find_prompt_literal(a.splice_python(PY_SRC, _py_block()))
    assert "customers are busy" in value
    assert "—" in value


def test_refuses_a_computed_prompt():
    src = 'NAME = "bot"\nSYSTEM_PROMPT = f"You are {NAME}."\n'
    with pytest.raises(a.ApplyError, match="not a plain string literal"):
        a.find_prompt_literal(src)


def test_refuses_when_several_candidates_exist():
    src = 'SYSTEM_PROMPT = "a"\nINSTRUCTIONS = "b"\n'
    with pytest.raises(a.ApplyError, match="several candidate"):
        a.find_prompt_literal(src)


def test_var_disambiguates():
    src = 'SYSTEM_PROMPT = "a"\nINSTRUCTIONS = "b"\n'
    name, value, _s, _e = a.find_prompt_literal(src, var="INSTRUCTIONS")
    assert (name, value) == ("INSTRUCTIONS", "b")


def test_reports_when_no_prompt_variable_is_found():
    with pytest.raises(a.ApplyError, match="no module-level system-prompt"):
        a.find_prompt_literal("x = 1\n")


def test_python_is_no_longer_refused_outright():
    a._check_target("agent.py")  # must not raise — it has a real path now


def test_still_refuses_structured_config():
    for path in ("config.yaml", "prompts.json", "bot.ts"):
        with pytest.raises(a.ApplyError, match="corrupt"):
            a._check_target(path)


def test_unsupported_format_points_at_the_general_path():
    """A shape the shortcut cannot edit is not a dead end — it must name confirm_applied.py.

    The old message said "this script is the wrong door" and stopped, which reads as "your
    prompt is unsupported". It is not: Claude edits it and acknowledges separately.
    """
    with pytest.raises(a.ApplyError) as exc:
        a._check_target("config.yaml")
    msg = str(exc.value)
    assert "confirm_applied.py" in msg
    assert "shortcut" in msg.lower()
