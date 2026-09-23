"""C-group acceptance tests (research-v5, the execution-recovery slice).

Pins:
1. fail-receipt-acted-on: a naive agent that commits the
   reading-level-best (atlas, oracle-FAIL in session 1) is refused; a
   recovering agent reads the fail receipt, switches, commits ember.
2. mutation-flips-answer: session 2's bonding-renewal mutation (a NEW
   oracle on the fresh award stage) flips atlas to pass — the re-award
   legal set contains only the mutation's winner; a stale ember
   recovery (no re-verification of the changed state) is refused.
3. two legal recovery paths pass session 1 (read-receipt-and-switch
   via the multi-turn loop; and verify-first-then-commit).
4. the naive non-recovering agent fails both sessions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_c_group import build_c1_sessions
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

from r2a_compare import _offline_responder


def _actions(turn, plan, ver_id, check="customs-preclearance"):
    return (
        turn.actions.request_verification(ver_id, check, plan),
        turn.actions.create_record("candidate_status-" + plan, {"plan": plan, "domain": "domain"}),
        turn.actions.create_record("migration_commit", {"plan": plan}),
        turn.actions.finalize(
            "migration_commit",
            {"plan": plan, "status": "final"},
            (ver_id, "candidate_status-" + plan),
        ),
    )


#: NAIVE: commits the reading-level best (atlas) WITHOUT reading the
#: outcome; on resume, re-awards the carried ember (stale recovery).
NAIVE_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "survey":
        turn.state["carry"] = {"winner": "atlas-carriage"}
        return {"pack_text": "survey"}
    if kind == "act_verify":
        if turn.view.stage_id == "c1-re-award":
            winner = "ember"  # the carried session-1 conclusion, stale
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


#: RECOVER (read-receipt-and-switch): verify the preferred candidate,
#: READ the receipt; on fail, switch to ember and re-verify; on resume,
#: re-verify the mutation's winner post-mutation.
RECOVER_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        state["carry"] = {"preferred": "atlas-carriage", "fallback": "ember"}
        return {"pack_text": "survey"}
    if kind == "act_verify":
        if turn.view.stage_id == "c1-re-award":
            # Post-mutation: re-verify the renewed carrier.
            winner = "atlas-carriage"
            return {
                "pack_text": "re-award " + winner,
                "actions": (
                    turn.actions.request_verification(
                        "v-rev2", "customs-preclearance", winner
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": winner}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": winner, "status": "final"},
                        ("v-rev2",),
                    ),
                ),
            }
        # Session 1, TURN 1: request the preferred's verification ONLY.
        # TURN 2+: ACCUMULATE the seen receipts into state (receipts
        # drain per turn — a one-turn memory loses earlier verdicts);
        # on a fail switch to the fallback and verify IT; commit once
        # the fallback's pass is seen. The multi-turn loop delivers
        # each verdict; the POLICY remembers it.
        seen = turn.state.setdefault("seen_receipts", [])
        seen.extend((r.record_id, r.verdict) for r in turn.receipts)
        known = dict(seen)
        probed = "v-pre" in known
        probe_fail = known.get("v-pre") == "fail"
        fallback_ok = known.get("v-fallback") == "pass"
        if not probed:
            return {
                "pack_text": "verify preferred",
                "actions": (
                    turn.actions.request_verification(
                        "v-pre", "customs-preclearance", "atlas-carriage"
                    ),
                ),
            }
        if probe_fail and not fallback_ok:
            return {
                "pack_text": "switch to fallback",
                "actions": (
                    turn.actions.request_verification(
                        "v-fallback", "customs-preclearance", "ember"
                    ),
                ),
            }
        plan = "ember" if probe_fail else "atlas-carriage"
        ver = "v-fallback" if probe_fail else "v-pre"
        return {
            "pack_text": "commit " + plan,
            "actions": (
                turn.actions.create_record(
                    "candidate_status-" + plan, {"plan": plan, "domain": "domain"}
                ),
                turn.actions.create_record("migration_commit", {"plan": plan}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": plan, "status": "final"},
                    (ver, "candidate_status-" + plan),
                ),
            ),
        }
    return {"pack_text": "ok"}
"""


