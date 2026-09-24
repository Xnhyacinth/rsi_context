"""The dossier world's acceptance tests (R1, A-group main task).

Pins what makes the three long-axis commitments REAL rather than
labeled:
- solvability through TWO DISTINCT legal paths (remember vs re-read);
- the load-bearing ledger: removing card-03/17/05/08 breaks exactly the
  decisions they carry (a no-lie corpus where each decisive fact has
  exactly one source);
- the decoy trap (superficially strongest candidate fails the check);
- the long-memory trap (follow-up 2 fires only for the superseded
  check's evidence, not the unaffected one);
- horizon + grammar shape (8 stages, follow-ups after the commit).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v4_dossier import (
    build_research_v4_dossier,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.tools import ToolBudget

#: The memory-light path: retain almost nothing, re-read the registry at
#: every decision point (metered). A policy any participant could write.
REREAD_POLICY = """
import re

def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        state["corpus"] = {}
        for line in turn.documents_text.split("[[doc:"):
            if "]" in line:
                doc_id = line[: line.index("]")].strip()
                state["corpus"][doc_id] = line
        return {"pack_text": "survey skim"}
    if kind == "act_verify":
        # Re-read the two decisive cards (the registry allows it).
        card3 = turn.tools.reread("card-03")
        card17 = turn.tools.reread("card-17")
        plan = "atlas-carriage" if "bonded corridor" in card3.answer else "unknown"
        ver = turn.actions.request_verification("v1", "customs-preclearance", plan)
        return {
            "pack_text": "award",
            "actions": (
                turn.actions.request_verification("v1", "customs-preclearance", plan),
                turn.actions.create_record(
                    "candidate_status-atlas", {"plan": plan, "domain": "shipping"}
                ),
                turn.actions.create_record("migration_commit", {"plan": plan}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": plan, "status": "final"},
                    ("v1", "candidate_status-atlas"),
                ),
            ),
        }
    if kind == "follow_up":
        doc_text = turn.view.documents[0].text if turn.view.documents else ""
        if "calibration" in doc_text:
            card8 = turn.tools.reread("card-08")
            supplier = "vesper-instruments" if "northern service hub" in card8.answer else "unknown"
            return {
                "pack_text": "calibration",
                "actions": (
                    turn.actions.create_record(
                        "followup_conclusion-calibration", {"supplier": supplier}
                    ),
                ),
            }
        # followup 2: the customs-preclearance evidence was stamped at
        # revision 2; the final rule change (revision 3) superseded that
        # check -> the evidence is stale -> reverify.
        return {
            "pack_text": "corridor",
            "actions": (
                turn.actions.create_record(
                    "followup_conclusion-corridor", {"status": "reverify"}
                ),
            ),
        }
    return {"pack_text": "ok"}
"""

#: The remember path: retain compressed conclusions at stage 1 and never
#: re-read (zero tool calls) — it must carry the four load-bearing
#: details across 4+ stages.
REMEMBER_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        text = turn.documents_text
        state["plan"] = "atlas-carriage" if "bonded corridor" in text else "unknown"
        state["decoy_disqualified"] = "lapsed" in text
        state["calibration"] = (
            "vesper-instruments" if "northern service hub" in text else "unknown"
        )
        state["checks"] = ("customs-preclearance", "cold-chain-integrity")
        return {"pack_text": "survey notes"}
    if kind == "act_verify":
        plan = state.get("plan", "unknown")
        return {
            "pack_text": "award",
            "actions": (
                turn.actions.request_verification("v1", "customs-preclearance", plan),
                turn.actions.create_record(
                    "candidate_status-atlas", {"plan": plan, "domain": "shipping"}
                ),
                turn.actions.create_record("migration_commit", {"plan": plan}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": plan, "status": "final"},
                    ("v1", "candidate_status-atlas"),
                ),
            ),
        }
    if kind == "follow_up":
        doc_text = turn.view.documents[0].text if turn.view.documents else ""
        if "calibration" in doc_text:
            return {
                "pack_text": "calibration",
                "actions": (
                    turn.actions.create_record(
                        "followup_conclusion-calibration",
                        {"supplier": state.get("calibration", "unknown")},
                    ),
                ),
            }
        return {
            "pack_text": "corridor",
            "actions": (
                turn.actions.create_record(
                    "followup_conclusion-corridor", {"status": "reverify"}
                ),
            ),
        }
    return {"pack_text": "ok"}
"""


def _run(policy_text):
    env = ProjectState()
    budget = ToolBudget()
    hook = PolicyHook({}, policy_text, tool_budget=budget)
    hook.bind_env(env)
    record = run_lifecycle(build_research_v4_dossier(), hook, env, max_turns_per_stage=2)
    return record, hook, env, budget


