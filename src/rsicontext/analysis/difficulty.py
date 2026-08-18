"""Pre-registered acceptance gate for hard-context task profiles."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _rate(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be finite and within [0, 1]")
    return numeric


def _named_rates(values: tuple[tuple[str, float], ...], field: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field} must be a non-empty tuple")
    names: list[str] = []
    for name, value in values:
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field} names must be non-empty")
        _rate(value, field)
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError(f"{field} names must be unique")


@dataclass(frozen=True, slots=True)
class DifficultyMeasurements:
    profile: str
    chance_accuracy: float
    gold_only_accuracy: float
    bounded_oracle_accuracy: float
    no_context_accuracy: float
    non_oracle_scores: tuple[tuple[str, float], ...]
    strongest_policy_disagreement: float
    gold_drop: float
    counterfactual_following: float
    stratum_scores: tuple[tuple[str, float], ...]
    replay_standard_deviation: float
    median_meaningful_delta: float

    def __post_init__(self) -> None:
        if not isinstance(self.profile, str) or not self.profile:
            raise ValueError("profile must be non-empty")
        for field in (
            "chance_accuracy",
            "gold_only_accuracy",
            "bounded_oracle_accuracy",
            "no_context_accuracy",
            "strongest_policy_disagreement",
            "gold_drop",
            "counterfactual_following",
        ):
            _rate(getattr(self, field), field)
        _named_rates(self.non_oracle_scores, "non_oracle_scores")
        _named_rates(self.stratum_scores, "stratum_scores")
        for field in ("replay_standard_deviation", "median_meaningful_delta"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field} must be finite and non-negative")
        if self.median_meaningful_delta <= 0:
            raise ValueError("median_meaningful_delta must be positive")


@dataclass(frozen=True, slots=True)
class DifficultyGateResult:
    profile: str
    passed: bool
    failures: tuple[str, ...]


def evaluate_difficulty(measurements: DifficultyMeasurements) -> DifficultyGateResult:
    """Apply thresholds fixed before a disposable calibration panel is scored."""
    failures: list[str] = []
    if measurements.gold_only_accuracy < 0.85:
        failures.append("gold-only accuracy is below 0.85")
    if measurements.bounded_oracle_accuracy < 0.80:
        failures.append("bounded oracle accuracy is below 0.80")
    no_context_ceiling = max(measurements.chance_accuracy + 0.05, 0.10)
    if measurements.no_context_accuracy > no_context_ceiling:
        failures.append("no-context accuracy exceeds its shortcut ceiling")

    non_oracle = tuple(score for _, score in measurements.non_oracle_scores)
    strongest = max(non_oracle)
    if not 0.25 <= strongest <= 0.75:
        failures.append("strongest non-oracle policy is outside [0.25, 0.75]")
    if strongest >= 0.90:
        failures.append("a non-oracle fixed policy saturates at or above 0.90")
    if strongest - min(non_oracle) < 0.20:
        failures.append("fixed-policy range is below 0.20")
    if measurements.strongest_policy_disagreement < 0.20:
        failures.append("strongest-policy item disagreement is below 0.20")
    if measurements.gold_drop < 0.40:
        failures.append("gold-drop decrease is below 0.40")
    if measurements.counterfactual_following < 0.80:
        failures.append("counterfactual answer-following is below 0.80")
    if any(score in {0.0, 1.0} for _, score in measurements.stratum_scores):
        failures.append("at least one task stratum is entirely correct or entirely wrong")
    noise_ceiling = 0.20 * measurements.median_meaningful_delta
    if measurements.replay_standard_deviation >= noise_ceiling or math.isclose(
        measurements.replay_standard_deviation, noise_ceiling, rel_tol=1e-12, abs_tol=1e-12
    ):
        failures.append("replay noise is not below 20% of the meaningful policy delta")
    return DifficultyGateResult(
        profile=measurements.profile,
        passed=not failures,
        failures=tuple(failures),
    )


def clone_aware_item_disagreement(ranked_vectors: tuple[tuple[float, ...], ...]) -> float:
    """Fraction of items where the two strongest *distinct* score vectors differ.

    Policies that match an earlier vector are grammar clones and are skipped.
    One distinct behavior in the search space scores 0.
    """

    if not ranked_vectors:
        raise ValueError("ranked_vectors must be non-empty")
    distinct: list[tuple[float, ...]] = []
    for vector in ranked_vectors:
        if not vector:
            raise ValueError("score vectors must be non-empty")
        if vector in distinct:
            continue
        if distinct and len(vector) != len(distinct[0]):
            raise ValueError("score vectors must be aligned")
        distinct.append(vector)
        if len(distinct) == 2:
            first, second = distinct
            return sum(left != right for left, right in zip(first, second, strict=True)) / len(
                first
            )
    return 0.0
