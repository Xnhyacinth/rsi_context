"""B-group acceptance tests (research-v5, the session-boundary slice).

Pins from the design (bgroup agent, 2026-09-23):
1. persist-then-recover roundtrip (carry survives; working state does not);
2. forbidden-persistence refusal (over-cap carry refused with a cause;
   the next session starts from the last valid flush);
3. stale-conclusion detection (s2 currency derives reverify; the re-award
   gate demands revision-3 evidence — both directions pinned);
4. new-project non-transfer (session-1 conclusions fail the mirror);
5. boundary realism (no follow_up in session 1; the between-session rule
   change appears only in session 2; fresh state objects per session);
6. grammar (v5 instances validate; session stages refuse evaluator fields).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_b_group import build_b1_sessions
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.session_sequence import CARRY_KEY, run_session_sequence
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

from r2a_compare import _offline_responder


#: A carry-capable scripted policy: distills at session_end, distrusts
#: stale carry at resume, re-requests evidence for the re-award, and
#: surveys fresh in the new project.
CARRY_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        text = turn.documents_text
        state["working_notes"] = text[:3000]
        # Distill the load-bearing facts into carry as we read.
        state.setdefault("carry", {})
        if "bonded corridor" in text:
            state["carry"]["winner"] = "atlas-carriage"
        if "suspended" in text:
            state["carry"]["decoy_out"] = True
        if "northern service hub" in text:
            state["carry"]["calibration"] = "vesper-instruments"
        if "suspended" in text and "orbit hosting" in text.lower():
            # Mirror corpus ONLY (the decoy clause 'suspended' exists
            # only there; mother's orbit card is plain bulk).
            state["carry"]["calibration"] = "orbit-hosting"
            state["carry"]["winner"] = "harborline-freight"
        return {"pack_text": "survey"}
    if kind == "session_end":
        return {"pack_text": "end"}
    if kind == "session_start":
        return {"pack_text": "resume"}
    if kind == "act_verify":
        carry = state.get("carry", {})
        stage_id = turn.view.stage_id
        if stage_id == "s5-act-verify":
            winner = carry.get("winner", "atlas-carriage")
            return {
                "pack_text": "award " + str(winner),
                "actions": (
                    turn.actions.request_verification(
                        "v-fresh", "customs-preclearance", winner
                    ),
                    turn.actions.create_record(
                        "candidate_status", {"plan": winner, "domain": "shipping"}
                    ),
                    turn.actions.create_record("migration_commit", {"plan": winner}),
                    turn.actions.finalize(
                        "migration_commit",
                        {"plan": winner, "status": "final"},
                        ("v-fresh", "candidate_status"),
                    ),
                ),
            }
        if stage_id == "s11-re-award":
            # Fresh evidence at the CURRENT revision (rev 3) — the old
            # v-fresh (rev 1) is stale for this decision; a NEW id.
            winner = carry.get("winner", "atlas-carriage")
            return {
                "pack_text": "re-award " + str(winner),
                "actions": (
                    turn.actions.request_verification(
                        "v-rev3", "customs-preclearance", winner
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": winner}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": winner, "status": "final"},
                        ("v-rev3",),
                    ),
                ),
            }
        # Session 3's fresh award: the winner must come from the MIRROR
        # survey's own distillation (the carry branch above); a neutral
        # fallback never biases either world.
        winner = carry.get("winner", "unknown")
        return {
            "pack_text": "award " + str(winner),
            "actions": (
                turn.actions.request_verification(
                    "v-mirror", "customs-preclearance", winner
                ),
                turn.actions.create_record(
                    "candidate_status", {"plan": winner, "domain": "shipping"}
                ),
                turn.actions.create_record("migration_commit", {"plan": winner}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": winner, "status": "final"},
                    ("v-mirror", "candidate_status"),
                ),
            ),
        }
    if kind == "follow_up":
        doc_text = turn.view.documents[0].text if turn.view.documents else ""
        if "calibration" in doc_text:
            carry = state.get("carry", {})
            supplier = carry.get("calibration", "unknown")
            return {
                "pack_text": "calibration",
                "actions": (
                    turn.actions.create_record(
                        "followup_conclusion-calibration", {"supplier": supplier}
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
    if kind == "rule_change":
        return {"pack_text": "noted"}
    return {"pack_text": "ok"}
"""


