from __future__ import annotations

from dataclasses import replace

import pytest

from rsicontext.experiment.a2 import build_a2_pilot_plan
from rsicontext.experiment.a2_controller import A2LaunchError, A2LaunchRequest, launch_a2_pilot
from rsicontext.experiment.ledger import SpendCaps


def _caps() -> SpendCaps:
    return SpendCaps(
        max_reader_calls=10_720,
        max_reader_input_tokens=200_000_000,
        max_cost_usd=50.0,
        max_gpu_seconds=200_000.0,
        max_wall_seconds=300_000.0,
        max_retries=20,
    )


def test_a2_launch_refuses_the_legacy_fixed_budget_schema() -> None:
    plan = build_a2_pilot_plan(
        researchers=("codex-gpt-5.6-sol", "claude-opus"),
        task_profiles=("compositional_multihop", "dense_global_comparison"),
        seeds=(17, 29),
    )
    request = A2LaunchRequest(
        plan=plan,
        caps=_caps(),
        landscape_passed=True,
        isolation_formal=True,
        difficulty_profiles_passed=plan.task_profiles,
    )

    with pytest.raises(A2LaunchError, match="legacy fixed-budget"):
        launch_a2_pilot(request)
    assert plan.qualification_only is True


def test_a2_launch_refuses_a_failed_landscape_before_execution() -> None:
    plan = replace(
        build_a2_pilot_plan(
            researchers=("codex-gpt-5.6-sol", "claude-opus"),
            task_profiles=("compositional_multihop", "dense_global_comparison"),
            seeds=(17, 29),
        ),
        qualification_only=False,
    )
    request = A2LaunchRequest(
        plan=plan,
        caps=_caps(),
        landscape_passed=False,
        isolation_formal=True,
        difficulty_profiles_passed=plan.task_profiles,
    )

    with pytest.raises(A2LaunchError, match="legacy fixed-budget"):
        launch_a2_pilot(request)


def test_a2_launch_refuses_missing_isolation_and_stays_disabled() -> None:
    plan = replace(
        build_a2_pilot_plan(
            researchers=("codex-gpt-5.6-sol", "claude-opus"),
            task_profiles=("compositional_multihop", "dense_global_comparison"),
            seeds=(17, 29),
        ),
        qualification_only=False,
    )
    missing_isolation = A2LaunchRequest(
        plan=plan,
        caps=_caps(),
        landscape_passed=True,
        isolation_formal=False,
        difficulty_profiles_passed=plan.task_profiles,
    )
    ready = A2LaunchRequest(
        plan=plan,
        caps=_caps(),
        landscape_passed=True,
        isolation_formal=True,
        difficulty_profiles_passed=plan.task_profiles,
    )

    with pytest.raises(A2LaunchError, match="legacy fixed-budget"):
        launch_a2_pilot(missing_isolation)
    with pytest.raises(A2LaunchError, match="legacy fixed-budget"):
        launch_a2_pilot(ready)