def test_reread_path_solves_the_world() -> None:
    record, hook, env, budget = _run(REREAD_POLICY)
    assert record.final_check.passed, record.final_check.failures
    assert hook.policy_errors == []
    # The reread path actually PAID for its re-reads (metered).
    assert budget.calls >= 3


def test_remember_path_solves_with_zero_rereads() -> None:
    # R1.1: "zero reread calls" — the path re-reads NOTHING, but its
    # request_verification ACTIONS are billed through the unified
    # accounting (the old "zero tool calls" claim hid the free action
    # channel).
    record, hook, env, budget = _run(REMEMBER_POLICY)
    assert record.final_check.passed, record.final_check.failures
    assert budget.receipts == []  # no tool-path receipts at all
    assert budget.calls >= 1  # the action-path verifications are billed


def test_the_decoy_fails_the_check_not_just_the_gate() -> None:
    env = ProjectState()
    inst = build_research_v4_dossier()
    env.begin_instance(inst.stages[4].verification_oracle)
    from rsicontext.lifecycle.env import Action as _A

    env.submit(
        _A(
            kind="request_verification",
            record_id="v",
            fields={"check": "customs-preclearance", "subject": "pinnacle-courier"},
        )
    )
    assert env.records["v"]["verdict"] == "fail"
    assert env.records["v"]["protocol_revision"] == 1


def test_followup_2_fires_for_the_superseded_check_only() -> None:
    # The corridor conclusion asks for 'reverify' BECAUSE the final rule
    # change superseded customs-preclearance; the oracle keeps
    # cold-chain-integrity verifiable and passing (unaffected).
    env = ProjectState()
    inst = build_research_v4_dossier()
    env.begin_instance(inst.stages[4].verification_oracle)
    from rsicontext.lifecycle.env import Action as _A

    env.submit(
        _A(
            kind="request_verification",
            record_id="c",
            fields={"check": "cold-chain-integrity", "subject": "atlas-carriage"},
        )
    )
    assert env.records["c"]["verdict"] == "pass"


def test_grammar_is_longitudinal() -> None:
    inst = build_research_v4_dossier()
    kinds = [stage.kind for stage in inst.stages]
    assert kinds == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
        "follow_up",
        "rule_change",
        "follow_up",
    ]
    assert inst.axes.persistence_span_resets >= 6
    assert len(inst.stages[0].documents) == 22


def test_load_bearing_ledger() -> None:
    # R1.1 ledger v2: the four DECISIVE PROPOSITIONS each have exactly
    # one textual source (the no-lie constraint); the check names occur
    # in multiple places (protocol, constraint doc, follow-ups) — that
    # is the RULE's source distribution, not evidence duplication.
    inst = build_research_v4_dossier()
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    assert survey.count("bonded corridor") == 1  # card-03 only
    assert survey.count("northern service hub") == 1  # card-08 only
    assert survey.count("lapsed") == 1  # card-17 only
    # card-05's exemption clause: sole source (kept as FUTURE B-group
    # material — not current required evidence; see the task card).
    assert survey.count("mutual-aid annex") == 1


def test_removal_simulation_award_evidence() -> None:
    """Ledger v2 — EVIDENCE REMOVAL: deleting card-03 makes the award
    UNANSWERABLE BY MEMORY, while the env-verification path stays
    available (a participant can still request the check; it will
    verify subjects the oracle covers). Text is not the only legal
    route — the simulation says what information was lost, not that
    every correct system must have read the card."""

    import rsicontext.lifecycle.material_v4_dossier as dossier_mod

    stripped = tuple(s for s in dossier_mod._SUPPLIERS if s["id"] != "card-03")
    original = dossier_mod._SUPPLIERS
    original_gold = "card-03", "card-17", "card-05", "card-08"
    dossier_mod._SUPPLIERS = stripped
    try:
        inst = build_research_v4_dossier()
        # The remaining corpus no longer contains the winning
        # qualification — memory-based award selection lost its basis.
        survey = "\n".join(doc.text for doc in inst.stages[0].documents)
        assert "bonded corridor" not in survey
        # The gate itself is unchanged (the oracle still covers the
        # subject): the ENV path remains legal.
        precondition = inst.stages[4].commit_precondition
        assert precondition["legal_plans"] == ["atlas-carriage"]
    finally:
        dossier_mod._SUPPLIERS = original