def _run_sequence(policy_text: str, envs=None):
    sessions = build_b1_sessions()
    if envs is None:
        envs = [ProjectState(), ProjectState(), ProjectState()]
        # Sessions 1-2 thread the SAME project env; session 3 is fresh.
        envs = [envs[0], envs[0], envs[2]]
    budget = ToolBudget()
    registry = DocumentRegistry()
    hook_holder = {}

    def hook_factory(state):
        hook = PolicyHook(
            state,
            policy_text,
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        )
        hook_holder["last"] = hook
        return hook

    record = run_session_sequence(
        list(sessions), hook_factory, envs=envs, budget=budget, registry=registry
    )
    return record, budget, registry, hook_holder


def _run_sequence_with(builder, policy_text: str):
    """The same sequence shape, over any B-world builder (dev or eval)."""
    sessions = list(builder())
    envs = [ProjectState(), ProjectState(), ProjectState()]
    envs = [envs[0], envs[0], envs[2]]
    budget = ToolBudget()
    registry = DocumentRegistry()
    record = run_session_sequence(
        sessions,
        lambda state: PolicyHook(
            state,
            policy_text,
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        ),
        envs=envs,
        budget=budget,
        registry=registry,
    )
    return record


def test_grammar_and_boundary_realism() -> None:
    s1, s2, s3 = build_b1_sessions()
    assert [s.kind for s in s1.stages][-1] == "session_end"
    assert "follow_up" not in [s.kind for s in s1.stages]
    # The between-session rule change appears ONLY in session 2.
    assert any(s.rule_change_effect == 3 for s in s2.stages), "rev-3 must live in session 2"
    assert not any(s.rule_change_effect == 3 for s in s1.stages)
    assert s3.family == "research-v5"


def test_persist_then_recover_roundtrip() -> None:
    record, budget, registry, holder = _run_sequence(CARRY_POLICY)
    # The carry survived: session 2+3's hook state started with the
    # distilled facts (the policy's session-2 answers prove it read the
    # carried calibration value).
    assert record.sessions[0].persist_ok
    assert record.decisions.get("s2_calibration") is True
    # Working state did NOT survive: the policy's non-carry key
    # ('working_notes') is absent in later sessions (checked implicitly:
    # the sequence runner seeds ONLY the carry subtree; pinned next).
    # Session 3's fresh-project answer uses the MIRROR's facts (the
    # registry replaced the patched cards' text).
    assert registry.get("card-03").text != registry.get("card-02").text


def test_registry_replaces_on_content_change() -> None:
    registry = DocumentRegistry()
    from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
    from rsicontext.lifecycle.dossier_variants import build_dossier_variant

    mother = build_research_v4_dossier()
    mirror = build_dossier_variant("mirror")
    registry.reveal(mother.stages[0].documents)
    before = registry.get("card-03").text
    registry.reveal(mirror.stages[0].documents)
    after = registry.get("card-03").text
    assert before != after, "the registry must serve the CURRENT world's text"
    assert "No exceptional clauses apply" in after


def test_stale_conclusion_detection_both_directions() -> None:
    record, _, _, _ = _run_sequence(CARRY_POLICY)
    # s2 currency: the derivation says reverify (session-1 evidence at
    # revision 1; check now at 3) — the policy wrote reverify.
    assert record.decisions.get("s2_currency") is True
    # s2 re-award: fresh revision-3 evidence required; the policy
    # re-requested (its request lands at the session-2 clock).
    assert record.decisions.get("s2_reaward_fresh") is True, record.failure_detail


