"""Aggregate-only qualification for causal MuSiQue long-context construction."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from rsicontext.analysis.difficulty import DifficultyGateResult
from rsicontext.datasets.musique import MuSiQueEvaluatorItem, MuSiQueRecord

_SHA256_CHARACTERS = frozenset("0123456789abcdef")


def _rate(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be finite and within [0, 1]")
    return numeric


def _positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256_digest(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class MuSiQueOfflineMeasurements:
    """Dataset-level evidence that contains no item identifiers or labels."""

    n_items: int
    duplicate_item_ids: int
    hop_counts: tuple[tuple[int, int], ...]
    pack_budget_tokens: int
    source_token_min: int
    source_token_median: float
    source_token_p95: int
    source_token_max: int
    pack_binding_rate: float
    answer_in_support_rate: float
    answer_in_nonsupport_rate: float
    intermediate_answers_in_support_rate: float
    intermediate_answers_in_nonsupport_rate: float
    source_sha256: str
    official_source_sha256: str | None
    source_revision: str
    tokenizer_id: str

    def __post_init__(self) -> None:
        _positive_integer(self.n_items, "n_items")
        if (
            not isinstance(self.duplicate_item_ids, int)
            or isinstance(self.duplicate_item_ids, bool)
            or self.duplicate_item_ids < 0
        ):
            raise ValueError("duplicate_item_ids must be a non-negative integer")
        if not isinstance(self.hop_counts, tuple) or not self.hop_counts:
            raise ValueError("hop_counts must be a non-empty immutable tuple")
        hops: list[int] = []
        total = 0
        for hop_count, item_count in self.hop_counts:
            hops.append(_positive_integer(hop_count, "hop count"))
            total += _positive_integer(item_count, "hop item count")
        if hops != sorted(set(hops)):
            raise ValueError("hop counts must be unique and sorted")
        if total != self.n_items:
            raise ValueError("hop counts must sum to n_items")
        _positive_integer(self.pack_budget_tokens, "pack_budget_tokens")
        source_tokens = (
            _positive_integer(self.source_token_min, "source_token_min"),
            self.source_token_median,
            _positive_integer(self.source_token_p95, "source_token_p95"),
            _positive_integer(self.source_token_max, "source_token_max"),
        )
        if (
            isinstance(self.source_token_median, bool)
            or not isinstance(self.source_token_median, (int, float))
            or not math.isfinite(self.source_token_median)
            or self.source_token_median <= 0
        ):
            raise ValueError("source_token_median must be a positive finite number")
        if tuple(float(value) for value in source_tokens) != tuple(
            sorted(float(value) for value in source_tokens)
        ):
            raise ValueError("source token statistics must be non-decreasing")
        _rate(self.pack_binding_rate, "pack_binding_rate")
        _rate(self.answer_in_support_rate, "answer_in_support_rate")
        _rate(self.answer_in_nonsupport_rate, "answer_in_nonsupport_rate")
        _rate(self.intermediate_answers_in_support_rate, "intermediate_answers_in_support_rate")
        _rate(
            self.intermediate_answers_in_nonsupport_rate,
            "intermediate_answers_in_nonsupport_rate",
        )
        _sha256_digest(self.source_sha256, "source_sha256")
        if self.official_source_sha256 is not None:
            _sha256_digest(self.official_source_sha256, "official_source_sha256")
        if not isinstance(self.source_revision, str) or not self.source_revision:
            raise ValueError("source_revision must be non-empty")
        if not isinstance(self.tokenizer_id, str) or not self.tokenizer_id:
            raise ValueError("tokenizer_id must be non-empty")

    @property
    def official_source_byte_match(self) -> bool:
        """Whether independently hashed mirror and official member bytes match."""

        return (
            self.official_source_sha256 is not None
            and self.source_sha256 == self.official_source_sha256
        )


def _contains_reference(text: str, references: Iterable[str]) -> bool:
    normalized = " ".join(text.split()).casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(' '.join(reference.split()).casefold())}(?!\w)", normalized)
        is not None
        for reference in references
    )


def measure_musique_records(
    records: Iterable[MuSiQueRecord],
    *,
    token_counter: Callable[[str], int],
    pack_budget_tokens: int,
    source_sha256: str,
    source_revision: str,
    official_source_sha256: str | None,
    tokenizer_id: str,
) -> MuSiQueOfflineMeasurements:
    """Measure one complete source split without retaining item-level labels."""

    _positive_integer(pack_budget_tokens, "pack_budget_tokens")
    seen_ids: set[str] = set()
    duplicate_item_ids = 0
    hop_counts: Counter[int] = Counter()
    source_tokens: list[int] = []
    answer_in_support = 0
    answer_in_nonsupport = 0
    intermediate_answers_in_support = 0
    intermediate_answers_in_nonsupport = 0
    for record in records:
        if record.item_id in seen_ids:
            duplicate_item_ids += 1
        seen_ids.add(record.item_id)
        hop_counts[len(record.steps)] += 1
        support_text = "\n\n".join(
            f"{paragraph.title}\n{paragraph.text}"
            for paragraph in record.paragraphs
            if paragraph.is_supporting
        )
        nonsupport_text = "\n\n".join(
            f"{paragraph.title}\n{paragraph.text}"
            for paragraph in record.paragraphs
            if not paragraph.is_supporting
        )
        source = support_text + "\n\n" + nonsupport_text
        token_count = token_counter(source)
        source_tokens.append(_positive_integer(token_count, "target tokenizer count"))
        final_references = (record.answer, *record.answer_aliases)
        intermediate_references = tuple(step.answer for step in record.steps[:-1])
        answer_in_support += int(_contains_reference(support_text, final_references))
        answer_in_nonsupport += int(_contains_reference(nonsupport_text, final_references))
        intermediate_answers_in_support += int(
            all(
                _contains_reference(support_text, (reference,))
                for reference in intermediate_references
            )
        )
        intermediate_answers_in_nonsupport += int(
            _contains_reference(nonsupport_text, intermediate_references)
        )
    if not source_tokens:
        raise ValueError("MuSiQue qualification requires at least one record")
    ordered = sorted(source_tokens)
    n_items = len(ordered)
    p95_index = math.ceil(0.95 * n_items) - 1
    return MuSiQueOfflineMeasurements(
        n_items=n_items,
        duplicate_item_ids=duplicate_item_ids,
        hop_counts=tuple(sorted(hop_counts.items())),
        pack_budget_tokens=pack_budget_tokens,
        source_token_min=ordered[0],
        source_token_median=float(statistics.median(ordered)),
        source_token_p95=ordered[p95_index],
        source_token_max=ordered[-1],
        pack_binding_rate=sum(value > pack_budget_tokens for value in ordered) / n_items,
        answer_in_support_rate=answer_in_support / n_items,
        answer_in_nonsupport_rate=answer_in_nonsupport / n_items,
        intermediate_answers_in_support_rate=intermediate_answers_in_support / n_items,
        intermediate_answers_in_nonsupport_rate=intermediate_answers_in_nonsupport / n_items,
        source_sha256=source_sha256,
        official_source_sha256=official_source_sha256,
        source_revision=source_revision,
        tokenizer_id=tokenizer_id,
    )


def measure_musique_evaluator_items(
    items: Iterable[MuSiQueEvaluatorItem],
    *,
    pack_budget_tokens: int,
    source_sha256: str,
    source_revision: str,
    official_source_sha256: str | None,
    tokenizer_id: str,
) -> MuSiQueOfflineMeasurements:
    """Measure packed evaluator items while retaining no item-level labels."""

    _positive_integer(pack_budget_tokens, "pack_budget_tokens")
    seen_ids: set[str] = set()
    duplicate_item_ids = 0
    hop_counts: Counter[int] = Counter()
    source_tokens: list[int] = []
    answer_in_support = 0
    answer_in_nonsupport = 0
    intermediate_answers_in_support = 0
    intermediate_answers_in_nonsupport = 0
    for item in items:
        item_id = item.policy_item.item_id
        if item_id in seen_ids:
            duplicate_item_ids += 1
        seen_ids.add(item_id)
        hop_counts[len(item.steps)] += 1
        chunks = item.policy_item.artifact.chunks
        source_tokens.append(sum(chunk.token_count for chunk in chunks))
        support_text = "\n".join(
            chunk.text for chunk in chunks if chunk.chunk_id in item.gold_chunk_ids
        )
        nonsupport_text = "\n".join(
            chunk.text for chunk in chunks if chunk.chunk_id not in item.gold_chunk_ids
        )
        intermediate_references = tuple(step.answer for step in item.steps[:-1])
        answer_in_support += int(_contains_reference(support_text, item.references))
        answer_in_nonsupport += int(_contains_reference(nonsupport_text, item.references))
        intermediate_answers_in_support += int(
            all(
                _contains_reference(support_text, (reference,))
                for reference in intermediate_references
            )
        )
        intermediate_answers_in_nonsupport += int(
            _contains_reference(nonsupport_text, intermediate_references)
        )
    if not source_tokens:
        raise ValueError("packed MuSiQue qualification requires at least one item")
    ordered = sorted(source_tokens)
    n_items = len(ordered)
    p95_index = math.ceil(0.95 * n_items) - 1
    return MuSiQueOfflineMeasurements(
        n_items=n_items,
        duplicate_item_ids=duplicate_item_ids,
        hop_counts=tuple(sorted(hop_counts.items())),
        pack_budget_tokens=pack_budget_tokens,
        source_token_min=ordered[0],
        source_token_median=float(statistics.median(ordered)),
        source_token_p95=ordered[p95_index],
        source_token_max=ordered[-1],
        pack_binding_rate=sum(value > pack_budget_tokens for value in ordered) / n_items,
        answer_in_support_rate=answer_in_support / n_items,
        answer_in_nonsupport_rate=answer_in_nonsupport / n_items,
        intermediate_answers_in_support_rate=intermediate_answers_in_support / n_items,
        intermediate_answers_in_nonsupport_rate=intermediate_answers_in_nonsupport / n_items,
        source_sha256=source_sha256,
        official_source_sha256=official_source_sha256,
        source_revision=source_revision,
        tokenizer_id=tokenizer_id,
    )


def evaluate_musique_offline_qualification(
    measurements: MuSiQueOfflineMeasurements,
) -> DifficultyGateResult:
    """Reject native or packed sources that cannot support the causal A2 claim."""

    failures: list[str] = []
    if measurements.n_items < 40:
        failures.append("MuSiQue qualification has fewer than 40 items")
    if measurements.duplicate_item_ids:
        failures.append("MuSiQue qualification contains duplicate item ids")
    if len(measurements.hop_counts) < 2:
        failures.append("MuSiQue qualification has fewer than two hop strata")
    if measurements.pack_binding_rate < 0.95:
        failures.append("MuSiQue source is not binding at the 8K pack budget on 95% of items")
    if measurements.answer_in_support_rate < 0.95:
        failures.append("answer is absent from supporting evidence on too many items")
    if measurements.answer_in_nonsupport_rate > 0.0:
        failures.append("answer appears in non-supporting evidence")
    if measurements.intermediate_answers_in_support_rate < 0.95:
        failures.append(
            "intermediate answers are absent from supporting evidence on too many items"
        )
    if measurements.intermediate_answers_in_nonsupport_rate > 0.0:
        failures.append("an intermediate answer appears in non-supporting evidence")
    if not measurements.official_source_byte_match:
        failures.append("source was not byte-matched to the official source bytes")
    return DifficultyGateResult(
        profile="musique-causal-multihop",
        passed=not failures,
        failures=tuple(failures),
    )
