"""M2 task-validity parents — acceptance tests (2026-09-24).

Pins for each new parent (the "genuinely different" axis):
- aurora-swap: the dependency graph INVERTED (the winner
  qualification and the decoy disqualifier live on different cards
  than the mother's); the load-bearing ledger stays single-source;
  BOTH legal paths (reread/remember) still solve the world.
- vector: the decision TYPE (two cumulative checks); a plan passing
  only ONE check fails the gate with the MISSING check named; the
  winner's cold-chain qualification is single-source.
- b2: FOUR sessions with TWO between-session mutations; the carry
  contract unchanged; the second mutation supersedes a DIFFERENT
  check; a correct carry-aware policy passes every decision.
- c2: the double-switch recovery (the top TWO ranked candidates
  fail session 1); the mutation renews ONE leader only; the
  public-rules-match-the-gate invariant (the c1 M1 pattern).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from m2_validity_panel import _b_responder

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_m2_parents import (
    build_aurora_swap,
    build_b2_sessions,
    build_c2_sessions,
    build_vector,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import StageSpec
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget


def _precondition(stage: StageSpec) -> Mapping[str, object]:
    precondition = stage.commit_precondition
    assert precondition is not None
    return precondition


def _oracle(stage: StageSpec) -> Mapping[str, Mapping[str, bool]]:
    oracle = stage.verification_oracle
    assert oracle is not None
    return oracle


# ---------------------------------------------------------------------------
# aurora-swap
# ---------------------------------------------------------------------------


def test_aurora_swap_inverts_the_dependency_graph() -> None:
    from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier

    inst = build_aurora_swap()
    mother = build_research_v4_dossier()
    # The legal set FLIPS (a different card is now load-bearing).
    assert _precondition(inst.stages[4])["legal_plans"] == ["harborline-freight"]
    assert _precondition(mother.stages[4])["legal_plans"] == ["atlas-carriage"]
    # The mother's winner card is now plain bulk (no qualification).
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    mother_survey = "\n".join(doc.text for doc in mother.stages[0].documents)
    assert "only tier-B carrier whose bonded corridor" not in survey
    # The new winner's clause exists in the aurora corpus only.
    assert "bonded port-corridor" not in mother_survey


def test_aurora_swap_load_bearing_ledger_single_source() -> None:
    inst = build_aurora_swap()
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    # The two DECISIVE propositions each have exactly one source.
    assert survey.count("bonded port-corridor") == 1  # card-02 only
    assert survey.count("depot bonding lapsed") == 1  # card-01 only
    # The follow-ups' facts (unchanged from the mother) stay single-source.
    assert survey.count("northern service hub") == 1  # card-08 only
    assert survey.count("mutual-aid annex") == 1  # card-05 only
    # The oracle agrees with the ledger (the winner passes, the decoy fails).
    oracle = _oracle(inst.stages[4])
    assert oracle["customs-preclearance"]["harborline-freight"] is True
    assert oracle["customs-preclearance"]["northwind-logistics"] is False


def test_aurora_swap_rule_change_scopes_unchanged() -> None:
    # The s4 doc-only rule change keeps its EMPTY scope (the trap is
    # structural); s7 keeps the customs-preclearance supersession.
    inst = build_aurora_swap()
    assert inst.stages[3].rule_change_scope == ()
    assert inst.stages[3].rule_change_effect == 2
    assert inst.stages[6].rule_change_scope == ("customs-preclearance",)
    assert inst.stages[6].rule_change_effect == 3


def test_aurora_swap_two_legal_paths_solve_it() -> None:
    # The two A-group legal paths (re-read vs remember), adapted to
    # the aurora facts: both must pass the world end-to-end.
    reread = _aurora_reread_policy()
    remember = _aurora_remember_policy()
    for policy in (reread, remember):
        env = ProjectState()
        budget = ToolBudget()
        hook = PolicyHook({}, policy, tool_budget=budget)
        hook.bind_env(env)
        record = run_lifecycle(build_aurora_swap(), hook, env, max_turns_per_stage=2)
        assert record.final_check.passed, (policy[:40], record.final_check.failures)
        assert hook.policy_errors == []


def _aurora_reread_policy() -> str:
    return """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        return {"pack_text": "skim"}
    if kind == "act_verify":
        card2 = turn.tools.reread("card-02")
        card1 = turn.tools.reread("card-01")
        plan = "harborline-freight" if "bonded port-corridor" in card2.answer else "unknown"
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
            supplier = (
                "vesper-instruments" if "northern service hub" in card8.answer else "unknown"
            )
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
    return {"pack_text": "ok"}
"""


def _aurora_remember_policy() -> str:
    return """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        text = turn.documents_text
        state["plan"] = "harborline-freight" if "bonded port-corridor" in text else "unknown"
        state["calibration"] = (
            "vesper-instruments" if "northern service hub" in text else "unknown"
        )
        return {"pack_text": "notes"}
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


# ---------------------------------------------------------------------------
# vector
# ---------------------------------------------------------------------------


def test_vector_decision_type_is_two_cumulative_checks() -> None:
    inst = build_vector()
    requirements = _precondition(inst.stages[4])["plan_requirements"]
    assert isinstance(requirements, dict)
    requirement = requirements["atlas-carriage"]
    assert isinstance(requirement, dict)
    # The commit precondition gains the SECOND requires_check entry.
    assert requirement["requires_check"] == ["customs-preclearance", "cold-chain-integrity"]
    # The oracle covers BOTH checks.
    oracle = _oracle(inst.stages[4])
    assert oracle["customs-preclearance"]["atlas-carriage"] is True
    assert oracle["cold-chain-integrity"]["atlas-carriage"] is True


