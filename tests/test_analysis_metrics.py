from __future__ import annotations

import math

import pytest

from rsicontext.analysis.metrics import (
    Outcome,
    calibration_metrics,
    replay_summary,
    retention_summary,
    trajectory_metrics,
)


def test_replay_summary_uses_population_noise_floor() -> None:
    summary = replay_summary([0.4, 0.5, 0.6])

    assert summary.mean == pytest.approx(0.5)
    assert summary.standard_deviation == pytest.approx(math.sqrt(0.02 / 3))
    assert summary.span == pytest.approx(0.2)


def test_trajectory_metrics_distinguish_discovery_and_retention() -> None:
    metrics = trajectory_metrics([0.40, 0.55, 0.52, 0.49])

    assert metrics.discovery_gain == pytest.approx(0.15)
    assert metrics.peak_round == 1
    assert metrics.last_minus_peak == pytest.approx(-0.06)
    assert metrics.post_peak_regression is True


def test_retention_summary_matches_rsibench_data_denominator() -> None:
    summary = retention_summary(
        (
            (0.2, 0.5, 0.4),
            (0.3, 0.6, 0.6),
            (0.4, 0.7),
        )
    )
    assert summary.n_continued_after_peak == 2
    assert summary.n_end_below_peak == 1
    assert summary.n_recover_peak == 1
    assert summary.fraction_end_below_peak == pytest.approx(0.5)


def test_calibration_rewards_correct_probabilities() -> None:
    perfect = calibration_metrics(
        [(0.99, 0.005, 0.005), (0.005, 0.005, 0.99)],
        [Outcome.IMPROVE, Outcome.REGRESS],
    )
    vague = calibration_metrics(
        [(1 / 3, 1 / 3, 1 / 3), (1 / 3, 1 / 3, 1 / 3)],
        [Outcome.IMPROVE, Outcome.REGRESS],
    )

    assert perfect.brier_score < vague.brier_score
    assert perfect.log_loss < vague.log_loss


def test_calibration_probability_order_matches_manifest_schema() -> None:
    unchanged = calibration_metrics([(0.0, 1.0, 0.0)], [Outcome.UNCHANGED])
    regress = calibration_metrics([(0.0, 0.0, 1.0)], [Outcome.REGRESS])

    assert unchanged.log_loss == 0.0
    assert regress.log_loss == 0.0


def test_calibration_rejects_invalid_probability_simplex() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        calibration_metrics([(0.8, 0.2, 0.1)], [Outcome.UNCHANGED])
