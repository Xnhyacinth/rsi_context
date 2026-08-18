from __future__ import annotations

import pytest

from rsicontext.experiment.a2 import A2PilotPlan, build_a2_pilot_plan


def _plan() -> A2PilotPlan:
    return build_a2_pilot_plan(
        researchers=("codex-gpt-5.6-sol", "claude-opus"),
        task_profiles=("compositional_multihop", "dense_global_comparison"),
        seeds=(17, 29),
    )


def test_a2_plan_materializes_the_preregistered_factorial() -> None:
    plan = _plan()

    assert len(plan.cells) == 8
    assert len({cell.cell_id for cell in plan.cells}) == 8
    assert {cell.research_seed for cell in plan.cells} == {17, 29}
    assert {cell.rounds for cell in plan.cells} == {5}
    assert plan.researcher_turns == 40
    assert plan.prediction_triples == 1_600
    assert plan.primary_estimand == (
        "gate_score_of_visible_selected_researcher_minus_visible_selected_control"
    )


def test_a2_plan_projects_nominal_successful_matrix_calls_before_execution() -> None:
    budget = _plan().target_call_projection

    assert budget.researcher_visible == 1_920
    assert budget.researcher_gate == 320
    assert budget.matched_control_visible == 1_600
    assert budget.matched_control_gate == 320
    assert budget.reference_visible == 1_280
    assert budget.reference_gate == 1_280
    assert budget.replay == 4_000
    assert budget.total_nominal == 10_720


def test_a2_plan_hash_is_stable_and_sensitive_to_scientific_inputs() -> None:
    first = _plan()
    same = _plan()
    changed = build_a2_pilot_plan(
        researchers=("codex-gpt-5.6-sol", "claude-opus"),
        task_profiles=("compositional_multihop", "dense_global_comparison"),
        seeds=(17, 29),
        items_per_split=44,
    )

    assert first.plan_sha256 == same.plan_sha256
    assert first.plan_sha256 != changed.plan_sha256
    serialized = first.to_dict()
    assert serialized["qualification_only"] is True
    assert serialized["research_seeds"] == [17, 29]
    assert "dataset_seeds" not in serialized
    assert serialized["selection_rule"] == "visible_historical_best"
    assert serialized["gate_evaluations_per_arm"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("researchers", ("codex",)),
        ("task_profiles", ("sparse", "sparse")),
        ("seeds", (1, 1)),
        ("rounds", 4),
        ("items_per_split", 0),
    ],
)
def test_a2_plan_rejects_incomplete_or_post_hoc_matrix_changes(field: str, value: object) -> None:
    arguments: dict[str, object] = {
        "researchers": ("codex", "claude"),
        "task_profiles": ("sparse", "dense"),
        "seeds": (1, 2),
    }
    arguments[field] = value

    with pytest.raises((TypeError, ValueError)):
        build_a2_pilot_plan(**arguments)  # type: ignore[arg-type]
