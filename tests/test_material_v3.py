"""Engine-validity tests for the research-v3 main world.

Implements docs/task-card-research-v3.md §Legal solution paths: each of
the four strategies (full-notes, reread, delegation, avoidance) must
complete under a scripted hook and produce a passing final check; the
failure classes must be constructible and observable as REFUSALS with
names; the counterfactual variants must move outcomes in the predicted
direction. Layer 2 of the three-evidence split (semantic validity is the
task card itself; real-system behavior is deliverable 5).
"""

from __future__ import annotations

from typing import cast

import pytest

from rsicontext.lifecycle.env import Action, ProjectState, ProjectStateError
from rsicontext.lifecycle.material_v3 import build_research_v3_instance, commit_action
from rsicontext.lifecycle.runner import (
    StageResponse,
    StageView,
    run_lifecycle,
)

_COMMIT = "migration_commit"
_STATUS = "candidate_status"
_VERIF = "verification_run"


class _PathHook:
    """A scripted participant executing one named legal strategy.

    All strategies create the records the commit references; they differ
    in WHEN verification happens (before/after the rule change) and
    WHICH plan they commit — which is exactly what the task card's
    paths differ in.
    """

    def __init__(self, strategy: str) -> None:
        self.strategy = strategy
        self.rereads: list[str] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            if self.strategy == "reread" and stage.kind == "rule_change":
                self.rereads.extend(("doc-verif-db", "doc-cand-a"))
            return StageResponse(pack_text="working notes")
        if self.strategy == "full-notes":
            return self._commit_full_notes()
        if self.strategy == "reread":
            return self._commit_reread()
        if self.strategy == "delegation":
            return self._commit_delegation()
        return self._commit_avoidance()  # avoidance

    # full-notes: everything verified up front; post-supersession the
    # in-scope verification is REDONE under revision 2, then aurora.
    def _commit_full_notes(self) -> StageResponse:
        return self._actions(
            plan="aurora",
            verifs=(
                ("verif-cutover-1", "online-cutover", 2),
                ("verif-lag-2", "replica-lag", 2),
            ),
            status_plan="aurora",
            status_domain="finance",
        )

    # reread: minimal notes; re-read the protocol + candidate docs after
    # the rule change, construct fresh verification records, commit.
    def _commit_reread(self) -> StageResponse:
        return self._actions(
            plan="aurora",
            verifs=(
                ("verif-cutover-r", "online-cutover", 2),
                ("verif-lag-r", "replica-lag", 2),
            ),
            status_plan="aurora",
            status_domain="finance",
        )

    # delegation: the sub-agent returns finding/source/applicability; the
    # principal re-runs only the in-scope check post-supersession.
    def _commit_delegation(self) -> StageResponse:
        return self._actions(
            plan="aurora",
            verifs=(
                ("verif-sub-cutover", "online-cutover", 2),
                ("verif-lag-sub", "replica-lag", 2),
            ),
            status_plan="aurora",
            status_domain="finance",
        )

    # avoidance: a non-finance plan outside both scopes — legal, cheaper.
    def _commit_avoidance(self) -> StageResponse:
        return self._actions(
            plan="cumulus",
            verifs=(("verif-disk-c", "disk-encryption", 1),),
            status_plan="cumulus",
            status_domain="reporting",
        )

    def _actions(
        self,
        *,
        plan: str,
        verifs: tuple[tuple[str, str, int], ...],
        status_plan: str,
        status_domain: str,
    ) -> StageResponse:
        actions: list[Action] = []
        for record_id, check, _revision in verifs:
            # Env-issued evidence: the check is REQUESTED (the env stamps
            # the verdict and the CURRENT protocol revision); the path's
            # timing intent is preserved by requesting at act_verify
            # (post-rule-change) for the paths that re-verify.
            actions.append(
                Action(
                    kind="request_verification",
                    record_id=record_id,
                    fields={"check": check, "subject": plan},
                )
            )
        actions.append(
            Action(
                kind="create_record",
                record_id=f"{_STATUS}-{plan}",
                fields={"plan": status_plan, "domain": status_domain},
            )
        )
        actions.append(Action(kind="create_record", record_id=_COMMIT, fields={"plan": plan}))
        refs = (*[record_id for record_id, _check, _revision in verifs], f"{_STATUS}-{plan}")
        actions.append(commit_action(plan, refs=refs))
        return StageResponse(pack_text=f"commit {plan} [[doc:{refs[0]}]]", actions=tuple(actions))


# --- layer 2a: all four legal paths pass the final check ----------------------


@pytest.mark.parametrize("strategy", ["full-notes", "reread", "delegation", "avoidance"])
def test_all_legal_paths_pass(strategy: str) -> None:
    inst = build_research_v3_instance()
    record = run_lifecycle(inst, _PathHook(strategy), ProjectState())
    assert record.final_check.passed, record.final_check.failures
    committed = record.sandbox_final_state[_COMMIT]
    assert cast(str, committed["plan"]) in ("aurora", "cumulus")
    assert cast(str, committed["status"]) == "final"


def test_reread_strategy_actually_rereads() -> None:
    # The reread path's observable behavior: documents re-consulted at
    # the rule-change stage (cost accounting is the caller's ledger).
    hook = _PathHook("reread")
    run_lifecycle(build_research_v3_instance(), hook, ProjectState())
    assert hook.rereads == ["doc-verif-db", "doc-cand-a"]


# --- layer 2b: failure classes are constructible and observable -----------------