def test_vector_one_check_passer_fails_the_gate() -> None:
    # The one-check trap: delta-catering passes cold-chain ONLY. A
    # commit citing only its passing check must FAIL with the MISSING
    # check named — the decision type, not the name, is what changed.
    inst = build_vector()
    env = ProjectState()
    env.begin_instance(inst.stages[4].verification_oracle)
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-cold",
            fields={"check": "cold-chain-integrity", "subject": "delta-catering"},
        )
    )
    env.submit(Action(kind="create_record", record_id="status", fields={"plan": "delta-catering"}))
    env.submit(
        Action(
            kind="create_record", record_id="migration_commit", fields={"plan": "delta-catering"}
        )
    )
    env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "delta-catering", "status": "final"},
            provenance=("v-cold", "status"),
        )
    )
    from rsicontext.lifecycle.runner import _commit_gate_failures

    precondition = dict(_precondition(inst.stages[4]))
    precondition["plan_requirements"] = {
        "delta-catering": {
            "domain": "shipping",
            "requires_check": ["customs-preclearance", "cold-chain-integrity"],
        }
    }
    failures = _commit_gate_failures(precondition, env.snapshot(), env)
    # The MISSING check is named; the PRESENT one is not flagged.
    assert any("'customs-preclearance' verification" in f and "lacks" in f for f in failures), (
        failures
    )
    assert not any("cold-chain-integrity" in f for f in failures), failures


def test_vector_winner_cold_chain_qualification_single_source() -> None:
    inst = build_vector()
    survey = "\n".join(doc.text for doc in inst.stages[0].documents)
    assert survey.count("cold-chain-annex") == 1  # card-03 only
    # The public rules (constraint + protocol) state the CUMULATIVE rule.
    constraint = inst.stages[1].documents[0].text
    assert "BOTH" in constraint and "cumulative" in constraint
    protocol = next(d for d in inst.stages[0].documents if d.doc_id == "doc-v4-verif-db").text
    assert "BOTH" in protocol and "cumulative" in protocol


def test_vector_two_check_winner_passes_and_str_requires_check_still_works() -> None:
    # Runner-change regression guard (EXERCISED, not spec-shape): the
    # gate's str requires_check path must behave exactly as before the
    # list support landed. The same sandbox/precondition is graded
    # with requires_check as (a) the pre-change str form and (b) the
    # one-element list — both must demand the SAME single check and
    # produce the SAME failures; a one-element list must not start
    # demanding the other check.
    from rsicontext.lifecycle.runner import _commit_gate_failures

    inst = build_vector()
    env = ProjectState()
    env.begin_instance(inst.stages[4].verification_oracle)
    # Customs evidence only (the one-check sandbox): the str gate
    # must accept it exactly as it did before the change; the
    # two-element list must reject it naming the missing check.
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-str",
            fields={"check": "customs-preclearance", "subject": "atlas-carriage"},
        )
    )
    env.submit(Action(kind="create_record", record_id="status", fields={"plan": "atlas-carriage"}))
    env.submit(
        Action(
            kind="create_record", record_id="migration_commit", fields={"plan": "atlas-carriage"}
        )
    )
    env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage", "status": "final"},
            provenance=("v-str", "status"),
        )
    )
    precondition = dict(_precondition(inst.stages[4]))
    str_form = dict(
        precondition,
        plan_requirements={
            "atlas-carriage": {
                "domain": "shipping",
                "requires_check": "customs-preclearance",
            }
        },
    )
    one_list = dict(
        precondition,
        plan_requirements={
            "atlas-carriage": {
                "domain": "shipping",
                "requires_check": ["customs-preclearance"],
            }
        },
    )
    failures_str = _commit_gate_failures(str_form, env.snapshot(), env)
    failures_one = _commit_gate_failures(one_list, env.snapshot(), env)
    # (a) The str form: pre-change behavior — customs satisfied, no
    # missing-check failure at all.
    assert failures_str == (), failures_str
    # (b) The one-element list: identical to the str form.
    assert failures_one == failures_str, (failures_str, failures_one)
    # (c) The two-element list: rejects, naming ONLY the missing check.
    failures_two = _commit_gate_failures(precondition, env.snapshot(), env)
    assert [f for f in failures_two if "lacks" in f and "customs-preclearance" in f] == []
    assert any("'cold-chain-integrity' verification" in f and "lacks" in f for f in failures_two), (
        failures_two
    )


def test_vector_reference_run_solves_it() -> None:
    # The panel's own reference executor (two-check award shape,
    # text-following worker) solves the vector world end-to-end.
    from m2_validity_panel import _run_a_world

    run = _run_a_world(build_vector())
    assert run["passed"], run["all_failures"]
    assert run["decisions"] == {
        "award": True,
        "followup_1": True,
        "followup_2": True,
    }


# ---------------------------------------------------------------------------
# b2
# ---------------------------------------------------------------------------


def test_b2_topology_four_sessions_two_mutations() -> None:
    sessions = list(build_b2_sessions())
    assert len(sessions) == 4
    # TWO between-session mutations: the first (customs -> rev 3)
    # appears in session 2; the second (cold-chain -> rev 4) in
    # session 3 — and they supersede DIFFERENT checks.
    rule_stages = [
        (s, st)
        for s in sessions
        for st in s.stages
        if st.kind == "rule_change" and st.rule_change_effect is not None and st.rule_change_scope
    ]
    scopes = [tuple(st.rule_change_scope) for _s, st in rule_stages]
    assert scopes.count(("customs-preclearance",)) == 1
    assert scopes.count(("cold-chain-integrity",)) == 1
    # No mutation lands INSIDE a session's survey/award phase (they
    # are between-session by construction: session 1 has none).
    assert not any(st.rule_change_scope for st in sessions[0].stages if st.kind == "rule_change")
    # The carry contract is unchanged: every session ends with
    # session_end; session boundaries are plain.
    for session in sessions:
        assert [s.kind for s in session.stages][-1] == "session_end"


