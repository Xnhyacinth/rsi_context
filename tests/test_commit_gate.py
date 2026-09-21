"""Evaluator-side commit-legality gate for research-v3.

The final check must fail an ILLEGAL commit even when the participant's
own finalize Action carried no preconditions (the opt-in gap).

Before this gate, a participant could finalize ``migration_commit`` with
plan "borealis" (finance domain, no online-cutover support) or with
stale-protocol evidence via a PLAIN finalize (no precondition fields,
which are participant-emitted and opt-in) and still pass the
ObjectiveChecker, because the v3 expected_state_delta only checked
``status == "final"``. Legality lived only in the participant's own
Action preconditions — the checker trusted the participant's framing.
The fix is evaluator-owned: the act_verify StageSpec carries a
``commit_precondition`` (evaluator-only, excluded from StageView like
the other evaluator fields), and ``run_lifecycle`` checks it against
the sandbox's ACTUAL records after the stages run, adding named
failures to the final CheckResult.
"""

from __future__ import annotations

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle


class _PlainCommitHook:
    """Commits a named plan via a PLAIN finalize (no Action preconditions).

    This is the adversarial shape the evaluator-side gate must catch:
    the participant's finalize carries no opt-in preconditions, so only
    the evaluator's own check over the sandbox records can fail it.
    """

    def __init__(self, plan: str, verif_revision: int = 1, with_cutover: bool = True) -> None:
        self.plan = plan
        self.verif_revision = verif_revision
        self.with_cutover = with_cutover

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            return StageResponse(pack_text="notes")
        domain = "finance" if self.plan in ("aurora", "borealis") else "other"
        actions: list[Action] = []
        if self.with_cutover:
            actions.append(
                Action(
                    kind="create_record",
                    record_id="verif-cutover",
                    fields={"check": "online-cutover", "protocol_revision": 2},
                )
            )
        actions.extend(
            (
                Action(
                    kind="create_record",
                    record_id="verif-lag",
                    fields={"check": "replica-lag", "protocol_revision": self.verif_revision},
                ),
                Action(
                    kind="create_record",
                    record_id=f"candidate_status-{self.plan}",
                    fields={"plan": self.plan, "domain": domain},
                ),
                Action(
                    kind="create_record", record_id="migration_commit", fields={"plan": self.plan}
                ),
                Action(
                    kind="finalize",
                    record_id="migration_commit",
                    fields={"status": "final"},
                    provenance=("verif-lag", f"candidate_status-{self.plan}")
                    + (("verif-cutover",) if self.with_cutover else ()),
                ),
            )
        )
        return StageResponse(pack_text=f"plain commit {self.plan}", actions=tuple(actions))


def test_illegal_plan_plain_finalize_fails_final_check() -> None:
    # borealis: finance domain, no online-cutover support -> the final
    # check must FAIL on the evaluator's own commit gate, even though
    # the participant's finalize carried no preconditions.
    record = run_lifecycle(
        build_research_v3_instance(), _PlainCommitHook("borealis"), ProjectState()
    )
    assert not record.final_check.passed
    assert any("commit gate" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )
    assert any("borealis" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_legal_plan_with_stale_evidence_fails_final_check() -> None:
    # aurora (legal plan) but the replica-lag verification is revision 1
    # (stale after the rule change): the evaluator gate must fail it.
    record = run_lifecycle(
        build_research_v3_instance(),
        _PlainCommitHook("aurora", verif_revision=1),
        ProjectState(),
    )
    assert not record.final_check.passed
    assert any("commit gate" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )
    assert any("stale" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_legal_plan_with_current_evidence_passes() -> None:
    # aurora with revision-2 evidence and the cutover check: passes both
    # the evaluator gate and the state delta.
    record = run_lifecycle(
        build_research_v3_instance(),
        _PlainCommitHook("aurora", verif_revision=2),
        ProjectState(),
    )
    assert record.final_check.passed, record.final_check.failures


def test_legal_plan_missing_cutover_check_fails() -> None:
    # aurora committed without the online-cutover verification record:
    # the finance-domain constraint is unsatisfied.
    record = run_lifecycle(
        build_research_v3_instance(),
        _PlainCommitHook("aurora", verif_revision=2, with_cutover=False),
        ProjectState(),
    )
    assert not record.final_check.passed
    assert any("commit gate" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_unknown_plan_fails_commit_gate() -> None:
    # A plan outside the derived legal set entirely.
    record = run_lifecycle(build_research_v3_instance(), _PlainCommitHook("zed"), ProjectState())
    assert not record.final_check.passed
    assert any("commit gate" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_v1_v2_instances_unaffected_by_the_gate() -> None:
    # No commit_precondition on v1/v2 act_verify stages -> the gate is a
    # no-op there and the final check is exactly the ObjectiveChecker's
    # state-delta result (backward compatibility pinned).
    from rsicontext.lifecycle.material_v2 import build_research_v2_instance

    row = {
        "id": 101,
        "question": "What genre is Alpha?",
        "possible_answers": '["alpha rock", "alpha rock music"]',
        "ctxs": [
            {
                "id": "101-gold",
                "title": "Gold source alpha",
                "text": "The verified answer is alpha rock.",
                "score": 0.71,
                "has_answer": True,
            },
            {
                "id": "101-noise-1",
                "title": "Noise doc one",
                "text": "Unrelated filler passage.",
                "score": 0.66,
                "has_answer": False,
            },
        ],
    }
    inst = build_research_v2_instance(row, world_id="w1", variant_label="a", noise_positions=[1])
    record = run_lifecycle(inst, _V2PassHook(), ProjectState())
    # The v2 final check fires exactly as before: no gate failures.
    assert all("commit gate" not in failure for failure in record.final_check.failures)


class _V2PassHook:
    """Advances a v2 lifecycle without committing (gate is a no-op anyway)."""

    def on_stage(self, stage: StageView) -> StageResponse:
        return StageResponse(pack_text="v2 notes [[doc:doc-101-gold-0]]")
