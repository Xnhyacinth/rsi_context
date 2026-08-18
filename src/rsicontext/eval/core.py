"""Deterministic evaluation loop for frozen-reader experiments."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from rsicontext.policy import Artifact, Budget, ContextPack, ContextPolicy


class FrozenReader(Protocol):
    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        """Return an answer without mutating policy or evaluation state."""
        ...


class Scorer(Protocol):
    def __call__(self, prediction: str, reference: str) -> float: ...


PolicyFactory = Callable[[], ContextPolicy]


@dataclass(frozen=True, slots=True)
class ReaderOutput:
    """One answer plus endpoint-reported token usage."""

    answer: str
    input_tokens: int
    output_tokens: int
    response_id: str | None = None
    response_model: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str):
            raise TypeError("reader answer must be a string")
        for field_name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"reader {field_name} must be a non-negative integer")
        for field_name, metadata_value in (
            ("response_id", self.response_id),
            ("response_model", self.response_model),
        ):
            if metadata_value is not None and (
                not isinstance(metadata_value, str) or not metadata_value
            ):
                raise ValueError(f"reader {field_name} must be a non-empty string or null")


@dataclass(frozen=True, slots=True)
class EvaluationItem:
    item_id: str
    query: str
    answer: str
    artifact: Artifact
    gold_chunk_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "gold_chunk_ids", frozenset(self.gold_chunk_ids))
        if not self.item_id:
            raise ValueError("item_id must not be empty")
        if not self.gold_chunk_ids <= self.artifact.chunk_ids:
            raise ValueError("gold provenance must be present in the artifact")


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    score: float
    predictions: tuple[str, ...]
    item_scores: tuple[float, ...]
    token_counts: tuple[int, ...]
    reader_input_tokens: tuple[int, ...]
    reader_output_tokens: tuple[int, ...]


_SPACE = re.compile(r"\s+")


def exact_match(prediction: str, reference: str) -> float:
    """Case-insensitive exact match with whitespace normalization."""

    return float(_normalize_answer(prediction) == _normalize_answer(reference))


def contained_match(prediction: str, reference: str) -> float:
    """Case-insensitive containment after whitespace normalization."""

    normalized_reference = _normalize_answer(reference)
    if not normalized_reference:
        raise ValueError("reference must be non-empty")
    return float(normalized_reference in _normalize_answer(prediction))


def extractive_span_match(prediction: str, reference: str) -> float:
    """Hit if either normalized string contains the other.

    Public RULER/SQuAD cells use this so a copied number is not killed when the
    gold string is ``3,677 seated`` and the reader returns ``3,677``. It does not
    change the 0.85 gold-only threshold.
    """

    normalized_prediction = _normalize_answer(prediction)
    normalized_reference = _normalize_answer(reference)
    if not normalized_reference:
        raise ValueError("reference must be non-empty")
    if not normalized_prediction:
        return 0.0
    return float(
        normalized_reference in normalized_prediction
        or normalized_prediction in normalized_reference
    )


def _normalize_answer(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("answers must be strings")
    return _SPACE.sub(" ", value.strip()).casefold()


def evaluate(
    policy_factory: PolicyFactory,
    items: list[EvaluationItem] | tuple[EvaluationItem, ...],
    reader: FrozenReader,
    budget: Budget,
    scorer: Scorer = exact_match,
) -> EvaluationResult:
    return _evaluate(policy_factory, items, reader, budget, scorer, seen_policies=[])


def _evaluate(
    policy_factory: PolicyFactory,
    items: list[EvaluationItem] | tuple[EvaluationItem, ...],
    reader: FrozenReader,
    budget: Budget,
    scorer: Scorer,
    *,
    seen_policies: list[ContextPolicy],
) -> EvaluationResult:
    if not items:
        raise ValueError("evaluation items must be non-empty")
    item_ids = [item.item_id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("evaluation item_id values must be unique")
    predictions: list[str] = []
    scores: list[float] = []
    token_counts: list[int] = []
    reader_input_tokens: list[int] = []
    reader_output_tokens: list[int] = []
    for item in items:
        policy = policy_factory()
        if any(policy is previous for previous in seen_policies):
            raise ValueError("policy_factory must return a fresh policy instance")
        seen_policies.append(policy)
        context = policy.assemble(item.artifact, item.query, budget)
        context.validate(item.artifact, budget)
        if context.request_reread is not None:
            raise ValueError("reread execution is not implemented in the single-reader track")
        output = ReaderOutput("", 0, 0) if context.abstain else reader.read(item.query, context)
        if not isinstance(output, ReaderOutput):
            raise TypeError("reader must return ReaderOutput")
        prediction = output.answer
        item_score = scorer(prediction, item.answer)
        if isinstance(item_score, bool) or not isinstance(item_score, (int, float)):
            raise TypeError("scorer outputs must be numeric")
        numeric_score = float(item_score)
        if not math.isfinite(numeric_score) or not 0 <= numeric_score <= 1:
            raise ValueError("scorer outputs must be finite and within [0, 1]")
        predictions.append(prediction)
        scores.append(numeric_score)
        token_counts.append(context.token_count)
        reader_input_tokens.append(output.input_tokens)
        reader_output_tokens.append(output.output_tokens)
    return EvaluationResult(
        score=sum(scores) / len(scores),
        predictions=tuple(predictions),
        item_scores=tuple(scores),
        token_counts=tuple(token_counts),
        reader_input_tokens=tuple(reader_input_tokens),
        reader_output_tokens=tuple(reader_output_tokens),
    )
