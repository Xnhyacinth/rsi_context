from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    IMPROVE = "improve"
    REGRESS = "regress"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    repetitions: int
    mean: float
    standard_deviation: float
    span: float


@dataclass(frozen=True, slots=True)
class TrajectoryMetrics:
    first_score: float
    peak_score: float
    last_score: float
    peak_round: int
    discovery_gain: float
    last_minus_peak: float
    post_peak_regression: bool


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    count: int
    brier_score: float
    log_loss: float
    expected_calibration_error: float


def replay_summary(scores: Sequence[float]) -> ReplaySummary:
    if not scores:
        raise ValueError("at least one replay score is required")
    return ReplaySummary(
        repetitions=len(scores),
        mean=statistics.fmean(scores),
        standard_deviation=statistics.pstdev(scores),
        span=max(scores) - min(scores),
    )


def trajectory_metrics(scores: Sequence[float]) -> TrajectoryMetrics:
    if not scores:
        raise ValueError("at least one trajectory score is required")
    peak_score = max(scores)
    peak_round = scores.index(peak_score)
    last_score = scores[-1]
    return TrajectoryMetrics(
        first_score=scores[0],
        peak_score=peak_score,
        last_score=last_score,
        peak_round=peak_round,
        discovery_gain=peak_score - scores[0],
        last_minus_peak=last_score - peak_score,
        post_peak_regression=peak_round < len(scores) - 1 and last_score < peak_score,
    )


@dataclass(frozen=True, slots=True)
class RetentionSummary:
    """RSIBench-Data-style peak retention over a set of trajectories."""

    n_trajectories: int
    n_continued_after_peak: int
    n_end_below_peak: int
    n_recover_peak: int

    @property
    def fraction_end_below_peak(self) -> float:
        if self.n_continued_after_peak == 0:
            return 0.0
        return self.n_end_below_peak / self.n_continued_after_peak


def retention_summary(trajectories: Sequence[Sequence[float]]) -> RetentionSummary:
    """Among searches that continue after a peak, how often the final score is worse.

    Matches RSIBench-Data's discovery-reliability split: continued-after-peak runs
    either end below the peak or only recover it.
    """

    if not trajectories:
        raise ValueError("at least one trajectory is required")
    continued = 0
    below = 0
    recover = 0
    for scores in trajectories:
        if not scores:
            raise ValueError("trajectory scores must be non-empty")
        peak = max(scores)
        peak_round = list(scores).index(peak)
        if peak_round >= len(scores) - 1:
            continue
        continued += 1
        if scores[-1] < peak:
            below += 1
        else:
            recover += 1
    return RetentionSummary(
        n_trajectories=len(trajectories),
        n_continued_after_peak=continued,
        n_end_below_peak=below,
        n_recover_peak=recover,
    )


def calibration_metrics(
    probabilities: Sequence[tuple[float, float, float]],
    outcomes: Sequence[Outcome],
    *,
    bins: int = 10,
) -> CalibrationMetrics:
    """Score triples ordered as ``(improve, unchanged, regress)`` like manifests."""
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have equal non-zero length")
    if bins <= 0:
        raise ValueError("bins must be positive")

    encoded = [_outcome_index(outcome) for outcome in outcomes]
    brier_total = 0.0
    log_total = 0.0
    confidence_bins: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    epsilon = 1e-15

    for prediction, observed in zip(probabilities, encoded, strict=True):
        _validate_probability_simplex(prediction)
        target = (float(observed == 0), float(observed == 1), float(observed == 2))
        brier_total += sum(
            (predicted - actual) ** 2 for predicted, actual in zip(prediction, target, strict=True)
        )
        log_total -= math.log(max(prediction[observed], epsilon))
        predicted_class = max(range(3), key=prediction.__getitem__)
        confidence = prediction[predicted_class]
        bin_index = min(int(confidence * bins), bins - 1)
        confidence_bins[bin_index].append((confidence, predicted_class == observed))

    count = len(probabilities)
    ece = 0.0
    for entries in confidence_bins:
        if entries:
            mean_confidence = statistics.fmean(confidence for confidence, _ in entries)
            accuracy = statistics.fmean(float(correct) for _, correct in entries)
            ece += len(entries) / count * abs(accuracy - mean_confidence)

    return CalibrationMetrics(
        count=count,
        brier_score=brier_total / count,
        log_loss=log_total / count,
        expected_calibration_error=ece,
    )


UNIFORM_COMPARATOR = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
ALWAYS_UNCHANGED_COMPARATOR = (0.0, 1.0, 0.0)


def leave_one_trajectory_out_base_rate(
    outcomes_by_trajectory: Mapping[str, Sequence[Outcome]],
    held_out: str,
) -> tuple[float, float, float]:
    """Empirical (improve, unchanged, regress) rates excluding one trajectory."""

    if held_out not in outcomes_by_trajectory:
        raise KeyError("held-out trajectory is not present")
    counts = [0, 0, 0]
    for trajectory_id, outcomes in outcomes_by_trajectory.items():
        if trajectory_id == held_out:
            continue
        if not outcomes:
            raise ValueError("trajectory outcomes must be non-empty")
        for outcome in outcomes:
            counts[_outcome_index(outcome)] += 1
    total = sum(counts)
    if total == 0:
        raise ValueError("leave-one-trajectory-out requires at least one other trajectory")
    return (counts[0] / total, counts[1] / total, counts[2] / total)


def _outcome_index(outcome: Outcome) -> int:
    return {
        Outcome.IMPROVE: 0,
        Outcome.UNCHANGED: 1,
        Outcome.REGRESS: 2,
    }[outcome]


def _validate_probability_simplex(prediction: tuple[float, float, float]) -> None:
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in prediction):
        raise ValueError("probabilities must lie in [0, 1]")
    if not math.isclose(sum(prediction), 1.0, abs_tol=1e-9):
        raise ValueError("probabilities must sum to one")
