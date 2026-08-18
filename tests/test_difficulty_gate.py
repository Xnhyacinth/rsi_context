from __future__ import annotations

from dataclasses import replace

import pytest

from rsicontext.analysis.difficulty import (
    DifficultyMeasurements,
    clone_aware_item_disagreement,
    evaluate_difficulty,
)


def _passing() -> DifficultyMeasurements:
    return DifficultyMeasurements(
        profile="compositional_multihop",
        chance_accuracy=0.0,
        gold_only_accuracy=0.90,
        bounded_oracle_accuracy=0.85,
        no_context_accuracy=0.05,
        non_oracle_scores=(
            ("head", 0.30),
            ("head-tail", 0.45),
            ("lexical", 0.65),
        ),
        strongest_policy_disagreement=0.25,
        gold_drop=0.55,
        counterfactual_following=0.85,
        stratum_scores=(
            ("head", 0.75),
            ("middle", 0.50),
            ("tail", 0.25),
            ("distributed", 0.50),
        ),
        replay_standard_deviation=0.01,
        median_meaningful_delta=0.10,
    )


def test_difficulty_gate_accepts_only_a_dynamic_causal_low_noise_profile() -> None:
    result = evaluate_difficulty(_passing())

    assert result.passed is True
    assert result.failures == ()
    assert result.profile == "compositional_multihop"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"gold_only_accuracy": 0.84}, "gold-only"),
        ({"bounded_oracle_accuracy": 0.79}, "bounded oracle"),
        ({"no_context_accuracy": 0.11}, "no-context"),
        ({"non_oracle_scores": (("a", 0.10), ("b", 0.20))}, "strongest non-oracle"),
        ({"non_oracle_scores": (("a", 0.60), ("b", 0.61))}, "policy range"),
        ({"strongest_policy_disagreement": 0.19}, "disagreement"),
        ({"gold_drop": 0.39}, "gold-drop"),
        ({"counterfactual_following": 0.79}, "counterfactual"),
        ({"stratum_scores": (("head", 1.0), ("tail", 0.5))}, "stratum"),
        ({"replay_standard_deviation": 0.02}, "replay noise"),
    ],
)
def test_difficulty_gate_reports_each_preregistered_failure(
    change: dict[str, object], message: str
) -> None:
    result = evaluate_difficulty(replace(_passing(), **change))  # type: ignore[arg-type]

    assert result.passed is False
    assert any(message in failure for failure in result.failures)


def test_clone_aware_disagreement_skips_identical_score_vectors() -> None:
    clones_then_distinct = ((1.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0))
    assert clone_aware_item_disagreement(clones_then_distinct) == pytest.approx(2 / 3)
    assert clone_aware_item_disagreement(((1.0, 0.0), (1.0, 0.0))) == 0.0


def test_clone_aware_disagreement_rejects_empty_or_misaligned_vectors() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        clone_aware_item_disagreement(())
    with pytest.raises(ValueError, match="aligned"):
        clone_aware_item_disagreement(((1.0, 0.0), (1.0,)))


def test_difficulty_measurements_reject_invalid_or_duplicate_inputs() -> None:
    with pytest.raises(ValueError, match="unique"):
        replace(_passing(), non_oracle_scores=(("same", 0.4), ("same", 0.5)))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        replace(_passing(), gold_drop=1.1)
    with pytest.raises(ValueError, match="positive"):
        replace(_passing(), median_meaningful_delta=0.0)