#: VERIFY-FIRST: no preference at all — verify BOTH candidates before
#: committing (the second legal path).
VERIFY_FIRST_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "act_verify":
        if turn.view.stage_id == "c1-re-award":
            return {
                "pack_text": "re-award atlas",
                "actions": (
                    turn.actions.request_verification(
                        "vf-rev", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": "atlas-carriage"}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("vf-rev",),
                    ),
                ),
            }
        # Verify both; commit the one whose receipt says pass.
        atlas_ok = any(
            r.record_id == "vf-atlas" and r.verdict == "pass" for r in turn.receipts
        )
        plan = "atlas-carriage" if atlas_ok else "ember"
        ver = "vf-atlas" if atlas_ok else "vf-ember"
        return {
            "pack_text": "commit " + plan,
            "actions": (
                turn.actions.request_verification(
                    "vf-atlas", "customs-preclearance", "atlas-carriage"
                ),
                turn.actions.request_verification(ver, "customs-preclearance", plan),
                turn.actions.create_record(
                    "candidate_status-" + plan, {"plan": plan, "domain": "domain"}
                ),
                turn.actions.create_record("migration_commit", {"plan": plan}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": plan, "status": "final"},
                    (ver, "candidate_status-" + plan),
                ),
            ),
        }
    return {"pack_text": "ok"}
"""


def _run_c1(policy_text: str, turns: int = 3):
    sessions = list(build_c1_sessions())
    env = ProjectState()
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            policy_text,
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        )

    record = run_session_sequence(
        sessions,
        hook_factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=turns,
    )
    return record, env


def test_naive_agent_fails_both_decisions() -> None:
    record, env = _run_c1(NAIVE_POLICY)
    s1, s2 = record.sessions
    # Session 1: committed the oracle-FAIL subject; the gate refuses
    # (no passing env-issued evidence for the plan).
    assert not s1.passed
    assert any(
        "lacks an environment-issued" in f or "not in the legal set" in f for f in s1.failures
    ), s1.failures
    # Session 2: the stale ember re-award is not in the mutation's
    # legal set (atlas only).
    assert not s2.passed
    assert any("not in the legal set" in f for f in s2.failures), s2.failures


def test_recover_policy_passes_both_sessions() -> None:
    record, env = _run_c1(RECOVER_POLICY)
    s1, s2 = record.sessions
    assert s1.passed, s1.failures
    assert s2.passed, s2.failures
    # The award went to ember (the session-1 oracle's passer).
    assert env.records["migration_commit"]["plan"] == "ember"
    # The re-award went to atlas (the mutation's winner), citing
    # post-mutation evidence (rev 2).
    assert env.records["corridor_reaward"]["plan"] == "atlas-carriage"
    assert env.records["v-rev2"]["protocol_revision"] == 2


def test_verify_first_policy_passes_session_one() -> None:
    # The second legal recovery path: verify both candidates, commit
    # the one whose outcome passed.
    record, env = _run_c1(VERIFY_FIRST_POLICY)
    s1 = record.sessions[0]
    assert s1.passed, s1.failures
    assert env.records["migration_commit"]["plan"] in ("ember", "atlas-carriage")


def test_session1_oracle_fails_the_reading_level_best() -> None:
    # The mutation contract: session 1's oracle marks atlas FAIL (the
    # pending audit) — the task's premise.
    s1, s2 = build_c1_sessions()
    oracle = s1.stages[2].verification_oracle
    assert oracle["customs-preclearance"]["atlas-carriage"] is False
    assert oracle["customs-preclearance"]["ember"] is True
    oracle2 = s2.stages[2].verification_oracle
    assert oracle2["customs-preclearance"]["atlas-carriage"] is True
    # The mutation flips the LEGAL SET (session 2's re-award: atlas only).
    assert s2.stages[2].commit_precondition["legal_plans"] == ["atlas-carriage"]


def test_receipts_deliver_the_fail_verdict_in_stage() -> None:
    # The mechanism the recovery depends on: a fail verdict comes back
    # as a RECEIPT on the next turn's view (multi-turn delivery).
    s1, _ = build_c1_sessions()
    env = ProjectState()
    env.begin_instance(s1.stages[2].verification_oracle)

    class ReceiptSpy:
        def __init__(self):
            self.seen = []

        def on_stage(self, stage: StageView) -> StageResponse:
            self.seen.extend(stage.receipts)
            if stage.kind != "act_verify":
                return StageResponse(pack_text="ok")
            if not any(r.record_id == "probe" for r in stage.receipts):
                return StageResponse(
                    pack_text="probe",
                    actions=(
                        Action(
                            kind="request_verification",
                            record_id="probe",
                            fields={"check": "customs-preclearance", "subject": "atlas-carriage"},
                        ),
                    ),
                )
            return StageResponse(pack_text="done")

    from rsicontext.lifecycle.env import Action

    spy = ReceiptSpy()
    record = run_lifecycle(s1, spy, env, max_turns_per_stage=3)
    probe = [r for r in spy.seen if r.record_id == "probe"]
    assert probe and probe[0].applied and probe[0].verdict == "fail"