def test_b2_second_mutation_stresses_the_carried_conclusions() -> None:
    # The second notice's scope (cold-chain) is a DIFFERENT check from
    # the session-2 re-award's evidence (customs at rev 3): a correct
    # currency diagnosis for the commit's OWN evidence stays 'current'
    # after it — and the derivation, not the notice text, decides.
    sessions = build_b2_sessions()
    s3 = sessions[2]
    currency_stage = next(st for st in s3.stages if st.stage_id == "b2-s3-followup-currency")
    spec = _precondition(currency_stage)["evidence_currency"]
    assert isinstance(spec, dict)
    assert spec["check"] == "customs-preclearance"
    # The re-award precondition demands rev-3 customs evidence (the
    # second notice did not bump it).
    reaward = next(st for st in s3.stages if st.stage_id == "b2-s3-re-award")
    assert _precondition(reaward)["current_revision"] == 3


def test_b2_carry_aware_reference_policy_passes_every_decision() -> None:
    sessions = list(build_b2_sessions())
    env = ProjectState()
    envs = [env, env, env, ProjectState()]
    budget = ToolBudget()
    registry = DocumentRegistry()
    from m2_validity_panel import _b2_policy_text, _b_decision_rules

    record = run_session_sequence(
        sessions,
        lambda state: PolicyHook(
            state,
            _b2_policy_text(),
            tool_budget=budget,
            responder=_b_responder,
            registry=registry,
        ),
        envs=envs,
        budget=budget,
        registry=registry,
        max_turns_per_stage=2,
        decision_rules=_b_decision_rules,
    )
    expected = {
        "s1_award": True,
        "s2_calibration": True,
        "s2_currency": True,
        "s2_reaward_fresh": True,
        "b2_s3_calibration": True,
        "b2_s3_currency": True,
        "b2_s3_reaward_fresh": True,
        "s4_award": True,
        "s4_calibration": True,
    }
    # The standard needles also derive (b1's own six keys stay).
    assert record.decisions.get("s1_award") is True
    for key, want in expected.items():
        assert record.decisions.get(key) is want, {
            "key": key,
            "decisions": record.decisions,
            "failure_detail": record.failure_detail,
        }
    # Every session flushed a non-empty carry (the contract ran).
    for session in record.sessions:
        assert session.persist_ok, session.persist_cause


def test_b2_double_boundary_stale_carry_is_caught() -> None:
    # The validity axis: the second boundary forces a NEW verification
    # id, exactly as the first did. A policy that tries to REFRESH the
    # session-2 evidence by re-requesting its ALREADY-ISSUED id (the
    # stale-carry move — 'my evidence exists, re-issue it') is REFUSED
    # by the env (evidence immutability), and its re-award then cites
    # a record that carries no env-issued evidence at that id: the
    # gate fails it as missing passing evidence.
    sessions = list(build_b2_sessions())
    env = ProjectState()
    envs = [env, env, env, ProjectState()]
    budget = ToolBudget()
    registry = DocumentRegistry()

    stale_reaward = """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "act_verify":
        if turn.view.stage_id == "s5-act-verify":
            return {
                "pack_text": "award",
                "actions": (
                    turn.actions.request_verification(
                        "b2-v1", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record(
                        "candidate_status", {"plan": "atlas-carriage", "domain": "shipping"}
                    ),
                    turn.actions.create_record(
                        "migration_commit", {"plan": "atlas-carriage"}
                    ),
                    turn.actions.finalize(
                        "migration_commit",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("b2-v1", "candidate_status"),
                    ),
                ),
            }
        if turn.view.stage_id == "s11-re-award":
            return {
                "pack_text": "re-award",
                "actions": (
                    turn.actions.request_verification(
                        "b2-v3", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record(
                        "corridor_reaward", {"plan": "atlas-carriage"}
                    ),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("b2-v3",),
                    ),
                ),
            }
        if turn.view.stage_id == "b2-s3-re-award":
            # The stale-carry move: re-request the session-2 evidence
            # id (the env refuses — re-verification needs a new id),
            # then commit the NEW renewal record citing only a
            # PARTICIPANT record (no env evidence for it): the gate
            # must name the missing verification.
            return {
                "pack_text": "stale re-award",
                "actions": (
                    turn.actions.request_verification(
                        "b2-v3", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record(
                        "corridor_reaward_2", {"plan": "atlas-carriage"}
                    ),
                    turn.actions.finalize(
                        "corridor_reaward_2",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("s3-status",),
                    ),
                ),
            }
        # Session 4's fresh-project award (mirror facts).
        return {
            "pack_text": "award",
            "actions": (
                turn.actions.request_verification(
                    "b2-vm", "customs-preclearance", "harborline-freight"
                ),
                turn.actions.create_record(
                    "candidate_status", {"plan": "harborline-freight", "domain": "shipping"}
                ),
                turn.actions.create_record(
                    "migration_commit", {"plan": "harborline-freight"}
                ),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": "harborline-freight", "status": "final"},
                    ("b2-vm", "candidate_status"),
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
                        "followup_conclusion-calibration", {"supplier": "vesper-instruments"}
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
    if kind == "constraint_injection":
        return {
            "pack_text": "status",
            "actions": (
                turn.actions.create_record(
                    "s3-status", {"plan": "atlas-carriage", "domain": "shipping"}
                ),
            ),
        }
    return {"pack_text": "ok"}
"""

    record = run_session_sequence(
        sessions,
        lambda state: PolicyHook(
            state, stale_reaward, tool_budget=budget, responder=_b_responder, registry=registry
        ),
        envs=envs,
        budget=budget,
        registry=registry,
        max_turns_per_stage=2,
    )
    # The session-3 re-award gate names the missing env evidence; the
    # env also REFUSED the re-request of the session-2 id (the receipt
    # the policy ignored).
    s3 = record.sessions[2]
    assert not s3.passed
    assert any(
        "lacks an environment-issued" in f or "lacks a 'customs-preclearance'" in f
        for f in s3.failures
    ), s3.failures
    # The immutability refusal is recorded: 'b2-v3' was NOT re-issued.
    assert env.records["b2-v3"]["performed_by"] == "environment"
    assert "b2-v3" in env.verification_record_ids