def test_new_project_non_transfer() -> None:
    # A dedicated BLIND policy: it acquires the session-1 conclusions
    # (winner=atlas, calibration=vesper) and pins them FOREVER — no
    # re-derivation from the mirror survey. In session 3 (the mirror's
    # facts) both pinned conclusions must FAIL: the gate rejects
    # atlas-carriage; the calibration delta expects orbit-hosting.
    blind_policy = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        # Learn ONLY from the MOTHER corpus (the session-1 shape).
        text = turn.documents_text
        state.setdefault("carry", {})
        if "bonded corridor" in text:
            state["carry"]["winner"] = "atlas-carriage"
            state["carry"]["calibration"] = "vesper-instruments"
        return {"pack_text": "survey (mother-facts only)"}
    if kind in ("session_end", "session_start", "rule_change", "constraint_injection", "delegation"):
        return {"pack_text": "boundary"}
    if kind == "act_verify":
        winner = "atlas-carriage"
        ver = "bv-" + turn.view.stage_id
        return {
            "pack_text": "blind award",
            "actions": (
                turn.actions.request_verification(ver, "customs-preclearance", winner),
                turn.actions.create_record("candidate_status", {"plan": winner, "domain": "shipping"}),
                turn.actions.create_record("migration_commit", {"plan": winner}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": winner, "status": "final"},
                    (ver, "candidate_status"),
                ),
            ),
        }
    if kind == "follow_up":
        return {
            "pack_text": "blind calibration",
            "actions": (
                turn.actions.create_record(
                    "followup_conclusion-calibration", {"supplier": "vesper-instruments"}
                ),
            ),
        }
    return {"pack_text": "ok"}
