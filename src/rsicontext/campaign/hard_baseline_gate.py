"""Visible-only fixed-baseline qualification for the hard long-context panel."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from rsicontext.datasets import (
    NOMINAL_HARD_CONTEXT_TOKENS,
    HardPrivateItem,
    HardTaskProfile,
    generate_hard_long_context_dataset,
)
from rsicontext.eval import (
    FrozenReader,
    ReaderOutput,
    exact_match,
    gold_context_pack,
)
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, build_profile_reader
from rsicontext.policy import Budget, ContextPack, LexicalPolicy, TruncationPolicy

DEFAULT_HARD_PROFILES = (
    HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
    HardTaskProfile.DENSE_GLOBAL_COMPARISON,
)
DEFAULT_HARD_DATASET_SEED = "hard-v3-visible-qualification-disposable-v1"
HARD_POLICY_TOKENS = 8_192
_HARD_OUTPUT_TOKENS = 512

ConditionRole = Literal["fixed_baseline", "evaluator_instrument"]


@dataclass(frozen=True, slots=True)
class HardProfileObservation:
    task_profile: str
    score: float
    item_ids: tuple[str, ...]
    predictions: tuple[str, ...]
    item_scores: tuple[float, ...]
    gold_recall: tuple[float, ...]
    context_tokens: tuple[int, ...]
    item_reader_input_tokens: tuple[int, ...]
    item_reader_output_tokens: tuple[int, ...]
    mean_gold_recall: float
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class HardConditionObservation:
    condition_name: str
    condition_role: ConditionRole
    context_budget_tokens: int
    score: float
    mean_gold_recall: float
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    profiles: tuple[HardProfileObservation, ...]


@dataclass(frozen=True, slots=True)
class HardBaselineGateResult:
    schema_version: int
    started_at: str
    reader_profile_id: str
    reader_profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    dataset_fingerprint: str
    dataset_seed_hash: str
    qualification_profile_hash: str
    split: str
    requested_target_tokens: int
    source_target_tokens_min: int
    source_target_tokens_max: int
    target_token_tolerance: int
    semantic_words_min: int
    semantic_words_max: int
    policy_budget_target_tokens: int
    tokenizer_id: str
    max_output_tokens: int
    items_per_profile: int
    task_profiles: tuple[str, ...]
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    conditions: tuple[HardConditionObservation, ...]
    qualification_only: bool
    difficulty_assessment: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _Condition:
    name: str
    role: ConditionRole
    budget_tokens: int
    assemble: Callable[[HardPrivateItem], ContextPack]


def hard_reader_output_limit(profile: APIProfile) -> int:
    """Use a bounded output reserve for the hard qualification panel."""

    return min(_HARD_OUTPUT_TOKENS, profile.max_output_tokens)


def run_hard_baseline_gate(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str | None,
    reader: FrozenReader | None = None,
    token_counter: Callable[[str], int],
    tokenizer_id: str,
    dataset_seed: str = DEFAULT_HARD_DATASET_SEED,
    items_per_profile: int = 4,
    task_profiles: tuple[HardTaskProfile, ...] = DEFAULT_HARD_PROFILES,
    source_tokens: int = NOMINAL_HARD_CONTEXT_TOKENS,
    policy_budget_tokens: int = HARD_POLICY_TOKENS,
    timer: Callable[[], float] = time.perf_counter,
    started_at: str | None = None,
) -> HardBaselineGateResult:
    """Run fixed policies and evaluator instruments without declaring a difficulty verdict."""

    _validate_configuration(
        profile=profile,
        dataset_seed=dataset_seed,
        items_per_profile=items_per_profile,
        task_profiles=task_profiles,
        source_tokens=source_tokens,
        policy_budget_tokens=policy_budget_tokens,
        token_counter=token_counter,
        tokenizer_id=tokenizer_id,
    )
    timestamp = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    dataset = generate_hard_long_context_dataset(
        seed=dataset_seed,
        items_per_profile=items_per_profile,
        requested_tokens=source_tokens,
        token_counter=token_counter,
        tokenizer_id=tokenizer_id,
    )
    source_target_tokens_min = min(dataset.source_token_counts)
    source_target_tokens_max = max(dataset.source_token_counts)
    if source_target_tokens_max + hard_reader_output_limit(profile) > (
        profile.evaluation_max_model_len
    ):
        raise ValueError("target-tokenized full context exceeds the reader model length")
    actual_reader: FrozenReader = reader or build_profile_reader(
        profile,
        ResolvedAPIEndpoint(endpoint=endpoint, api_key=api_key),
        max_tokens=hard_reader_output_limit(profile),
    )
    conditions = _conditions(source_target_tokens_max, policy_budget_tokens)
    visible = dataset.visible_items()
    observations = tuple(
        _evaluate_condition(
            condition=condition,
            task_profiles=task_profiles,
            visible=visible,
            reader=actual_reader,
            timer=timer,
        )
        for condition in conditions
    )
    expected_calls = len(conditions) * len(task_profiles) * items_per_profile
    observed_calls = sum(
        len(profile_observation.item_scores)
        for condition_observation in observations
        for profile_observation in condition_observation.profiles
    )
    if observed_calls != expected_calls:
        raise RuntimeError("hard qualification did not make exactly one call per selected item")
    task_profile_values = tuple(task_profile.value for task_profile in task_profiles)
    return HardBaselineGateResult(
        schema_version=4,
        started_at=timestamp,
        reader_profile_id=profile.id,
        reader_profile_hash=profile.profile_hash,
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        dataset_fingerprint=dataset.fingerprint,
        dataset_seed_hash=hashlib.sha256(dataset_seed.encode()).hexdigest(),
        qualification_profile_hash=_qualification_profile_hash(
            source_tokens=source_tokens,
            source_target_tokens_min=source_target_tokens_min,
            source_target_tokens_max=source_target_tokens_max,
            policy_budget_tokens=policy_budget_tokens,
            tokenizer_id=tokenizer_id,
            task_profiles=task_profile_values,
            conditions=conditions,
        ),
        split="visible",
        requested_target_tokens=source_tokens,
        source_target_tokens_min=source_target_tokens_min,
        source_target_tokens_max=source_target_tokens_max,
        target_token_tolerance=dataset.target_token_tolerance,
        semantic_words_min=min(dataset.semantic_word_counts),
        semantic_words_max=max(dataset.semantic_word_counts),
        policy_budget_target_tokens=policy_budget_tokens,
        tokenizer_id=tokenizer_id,
        max_output_tokens=hard_reader_output_limit(profile),
        items_per_profile=items_per_profile,
        task_profiles=task_profile_values,
        reader_calls=observed_calls,
        reader_input_tokens=sum(observation.reader_input_tokens for observation in observations),
        reader_output_tokens=sum(observation.reader_output_tokens for observation in observations),
        wall_seconds=sum(observation.wall_seconds for observation in observations),
        conditions=observations,
        qualification_only=True,
        difficulty_assessment="not_assessed",
    )


def write_hard_baseline_gate(result: HardBaselineGateResult, path: str | Path) -> None:
    """Write one immutable qualification record without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _validate_configuration(
    *,
    profile: APIProfile,
    dataset_seed: str,
    items_per_profile: int,
    task_profiles: tuple[HardTaskProfile, ...],
    source_tokens: int,
    policy_budget_tokens: int,
    token_counter: Callable[[str], int],
    tokenizer_id: str,
) -> None:
    if not isinstance(dataset_seed, str):
        raise TypeError("dataset_seed must be a string")
    if not dataset_seed:
        raise ValueError("dataset_seed must be non-empty")
    if not callable(token_counter):
        raise TypeError("token_counter must be callable")
    if not isinstance(tokenizer_id, str) or not tokenizer_id:
        raise ValueError("tokenizer_id must be non-empty")
    if isinstance(items_per_profile, bool) or not isinstance(items_per_profile, int):
        raise TypeError("items_per_profile must be an integer")
    if items_per_profile < 1:
        raise ValueError("items_per_profile must be positive")
    if (
        not task_profiles
        or len(task_profiles) != len(set(task_profiles))
        or any(not isinstance(task_profile, HardTaskProfile) for task_profile in task_profiles)
    ):
        raise ValueError("task_profiles must be non-empty and unique HardTaskProfile values")
    if HardTaskProfile.INSUFFICIENT_EVIDENCE in task_profiles:
        raise ValueError("abstention tasks require a separate verification-policy qualification")
    for field_name, value in (
        ("source_tokens", source_tokens),
        ("policy_budget_tokens", policy_budget_tokens),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer")
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
    if policy_budget_tokens > source_tokens:
        raise ValueError("policy budget cannot exceed the source length")


def _conditions(source_tokens: int, policy_budget_tokens: int) -> tuple[_Condition, ...]:
    return (
        _Condition(
            "head-8k",
            "fixed_baseline",
            policy_budget_tokens,
            lambda item: TruncationPolicy("head").assemble(
                item.evaluation_item.artifact,
                item.evaluation_item.query,
                Budget(policy_budget_tokens),
            ),
        ),
        _Condition(
            "head-tail-8k",
            "fixed_baseline",
            policy_budget_tokens,
            lambda item: TruncationPolicy("head_tail").assemble(
                item.evaluation_item.artifact,
                item.evaluation_item.query,
                Budget(policy_budget_tokens),
            ),
        ),
        _Condition(
            "lexical-8k",
            "fixed_baseline",
            policy_budget_tokens,
            lambda item: LexicalPolicy().assemble(
                item.evaluation_item.artifact,
                item.evaluation_item.query,
                Budget(policy_budget_tokens),
            ),
        ),
        _Condition(
            "full-context-unbudgeted-instrument",
            "evaluator_instrument",
            source_tokens,
            lambda item: TruncationPolicy("head").assemble(
                item.evaluation_item.artifact,
                item.evaluation_item.query,
                Budget(source_tokens),
            ),
        ),
        _Condition("no-context-instrument", "evaluator_instrument", 0, _no_context),
        _Condition(
            "gold-only-instrument",
            "evaluator_instrument",
            policy_budget_tokens,
            lambda item: _gold_context(item, policy_budget_tokens, fill=False),
        ),
        _Condition(
            "bounded-oracle-8k-instrument",
            "evaluator_instrument",
            policy_budget_tokens,
            lambda item: _gold_context(item, policy_budget_tokens, fill=True),
        ),
    )


def _no_context(item: HardPrivateItem) -> ContextPack:
    del item
    return ContextPack()


def _gold_context(private_item: HardPrivateItem, budget_tokens: int, *, fill: bool) -> ContextPack:
    return gold_context_pack(private_item.evaluation_item, budget_tokens, fill=fill)


def _evaluate_condition(
    *,
    condition: _Condition,
    task_profiles: tuple[HardTaskProfile, ...],
    visible: tuple[HardPrivateItem, ...],
    reader: FrozenReader,
    timer: Callable[[], float],
) -> HardConditionObservation:
    profile_observations = tuple(
        _evaluate_profile(
            condition=condition,
            task_profile=task_profile,
            private_items=tuple(item for item in visible if item.task_profile is task_profile),
            reader=reader,
            timer=timer,
        )
        for task_profile in task_profiles
    )
    return HardConditionObservation(
        condition_name=condition.name,
        condition_role=condition.role,
        context_budget_tokens=condition.budget_tokens,
        score=_weighted_mean(
            tuple((profile.score, len(profile.item_scores)) for profile in profile_observations)
        ),
        mean_gold_recall=_weighted_mean(
            tuple(
                (profile.mean_gold_recall, len(profile.gold_recall))
                for profile in profile_observations
            )
        ),
        reader_input_tokens=sum(profile.reader_input_tokens for profile in profile_observations),
        reader_output_tokens=sum(profile.reader_output_tokens for profile in profile_observations),
        wall_seconds=sum(profile.wall_seconds for profile in profile_observations),
        profiles=profile_observations,
    )


def _evaluate_profile(
    *,
    condition: _Condition,
    task_profile: HardTaskProfile,
    private_items: tuple[HardPrivateItem, ...],
    reader: FrozenReader,
    timer: Callable[[], float],
) -> HardProfileObservation:
    if not private_items:
        raise ValueError("hard profile evaluation items must be non-empty")
    item_ids: list[str] = []
    predictions: list[str] = []
    item_scores: list[float] = []
    gold_recall: list[float] = []
    context_tokens: list[int] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    before = timer()
    for private_item in private_items:
        item = private_item.evaluation_item
        context = condition.assemble(private_item)
        context.validate(item.artifact, Budget(condition.budget_tokens))
        if context.abstain or context.request_reread is not None:
            raise ValueError("hard fixed conditions must make exactly one target-reader call")
        output = reader.read(item.query, context)
        if not isinstance(output, ReaderOutput):
            raise TypeError("reader must return ReaderOutput")
        selected_ids = frozenset(span.chunk_id for span in context.spans)
        item_ids.append(item.item_id)
        predictions.append(output.answer)
        item_scores.append(exact_match(output.answer, item.answer))
        gold_recall.append(len(selected_ids & item.gold_chunk_ids) / len(item.gold_chunk_ids))
        context_tokens.append(context.token_count)
        input_tokens.append(output.input_tokens)
        output_tokens.append(output.output_tokens)
    wall_seconds = _elapsed(timer() - before)
    return HardProfileObservation(
        task_profile=task_profile.value,
        score=sum(item_scores) / len(item_scores),
        item_ids=tuple(item_ids),
        predictions=tuple(predictions),
        item_scores=tuple(item_scores),
        gold_recall=tuple(gold_recall),
        context_tokens=tuple(context_tokens),
        item_reader_input_tokens=tuple(input_tokens),
        item_reader_output_tokens=tuple(output_tokens),
        mean_gold_recall=sum(gold_recall) / len(gold_recall),
        reader_input_tokens=sum(input_tokens),
        reader_output_tokens=sum(output_tokens),
        wall_seconds=wall_seconds,
    )


def _qualification_profile_hash(
    *,
    source_tokens: int,
    source_target_tokens_min: int,
    source_target_tokens_max: int,
    policy_budget_tokens: int,
    tokenizer_id: str,
    task_profiles: tuple[str, ...],
    conditions: tuple[_Condition, ...],
) -> str:
    canonical = {
        "conditions": [
            {
                "budget_tokens": condition.budget_tokens,
                "name": condition.name,
                "role": condition.role,
            }
            for condition in conditions
        ],
        "policy_budget_tokens": policy_budget_tokens,
        "requested_target_tokens": source_tokens,
        "source_target_tokens_min": source_target_tokens_min,
        "source_target_tokens_max": source_target_tokens_max,
        "task_profiles": task_profiles,
        "tokenizer_id": tokenizer_id,
    }
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _weighted_mean(values: tuple[tuple[float, int], ...]) -> float:
    total_weight = sum(weight for _, weight in values)
    if total_weight < 1:
        raise ValueError("weighted mean requires positive total weight")
    return sum(value * weight for value, weight in values) / total_weight


def _elapsed(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("hard gate timer returned an invalid duration")
    return value
