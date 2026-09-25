"""Source-independent checks for the optional cross-session prior evidence gate."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.spec import DescriptionAxes, LifecycleInstance, StageSpec

_PRIOR = "migration_commit"
_LATER = "query_text_rollout"
_PRIOR_CHECK = "dual-emission"
_LATER_CHECK = "query-text-safety"
_GOOD_PRIOR = "database/dup"
_LATER_PLAN = "hold-raw-enable-parameterized"


def _verify(record_id: str, check: str, subject: str) -> Action:
    return Action("request_verification", record_id, {"check": check, "subject": subject})


def _seed_prior(
    *, plan: str = _GOOD_PRIOR, verdict: bool | None = True, forged: bool = False
) -> ProjectState:
    env = ProjectState()
    env.begin_instance({_PRIOR_CHECK: {plan: bool(verdict)}})
    if forged:
        env.submit(
            Action(
                "create_record",
                "prior-v",
                {
                    "check": _PRIOR_CHECK,
                    "subject": plan,
                    "verdict": "pass",
                    "performed_by": "environment",
                },
            )
        )
    elif verdict is not None:
        env.submit(_verify("prior-v", _PRIOR_CHECK, plan))
    env.submit(Action("create_record", _PRIOR, {"plan": plan}))
    env.submit(Action("finalize", _PRIOR, {"status": "final"}, ("prior-v",)))
    assert _PRIOR in env.finalized_record_ids
    assert env.records[_PRIOR]["finalized"] is True
    return env


def _later_world(*, bind_plan: bool = True) -> LifecycleInstance:
    prior_rule: dict[str, object] = {"check": _PRIOR_CHECK, "plan_field": "plan"}
    if bind_plan:
        prior_rule["allowed_later_plans"] = {_GOOD_PRIOR: [_LATER_PLAN]}
    return LifecycleInstance(
        instance_id="test-prior-verification-session-two",
        family="research-v5",
        stages=(
            StageSpec("resume", "session_start", "Resume the same project.", (), ()),
            StageSpec(
                "later-award",
                "act_verify",
                "Finalize the later plan after a passing verification.",
                (),
                (),
                expected_state_delta={_LATER: {"status": "final"}},
                commit_precondition={
                    "record_id": _LATER,
                    "prior_finalized_record": _PRIOR,
                    "prior_verification": prior_rule,
                    "plan_field": "plan",
                    "legal_plans": [_LATER_PLAN],
                    "plan_requirements": {_LATER_PLAN: {"requires_check": _LATER_CHECK}},
                },
                verification_oracle={
                    _PRIOR_CHECK: {_GOOD_PRIOR: True, "database": True},
                    _LATER_CHECK: {_LATER_PLAN: True},
                },
            ),
        ),
        axes=DescriptionAxes(1, 1, 1, "strong", 0),
        answer_norm=_LATER_PLAN,
        sandbox_spec={"records": [_PRIOR, _LATER]},
    )


def _first_world() -> LifecycleInstance:
    return LifecycleInstance(
        instance_id="test-prior-verification-session-one",
        family="research-v5",
        stages=(
            StageSpec(
                "first-award",
                "act_verify",
                "Finalize the initial plan after verification.",
                (),
                (),
                expected_state_delta={_PRIOR: {"status": "final"}},
                commit_precondition={
                    "record_id": _PRIOR,
                    "plan_field": "plan",
                    "legal_plans": [_GOOD_PRIOR],
                    "plan_requirements": {_GOOD_PRIOR: {"requires_check": _PRIOR_CHECK}},
                },
                verification_oracle={_PRIOR_CHECK: {_GOOD_PRIOR: True}},
            ),
        ),
        axes=DescriptionAxes(1, 1, 1, "strong", 0),
        answer_norm=_GOOD_PRIOR,
        sandbox_spec={"records": [_PRIOR]},
    )


class _LaterHook:
    def __init__(self, *, late_prior: bool = False) -> None:
        self.late_prior = late_prior
        self.views: list[StageView] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        self.views.append(stage)
        if stage.kind == "session_start" and self.late_prior:
            return StageResponse(
                "Try to backfill prior evidence", (_verify("prior-v", _PRIOR_CHECK, _GOOD_PRIOR),)
            )
        if stage.kind == "act_verify":
            return StageResponse(
                "Finalize later plan",
                (
                    _verify("later-v", _LATER_CHECK, _LATER_PLAN),
                    Action("create_record", _LATER, {"plan": _LATER_PLAN}),
                    Action("finalize", _LATER, {"status": "final"}, ("later-v",)),
                ),
            )
        return StageResponse("No action")


def test_prior_environment_pass_allows_later_plan_without_view_leak() -> None:
    hook = _LaterHook()
    result = run_lifecycle(_later_world(), hook, _seed_prior())
    assert result.final_check.passed, result.final_check.failures
    assert all(not hasattr(view, "commit_precondition") for view in hook.views)
    assert all(not hasattr(view, "verification_oracle") for view in hook.views)


def test_failed_prior_receipt_force_finalized_still_blocks_later_gate() -> None:
    # R5 OTel bypass: finalize after a failed environment receipt. Its
    # first-session gate fails, but the old later gate saw only the prior
    # finalized ID and incorrectly passed.
    env = _seed_prior(verdict=False)
    assert env.records["prior-v"]["verdict"] == "fail"
    result = run_lifecycle(_later_world(), _LaterHook(), env)
    assert not result.final_check.passed
    assert any("prior" in failure and "PASS" in failure for failure in result.final_check.failures)


def test_late_backfill_cannot_satisfy_prior_evidence_gate() -> None:
    # The prior finalized record cites a future ID. Supplying a PASS at
    # session 2's first stage must not retroactively validate it.
    env = _seed_prior(verdict=None)
    assert "prior-v" not in env.verification_record_ids
    result = run_lifecycle(_later_world(), _LaterHook(late_prior=True), env)
    assert env.records["prior-v"]["verdict"] == "pass"
    assert not result.final_check.passed
    assert any("prior" in failure and "PASS" in failure for failure in result.final_check.failures)


def test_prior_pass_issued_after_earlier_finalize_cannot_validate_later_gate() -> None:
    class _OutOfOrderFirst:
        def on_stage(self, _stage: StageView) -> StageResponse:
            return StageResponse(
                "Cite a future verification before requesting it",
                (
                    Action("create_record", _PRIOR, {"plan": _GOOD_PRIOR}),
                    Action("finalize", _PRIOR, {"status": "final"}, ("prior-v",)),
                    _verify("prior-v", _PRIOR_CHECK, _GOOD_PRIOR),
                ),
            )

    env = ProjectState()
    first = run_lifecycle(_first_world(), _OutOfOrderFirst(), env)
    # The shared gate grades evidence as it existed at finalization, even
    # though both actions occurred before end-of-stage grading.
    assert not first.final_check.passed
    assert any("verification" in failure for failure in first.final_check.failures)
    assert [action.kind for action in env.transcript] == [
        "create_record",
        "finalize",
        "request_verification",
    ]
    assert env.records["prior-v"]["verdict"] == "pass"
    second = run_lifecycle(_later_world(), _LaterHook(), env)
    assert not second.final_check.passed
    assert any("prior" in failure and "PASS" in failure for failure in second.final_check.failures)


def test_forged_prior_pass_record_is_not_environment_evidence() -> None:
    env = _seed_prior(forged=True)
    assert "prior-v" not in env.verification_record_ids
    result = run_lifecycle(_later_world(), _LaterHook(), env)
    assert not result.final_check.passed
    assert any("prior" in failure and "PASS" in failure for failure in result.final_check.failures)


@pytest.mark.parametrize(
    ("check", "subject"),
    [("other-check", _GOOD_PRIOR), (_PRIOR_CHECK, "database")],
)
def test_prior_pass_must_match_check_and_prior_plan(check: str, subject: str) -> None:
    env = ProjectState()
    env.begin_instance({check: {subject: True}})
    env.submit(_verify("prior-v", check, subject))
    env.submit(Action("create_record", _PRIOR, {"plan": _GOOD_PRIOR}))
    env.submit(Action("finalize", _PRIOR, {"status": "final"}, ("prior-v",)))
    result = run_lifecycle(_later_world(), _LaterHook(), env)
    assert not result.final_check.passed
    assert any("prior" in failure and "PASS" in failure for failure in result.final_check.failures)


def test_prior_plan_mapping_blocks_wrong_prior_plan() -> None:
    env = _seed_prior(plan="database")
    assert env.records["prior-v"]["verdict"] == "pass"
    result = run_lifecycle(_later_world(), _LaterHook(), env)
    assert not result.final_check.passed
    assert any("prior plan" in failure for failure in result.final_check.failures)


def test_prior_plan_mapping_can_be_omitted_for_receipt_only_worlds() -> None:
    env = _seed_prior(plan="database")
    result = run_lifecycle(_later_world(bind_plan=False), _LaterHook(), env)
    assert result.final_check.passed, result.final_check.failures


def test_prior_verification_on_unsupported_followup_is_rejected() -> None:
    world = _later_world()
    follow = StageSpec(
        "unsupported-followup",
        "follow_up",
        "A follow-up cannot silently ignore a prior verification gate.",
        (),
        (),
        expected_state_delta={"note": {"status": "final"}},
        commit_precondition={
            "prior_finalized_record": _PRIOR,
            "prior_verification": {"check": _PRIOR_CHECK, "plan_field": "plan"},
        },
    )
    with pytest.raises(ValueError, match="act_verify stages only"):
        run_lifecycle(replace(world, stages=(*world.stages, follow)), _LaterHook(), _seed_prior())


@pytest.mark.parametrize("kind", ["update_record", "finalize"])
def test_environment_issued_verification_record_is_not_participant_writable(
    kind: Literal["update_record", "finalize"],
) -> None:
    env = ProjectState()
    env.begin_instance({_PRIOR_CHECK: {_GOOD_PRIOR: True}})
    env.submit(_verify("prior-v", _PRIOR_CHECK, _GOOD_PRIOR))
    before = env.snapshot()["prior-v"]
    if kind == "update_record":
        action = Action(kind, "prior-v", {"verdict": "fail", "subject": "database"})
    else:
        action = Action(kind, "prior-v", {"status": "final"}, ("prior-v",))
    receipt = env.submit(action)
    assert not receipt.applied
    assert "environment-issued verification" in receipt.cause
    assert env.records["prior-v"] == before
    assert "prior-v" in env.verification_record_ids
