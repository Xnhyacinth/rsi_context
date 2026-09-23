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
    record, hook, env, budget = _run(REMEMBER_POLICY)
    assert record.final_check.passed, record.final_check.failures
    assert budget.calls == 0


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
    # Each decisive fact has EXACTLY ONE source in the corpus (the
    # no-lie constraint): removing card-03's clause breaks the award,
    # card-08's line breaks follow-up 1, card-17's line undefuses the
    # decoy, card-05's clause grounds the exemption transfer.
    inst = build_research_v4_dossier()
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    assert survey.count("bonded corridor") == 1  # card-03 only
    assert survey.count("northern service hub") == 1  # card-08 only
    assert survey.count("lapsed") == 1  # card-17 only
    assert survey.count("mutual-aid annex") == 1  # card-05 only


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
