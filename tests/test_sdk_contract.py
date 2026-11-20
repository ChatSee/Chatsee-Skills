"""Pin the parts of the third-party `chatsee-ai` SDK that our docs make claims about.

Skill 1 tells a developer to write code against `ChatseeTracker`, and several of our
documents state things about it as fact: which arguments it takes, that `verify_ssl`
defaults to `False`, that the portal's snippet cannot work. Those are claims about a
package **we do not control**, and it changes.

It already caught us out once. `user_id` was rejected by `0.10.0` and is accepted by
`0.12.1`, so a note written against the older version read as sloppy when checked against
the newer one — and a wrong detail in a bug report gets the correct details discounted with it.

So these are not tests of our code. They are a tripwire: if the SDK's shape no longer
matches what we tell people, a test goes red instead of a document quietly going stale.
When one fails, fix the DOC first, then decide whether the skill needs to change.

⚠️ **These fire at UPGRADE time, not at release time.** `requirements.txt` pins an exact
version, so the suite keeps passing however many versions ChatSee publishes — it only
speaks up when someone moves the pin. That is deliberate (network-free tests, reproducible
runs), but it means it does not answer "is there a newer SDK?". Nothing here does. Skill 1
tells customers `pip install chatsee-ai` **unpinned**, so they get latest while we test the
pin; the gap is closed by stamping our version-specific claims with the version they were
checked against, not by this file. Check PyPI by hand when a claim starts to matter.

    ./.venv/bin/python -m pytest tests/ -q
"""

import inspect

import pytest

chatsee = pytest.importorskip("chatsee", reason="chatsee-ai is only needed by skill 1")
ChatseeTracker = chatsee.ChatseeTracker


def _init_params():
    return inspect.signature(ChatseeTracker.__init__).parameters


# ---- what our own instrumentation depends on --------------------------------


def test_identity_args_are_the_only_required_ones():
    """Keyless auth: agent_id + tenant_id, and nothing else without a default.

    `telemetry-setup/SKILL.md` states this. If the SDK ever adds a
    required argument, every instrumented agent breaks at construction.
    """
    required = [
        n for n, p in _init_params().items() if n != "self" and p.default is inspect.Parameter.empty
    ]
    assert required == ["agent_id", "tenant_id"], required


@pytest.mark.parametrize("arg", ["api_base_url", "verify_ssl", "session_id"])
def test_args_our_asset_passes_still_exist(arg):
    """`assets/instrumented_agent.py` is copied into customer agents. These must resolve."""
    assert arg in _init_params()


def test_verify_ssl_still_defaults_to_false():
    """The security warning in `telemetry-setup/SKILL.md` depends on this being True.

    If the SDK ever flips the default, that warning becomes wrong and should be softened
    rather than left shouting about a fixed problem.
    """
    assert _init_params()["verify_ssl"].default is False


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("start_turn", ["user_message", "system_prompt", "metadata"]),
        ("log_tool_call", ["tool_name", "arguments", "result"]),
        ("end_turn", ["bot_message"]),
        ("log_exception", ["exception"]),
    ],
)
def test_turn_methods_keep_the_arguments_we_document(method, args):
    """The four calls skill 1 installs into a customer's turn loop."""
    fn = getattr(ChatseeTracker, method, None)
    assert fn is not None, f"{method} disappeared from the SDK"
    params = inspect.signature(fn).parameters
    for a in args:
        assert a in params, f"{method}() lost {a!r}"


# ---- what we assert about the PORTAL's broken snippet ------------------------


@pytest.mark.parametrize("arg", ["tenant_name", "api_key"])
def test_portal_snippet_args_are_still_rejected(arg):
    """The bug we reported upstream.

    These two are what actually raise. If the SDK ever adds them, the report is obsolete
    and the PR should be closed rather than left arguing for a fix nobody needs.
    """
    assert arg not in _init_params()


def test_user_id_is_accepted_and_must_not_be_cited_as_the_failure():
    """The detail that made the original report look wrong.

    `user_id` is a real parameter now. Cite `tenant_name`/`api_key` as the fatal pair —
    a reviewer who tests `user_id`, sees it work, and concludes the report is careless is
    the failure mode this pins.
    """
    assert "user_id" in _init_params()
