"""Pre-registered T0 gate for public long-context cells.

Synthetic hop thresholds in ``evaluate_difficulty`` stay attached to the homemade
32K panel. Public cells use this contract: packing must be binding, the answer
must exist in the source, and a non-oracle packer must not already place it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rsicontext.analysis.difficulty import DifficultyGateResult, clone_aware_item_disagreement


def _rate(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be finite and within [0, 1]")
    return numeric


@dataclass(frozen=True, slots=True)
class PublicOfflineMeasurements:
    """Tokenizer-only screen committed before any public-cell reader landscape."""

    cell_id: str
    n_items: int
    pack_budget_tokens: int
    median_source_tokens: float
    pack_binding_rate: float
    answer_in_source_rate: float
    packer_answer_rates: tuple[tuple[str, float], ...]
    packer_answer_disagreement: float

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not self.cell_id.strip():
            raise ValueError("cell_id must be a non-empty string")
        if not isinstance(self.n_items, int) or isinstance(self.n_items, bool) or self.n_items < 1:
            raise ValueError("n_items must be a positive integer")
        if (
            not isinstance(self.pack_budget_tokens, int)
            or isinstance(self.pack_budget_tokens, bool)
            or self.pack_budget_tokens < 1
        ):
            raise ValueError("pack_budget_tokens must be a positive integer")
        if (
            isinstance(self.median_source_tokens, bool)
            or not isinstance(self.median_source_tokens, (int, float))
            or not math.isfinite(self.median_source_tokens)
            or self.median_source_tokens <= 0
        ):
            raise ValueError("median_source_tokens must be a positive finite number")
        _rate(self.pack_binding_rate, "pack_binding_rate")
        _rate(self.answer_in_source_rate, "answer_in_source_rate")
        _rate(self.packer_answer_disagreement, "packer_answer_disagreement")
        if not self.packer_answer_rates:
            raise ValueError("packer_answer_rates must be non-empty")
        names: list[str] = []
        for name, value in self.packer_answer_rates:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("packer names must be non-empty")
            _rate(value, f"packer_answer_rates[{name}]")
            names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("packer names must be unique")


def evaluate_public_offline_difficulty(
    measurements: PublicOfflineMeasurements,
) -> DifficultyGateResult:
    """Kill public cells that are identity maps or already solved by packing."""

    failures: list[str] = []
    if measurements.n_items < 16:
        failures.append("public T0 cell has fewer than 16 items")
    if measurements.median_source_tokens <= measurements.pack_budget_tokens:
        failures.append("median source does not exceed the pack budget")
    if measurements.pack_binding_rate < 0.95:
        failures.append("pack is not binding on at least 95% of items")
    if measurements.answer_in_source_rate < 0.90:
        failures.append("answer is missing from the source on too many items")
    rates = tuple(score for _, score in measurements.packer_answer_rates)
    strongest = max(rates)
    weakest = min(rates)
    if strongest >= 0.90:
        failures.append("a non-oracle packer already places the answer on >=90% of items")
    if strongest - weakest < 0.20:
        failures.append("packer answer-in-pack range is below 0.20")
    if measurements.packer_answer_disagreement < 0.20:
        failures.append("packer item disagreement is below 0.20")
    return DifficultyGateResult(
        profile=measurements.cell_id,
        passed=not failures,
        failures=tuple(failures),
    )


def packer_item_disagreement(vectors: tuple[tuple[float, ...], ...]) -> float:
    """Disagreement among packer answer-in-pack indicator vectors."""

    return clone_aware_item_disagreement(vectors)


def answer_in_haystack(haystack: str, answer: str) -> bool:
    """Case-insensitive substring check used by the public packing screen."""

    if not isinstance(haystack, str):
        raise TypeError("haystack must be a string")
    if not isinstance(answer, str) or not answer:
        raise ValueError("answer must be a non-empty string")
    return answer.casefold() in haystack.casefold()


@dataclass(frozen=True, slots=True)
class PublicReaderMeasurements:
    """Reader landscape committed after a public cell passes the offline screen."""

    cell_id: str
    n_items: int
    gold_only_accuracy: float
    no_context_accuracy: float
    packer_scores: tuple[tuple[str, float], ...]
    packer_disagreement: float
    replay_standard_deviation: float
    median_meaningful_delta: float

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not self.cell_id.strip():
            raise ValueError("cell_id must be a non-empty string")
        if not isinstance(self.n_items, int) or isinstance(self.n_items, bool) or self.n_items < 1:
            raise ValueError("n_items must be a positive integer")
        _rate(self.gold_only_accuracy, "gold_only_accuracy")
        _rate(self.no_context_accuracy, "no_context_accuracy")
        _rate(self.packer_disagreement, "packer_disagreement")
        if not self.packer_scores:
            raise ValueError("packer_scores must be non-empty")
        names: list[str] = []
        for name, value in self.packer_scores:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("packer names must be non-empty")
            _rate(value, f"packer_scores[{name}]")
            names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("packer names must be unique")
        for field in ("replay_standard_deviation", "median_meaningful_delta"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field} must be finite and non-negative")
        if self.median_meaningful_delta <= 0:
            raise ValueError("median_meaningful_delta must be positive")


def evaluate_public_reader_difficulty(
    measurements: PublicReaderMeasurements,
) -> DifficultyGateResult:
    """Kill public cells the frozen reader cannot use or that packing already solves."""

    failures: list[str] = []
    if measurements.n_items < 16:
        failures.append("public T0 reader cell has fewer than 16 items")
    if measurements.gold_only_accuracy < 0.85:
        failures.append("gold-only accuracy is below 0.85")
    if measurements.no_context_accuracy > 0.10:
        failures.append("no-context accuracy exceeds 0.10")
    scores = tuple(score for _, score in measurements.packer_scores)
    strongest = max(scores)
    weakest = min(scores)
    if not 0.25 <= strongest <= 0.75:
        failures.append("strongest non-oracle packer is outside [0.25, 0.75]")
    if strongest >= 0.90:
        failures.append("a non-oracle packer saturates at or above 0.90")
    if strongest - weakest < 0.20:
        failures.append("packer score range is below 0.20")
    if measurements.packer_disagreement < 0.20:
        failures.append("packer item disagreement is below 0.20")
    noise_ceiling = 0.20 * measurements.median_meaningful_delta
    if measurements.replay_standard_deviation >= noise_ceiling or math.isclose(
        measurements.replay_standard_deviation, noise_ceiling, rel_tol=1e-12, abs_tol=1e-12
    ):
        failures.append("replay noise is not below 20% of the meaningful packer delta")
    return DifficultyGateResult(
        profile=measurements.cell_id,
        passed=not failures,
        failures=tuple(failures),
    )
