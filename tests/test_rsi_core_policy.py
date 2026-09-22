"""RSI core v1 — the policy surface and the strong-fixed baseline, pinned.

The gap analysis found the strategy surface was four config knobs whose
combined reachable difference is one boolean, and the fixed control was
designed to lose. These tests pin the v2 surface: an executable
``on_turn`` policy over observations and tools, running under a
restricted namespace, with the STRONG-FIXED baseline (competent, static)
as the honest control.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.material_v3_variant import build_research_v3_variant
from rsicontext.lifecycle.policy import (
    PolicyBoundaryError,
    PolicyHook,
    load_policy,
    scan_policy,
)
from rsicontext.lifecycle.tools import ToolBudget
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.strong_fixed_policy import strong_fixed_policy_text


def _run_policy(policy_text: str, inst) -> tuple:
    env = ProjectState()
    budget = ToolBudget()
    hook = PolicyHook({}, policy_text, tool_budget=budget)
    hook.bind_env(env)
    record = run_lifecycle(inst, hook, env)
    return record, hook, budget


def test_strong_fixed_passes_the_main_world() -> None:
    record, hook, budget = _run_policy(strong_fixed_policy_text(), build_research_v3_instance())
    assert record.final_check.passed, record.final_check.failures
    assert hook.policy_errors == []


def test_strong_fixed_is_world_generic() -> None:
    for spec_id in ("orinoco", "parana"):
        record, hook, _ = _run_policy(
            strong_fixed_policy_text(), build_research_v3_variant(spec_id)
        )
        assert record.final_check.passed, (spec_id, record.final_check.failures)
        assert hook.policy_errors == []


def test_policy_boundary_scans_forbidden_capabilities() -> None:
    for bad in (
        "import os\n",
        "open('/etc/passwd')\n",
        "import subprocess\n",
        "x = __import__('sys')\n",
    ):
        with pytest.raises(PolicyBoundaryError):
            scan_policy(bad)


def test_policy_load_rejects_missing_on_turn() -> None:
    with pytest.raises(PolicyBoundaryError):
        load_policy("x = 1\n")


def test_policy_runtime_error_is_named_not_silent() -> None:
    # ZeroDivisionError is interpreter-raised (policies cannot name
    # exception classes — restricted builtins).
    bad_policy = "def on_turn(turn):\n    return 1 / 0\n"
    record, hook, _ = _run_policy(bad_policy, build_research_v3_instance())
    assert not record.final_check.passed
    assert any("on_turn raised ZeroDivisionError" in e for e in hook.policy_errors)


def test_policy_receives_receipts_and_can_react() -> None:
    """The closed loop, end to end: a policy that reads its receipts."""

    policy = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "survey":
        turn.state["log"] = []
        checks = [c for c in ("replica-lag", "online-cutover") if c in turn.documents_text]
        acts = tuple(
            turn.actions.request_verification(f"probe-{i}", c, "aurora")
            for i, c in enumerate(checks)
        )
        return {"pack_text": "survey", "actions": acts}
    if kind != "act_verify":
        seen = turn.state.get("log", [])
        seen.append(len(turn.receipts))
        turn.state["log"] = seen
    return {"pack_text": "ok"}
"""
    record, hook, _ = _run_policy(policy, build_research_v3_instance())
    # The survey stage's verification receipts arrived at the constraint
    # stage — the policy SAW its own consequences.
    assert hook.state["log"][0] >= 2
    assert record.final_check is not None


def test_policy_tools_are_metered() -> None:
    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        r = turn.tools.reread("doc-cand-a")
        turn.state["reread_ok"] = r.ok
    return {"pack_text": "ok"}
"""
    record, hook, budget = _run_policy(policy, build_research_v3_instance())
    assert hook.state["reread_ok"] is True
    assert budget.calls == 1 and budget.tokens_in > 0