# ---------------------------------------------------------------------------
# c2
# ---------------------------------------------------------------------------


def test_c2_oracle_fails_the_top_two_ranked_candidates() -> None:
    s1, _ = build_c2_sessions()
    oracle = _oracle(s1.stages[2])
    assert oracle["customs-preclearance"]["atlas-carriage"] is False
    assert oracle["customs-preclearance"]["harborline-freight"] is False
    # The double-switch target passes.
    assert oracle["customs-preclearance"]["thule-carriage"] is True
    # The session-1 legal set is the THIRD carrier.
    assert _precondition(s1.stages[2])["legal_plans"] == ["thule-carriage"]


def test_c2_mutation_renews_only_one_leader() -> None:
    _s1, s2 = build_c2_sessions()
    oracle2 = _oracle(s2.stages[2])
    assert oracle2["customs-preclearance"]["atlas-carriage"] is True  # renewed
    assert oracle2["customs-preclearance"]["harborline-freight"] is False  # still pending
    assert oracle2["customs-preclearance"]["thule-carriage"] is True  # unaffected
    # The re-award legal set is the renewed leader (the SLA rule).
    assert _precondition(s2.stages[2])["legal_plans"] == ["atlas-carriage"]


def test_c2_public_rules_match_the_gate() -> None:
    # The c1 M1 pattern, on the c2 world: (a) the double-switch target
    # is READABLE MATERIAL; (b) the mutation notice's stated rule (SLA
    # rank, shortest first) plus its eligibility sentences DERIVE the
    # re-award legal set — including that harborline (the shorter-SLA
    # leader) is NOT eligible because its audit is still pending.
    s1, s2 = build_c2_sessions()
    survey_text = "\n".join(d.text for d in s1.stages[0].documents)
    assert "Supplier card: thule-carriage" in survey_text
    legal_s1 = _precondition(s1.stages[2])["legal_plans"]
    assert isinstance(legal_s1, list)
    assert set(legal_s1) <= {
        d.text.split("] ", 1)[1].split("\n", 1)[0].replace("Supplier card: ", "")
        for d in s1.stages[0].documents
        if d.text.startswith("[[doc:card-")
    }
    notice = s2.stages[1].documents[0].text
    assert "HIGHEST-ranked eligible carrier" in notice and "STANDARD SLA, shortest first" in notice
    assert "Harborline Freight's bonded audit is STILL PENDING" in notice
    assert "Thule Carriage remains eligible" in notice
    assert "HIGHEST-ranked eligible carrier" in s2.stages[2].prompt_text
    # The rule derives the legal winner: among the s2 oracle passers
    # named in the survey, ranked by stated SLA, atlas (36h) beats
    # thule (52h) — harborline is excluded by its pending status.
    import re

    cards = {
        d.text.split("] ", 1)[1].split("\n", 1)[0].replace("Supplier card: ", ""): d.text
        for d in s1.stages[0].documents
        if d.text.startswith("[[doc:card-")
    }
    slas: dict[str, int] = {}
    for name, text in cards.items():
        match = re.search(r"Standard SLA (\d+)h", text)
        if match:
            slas[name] = int(match.group(1))
    passing = [
        subject
        for subject, ok in _oracle(s2.stages[2])["customs-preclearance"].items()
        if ok and subject in slas
    ]
    ranked = sorted(passing, key=lambda name: slas[name])
    legal_s2 = _precondition(s2.stages[2])["legal_plans"]
    assert isinstance(legal_s2, list)
    assert ranked[0] == legal_s2[0] == "atlas-carriage"


def test_c2_two_legal_recovery_paths_pass_session_one() -> None:
    # Path A (read-receipt-and-switch, double): probe leader 1, fail,
    # probe leader 2, fail, switch to thule, commit.
    # Path B (verify-first): verify ALL THREE visible candidates, commit
    # the one whose receipt passes (thule).
    for policy in (_c2_recover_policy(), _c2_verify_first_policy()):
        record, env = _run_c2(policy)
        s1, s2 = record.sessions
        assert s1.passed, s1.failures
        assert s2.passed, s2.failures
        assert env.records["migration_commit"]["plan"] == "thule-carriage"
        assert env.records["corridor_reaward"]["plan"] == "atlas-carriage"


def _run_c2(policy_text: str, turns: int = 5) -> tuple[SequenceRecord, ProjectState]:
    sessions = list(build_c2_sessions())
    env = ProjectState()
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(
            state,
            policy_text,
            tool_budget=budget,
            responder=_offline_stub,
            registry=registry,
        )

    from rsicontext.lifecycle.session_sequence import run_session_sequence as _rs

    record = _rs(
        sessions,
        hook_factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=turns,
    )
    return record, env


def _offline_stub(prompt: str) -> str:
    return "notes: (stub)"