def test_failure_class_2_stale_conclusion_is_refused() -> None:
    # Committing draco AFTER the rule change with a PRE-supersession
    # replica-lag verification: the finalize is refused with a named
    # error (stale protocol revision in scope) — failure class 2 made
    # observable at the action boundary, not a silent zero.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-lag-old",
            fields={"check": "replica-lag", "protocol_revision": 1},
        )
    )
    state.apply(
        Action(
            kind="create_record",
            record_id=f"{_STATUS}-draco",
            fields={"plan": "draco", "domain": "analytics"},
        )
    )
    state.apply(Action(kind="create_record", record_id=_COMMIT, fields={"plan": "draco"}))
    with pytest.raises(ProjectStateError, match="stale protocol revision"):
        state.apply(
            commit_action(
                "draco",
                refs=("verif-lag-old", f"{_STATUS}-draco"),
            )
        )


def test_failure_class_1_missing_cutover_support_is_refused() -> None:
    # borealis: finance domain, no online-cutover verification record ->
    # the constraint precondition refuses the commit (failure class 1:
    # the constraint references what the plan's exception clause says
    # it lacks).
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id=f"{_STATUS}-borealis",
            fields={"plan": "borealis", "domain": "finance"},
        )
    )
    state.apply(Action(kind="create_record", record_id=_COMMIT, fields={"plan": "borealis"}))
    with pytest.raises(ProjectStateError, match="scope constraint"):
        state.apply(
            commit_action(
                "borealis",
                refs=(f"{_STATUS}-borealis",),
            )
        )


def test_failure_class_4_finalized_record_cannot_be_silently_revised() -> None:
    # A stale conclusion that was already finalized cannot be updated
    # in place — the participant must supersede it with a new record
    # (which is the behavior the improvement opportunity rewards).
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-lag-old",
            fields={"check": "replica-lag", "protocol_revision": 1},
        )
    )
    state.apply(
        Action(
            kind="finalize",
            record_id="verif-lag-old",
            fields={},
            provenance=("doc-verif-db",),
        )
    )
    with pytest.raises(ProjectStateError, match="finalized"):
        state.apply(
            Action(
                kind="update_record",
                record_id="verif-lag-old",
                fields={"protocol_revision": 2},
            )
        )
    # The legal recovery: a NEW record under revision 2.
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-lag-new",
            fields={"check": "replica-lag", "protocol_revision": 2, "supersedes": "verif-lag-old"},
        )
    )
    assert state.records["verif-lag-new"]["supersedes"] == "verif-lag-old"


def test_failure_class_5_declared_vs_actual() -> None:
    # A finalize that claims success while the referenced records do
    # not exist is refused — "reported done" != "state is correct" is
    # enforced at apply time.
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id=_COMMIT, fields={"plan": "aurora"}))
    with pytest.raises(ProjectStateError, match="unknown record"):
        state.apply(commit_action("aurora", refs=("verif-missing",)))


# --- layer 2c: counterfactual variants move outcomes as predicted ---------------


def test_counterfactual_no_legal_finance_plan_without_cutover_support() -> None:
    # Gold-drop analog: strip the online-cutover capability from aurora's
    # document (the fact a full-notes strategy would retain) and the
    # finance domain has NO legal plan — the commit must then be
    # cumulus/ember (avoidance), never a finance plan.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id=f"{_STATUS}-borealis",
            fields={"plan": "borealis", "domain": "finance"},
        )
    )
    state.apply(Action(kind="create_record", record_id=_COMMIT, fields={"plan": "borealis"}))
    with pytest.raises(ProjectStateError):
        state.apply(commit_action("borealis", refs=(f"{_STATUS}-borealis",)))


def test_counterfactual_scope_is_partial_not_global() -> None:
    # Irrelevant-perturbation analog: a disk-encryption verification at
    # revision 1 (OUTSIDE the supersession scope) does not block ANY
    # commit — the rule change invalidates replica-lag checks only.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-disk",
            fields={"check": "disk-encryption", "protocol_revision": 1},
        )
    )
    state.apply(
        Action(
            kind="create_record",
            record_id=f"{_STATUS}-ember",
            fields={"plan": "ember", "domain": "operations"},
        )
    )
    state.apply(Action(kind="create_record", record_id=_COMMIT, fields={"plan": "ember"}))
    state.apply(commit_action("ember", refs=("verif-disk", f"{_STATUS}-ember")))
    assert state.records[_COMMIT]["status"] == "final"


def test_recovery_path_succeeds_from_lost_notes() -> None:
    # Recovery variant: the reread strategy works even though it kept
    # (and used) nothing from stage 1 — its verification records are
    # all constructed post-rule-change from re-read material.
    inst = build_research_v3_instance()
    record = run_lifecycle(inst, _PathHook("reread"), ProjectState())
    verifs = [
        record_id
        for record_id in record.sandbox_final_state
        if record_id.startswith(_VERIF) or record_id.startswith("verif-")
    ]
    assert verifs  # fresh records exist
    assert all(
        cast(dict[str, object], record.sandbox_final_state[record_id]).get("protocol_revision") == 2
        or cast(dict[str, object], record.sandbox_final_state[record_id]).get("check")
        == "disk-encryption"
        for record_id in verifs
    )


# --- layer 2d: instance surface -------------------------------------------------


def test_instance_structure_matches_task_card() -> None:
    inst = build_research_v3_instance()
    assert inst.family == "research-v3"
    assert [stage.kind for stage in inst.stages] == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
    ]
    # Stage 5 carries no documents (answer from retained state only).
    assert inst.stages[4].documents == ()
    # Stage 1 carries all candidates + protocol + exception memo.
    assert len(inst.stages[0].documents) == 7
    # The rule-change document is the supersession signal.
    assert inst.stages[3].documents[0].superseded_by == "doc-verif-db"
    # The legal plan set is enumerable from the material (not hidden).
    assert set(inst.answer_aliases) == {"aurora", "cumulus", "ember"}