def test_removal_simulation_calibration_evidence() -> None:
    """Ledger v2 — removing card-08 removes follow-up 1's ANSWER FACTS
    (the asked-about supplier's coverage); the follow-up expectation
    still names vesper-instruments (the proposition is now
    unanswerable from the corpus — exactly the explainable loss)."""

    import rsicontext.lifecycle.material_v4_dossier as dossier_mod

    stripped = tuple(s for s in dossier_mod._SUPPLIERS if s["id"] != "card-08")
    original = dossier_mod._SUPPLIERS
    dossier_mod._SUPPLIERS = stripped
    try:
        inst = build_research_v4_dossier()
        survey = "\n".join(doc.text for doc in inst.stages[0].documents)
        assert "northern service hub" not in survey
        assert (
            inst.stages[5].expected_state_delta["followup_conclusion-calibration"]["supplier"]
            == "vesper-instruments"
        )
    finally:
        dossier_mod._SUPPLIERS = original


def test_irrelevant_perturbation_leaves_decisions_stable() -> None:
    """Ledger v2 — IRRELEVANT PERTURBATION: growing the filler bulk
    changes nothing about the legal answers (decisions depend on the
    propositions, not on the surrounding text mass)."""

    inst_small = build_research_v4_dossier()
    inst_bulk = build_research_v4_dossier(bulk_cards=50)
    assert (
        inst_small.stages[4].commit_precondition["legal_plans"]
        == inst_bulk.stages[4].commit_precondition["legal_plans"]
    )
    assert inst_small.stages[5].expected_state_delta == inst_bulk.stages[5].expected_state_delta


def test_followup_grading_names_the_broken_stage() -> None:
    # A policy that fails follow-up 2 shows WHICH horizon link broke.
    broken_policy = REREAD_POLICY.replace('"status": "reverify"', '"status": "current"')
    record, hook, env, budget = _run(broken_policy)
    assert not record.final_check.passed
    assert any("follow_up[" in failure for failure in record.final_check.failures)


def test_corpus_scaling_preserves_the_load_bearing_ledger() -> None:
    # The long-context axis: bulk grows the corpus; the four decisive
    # facts stay single-source (filler never carries them); the two
    # legal paths still solve the world.
    inst = build_research_v4_dossier(bulk_cards=100)
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    assert len(inst.stages[0].documents) == 122
    for needle in ("bonded corridor", "northern service hub", "lapsed", "mutual-aid annex"):
        assert survey.count(needle) == 1, needle


def test_phase1_acceptance_doc_update_does_not_stale_unrelated_evidence() -> None:
    """R1.1 acceptance (review §2.1): the s4 documentation-only update
    must NOT invalidate customs-preclearance evidence acquired at s2 —
    a correct system commits at s5 WITHOUT re-verification; after the
    s7 supersession the same evidence is stale for NEW decisions."""

    policy = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "constraint_injection":
        # Acquire customs evidence EARLY (s2), before any rule change.
        return {
            "pack_text": "early evidence",
            "actions": (
                turn.actions.request_verification(
                    "early-customs", "customs-preclearance", "atlas-carriage"
                ),
            ),
        }
    if kind == "act_verify":
        # Cite the EARLY evidence — never re-verified.
        return {
            "pack_text": "award on early evidence",
            "actions": (
                turn.actions.create_record(
                    "candidate_status-atlas", {"plan": "atlas-carriage", "domain": "shipping"}
                ),
                turn.actions.create_record("migration_commit", {"plan": "atlas-carriage"}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": "atlas-carriage", "status": "final"},
                    ("early-customs", "candidate_status-atlas"),
                ),
            ),
        }
    return {"pack_text": "ok"}