def _c2_recover_policy() -> str:
    return """
def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "act_verify":
        if turn.view.stage_id == "c2-re-award":
            return {
                "pack_text": "re-award atlas",
                "actions": (
                    turn.actions.request_verification(
                        "c2-rev", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": "atlas-carriage"}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("c2-rev",),
                    ),
                ),
            }
        seen = state.setdefault("seen_receipts", [])
        seen.extend((r.record_id, r.subject, r.verdict) for r in turn.receipts)
        known = {rid: verdict for rid, subject, verdict in seen}
        verdicts = {subject: verdict for rid, subject, verdict in seen}
        probed1 = "c2-p1" in known
        probed2 = "c2-p2" in known
        if not probed1:
            return {
                "pack_text": "probe leader 1",
                "actions": (
                    turn.actions.request_verification(
                        "c2-p1", "customs-preclearance", "atlas-carriage"
                    ),
                ),
            }
        if known.get("c2-p1") == "fail" and not probed2:
            return {
                "pack_text": "probe leader 2",
                "actions": (
                    turn.actions.request_verification(
                        "c2-p2", "customs-preclearance", "harborline-freight"
                    ),
                ),
            }
        if verdicts.get("harborline-freight") != "pass":
            if known.get("c2-p3") != "pass":
                if "c2-p3" not in known:
                    return {
                        "pack_text": "switch to thule",
                        "actions": (
                            turn.actions.request_verification(
                                "c2-p3", "customs-preclearance", "thule-carriage"
                            ),
                        ),
                    }
            if known.get("c2-p3") == "pass":
                return {
                    "pack_text": "commit thule",
                    "actions": (
                        turn.actions.create_record(
                            "candidate_status-thule",
                            {"plan": "thule-carriage", "domain": "shipping"},
                        ),
                        turn.actions.create_record(
                            "migration_commit", {"plan": "thule-carriage"}
                        ),
                        turn.actions.finalize(
                            "migration_commit",
                            {"plan": "thule-carriage", "status": "final"},
                            ("c2-p3", "candidate_status-thule"),
                        ),
                    ),
                }
        plan = "atlas-carriage" if verdicts.get("atlas-carriage") == "pass" else "thule-carriage"
        ver = "c2-p1" if verdicts.get("atlas-carriage") == "pass" else "c2-p3"
        return {
            "pack_text": "commit " + plan,
            "actions": (
                turn.actions.create_record(
                    "candidate_status-" + plan, {"plan": plan, "domain": "shipping"}
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


def _c2_verify_first_policy() -> str:
    return """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "act_verify":
        if turn.view.stage_id == "c2-re-award":
            return {
                "pack_text": "re-award atlas",
                "actions": (
                    turn.actions.request_verification(
                        "c2-vf-rev", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": "atlas-carriage"}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("c2-vf-rev",),
                    ),
                ),
            }
        seen = dict(
            (r.record_id, r.verdict) for r in turn.receipts
        )
        all_probed = "c2-vf-a" in seen and "c2-vf-h" in seen and "c2-vf-t" in seen
        if not all_probed:
            actions = []
            for rid, subject in (
                ("c2-vf-a", "atlas-carriage"),
                ("c2-vf-h", "harborline-freight"),
                ("c2-vf-t", "thule-carriage"),
            ):
                if rid not in seen and rid not in turn.state.get("requested", []):
                    actions.append(
                        turn.actions.request_verification(rid, "customs-preclearance", subject)
                    )
            requested = turn.state.setdefault("requested", [])
            for rid, subject in (
                ("c2-vf-a", "atlas-carriage"),
                ("c2-vf-h", "harborline-freight"),
                ("c2-vf-t", "thule-carriage"),
            ):
                if rid not in requested:
                    requested.append(rid)
            return {"pack_text": "verify all", "actions": tuple(actions)}
        # All three verdicts seen: commit the passer.
        if seen.get("c2-vf-t") == "pass":
            plan, ver = "thule-carriage", "c2-vf-t"
        elif seen.get("c2-vf-a") == "pass":
            plan, ver = "atlas-carriage", "c2-vf-a"
        else:
            plan, ver = "harborline-freight", "c2-vf-h"
        return {
            "pack_text": "commit " + plan,
            "actions": (
                turn.actions.create_record(
                    "candidate_status-" + plan, {"plan": plan, "domain": "shipping"}
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


def test_c2_naive_single_switch_fails() -> None:
    # The validity axis: an agent that recovers ONCE (the c1 shape —
    # switch to the second leader harborline) and commits it FAILS:
    # harborline is oracle-FAIL in session 1 too. The DOUBLE-switch is
    # forced by the world, not the policy's preference.
    naive_single_switch = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "act_verify":
        if turn.view.stage_id == "c2-re-award":
            return {
                "pack_text": "re-award",
                "actions": (
                    turn.actions.request_verification(
                        "c2-n-rev", "customs-preclearance", "atlas-carriage"
                    ),
                    turn.actions.create_record("corridor_reaward", {"plan": "atlas-carriage"}),
                    turn.actions.finalize(
                        "corridor_reaward",
                        {"plan": "atlas-carriage", "status": "final"},
                        ("c2-n-rev",),
                    ),
                ),
            }
        # Accumulate receipts in state (they drain per turn).
        seen = turn.state.setdefault("seen_receipts", {})
        for r in turn.receipts:
            seen[r.record_id] = r.verdict
        if "c2-n1" not in seen:
            return {
                "pack_text": "probe",
                "actions": (
                    turn.actions.request_verification(
                        "c2-n1", "customs-preclearance", "atlas-carriage"
                    ),
                ),
            }
        # Single switch to the SECOND leader (the c1 shape).
        plan, ver = "harborline-freight", "c2-n2"
        if "c2-n2" not in seen:
            return {
                "pack_text": "switch to second leader",
                "actions": (
                    turn.actions.request_verification(
                        "c2-n2", "customs-preclearance", "harborline-freight"
                    ),
                ),
            }
        return {
            "pack_text": "commit " + plan,
            "actions": (
                turn.actions.create_record(
                    "candidate_status-" + plan, {"plan": plan, "domain": "shipping"}
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
    record, _env = _run_c2(naive_single_switch)
    s1 = record.sessions[0]
    assert not s1.passed
    assert any(
        "lacks an environment-issued" in f or "not in the legal set" in f for f in s1.failures
    ), s1.failures


# ---------------------------------------------------------------------------
# The panel reconciliation (the M2 deliverable's acceptance)
# ---------------------------------------------------------------------------


def test_m2_panel_all_worlds_reference_solvable() -> None:
    # The reconciliation the M2 plan demands: every parent world AND
    # every eval twin is reference-solvable offline, with the audit
    # checks executed (not asserted).
    from m2_validity_panel import run_panel

    out = Path(__file__).resolve().parent.parent / "artifacts" / "rsi-core-v1"
    out.mkdir(parents=True, exist_ok=True)
    panel = run_panel(out / "m2-validity-panel.json")
    assert panel["summary"]["all_reference_solvable"] is True
    # Every world: the full decision set true, no gate failures, the
    # audit checks all ok.
    for group_id, rows in panel["groups"].items():
        assert rows, group_id
        for row in rows:
            assert row["reference_solvable"] is True, (group_id, row["world_id"])
            assert all(v for v in row["decisions"].values()), (group_id, row["world_id"])
            assert row["gate_failures"] == []
            for check in row["audit_checks"]:
                assert check["ok"], (group_id, row["world_id"], check)
    # The new parents are present; the eval twins are present.
    ids = {row["world_id"] for rows in panel["groups"].values() for row in rows}
    assert {"a-aurora-swap", "a-vector", "b-b2", "c-c2"} <= ids
    assert {"a-mirror", "b-b1-reverse", "c-c1-mirror"} <= ids


# ---------------------------------------------------------------------------
# Review-defect regressions (2026-09-24 adversarial review, defects 1-3):
# the reference workers must FOLLOW THE PROMPT, never a hardwired world
# answer.
# ---------------------------------------------------------------------------


def _vector_award_prompt(card_line: str) -> str:
    """The strong-fixed award prompt shape with one card line swapped in."""

    return (
        "Retained notes: notes: " + card_line + " | Beacon Power provides "
        "grid-tied supply for industrial sites. Pricing tier B. Their "
        "standard contract has a curtailment clause during regional "
        "shortages. Exception clause: hospital-adjacent facilities are "
        "exempt from curtailment under the mutual-aid annex, and this "
        "exemption transfers with the site's supply contract.\n"
        "notes: Pinnacle Courier runs same-day metro delivery with the "
        "newest fleet and the best headline SLA (2h) at tier B — on "
        "paper the strongest candidate. Buried condition: their customs "
        "bonding lapsed last quarter and is pending renewal, so the "
        "customs-preclearance check fails for Pinnacle Couriers until "
        "renewal completes.\n"
        "check=customs-preclearance candidate=atlas-carriage\n"
        "Constraint analysis: check=customs-preclearance candidate=atlas-carriage\n"
        "\n"
        "Name the ONE supplier to award (the one whose qualification "
        "satisfies the required check). Reply with exactly 'supplier=<id>' "
        "where <id> is the supplier's kebab-case id exactly as printed in "
        "the card headers (the id after 'Supplier card:'), and nothing else."
    )


_VECTOR_ATLAS_CARD = (
    "Atlas Carriage runs cross-border carriage with customs bonding. "
    "Standard SLA 36h. Pricing tier B. Exception clause: Atlas Carriage is "
    "the only tier-B carrier whose bonded corridor satisfies the "
    "customs-preclearance check — the corridor agreement covers all five "
    "northern checkpoints. Cold-chain exception clause: under the "
    "corridor's cold-chain-annex, Atlas Carriage's bonded corridor also "
    "satisfies the cold-chain-integrity check for the same five northern "
    "checkpoints."
)

#: The fact-swap probe (review defect 1): harborline becomes the
#: two-check winner; atlas is demoted to a one-check card.
_VECTOR_HARBORLINE_CARD = (
    "Harborline Freight runs cross-border carriage with customs bonding. "
    "Standard SLA 24h. Pricing tier A. Exception clause: Harborline "
    "Freight is the only tier-A carrier whose bonded corridor satisfies "
    "the customs-preclearance check — the corridor agreement covers all "
    "five northern checkpoints. Cold-chain exception clause: under the "
    "corridor's cold-chain-annex, Harborline Freight's bonded corridor "
    "also satisfies the cold-chain-integrity check for the same five "
    "northern checkpoints."
)

#: A one-check card: customs only — no honest two-check winner exists.
_VECTOR_ONE_CHECK_CARD = (
    "Atlas Carriage runs cross-border carriage with customs bonding. "
    "Standard SLA 36h. Pricing tier B. Exception clause: Atlas Carriage is "
    "the only tier-B carrier whose bonded corridor satisfies the "
    "customs-preclearance check — the corridor agreement covers all five "
    "northern checkpoints."
)


def test_vector_responder_follows_the_prompt_facts() -> None:
    # Defect 1 regression: the award answer is DERIVED from the card
    # text in the prompt — the mother facts name atlas, the fact-swap
    # names harborline (and a renamed variant), and a one-check corpus
    # yields the honest 'unknown'. No winner literal is hardwired
    # anywhere the worker can be probed from.
    from m2_validity_panel import _vector_responder

    assert _vector_responder(_vector_award_prompt(_VECTOR_ATLAS_CARD)) == "supplier=atlas-carriage"
    swapped = _vector_award_prompt(_VECTOR_HARBORLINE_CARD)
    assert _vector_responder(swapped) == "supplier=harborline-freight"
    renamed = swapped.replace("harborline", "aurora").replace("Harborline", "Aurora")
    assert _vector_responder(renamed) == "supplier=aurora-freight"
    assert _vector_responder(_vector_award_prompt(_VECTOR_ONE_CHECK_CARD)) == "supplier=unknown"


def test_vector_responder_fact_swap_probe_breaks_hardcoding() -> None:
    # The full reference-run level of the probe (review defect 1): a
    # fact-swapped VECTOR world — atlas FAILS customs, harborline is
    # the two-check winner, the gate re-keyed — must be solved by the
    # SAME responder; a hardcoded atlas answer would fail the swapped
    # gate ('not in the legal set').
    import dataclasses

    from m2_validity_panel import _vector_policy_text, _vector_responder

    import rsicontext.lifecycle.material_v4_dossier as dossier
    from rsicontext.lifecycle.runner import run_lifecycle

    original_suppliers = dossier._SUPPLIERS
    original_oracle = dossier._VERIFICATION_ORACLE
    original_legal = dossier._LEGAL_PLANS
    patched = []
    for supplier in original_suppliers:
        entry = dict(supplier)
        if entry["id"] == "card-03":
            entry["text"] = (
                "Atlas Carriage runs cross-border carriage with customs "
                "bonding. Standard SLA 36h. Pricing tier B. Buried "
                "condition: their customs bonding lapsed last quarter, so "
                "the customs-preclearance check fails for Atlas Carriage "
                "until renewal completes."
            )
        elif entry["id"] == "card-02":
            base = str(entry["text"]).split("Their cold-chain")[0].rstrip()
            entry["text"] = (
                base + " Exception clause: Harborline Freight is the only "
                "tier-A carrier whose bonded port-corridor satisfies the "
                "customs-preclearance check — the corridor agreement "
                "covers all five northern checkpoints. Cold-chain "
                "exception clause: under the corridor's cold-chain-annex, "
                "Harborline Freight's bonded port-corridor also satisfies "
                "the cold-chain-integrity check for the same five "
                "northern checkpoints."
            )
        patched.append(entry)
    dossier._SUPPLIERS = tuple(patched)
    dossier._VERIFICATION_ORACLE = {
        "customs-preclearance": {
            "atlas-carriage": False,
            "harborline-freight": True,
            "pinnacle-courier": False,
            "northwind-logistics": False,
        },
        "cold-chain-integrity": {
            "atlas-carriage": True,
            "delta-catering": True,
            "harborline-freight": True,
            "pinnacle-courier": False,
        },
    }
    dossier._LEGAL_PLANS = ("harborline-freight",)
    try:
        from rsicontext.lifecycle.material_m2_parents import build_vector

        swapped = build_vector(instance_id="research-v4-vector-swap-0001")
        stages = list(swapped.stages)
        s5 = stages[4]
        precondition = dict(s5.commit_precondition or {})
        precondition["legal_plans"] = ["harborline-freight"]
        precondition["plan_requirements"] = {
            "harborline-freight": {
                "domain": "shipping",
                "requires_check": ["customs-preclearance", "cold-chain-integrity"],
            }
        }
        stages[4] = s5.__class__(
            stage_id=s5.stage_id,
            kind=s5.kind,
            prompt_text=s5.prompt_text,
            documents=s5.documents,
            gold_evidence_ids=s5.gold_evidence_ids,
            expected_state_delta=s5.expected_state_delta,
            expected_aliases=s5.expected_aliases,
            commit_precondition=precondition,
            verification_oracle=s5.verification_oracle,
            rule_change_effect=s5.rule_change_effect,
            rule_change_scope=s5.rule_change_scope,
        )
        swapped = dataclasses.replace(swapped, stages=tuple(stages))
        env = ProjectState()
        budget = ToolBudget()
        hook = PolicyHook(
            {}, _vector_policy_text(), tool_budget=budget, responder=_vector_responder
        )
        hook.bind_env(env)
        record = run_lifecycle(swapped, hook, env, max_turns_per_stage=2)
        assert not any("not in the legal set" in f for f in record.final_check.failures), (
            record.final_check.failures
        )
        assert env.records["migration_commit"]["plan"] == "harborline-freight"
    finally:
        dossier._SUPPLIERS = original_suppliers
        dossier._VERIFICATION_ORACLE = original_oracle
        dossier._LEGAL_PLANS = original_legal


def test_b_responder_currency_follows_the_carried_analyses() -> None:
    # Defect 2 regression: the b2-s3 currency question is answered
    # from the analyses the prompt carries — mutation A's carried
    # 'invalidates=customs-preclearance' (in the distilled carry)
    # yields 'reverify' (the derivation for the s1 commit's rev-1
    # customs evidence), even while the CURRENT session's analysis
    # line says cold-chain. The old dead branch answered 'current'.
    from m2_validity_panel import _b_responder

    prompt = (
        "The corridor contract is up for review. Retained notes: \n"
        "Retained conclusions:\n"
        "atlas-carriage\n"
        "check=customs-preclearance candidate=atlas-carriage\n"
        "invalidates=customs-preclearance\n"
        "Rule analyses held: invalidates=cold-chain-integrity\n"
        "\n"
        "Was the award's verification evidence acquired before or after "
        "the latest rule change that affects its check? Is that evidence "
        "still current? Reply with exactly 'status=<current or reverify>'."
    )
    assert _b_responder(prompt) == "status=reverify"
    clean = prompt.replace("invalidates=customs-preclearance\n", "").replace(
        "invalidates=cold-chain-integrity", "invalidates=none"
    )
    assert _b_responder(clean) == "status=current"


def test_c_responder_reaward_follows_the_renewal_notice() -> None:
    # Defect 3 regression: the session-2 re-award answer follows the
    # RENEWAL NOTICE the prompt carries (c2's world attaches it to the
    # re-award stage and the C baseline includes stage documents) —
    # NOT the receipt order. Probing harborline first vs atlas first
    # must give the SAME answer (atlas, the renewed subject).
    from m2_validity_panel import _c_responder

    notice = (
        "Atlas Carriage's bonding audit has CLEARED: their bonded "
        "corridor now satisfies the customs-preclearance check. Prior "
        "FAILED verifications for atlas-carriage are superseded by this "
        "notice; re-verification reflects the renewed state. Harborline "
        "Freight's bonded audit is STILL PENDING — their prior failed "
        "verdicts stand. Thule Carriage remains eligible. RE-AWARD RULE: "
        "the corridor re-award goes to the HIGHEST-ranked eligible "
        "carrier — ranked by STANDARD SLA, shortest first."
    )

    def _prompt(receipts: str) -> str:
        return (
            "The corridor contract renews after a state change. Retained "
            "conclusions:\nthule-carriage\n"
            "Rule analyses held: invalidates=customs-preclearance\n"
            "Verification outcomes seen so far:\n"
            + receipts
            + "\nRenewal material attached:\n"
            + notice
            + "\n\nName the ONE supplier to verify now at the CURRENT "
            "revision (prior verdicts may be superseded). Reply with exactly "
            "'supplier=<id>' where <id> is the supplier's kebab-case id "
            "exactly as printed in the card headers (the id after "
            "'Supplier card:'), and nothing else."
        )

    harborline_first = _prompt(
        "record=r1 subject=harborline-freight verdict=fail\n"
        "record=r2 subject=atlas-carriage verdict=fail"
    )
    atlas_first = _prompt(
        "record=r1 subject=atlas-carriage verdict=fail\n"
        "record=r2 subject=harborline-freight verdict=fail"
    )
    assert _c_responder(harborline_first) == "supplier=atlas-carriage"
    assert _c_responder(atlas_first) == "supplier=atlas-carriage"
    # Without the notice (c1's shape): exactly one failed leader — the
    # receipts identify the renewed subject unambiguously.
    c1_prompt = (
        "The corridor contract renews after a state change. Retained "
        "conclusions:\nmeridian-carriage\n"
        "Rule analyses held: invalidates=customs-preclearance\n"
        "Verification outcomes seen so far:\n"
        "record=r1 subject=atlas-carriage verdict=fail\n"
        "\nName the ONE supplier to verify now at the CURRENT revision "
        "(prior verdicts may be superseded). Reply with exactly "
        "'supplier=<id>'."
    )
    assert _c_responder(c1_prompt) == "supplier=atlas-carriage"


def test_c2_reaward_stage_presents_the_renewal_notice() -> None:
    # The world-side half of defect 3: c2's re-award stage CARRIES the
    # notice (public material at the decision point) — the stage's
    # prompt text references the notice's rule, and the stage presents
    # the notice itself.
    _s1, s2 = build_c2_sessions()
    reaward = next(st for st in s2.stages if st.stage_id == "c2-re-award")
    assert reaward.documents, "the re-award stage must present the renewal notice"
    notice = reaward.documents[0].text
    assert "HIGHEST-ranked eligible carrier" in notice
    assert "STANDARD SLA, shortest first" in notice
    assert "STILL PENDING" in notice


def test_env_scope_constraint_accepts_check_lists() -> None:
    # Defect 7 (env half): a participant-declared scope constraint
    # with a LIST requires_check gets the gate's semantics — every
    # named check must appear among the referenced records. The old
    # code silently SKIPPED the list (env-side pass, gate-side
    # reject). str behavior unchanged.
    env = ProjectState()
    env.begin_instance(
        {
            "customs-preclearance": {"atlas-carriage": True},
            "cold-chain-integrity": {"atlas-carriage": True},
        }
    )
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-customs",
            fields={"check": "customs-preclearance", "subject": "atlas-carriage"},
        )
    )
    env.submit(
        Action(
            kind="create_record",
            record_id="status",
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
    # A finalize whose declared scope constraint demands BOTH checks,
    # citing only the customs one: REFUSED with the missing check named
    # (matching the evaluator gate's rule).
    receipt = env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage", "status": "final"},
            provenance=("v-customs", "status"),
            precondition_refs=("v-customs", "status"),
            precondition_scope_constraint={
                "domain": "shipping",
                "requires_check": ["customs-preclearance", "cold-chain-integrity"],
            },
        )
    )
    assert not receipt.applied
    assert "cold-chain-integrity" in receipt.cause, receipt.cause
    # With BOTH checks cited: the constraint passes.
    env.submit(
        Action(
            kind="request_verification",
            record_id="v-cold",
            fields={"check": "cold-chain-integrity", "subject": "atlas-carriage"},
        )
    )
    receipt_ok = env.submit(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"plan": "atlas-carriage", "status": "final"},
            provenance=("v-customs", "v-cold", "status"),
            precondition_refs=("v-customs", "v-cold", "status"),
            precondition_scope_constraint={
                "domain": "shipping",
                "requires_check": ["customs-preclearance", "cold-chain-integrity"],
            },
        )
    )
    assert receipt_ok.applied, receipt_ok.cause
