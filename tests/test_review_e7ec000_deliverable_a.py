"""Deliverable A regression tests (external review of e7ec000, 2026-09-22).

The review's attack paths, executed and pinned: a self-declared final
status, garbage provenance, self-filled verification records, and stale
pre-rule-change evidence must ALL fail the evaluator's gate; the honest
path (environment-requested verification) must pass. Feedback isolation,
world-identity recording, author-draw attempt logs, zephyr's
constraint-evaluator correspondence, and snapshot digest integrity are
pinned alongside.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest
import trajectory_v3 as t3

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.runner import LifecycleRunRecord, StageResponse, StageView, run_lifecycle
from rsicontext.participant.snapshot import (
    BranchKind,
    FrozenSnapshot,
    SnapshotStateError,
    run_evaluation_branch,
)


class _CommitOnlyHook:
    """Emits the given actions at act_verify; notes otherwise."""

    def __init__(self, actions_fn: Callable[[], Sequence[Action]]) -> None:
        self.actions_fn = actions_fn

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            return StageResponse(pack_text="notes")
        return StageResponse(pack_text="commit", actions=tuple(self.actions_fn()))


def _run(actions_fn: Callable[[], Sequence[Action]]) -> LifecycleRunRecord:
    return run_lifecycle(build_research_v3_instance(), _CommitOnlyHook(actions_fn), ProjectState())


# --- The review's attack paths (external review §2.2) ------------------------------


def test_self_declared_final_status_fails() -> None:
    # P1: bare create_record with status="final" — a claim, not a state.
    record = _run(
        lambda: [
            Action(
                kind="create_record",
                record_id="migration_commit",
                fields={"plan": "ember", "status": "final"},
            )
        ]
    )
    assert not record.final_check.passed
    assert any("never finalized through the environment" in f for f in record.final_check.failures)


def test_garbage_provenance_fails() -> None:
    # P2: a finalize citing a record that does not exist.
    record = _run(
        lambda: [
            Action(kind="create_record", record_id="migration_commit", fields={"plan": "ember"}),
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("totally-fake-ref",),
            ),
        ]
    )
    assert not record.final_check.passed
    assert any("does not exist in the sandbox" in f for f in record.final_check.failures)


def test_self_filled_verification_records_do_not_count() -> None:
    # P3: participant-written check/protocol_revision records are data,
    # not evidence — the required verification must be env-issued.
    record = _run(
        lambda: [
            Action(
                kind="create_record",
                record_id="v1",
                fields={"check": "online-cutover", "protocol_revision": 2},
            ),
            Action(
                kind="create_record",
                record_id="v2",
                fields={"check": "replica-lag", "protocol_revision": 2},
            ),
            Action(kind="create_record", record_id="migration_commit", fields={"plan": "aurora"}),
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("v1", "v2"),
            ),
        ]
    )
    assert not record.final_check.passed
    assert any("lacks" in f and "verification" in f for f in record.final_check.failures)


def test_honest_env_requested_verification_passes() -> None:
    # P8: request the verifications through the environment; cite them.
    record = _run(
        lambda: [
            Action(
                kind="request_verification",
                record_id="verif-cutover",
                fields={"check": "online-cutover", "subject": "aurora"},
            ),
            Action(
                kind="request_verification",
                record_id="verif-lag",
                fields={"check": "replica-lag", "subject": "aurora"},
            ),
            Action(kind="create_record", record_id="migration_commit", fields={"plan": "aurora"}),
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("verif-cutover", "verif-lag"),
            ),
        ]
    )
    assert record.final_check.passed, record.final_check.failures


class _EarlyEvidenceHook:
    """Requests verification BEFORE the rule change, cites it after."""

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind == "constraint_injection":
            return StageResponse(
                pack_text="notes",
                actions=(
                    Action(
                        kind="request_verification",
                        record_id="verif-lag-early",
                        fields={"check": "replica-lag", "subject": "aurora"},
                    ),
                ),
            )
        if stage.kind != "act_verify":
            return StageResponse(pack_text="notes")
        return StageResponse(
            pack_text="commit",
            actions=(
                Action(
                    kind="request_verification",
                    record_id="verif-cutover",
                    fields={"check": "online-cutover", "subject": "aurora"},
                ),
                Action(
                    kind="create_record", record_id="migration_commit", fields={"plan": "aurora"}
                ),
                Action(
                    kind="finalize",
                    record_id="migration_commit",
                    fields={"status": "final"},
                    provenance=("verif-cutover", "verif-lag-early"),
                ),
            ),
        )


def test_pre_rule_change_evidence_is_revision_stale() -> None:
    # P9: the env stamps the revision it executed under; in-scope checks
    # requested before the rule change are stale for scoped plans.
    record = run_lifecycle(build_research_v3_instance(), _EarlyEvidenceHook(), ProjectState())
    assert not record.final_check.passed
    assert any("stale" in f for f in record.final_check.failures)


def test_environment_verification_records_carry_provenance_fields() -> None:
    # The env's records bind check, subject, verdict, revision, issuer.
    env = ProjectState()
    env.begin_instance({"genre": {"aurora": True}})
    env.apply(
        Action(
            kind="request_verification",
            record_id="v",
            fields={"check": "genre", "subject": "aurora"},
        )
    )
    assert env.records["v"] == {
        "check": "genre",
        "subject": "aurora",
        "verdict": "pass",
        "protocol_revision": 1,
        "performed_by": "environment",
    }
    assert "v" in env.verification_record_ids


def test_uncovered_verification_request_is_unverifiable_not_a_crash() -> None:
    # A wrong check list is a recorded outcome, not a mid-run abort.
    env = ProjectState()
    env.begin_instance({"genre": {"aurora": True}})
    env.apply(
        Action(
            kind="request_verification",
            record_id="v",
            fields={"check": "no-such-check", "subject": "aurora"},
        )
    )
    assert env.records["v"]["verdict"] == "unverifiable"


def test_request_verification_shape_is_validated() -> None:
    # The request names WHAT to verify; outcome fields are not writable.
    with pytest.raises(ValueError):
        Action(
            kind="request_verification",
            record_id="v",
            fields={"check": "genre", "verdict": "pass"},
        )
    with pytest.raises(ValueError):
        Action(kind="request_verification", record_id="v", fields={"check": "genre"})


# --- Feedback isolation + world identity (external review §2.3, §4.1) --------------


def test_dev_feedback_excludes_heldout_world_failures() -> None:
    # The probe feeds the researcher from DEV-distribution surfaces; the
    # new_world branch it reports must not run held-out Option-2 worlds.
    # The pool constant is the pin: the dev pool is disjoint from the
    # evaluation pool.
    assert set(t3._DEV_UNSEEN_POOL).isdisjoint(t3._OPTION2_IDS)


def test_world_identity_records_material_hash() -> None:
    inst = build_research_v3_instance()
    identity = t3._world_identity(inst)
    assert identity["instance_id"].startswith("research-v3-")
    assert len(identity["material_sha256"]) == 16
    other = t3._world_identity(build_research_v3_instance())
    assert identity == other  # deterministic for the same material


def test_zephyr_constraint_has_no_unimplemented_clause() -> None:
    # External review 3.4: the post-1990 clause had no evaluator
    # counterpart; the constraint text must now match the derived legal
    # set exactly (genre-only).
    from rsicontext.lifecycle.material_v3_segment import build_option2_world

    inst = build_option2_world("zephyr")
    constraint_doc = inst.stages[1].documents[0]
    assert "1990" not in constraint_doc.text
    precondition = inst.stages[4].commit_precondition
    assert precondition is not None
    assert precondition["legal_plans"] == [
        "play-the-game",
        "ill-be-there",
        "no-direction-home",
        "this-love",
    ]


# --- Snapshot digest integrity (external review §4.4) ------------------------------


def _tiny_snapshot() -> FrozenSnapshot:
    return FrozenSnapshot.from_parts(
        participant_id="p",
        snapshot_id="S",
        memory={"notes": ["a"]},
        code_files={},
        skill_files={},
        schema={},
        byte_cap=1000,
    )


def test_in_place_snapshot_mutation_refuses_to_serve_carry() -> None:
    snapshot = _tiny_snapshot()
    notes = snapshot.memory["notes"]
    assert isinstance(notes, list)
    notes.append("tampered")  # in-place, post-freeze
    with pytest.raises(SnapshotStateError):
        run_evaluation_branch(
            snapshot,
            BranchKind.CONTINUATION,
            "probe-session",
            instances=[build_research_v3_instance()],
            hook_factory=lambda state, carry: _CommitOnlyHook(lambda: ()),
            byte_cap=1000,
        )


def test_untouched_snapshot_still_serves_carry() -> None:
    snapshot = _tiny_snapshot()
    record = run_evaluation_branch(
        snapshot,
        BranchKind.CONTINUATION,
        "probe-session-2",
        instances=[build_research_v3_instance()],
        hook_factory=lambda state, carry: _CommitOnlyHook(lambda: ()),
        byte_cap=1000,
    )
    assert record.snapshot_digest == snapshot.digest


# --- Reference / fixed / scripted arms on the main world (wiring) ------------------


def test_reference_and_strategy_arms_on_main_world() -> None:
    ref = run_lifecycle(build_research_v3_instance(), t3.ReferenceHook(), ProjectState())
    assert ref.final_check.passed, ref.final_check.failures
    offline_answers = {
        "Constraint": "finance-domain plans must support online cutover.",
        "Rule change": "revision supersedes the replica-lag check only.",
        "Survey": "aurora finance online cutover; borealis; cumulus; draco; ember.",
    }
    fixed = run_lifecycle(
        build_research_v3_instance(),
        t3.TrajectoryHook({}, offline=True, offline_answers=offline_answers),
        ProjectState(),
    )
    assert not fixed.final_check.passed  # the designed control: stale evidence
    scripted = run_lifecycle(
        build_research_v3_instance(),
        t3.TrajectoryHook(
            {}, offline=True, offline_answers=offline_answers, strategy_text=t3._SCRIPTED_STRATEGY
        ),
        ProjectState(),
    )
    assert scripted.final_check.passed, scripted.final_check.failures


def test_author_failure_attempt_log_is_preserved() -> None:
    # The failure path copies exc.attempts (the review's 4.3: author draws
    # lost their per-attempt reliability record). Shape test via the
    # module's own exception contract.
    exc = t3.ResearcherRoundFailure([{"attempt": 1, "outcome": "empty_content"}])
    assert isinstance(exc.attempts, list) and exc.attempts[0]["outcome"] == "empty_content"


def test_pass_fraction_scores_crashed_cells_as_zero() -> None:
    # P7 / Rethinking rule (spec Part 2.2): a crashed cell must never
    # silently leave the denominator (1 crash + 1 pass was 1.0 before).
    results = {
        "new_world": [
            {"ran": False, "error": "boom"},
            {"final_checks": [{"passed": True, "failures": []}]},
        ]
    }
    assert t3._pass_fraction(results) == 0.5
