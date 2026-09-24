"""The real Recuris-adapted arm — pinned per the design's test plan.

The crux (memory→behavior), three ways:
1. injection changes prompts (the card physically enters the metered
   prompt on matching stages and is logged as delivered);
2. injection changes WORKER BEHAVIOR end-to-end (a memory-section-aware
   responder flips a graded decision);
3. the neutral package matches the baseline's decisions (the memory-
   aware policy smuggles in no improvement — this licenses the
   S0-matched control).

The gate: strict repair / tie reject / regression reject / fingerprint
reject / new-error reject. The plan validator: menu, evidence citation,
capability disclosure, ledger, edit_card — and NO content screen on
card bodies (the dev/eval split, not eval-answer token filtering, is
the leak defense). Meta-agent failure admits nothing. Wiring: the
improver's rounds + package carry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.recuris_memory_policy import recuris_memory_policy_text
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.tools import ToolBudget
from rsicontext.participant.recuris_real_arm import (
    PlanBounce,
    RecurisAdaptedImprover,
    apply_patch,
    build_trace_doc,
    package_to_state,
    run_gate,
    validate_plan,
)

from r2a_compare import _offline_responder, _run_arm


from rsicontext.participant.recuris_real_arm import R2B_NEUTRAL_SEED

#: One seed, one place: the tests consume the canonical r2b seed (the
#: wiring audit's dedup finding — a drifting test-local copy would
#: silently diverge from the arm's).
NEUTRAL = json.loads(json.dumps(R2B_NEUTRAL_SEED))


def _card(card_id: str, body: str, stage: str = "*") -> dict:
    return {"id": card_id, "body": body, "stage": stage, "requires_field": None}


def _with_card(body: str, stage: str = "*") -> dict:
    pkg = json.loads(json.dumps(NEUTRAL))
    pkg["entries"] = [_card("test-card", body, stage)]
    return pkg


# --- 1-3: the memory→behavior path --------------------------------------


def test_memory_injection_changes_prompts() -> None:
    inst = build_research_v4_dossier()
    run_plain = _run_arm(
        recuris_memory_policy_text(),
        inst,
        _offline_responder,
        initial_state=package_to_state(NEUTRAL),
    )
    run_with = _run_arm(
        recuris_memory_policy_text(),
        inst,
        _offline_responder,
        initial_state=package_to_state(_with_card("cite the exception clause before awarding")),
    )
    # Delivered on matching stages (act_verify/follow_up), logged.
    state = run_with["final_state"]
    delivered = state.get("memory_delivered") or []
    stages_delivered = {log[0] for log in delivered if isinstance(log, list)}
    assert "act_verify" in stages_delivered and "follow_up" in stages_delivered
    # The card body PHYSICALLY entered the metered prompts.
    heads = " ".join(str(call.get("prompt_head", "")) for call in run_with["model_transcript"])
    assert "Prior-failure memory" in heads
    assert "cite the exception clause" in heads
    # And NOT in the neutral run.
    heads_plain = " ".join(
        str(call.get("prompt_head", "")) for call in run_plain["model_transcript"]
    )
    assert "Prior-failure memory" not in heads_plain


def test_memory_changes_worker_behavior_end_to_end() -> None:
    # A responder whose award answer depends on the memory section: with
    # the card delivered, it answers atlas-carriage (pass); without, it
    # answers pinnacle-courier (fail the gate). Prompt -> reply ->
    # action -> env-graded outcome: the whole chain.
    def memory_aware_responder(prompt: str) -> str:
        lowered = prompt.lower()
        if "name the one supplier" in lowered:
            if "prior-failure memory" in lowered:
                return "supplier=atlas-carriage"
            return "supplier=pinnacle-courier"
        return _offline_responder(prompt)

    inst = build_research_v4_dossier()
    run_with = _run_arm(
        recuris_memory_policy_text(),
        inst,
        memory_aware_responder,
        initial_state=package_to_state(_with_card("prefer the bonded-corridor carrier")),
    )
    run_without = _run_arm(
        recuris_memory_policy_text(),
        inst,
        memory_aware_responder,
        initial_state=package_to_state(NEUTRAL),
    )
    assert run_with["decisions"]["award"] is True
    assert run_without["decisions"]["award"] is False


def test_neutral_package_matches_baseline_decisions() -> None:
    inst = build_research_v4_dossier()
    from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text

    run_memory = _run_arm(
        recuris_memory_policy_text(),
        inst,
        _offline_responder,
        initial_state=package_to_state(NEUTRAL),
    )
    run_base = _run_arm(strong_model_fixed_policy_text(), inst, _offline_responder)
    assert run_memory["decisions"] == run_base["decisions"]


# --- 4-7: the gate --------------------------------------------------------


def _run(decisions: dict, errors: list | None = None, delivered: list | None = None) -> dict:
    return {
        "decisions": decisions,
        "policy_errors": errors or [],
        "final_state": {"memory_delivered": delivered or []},
    }


def test_gate_accepts_strict_repair() -> None:
    inc = _run({"award": False, "followup_1": False, "followup_2": True})
    cand = _run(
        {"award": True, "followup_1": False, "followup_2": True},
        delivered=[["act_verify", "test-card"]],
    )
    patch = {"action": "add_card", "target": "test-card"}
    accepted, reason, gate = run_gate(inc, cand, patch)
    assert accepted, reason
    assert "strict repair" in reason


def test_gate_rejects_tie() -> None:
    inc = _run({"award": False, "followup_1": False, "followup_2": True})
    cand = _run({"award": False, "followup_1": False, "followup_2": True})
    accepted, reason, _ = run_gate(inc, cand, {"action": "add_card", "target": "x"})
    assert not accepted and "tie-or-worse" in reason


def test_gate_rejects_regression() -> None:
    # Fixes fu1 AND award, breaks followup_2: net +1 but regressed.
    inc = _run({"award": False, "followup_1": False, "followup_2": True})
    cand = _run({"award": True, "followup_1": True, "followup_2": False})
    accepted, reason, _ = run_gate(inc, cand, {"action": "add_card", "target": "x"})
    assert not accepted and "regression" in reason


def test_gate_rejects_unfired_card() -> None:
    # Score improved but the patched card never delivered.
    inc = _run({"award": False, "followup_1": False, "followup_2": True})
    cand = _run({"award": True, "followup_1": False, "followup_2": True}, delivered=[])
    accepted, reason, _ = run_gate(inc, cand, {"action": "add_card", "target": "test-card"})
    assert not accepted and "fingerprint" in reason


def test_gate_rejects_new_policy_errors() -> None:
    inc = _run({"award": False, "followup_1": False, "followup_2": True}, errors=["old"])
    cand = _run(
        {"award": True, "followup_1": False, "followup_2": True},
        errors=["old", "new"],
        delivered=[["act_verify", "test-card"]],
    )
    accepted, reason, _ = run_gate(inc, cand, {"action": "add_card", "target": "test-card"})
    assert not accepted and "new policy errors" in reason


# --- 8-10: the plan validator ---------------------------------------------


def _trace(failed: list[str]) -> dict:
    # `failed` names the decisions that FAILED (everything else passed).
    return {
        "decisions": {
            "award": "award" not in failed,
            "followup_1": "followup_1" not in failed,
            "followup_2": "followup_2" not in failed,
        },
        "failures": [f"follow_up: {d}" for d in failed],
    }


def _plan(
    action: str = "add_card",
    target: str = "c1",
    body: str = "hint text",
    field=None,
    evidence=("award",),
):
    card = {"body": body, "stage": "*", "requires_field": field}
    return {
        "clusters": [
            {
                "component": "E",
                "action": action,
                "target": target,
                "card": card,
                "evidence": list(evidence),
            }
        ]
    }


def test_plan_validator_bounces() -> None:
    pkg = json.loads(json.dumps(NEUTRAL))
    disclosure = {"state_fields": ("notes", "constraint_reply")}

    # Wrong component/action pair.
    with pytest_wrap(PlanBounce, "menu"):
        validate_plan(_plan(action="set_max_cards"), _trace(["award"]), pkg, set(), disclosure)
    # Evidence must cite a failed decision.
    with pytest_wrap(PlanBounce, "failed"):
        validate_plan(_plan(evidence=("followup_2",)), _trace(["award"]), pkg, set(), disclosure)
    # Capability disclosure: untracked state field.
    with pytest_wrap(PlanBounce, "disclosure"):
        validate_plan(_plan(field="not_tracked"), _trace(["award"]), pkg, set(), disclosure)
    # Ledger: repeat.
    with pytest_wrap(PlanBounce, "ledger"):
        validate_plan(
            _plan(),
            _trace(["award"]),
            pkg,
            {("E", "add_card", "c1")},
            disclosure,
        )
    # No leak screen (review 892f1d0 M1): a card body carrying the
    # mirror variant's words is NOT bounced — those words are dev-world
    # material for the B-group, and filtering candidate bodies against
    # eval-answer tokens would leak eval facts into the improvement
    # loop. The dev/eval split is the defense.
    cluster = validate_plan(
        _plan(body="prefer harborline-freight"), _trace(["award"]), pkg, set(), disclosure
    )
    assert cluster["target"] == "c1"
    # add_card on an existing id.
    pkg2 = json.loads(json.dumps(NEUTRAL))
    pkg2["entries"] = [_card("c1", "x")]
    with pytest_wrap(PlanBounce, "already exists"):
        validate_plan(_plan(), _trace(["award"]), pkg2, set(), disclosure)
    # edit_card on a missing id.
    with pytest_wrap(PlanBounce, "does not exist"):
        validate_plan(_plan(action="edit_card"), _trace(["award"]), pkg, set(), disclosure)
    # And a GOOD plan passes.
    cluster = validate_plan(_plan(), _trace(["award"]), pkg, set(), disclosure)
    assert cluster["target"] == "c1"


def test_edit_card_action() -> None:
    pkg = json.loads(json.dumps(NEUTRAL))
    pkg["entries"] = [_card("c1", "old body")]
    plan = _plan(action="edit_card", target="c1", body="revised body")
    patched = apply_patch(
        pkg, validate_plan(plan, _trace(["award"]), pkg, set(), {"state_fields": ()})
    )
    assert patched["entries"][0]["body"] == "revised body"
    # The do-not-repeat ledger blocks add on the same target but the
    # edit is a different key.
    with pytest_wrap(PlanBounce, "ledger"):
        validate_plan(
            _plan(), _trace(["award"]), pkg, {("E", "add_card", "c1")}, {"state_fields": ()}
        )
    cluster = validate_plan(
        plan, _trace(["award"]), pkg, {("E", "add_card", "c1")}, {"state_fields": ()}
    )
    assert cluster["action"] == "edit_card"


# --- 10-13: meta-agent failure + wiring -----------------------------------


def test_meta_agent_failure_admits_nothing() -> None:
    def boom(prompt: str) -> str:
        raise RuntimeError("endpoint down")

    def dev_runner(package: dict) -> dict:
        return _run_arm(
            recuris_memory_policy_text(),
            build_research_v4_dossier(),
            _offline_responder,
            initial_state=package_to_state(package),
        )

    improver = RecurisAdaptedImprover(meta_agent=boom, dev_runner=dev_runner, rounds=1)
    final, record = improver.improve(json.loads(json.dumps(NEUTRAL)))
    assert final == NEUTRAL, "a failed meta-agent admits nothing"
    assert record["rounds"][0]["outcome"].startswith("failed: meta-agent")
    assert record["final_package_digest"] == record["rounds"][0]["package_digest_before"]


def test_offline_improver_end_to_end_accepts_a_repair() -> None:
    # A responder that fails the award UNLESS the memory card is
    # delivered (the memory-section dependency from test 2); the stub
    # meta-agent proposes the card; the gate must accept it.
    def memory_aware_responder(prompt: str) -> str:
        lowered = prompt.lower()
        if "name the one supplier" in lowered:
            if "prior-failure memory" in lowered:
                return "supplier=atlas-carriage"
            return "supplier=pinnacle-courier"
        return _offline_responder(prompt)

    def dev_runner(package: dict) -> dict:
        return _run_arm(
            recuris_memory_policy_text(),
            build_research_v4_dossier(),
            memory_aware_responder,
            initial_state=package_to_state(package),
        )

    def stub_meta_agent(prompt: str) -> str:
        return json.dumps(
            {
                "clusters": [
                    {
                        "component": "E",
                        "action": "add_card",
                        "target": "repair-award",
                        "card": {
                            "body": "cite the exception clause before awarding",
                            "stage": "act_verify",
                            "requires_field": None,
                        },
                        "evidence": ["award"],
                    }
                ]
            }
        )

    improver = RecurisAdaptedImprover(meta_agent=stub_meta_agent, dev_runner=dev_runner, rounds=1)
    final, record = improver.improve(json.loads(json.dumps(NEUTRAL)))
    assert record["rounds"][0]["outcome"].startswith("accepted"), record["rounds"][0]
    assert any(str(e.get("id")) == "repair-award" for e in final["entries"])
    # The card actually delivers in the accepted run (fingerprint evidence).
    gate = record["rounds"][0]["gate"]
    assert "repair-award" in gate.get("fingerprint_delivered_ids", [])


def test_state_survives_all_stages() -> None:
    inst = build_research_v4_dossier()
    pkg = _with_card("stable memory")
    run = _run_arm(
        recuris_memory_policy_text(),
        inst,
        _offline_responder,
        initial_state=package_to_state(pkg),
    )
    # The memory key survived every stage (the frozen policy never
    # writes it; memory_writes merge never clobbers it).
    state = run["final_state"]
    assert isinstance(state.get("recuris_memory"), dict)
    assert state["recuris_memory"]["entries"][0]["body"] == "stable memory"


class pytest_wrap:
    """Minimal pytest.raises shim so the file has one import path."""

    def __init__(self, exc_type, needle: str):
        self.exc_type = exc_type
        self.needle = needle

    def __enter__(self):
        import pytest

        self._ctx = pytest.raises(self.exc_type)
        return self._ctx.__enter__()

    def __exit__(self, *args):
        outcome = self._ctx.__exit__(*args)
        if args[0] is not None:
            message = str(args[1])
            assert self.needle in message, f"expected {self.needle!r} in {message!r}"
        return outcome


def test_citation_accepts_failure_strings_not_just_decision_names() -> None:
    # The live-v2 finding: the trace's failure strings use stage ids
    # ('commit gate[s5-act-verify]: plan ... not in the legal set'),
    # never the literal word 'award' — a meta-agent citing the CORRECT
    # failure by its string was wrongly bounced. Citation by either the
    # decision name OR the decision's failure string must pass.
    import pytest

    trace = {
        "decisions": {"award": False, "followup_1": True, "followup_2": False},
        "failures": [
            "commit gate[s5-act-verify]: commit gate: plan 'vesper-instruments' is not in the legal set",
            "follow_up[s8-followup-2]: record 'followup_conclusion-corridor': field 'status' expected 'reverify', got 'current'",
        ],
    }
    plan_by_string = _plan(
        evidence=(
            "commit gate[s5-act-verify]: commit gate: plan 'vesper-instruments' is not in the legal set",
        )
    )
    cluster = validate_plan(plan_by_string, trace, NEUTRAL, set(), {"state_fields": ()})
    assert cluster["action"] == "add_card"
    # The name form still passes too.
    cluster2 = validate_plan(
        _plan(evidence=("award",)), trace, NEUTRAL, set(), {"state_fields": ()}
    )
    assert cluster2["target"] == "c1"
    # And citing a PASSING decision by name still bounces.
    with pytest.raises(PlanBounce):
        validate_plan(_plan(evidence=("followup_1",)), trace, NEUTRAL, set(), {"state_fields": ()})