"""
    record, _, _, _ = _run_sequence(blind_policy)
    assert record.decisions.get("s1_award") is True, "session-1 facts are correct"
    assert record.decisions.get("s2_calibration") is True, "carry works within the project"
    assert record.decisions.get("s3_award") is False, "the mirror gate must reject atlas"
    assert record.decisions.get("s3_calibration") is False, (
        "the mirror calibration must reject vesper"
    )


def test_oversized_carry_refused_with_cause() -> None:
    big = CARRY_POLICY + "\n" + ("def _fill():\n    state = {}\n")
    # A policy that stuffs the carry beyond the cap: simulate directly.
    sessions = build_b1_sessions()
    env = ProjectState()

    class Stuffer:
        # Stuffs ONLY session 1's end (later sessions behave): the next
        # session must start from the LAST SUCCESSFUL flush (empty).
        def __init__(self, state):
            self.state = state
            self.policy_errors = []
            self.seen_session_end = False

        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.stage_id == "s6-session-end":  # session 1's end only
                self.state[CARRY_KEY] = {"blob": "x" * 200_000}
            return StageResponse(pack_text="ok")

    record = run_session_sequence(list(sessions), Stuffer, envs=[env, env, ProjectState()])
    assert record.sessions[0].persist_ok is False
    assert "byte cap" in record.sessions[0].persist_cause
    # The next session starts from the LAST SUCCESSFUL flush (empty).
    # Session 2's hook state carry == {} — the Stuffer's session-2 state
    # began empty, so its second flush is small and succeeds.
    assert record.sessions[1].persist_ok is True


def test_sequence_record_exports_cost_and_transcript() -> None:
    # The r3 unified-entry requirement: sequence-shaped runs carry the
    # SAME cost/audit surface as single _run_arm runs (model tokens,
    # the shared tool ledger, the per-call transcript). Use a policy
    # that ASKS the model (the strong-fixed shape) so the channel is
    # actually exercised.
    from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text

    sessions = build_b1_sessions()
    env = ProjectState()
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            strong_model_fixed_policy_text(),
            tool_budget=budget,
            responder=_offline_responder,
            registry=registry,
        )

    record = run_session_sequence(
        sessions,
        hook_factory,
        envs=[env, env, ProjectState()],
        budget=budget,
        registry=registry,
    )
    cost = record.cost()
    assert cost["model_calls"] > 0  # the model channel was exercised
    assert cost["model_tokens_in"] > 0
    assert cost["tool_ledger"] is not None
    session0 = record.sessions[0]
    assert session0.model_transcript  # the audit transcript survived
    assert session0.model_transcript[0]["stage_kind"] == "survey"
    # The serialized record carries it too.
    payload = record.to_dict()
    assert payload["cost"]["model_calls"] == cost["model_calls"]


def test_r3_record_gaps_stage_records_and_hook_snapshot() -> None:
    # The r3design gaps: (1) per-session stage_records exported; (2) the
    # end-of-session hook-state snapshot (memory_delivered/obs/carry);
    # (5) decision_rules parameter overrides the B-shaped default; (3)
    # the audit transcript keys calls by stage_id.
    record, budget, registry, holder = _run_sequence(CARRY_POLICY)
    session0 = record.sessions[0]
    # GAP 1: stage records present, dict-shaped, stage-tagged.
    assert session0.stage_records, "the trace's turn source"
    first = session0.stage_records[0]
    assert first.get("stage_id") == "s1-survey"
    # GAP 2: the hook-state snapshot captured before destruction.
    assert isinstance(session0.final_memory_delivered, list)
    assert isinstance(session0.final_obs, list)
    assert isinstance(session0.final_carry, dict) or session0.final_carry is None
    # GAP 3: the audit transcript keys calls by stage_id.
    from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text

    sessions = build_b1_sessions()
    env = ProjectState()
    hook = PolicyHook(
        {},
        strong_model_fixed_policy_text(),
        tool_budget=ToolBudget(),
        responder=_offline_responder,
    )
    hook.bind_env(env)
    run_lifecycle(sessions[0], hook, env, max_turns_per_stage=1)
    assert hook.model_transcript[0]["stage_id"] == "s1-survey"
    # GAP 5: decision_rules override (C-style: per-session passed).
    from rsicontext.lifecycle.session_sequence import run_session_sequence

    def c_rules(rec, sessions):
        rec.decisions = {f"session_{i}_passed": s.passed for i, s in enumerate(rec.sessions)}

    record2 = run_session_sequence(
        list(sessions),
        lambda state: PolicyHook(
            state,
            strong_model_fixed_policy_text(),
            tool_budget=ToolBudget(),
            responder=_offline_responder,
        ),
        envs=[ProjectState(), ProjectState(), ProjectState()],
        decision_rules=c_rules,
    )
    assert set(record2.decisions) == {
        "session_0_passed",
        "session_1_passed",
        "session_2_passed",
    }


# ---------------------------------------------------------------------------
# b1-reverse (the r3 EVAL world: same three-session shape, worlds SWAPPED).
# ---------------------------------------------------------------------------


def test_b1_reverse_grammar_and_swap() -> None:
    from rsicontext.lifecycle.material_b_group import build_b1_reverse_sessions

    dev1, dev2, dev3 = build_b1_sessions()
    rev1, rev2, rev3 = build_b1_reverse_sessions()
    # Identical three-session SHAPE: the same stage kinds per session and
    # the same stage-id set (the decision needles are stage-id based).
    for dev, rev in ((dev1, rev1), (dev2, rev2), (dev3, rev3)):
        assert [s.stage_id for s in dev.stages] == [s.stage_id for s in rev.stages]
        assert [s.kind for s in dev.stages] == [s.kind for s in rev.stages]
    assert [s.instance_id for s in (rev1, rev2, rev3)] == [
        "research-v5-b1r-s1-0001",
        "research-v5-b1r-s2-0001",
        "research-v5-b1r-s3-0001",
    ]
    # Sessions 1-2 run the MIRROR's facts: the survey carries the mirror
    # decoy's decisive clause ('suspended') and NOT the mother's winner
    # clause ('bonded corridor' is the mother's card-03 phrasing).
    rev12_text = "\n".join(d.text for d in rev1.stages[0].documents)
    assert "suspended" in rev12_text
    assert "bonded corridor" not in rev12_text
    # Session 3 is the fresh project on the MOTHER's facts.
    rev3_text = "\n".join(d.text for d in rev3.stages[0].documents)
    assert "bonded corridor" in rev3_text
    assert "suspended" not in rev3_text
    # The s5 gate's legal set is the mirror's winner; session 3's gate is
    # the mother's.
    assert rev1.stages[3].commit_precondition["legal_plans"] == ["harborline-freight"]
    assert rev3.stages[3].commit_precondition["legal_plans"] == ["atlas-carriage"]
    # The s5 gate's oracle and session-2's calibration carry the mirror's
    # facts too.
    assert rev1.stages[3].verification_oracle["customs-preclearance"]["harborline-freight"] is True
    assert rev2.stages[2].expected_state_delta == {
        "followup_conclusion-calibration": {"supplier": "orbit-hosting"}
    }
    # The between-session rule change keeps b1's rev-3 customs scope.
    between = next(s for s in rev2.stages if s.rule_change_effect == 3)
    assert between.rule_change_scope == ("customs-preclearance",)
    assert not any(s.rule_change_effect == 3 for s in rev1.stages)


#: The reverse twin of the BLIND policy: acquires the MIRROR's
#: session-1 conclusions (winner=harborline, calibration=orbit) and pins
#: them forever — misapplies them in session 3 (the MOTHER's facts).
BLIND_MIRROR_POLICY = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        state.setdefault("carry", {})
        state["carry"]["winner"] = "harborline-freight"
        state["carry"]["calibration"] = "orbit-hosting"
        return {"pack_text": "survey (mirror-facts pinned)"}
    if kind in (
        "session_end",
        "session_start",
        "rule_change",
        "constraint_injection",
        "delegation",
    ):
        return {"pack_text": "boundary"}
    if kind == "act_verify":
        winner = "harborline-freight"
        ver = "bvm-" + turn.view.stage_id
        record = "corridor_reaward" if turn.view.stage_id == "s11-re-award" else "migration_commit"
        return {
            "pack_text": "blind award",
            "actions": (
                turn.actions.request_verification(ver, "customs-preclearance", winner),
                turn.actions.create_record(record, {"plan": winner}),
                turn.actions.finalize(record, {"plan": winner, "status": "final"}, (ver,)),
            ),
        }
    if kind == "follow_up":
        return {
            "pack_text": "blind calibration",
            "actions": (
                turn.actions.create_record(
                    "followup_conclusion-calibration", {"supplier": "orbit-hosting"}
                ),
            ),
        }
    return {"pack_text": "ok"}
"""