"""
    record, hook, env, _ = _run(policy)
    # The s5 award gate (graded IN TIME, before s7) passes on the
    # revision-1 evidence: the doc update at s4 did not stale it.
    assert not any("commit gate" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )
    # The evidence record itself carries the CHECK's revision: 1 (never
    # superseded at acquisition time).
    assert env.records["early-customs"]["protocol_revision"] == 1
    # After s7, the check's revision is 3 — the same evidence IS stale
    # for new decisions now (the followup-2 derivation would say
    # 'reverify' for a commit citing this record).
    assert env.check_revisions["customs-preclearance"] == 3


def _currency_env(commit_refs: tuple[str, ...]) -> ProjectState:
    """A sandbox whose commit cites ``commit_refs``, over a real history.

    One env-issued customs verification at revision 1, the s7
    supersession (customs -> revision 3), then a second customs
    verification stamped at revision 3 — so a commit may cite old
    evidence, new evidence, both, or neither, by provenance choice.
    """

    env = ProjectState()
    inst = build_research_v4_dossier()
    env.begin_instance(inst.stages[4].verification_oracle)
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-old",
            fields={"check": "customs-preclearance", "subject": "atlas-carriage"},
        )
    )
    env.apply_protocol_revision(3, ("customs-preclearance",))
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-new",
            fields={"check": "customs-preclearance", "subject": "atlas-carriage"},
        )
    )
    env.submit(
        Action(
            kind="create_record",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage"},
        )
    )
    env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage", "status": "final"},
            provenance=commit_refs,
        )
    )
    return env


_CURRENCY_SPEC: dict[str, object] = {
    "commit_record": "migration_commit",
    "check": "customs-preclearance",
    "stale_value": "reverify",
    "current_value": "current",
}


def test_currency_derivation_is_order_independent() -> None:
    """Review 892f1d0 M1: a commit citing BOTH rev-1 and rev-3 customs
    evidence derives 'reverify' regardless of provenance order — the old
    first-match loop answered 'current' when the fresh record came
    first. ANY stale in-scope reference fails the diagnosis, exactly as
    the scoped commit gate treats the same commit."""

    from rsicontext.lifecycle.runner import _derive_evidence_currency

    stale_first = _derive_evidence_currency(_currency_env(("v-old", "v-new")), _CURRENCY_SPEC)
    fresh_first = _derive_evidence_currency(_currency_env(("v-new", "v-old")), _CURRENCY_SPEC)
    assert stale_first == fresh_first == "reverify"
    # All-fresh and all-stale citations keep their answers.
    assert _derive_evidence_currency(_currency_env(("v-new",)), _CURRENCY_SPEC) == "current"
    assert _derive_evidence_currency(_currency_env(("v-old",)), _CURRENCY_SPEC) == "reverify"


def test_currency_derivation_names_missing_evidence_explicitly() -> None:
    """Review 892f1d0 M1: a commit citing NO in-scope evidence must NOT
    default to 'current' (the optimistic guess). The derivation returns
    the explicit missing value, so the ObjectiveChecker grades the
    participant's diagnosis as a mismatch — diagnosing currency with
    nothing to diagnose is wrong."""

    from rsicontext.lifecycle.runner import _derive_evidence_currency

    env = ProjectState()
    inst = build_research_v4_dossier()
    env.begin_instance(inst.stages[4].verification_oracle)
    # Out-of-scope env evidence + a bare participant record: no
    # referenced record carries the customs check.
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-cold",
            fields={"check": "cold-chain-integrity", "subject": "atlas-carriage"},
        )
    )
    env.submit(
        Action(
            kind="create_record",
            record_id="candidate_status",
            fields={"plan": "atlas-carriage", "domain": "shipping"},
        )
    )
    env.submit(
        Action(
            kind="create_record",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage"},
        )
    )
    env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage", "status": "final"},
            provenance=("v-cold", "candidate_status"),
        )
    )
    assert _derive_evidence_currency(env, _CURRENCY_SPEC) == "no-evidence"
    overridden = dict(_CURRENCY_SPEC, missing_value="nothing-to-diagnose")
    assert _derive_evidence_currency(env, overridden) == "nothing-to-diagnose"


def test_followup2_diagnosis_matches_derivation_not_memory() -> None:
    """Option A: the follow-up grades a DIAGNOSIS derived from the
    sandbox. A policy that writes 'current' while its commit cites
    pre-supersession evidence must FAIL (the derivation says
    reverify); the correct answer for that history is 'reverify'."""

    wrong_diagnosis = REREAD_POLICY.replace('"status": "reverify"', '"status": "current"')
    record, _, _, _ = _run(wrong_diagnosis)
    assert not record.final_check.passed
    assert any("follow_up[" in f for f in record.final_check.failures)

    # And the s8-time re-verification arm: the commit cites rev-1
    # evidence, s8 re-verifies (rev 3), the DERIVED answer for the
    # commit's OWN evidence stays 'reverify' — a fresh verification
    # does not retroactively cure the commit's stale citation; the
    # policy that correctly diagnoses its commit passes.
    fresh_arm = REREAD_POLICY.replace(
        """        # followup 2: the customs-preclearance evidence was stamped at
        # revision 2; the final rule change (revision 3) superseded that
        # check -> the evidence is stale -> reverify.
        return {""",
        """        # Re-verify NOW (post-s7, revision 3): the fresh record does
        # not cure the commit's rev-1 citation; the honest diagnosis of
        # the AWARD's evidence is still 'reverify'.
        turn.actions.request_verification("fresh", "customs-preclearance", "atlas-carriage")
        return {""",
    )
    record2, _, env2, _ = _run(fresh_arm)
    assert record2.final_check.passed, record2.final_check.failures
    assert env2.check_revisions["customs-preclearance"] == 3
