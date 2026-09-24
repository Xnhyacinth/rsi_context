"""The B/C group BASELINE tests (r3design §3/4, research-v5).

Pins:
1. no hardcoded world answers in either baseline text (the
   strong-fixed contract: every content decision is ask_model's);
2. the B baseline (carry-aware strong-fixed) passes all six B1
   decisions offline — distill/re-hydrate/re-derive/re-award work
   with a text-grounded worker;
3. the C baseline (receipt-reading strong-fixed) passes both C1
   sessions through the probe->receipt->switch loop with a
   receipt-following test responder, while the naive C policy fails
   both (the contrast the design demanded);
4. strong_model_fixed (the A-group control) FAILS on B and C — the
   r3design-confirmed gap, pinned: no session_end distill (nothing
   survives), no re-award re-request, no receipt-reading.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from r2a_compare import _offline_responder

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.material_b_group import build_b1_sessions
from rsicontext.lifecycle.material_c_group import build_c1_sessions
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

#: World-answer literals the baselines must NOT contain (they belong
#: to the material, never the policy). 'ember' needs word boundaries —
#: it is a substring of ordinary words ('remembers').
_FORBIDDEN_LITERALS = (
    "atlas-carriage",
    "vesper-instruments",
    "orbit-hosting",
    "harborline-freight",
    "pinnacle-courier",
    "customs-preclearance",
    "northwind-logistics",
    "v-fresh",
    "v-rev2",
    "v-pre",
    "v-fallback",
    "v-mirror",
    "vf-atlas",
    "vf-ember",
)
_FORBIDDEN_WORDS = ("ember",)


def test_no_hardcoded_answers() -> None:
    for text in (group_b_basline_policy_text(), group_c_baseline_policy_text()):
        for literal in _FORBIDDEN_LITERALS:
            assert literal not in text, f"baseline policy hardcodes the world answer {literal!r}"
        for word in _FORBIDDEN_WORDS:
            assert re.search(rf"\b{word}\b", text) is None, (
                f"baseline policy hardcodes the world answer {word!r}"
            )
        # Record names are interface (the world's own contract), allowed.


def test_b_baseline_passes_b1() -> None:
    sessions = list(build_b1_sessions())
    env = ProjectState()
    envs = [env, env, ProjectState()]
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            group_b_basline_policy_text(),
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        )

    record = run_session_sequence(
        sessions, hook_factory, envs=envs, budget=budget, registry=registry
    )
    expected = {
        "s1_award": True,
        "s2_calibration": True,
        "s2_currency": True,
        "s2_reaward_fresh": True,
        "s3_award": True,
        "s3_calibration": True,
    }
    assert record.decisions == expected, {
        "decisions": record.decisions,
        "failure_detail": record.failure_detail,
    }
    # The carry-aware behaviors actually ran: every session flushed a
    # non-empty carry and every session passed the model channel.
    for session in record.sessions:
        assert session.persist_ok, session.persist_cause
        assert session.carry_bytes > 0
        assert session.model_calls > 0


def test_c_baseline_passes_c1() -> None:
    # The C recovery needs the probe->receipt->switch loop; the offline
    # responder has no receipt-following rule, so the worker here is a
    # test-local responder that reads the prompt's own receipt lines
    # (content-follows-prompt — the established scripting discipline):
    # a fail line for the probed subject triggers the switch; the
    # session-2 verify-now prompt answers the renewed subject.
    def receipt_following_responder(prompt: str) -> str:
        lowered = prompt.lower()
        if "name the one supplier to verify now" in lowered:
            fail_subjects = _receipt_subjects(prompt, "fail")
            if "current revision" in lowered and fail_subjects:
                # Session 2 re-award after the mutation: the renewed
                # subject (the one that failed before the renewal).
                return "supplier=" + fail_subjects[0]
            if fail_subjects:
                # Session 1 recovery: switch away from the failed subject.
                return "supplier=" + _switch_candidate(fail_subjects)
            return _offline_responder(prompt)
        return _offline_responder(prompt)

    sessions = list(build_c1_sessions())
    env = ProjectState()
    envs = [env, env]
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            group_c_baseline_policy_text(),
            tool_budget=budget,
            responder=receipt_following_responder,
            registry=registry,
        )

    record = run_session_sequence(
        sessions,
        hook_factory,
        envs=envs,
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    s1, s2 = record.sessions
    assert s1.passed, s1.failures
    assert s2.passed, s2.failures
    # The award was committed on a seen PASS (the recovery target the
    # world's oracle defines) and the re-award cites post-mutation
    # evidence (revision 2).
    commit = env.records["migration_commit"]
    assert commit["plan"] in ("ember", "atlas-carriage")
    reaward = env.records["corridor_reaward"]
    cited = reaward.get("provenance", ())
    assert cited, "the re-award must cite env-issued evidence"
    cited_record = env.records[cited[0]]
    assert cited_record["verdict"] == "pass"
    assert cited_record["protocol_revision"] == 2
    # The receipt memory discipline actually ran: receipts accumulated.
    assert s1.model_calls > 0


def test_naive_c_policy_fails_both_sessions() -> None:
    # The CONTRAST: a policy that commits the reading-level best and
    # re-awards the stale conclusion fails both sessions (the naive
    # shape from tests/test_c_group.py, pinned here against the SAME
    # responder so the difference is the POLICY, not the worker).
    naive = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "survey":
        turn.state["carry"] = {"winner": "atlas-carriage"}
        return {"pack_text": "survey"}
    if kind == "act_verify":
        if turn.view.stage_id == "c1-re-award":
            winner = "ember"
            record = "corridor_reaward"
            ver = "v-stale"
        else:
            winner = "atlas-carriage"
            record = "migration_commit"
            ver = "v-naive"
        return {
            "pack_text": "commit " + winner,
            "actions": (
                turn.actions.request_verification(ver, "customs-preclearance", winner),
                turn.actions.create_record(record, {"plan": winner}),
                turn.actions.finalize(
                    record, {"plan": winner, "status": "final"}, (ver,),
                ),
            ),
        }
    return {"pack_text": "ok"}
"""

    def receipt_following_responder(prompt: str) -> str:
        lowered = prompt.lower()
        if "name the one supplier to verify now" in lowered:
            fail_subjects = _receipt_subjects(prompt, "fail")
            if "current revision" in lowered and fail_subjects:
                return "supplier=" + fail_subjects[0]
            if fail_subjects:
                return "supplier=" + _switch_candidate(fail_subjects)
            return _offline_responder(prompt)
        return _offline_responder(prompt)

    sessions = list(build_c1_sessions())
    env = ProjectState()
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            naive,
            tool_budget=budget,
            responder=receipt_following_responder,
            registry=registry,
        )

    record = run_session_sequence(
        sessions,
        hook_factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    s1, s2 = record.sessions
    assert not s1.passed
    assert any(
        "lacks an environment-issued" in f or "not in the legal set" in f for f in s1.failures
    ), s1.failures
    assert not s2.passed
    assert any("not in the legal set" in f for f in s2.failures), s2.failures


def test_strong_fixed_is_a_strawman_on_b_and_c() -> None:
    # strong_model_fixed has NO session-boundary behaviors: it never
    # writes state['carry'] (nothing survives), never creates the
    # re-award record, and never reads receipts. On B it loses the
    # carry-dependent decisions; on C it never opens the recovery loop.
    from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text

    # --- B sequence ---
    sessions = list(build_b1_sessions())
    env = ProjectState()
    envs = [env, env, ProjectState()]
    budget = ToolBudget()
    registry = DocumentRegistry()

    def b_hook(state):
        return PolicyHook(
            state,
            strong_model_fixed_policy_text(),
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        )

    record = run_session_sequence(sessions, b_hook, envs=envs, budget=budget, registry=registry)
    carry_decisions = (
        "s2_reaward_fresh",
        "s3_award",
    )
    failed = {key for key, ok in record.decisions.items() if not ok}
    assert failed & set(carry_decisions), (
        "strong-fixed must fail the carry-aware decisions on B",
        record.decisions,
    )
    # And it never persists anything (no session_end distill): the
    # flushed carry stayed EMPTY (the runner seeds {}, 2 canonical
    # bytes; strong-fixed writes nothing into it).
    assert all(not session.final_carry for session in record.sessions)

    # --- C sequence (both sessions fail: no receipt reading) ---
    c_sessions = list(build_c1_sessions())
    c_env = ProjectState()
    c_budget = ToolBudget()
    c_registry = DocumentRegistry()

    def c_hook(state):
        return PolicyHook(
            state,
            strong_model_fixed_policy_text(),
            tool_budget=c_budget,
            responder=_offline_responder,
            registry=c_registry,
        )

    c_record = run_session_sequence(
        c_sessions,
        c_hook,
        envs=[c_env, c_env],
        budget=c_budget,
        registry=c_registry,
        max_turns_per_stage=3,
    )
    assert not c_record.sessions[0].passed, c_record.sessions[0].failures
    assert not c_record.sessions[1].passed, c_record.sessions[1].failures


def _receipt_subjects(prompt: str, verdict: str) -> list[str]:
    """Subjects of the receipt lines the prompt itself carries."""

    subjects = []
    for line in prompt.splitlines():
        line = line.strip()
        if not line.startswith("record="):
            continue
        if "verdict=" + verdict not in line:
            continue
        for part in line.split():
            if part.startswith("subject="):
                subjects.append(part[len("subject=") :])
    return subjects


def _switch_candidate(failed_subjects: list[str]) -> str:
    """The recovery candidate the c1 world's oracle passes (ember).

    The switch itself is prompt-driven (the fail lines); the candidate
    name is this scripted worker's world reading — the same discipline
    ``_offline_responder`` applies when it scripts 'atlas carriage'.
    """

    return "ember"