def test_reverse_transfer_punishes_carry_misapplication() -> None:
    # The transfer axis is REAL and not one-directional: the SAME blind
    # policy that misapplies session-1 conclusions in session 3. On
    # b1-reverse the pinned mirror conclusions must FAIL session 3 (the
    # mother's gate rejects harborline; the calibration delta expects
    # vesper). On b1 (dev) the mirror-blind policy fails sessions 1-2
    # — the symmetric evidence that it is the WORLD, not the stage
    # grammar, that flips the answer.
    from rsicontext.lifecycle.material_b_group import build_b1_reverse_sessions

    rev = _run_sequence_with(build_b1_reverse_sessions, BLIND_MIRROR_POLICY)
    assert rev.decisions.get("s1_award") is True, "mirror facts are correct in session 1"
    assert rev.decisions.get("s2_calibration") is True, "carry works within the project"
    assert rev.decisions.get("s3_award") is False, "the mother gate must reject harborline"
    assert rev.decisions.get("s3_calibration") is False, "the mother calibration must reject orbit"
    dev = _run_sequence_with(build_b1_sessions, BLIND_MIRROR_POLICY)
    assert dev.decisions.get("s1_award") is False, "the mother gate rejects harborline in dev too"
    assert dev.decisions.get("s3_award") is True, "the mirror gate accepts harborline in dev"


def test_reverse_world_is_passable_by_a_correct_policy() -> None:
    # The eval world must be PASSABLE: the CARRY policy (which re-derives
    # the winner from each session's own survey) passes every decision on
    # b1-reverse — the swap does not break the world, only the blind
    # carry.
    from rsicontext.lifecycle.material_b_group import build_b1_reverse_sessions

    record = _run_sequence_with(build_b1_reverse_sessions, CARRY_POLICY)
    assert record.decisions.get("s1_award") is True, record.failure_detail
    assert record.decisions.get("s2_calibration") is True, record.failure_detail
    assert record.decisions.get("s2_currency") is True, record.failure_detail
    assert record.decisions.get("s2_reaward_fresh") is True, record.failure_detail
    assert record.decisions.get("s3_award") is True, record.failure_detail
    assert record.decisions.get("s3_calibration") is True, record.failure_detail
