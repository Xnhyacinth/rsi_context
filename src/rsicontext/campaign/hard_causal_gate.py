"""Visible-only causal and replay qualification for hard long-context tasks."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from statistics import fmean, pstdev, pvariance
from typing import Any, Literal

from rsicontext.analysis.difficulty import (
    DifficultyMeasurements,
    clone_aware_item_disagreement,
    evaluate_difficulty,
)
from rsicontext.campaign.hard_baseline_gate import (
    DEFAULT_HARD_PROFILES,
    HARD_POLICY_TOKENS,
    hard_reader_output_limit,
)
from rsicontext.datasets import (
    NOMINAL_HARD_CONTEXT_TOKENS,
    EvidencePosition,
    HardPrivateItem,
    HardTaskProfile,
    generate_hard_long_context_dataset,
)
from rsicontext.eval import (
    EvaluationItem,
    FrozenReader,
    ReaderOutput,
    exact_match,
    gold_context_pack,
)
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, build_profile_reader
from rsicontext.policy import (
    CANONICAL_POLICY_SPECS_V1,
    Artifact,
    Budget,
    ContextPack,
    DocumentChunk,
    LexicalPolicy,
    PolicySpecV1Interpreter,
    TruncationPolicy,
    policy_spec_v1_hashes,
)

DEFAULT_CAUSAL_DATASET_SEED = "hard-v3-visible-causal-disposable-v1"
DEFAULT_REPLAY_REPEATS = 5

ConditionRole = Literal["fixed_baseline", "search_space_policy", "evaluator_instrument", "replay"]
_OPAQUE_ANSWER = re.compile(r"(?P<prefix>[a-z]{2})-[0-9a-f]{12}\Z")


@dataclass(frozen=True, slots=True)
class CausalItemObservation:
    item_id: str
    task_profile: str
    evidence_position: str
    prediction: str
    score: float
    gold_recall: float
    context_tokens: int
    reader_input_tokens: int
    reader_output_tokens: int
    reader_calls: int
    wall_seconds: float
    response_id: str | None
    response_model: str | None


@dataclass(frozen=True, slots=True)
class CausalProfileObservation:
    task_profile: str
    score: float
    mean_gold_recall: float
    items: tuple[CausalItemObservation, ...]
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class CausalConditionObservation:
    condition_name: str
    condition_role: ConditionRole
    policy_config: tuple[tuple[str, str | int], ...]
    score: float
    mean_gold_recall: float
    items: tuple[CausalItemObservation, ...]
    profiles: tuple[CausalProfileObservation, ...]
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    transformation_failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplayObservation:
    policy_name: str
    repeats: tuple[CausalConditionObservation, ...]
    scores: tuple[float, ...]
    mean: float
    variance: float
    standard_deviation: float
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class CausalStratumObservation:
    policy_name: str
    task_profile: str
    evidence_position: str
    item_ids: tuple[str, ...]
    item_scores: tuple[float, ...]
    item_count: int
    score: float


@dataclass(frozen=True, slots=True)
class CounterfactualRewriteAudit:
    item_id: str
    task_profile: str
    evidence_position: str
    original_query_occurrences: int
    original_gold_occurrences: int
    original_nongold_occurrences: int
    transformed_query_original_occurrences: int
    transformed_gold_original_occurrences: int
    transformed_query_new_occurrences: int
    transformed_gold_new_occurrences: int
    transformed_nongold_original_occurrences: int
    nongold_unchanged: bool


@dataclass(frozen=True, slots=True)
class HardCausalGateResult:
    schema_version: int
    started_at: str
    reader_profile_id: str
    reader_profile_hash: str
    reader_implementation: str
    provider: str
    requested_model: str
    provider_revision: str | None
    observed_response_models: tuple[str, ...]
    dataset_fingerprint: str
    dataset_seed_hash: str
    qualification_profile_hash: str
    split: str
    requested_target_tokens: int
    source_target_tokens_min: int
    source_target_tokens_max: int
    target_token_tolerance: int
    policy_budget_target_tokens: int
    tokenizer_id: str
    max_output_tokens: int
    items_per_profile: int
    task_profiles: tuple[str, ...]
    replay_repeats: int
    policy_spec_v1_hashes: tuple[tuple[str, str], ...]
    fixed_policies: tuple[CausalConditionObservation, ...]
    policy_search_space: tuple[CausalConditionObservation, ...]
    strongest_non_oracle_policies: tuple[str, str]
    strongest_policy_item_disagreement: float
    full_context: CausalConditionObservation
    no_context: CausalConditionObservation
    gold_only: CausalConditionObservation
    bounded_oracle: CausalConditionObservation
    gold_drop: CausalConditionObservation
    gold_drop_raw_delta: float
    gold_drop_decrease: float
    counterfactual: CausalConditionObservation
    counterfactual_rewrite_audits: tuple[CounterfactualRewriteAudit, ...]
    counterfactual_fingerprint: str
    counterfactual_following: float
    strata: tuple[CausalStratumObservation, ...]
    replay: ReplayObservation
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    qualification_only: bool
    difficulty_assessment: str
    difficulty_results: tuple[tuple[str, bool, tuple[str, ...]], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _FixedPolicy:
    name: str
    assemble: Callable[[HardPrivateItem], ContextPack]


def run_hard_causal_gate(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str | None,
    reader: FrozenReader | None = None,
    token_counter: Callable[[str], int],
    tokenizer_id: str,
    dataset_seed: str = DEFAULT_CAUSAL_DATASET_SEED,
    items_per_profile: int = 4,
    task_profiles: tuple[HardTaskProfile, ...] = DEFAULT_HARD_PROFILES,
    source_tokens: int = NOMINAL_HARD_CONTEXT_TOKENS,
    policy_budget_tokens: int = HARD_POLICY_TOKENS,
    replay_repeats: int = DEFAULT_REPLAY_REPEATS,
    timer: Callable[[], float] = time.perf_counter,
    started_at: str | None = None,
) -> HardCausalGateResult:
    """Measure causal evidence use and exact-condition replay without passing a gate."""

    _validate_configuration(
        dataset_seed=dataset_seed,
        items_per_profile=items_per_profile,
        task_profiles=task_profiles,
        source_tokens=source_tokens,
        policy_budget_tokens=policy_budget_tokens,
        replay_repeats=replay_repeats,
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
    visible = tuple(item for item in dataset.visible_items() if item.task_profile in task_profiles)
    expected_items = len(task_profiles) * items_per_profile
    if len(visible) != expected_items:
        raise RuntimeError("hard causal panel did not contain the requested visible strata")
    output_limit = hard_reader_output_limit(profile)
    source_min = min(item.source_target_tokens for item in visible)
    source_max = max(item.source_target_tokens for item in visible)
    if source_max + output_limit > profile.evaluation_max_model_len:
        raise ValueError("target-tokenized full context exceeds the reader model length")
    actual_reader: FrozenReader = reader or build_profile_reader(
        profile,
        ResolvedAPIEndpoint(endpoint=endpoint, api_key=api_key),
        max_tokens=output_limit,
    )

    fixed_specs = _fixed_policies(policy_budget_tokens)
    fixed = tuple(
        _evaluate(
            condition_name=spec.name,
            condition_role="fixed_baseline",
            items=visible,
            reader=actual_reader,
            prepare=partial(_fixed_context, assemble=spec.assemble),
            timer=timer,
        )
        for spec in fixed_specs
    )
    interpreter = PolicySpecV1Interpreter()
    materialized_specs = tuple(
        (spec, interpreter.materialize(spec)) for spec in CANONICAL_POLICY_SPECS_V1
    )
    search_space = tuple(
        _evaluate(
            condition_name=spec.canonical_key,
            condition_role="search_space_policy",
            policy_config=tuple(sorted(spec.to_config().items())),
            items=visible,
            reader=actual_reader,
            prepare=partial(
                _materialized_context,
                assemble=policy.assemble,
                budget=Budget(policy_budget_tokens),
            ),
            timer=timer,
        )
        for spec, policy in materialized_specs
    )
    strongest = tuple(
        condition.condition_name
        for condition in sorted(
            search_space, key=lambda value: (-value.score, value.condition_name)
        )[:2]
    )
    if len(strongest) != 2:
        raise RuntimeError("hard causal gate requires at least two fixed policies")
    search_by_name = {condition.condition_name: condition for condition in search_space}
    disagreement = _item_disagreement(search_by_name[strongest[0]], search_by_name[strongest[1]])

    full_context = _evaluate(
        condition_name="full-context-original-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=lambda item: (item.evaluation_item, _all_context(item.evaluation_item)),
        timer=timer,
    )
    no_context = _evaluate(
        condition_name="no-context-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=_no_context,
        timer=timer,
    )
    gold_only = _evaluate(
        condition_name="gold-only-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=partial(_gold_context, budget_tokens=policy_budget_tokens, fill=False),
        timer=timer,
    )
    bounded_oracle = _evaluate(
        condition_name="bounded-oracle-8k-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=partial(_gold_context, budget_tokens=policy_budget_tokens, fill=True),
        timer=timer,
    )
    gold_drop = _evaluate(
        condition_name="gold-drop-full-context-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=_gold_drop,
        timer=timer,
    )
    raw_gold_drop_delta = full_context.score - gold_drop.score
    transformed_and_audited = tuple(
        _counterfactual_evaluation_item(item, token_counter) for item in visible
    )
    transformed_items = {
        transformed.item_id: transformed for transformed, _ in transformed_and_audited
    }
    rewrite_audits = tuple(audit for _, audit in transformed_and_audited)
    counterfactual_fingerprint = _counterfactual_fingerprint(tuple(transformed_items.values()))
    transformed_source_max = max(
        sum(chunk.token_count for chunk in item.artifact.chunks)
        for item in transformed_items.values()
    )
    if transformed_source_max + output_limit > profile.evaluation_max_model_len:
        raise ValueError("counterfactual full context exceeds the reader model length")
    counterfactual = _evaluate(
        condition_name="counterfactual-full-context-instrument",
        condition_role="evaluator_instrument",
        items=visible,
        reader=actual_reader,
        prepare=partial(_stored_counterfactual_context, transformed=transformed_items),
        timer=timer,
    )

    replay_policy = next(
        policy for spec, policy in materialized_specs if spec.canonical_key == strongest[0]
    )
    replay_conditions = tuple(
        _evaluate(
            condition_name=f"replay-{repeat_index + 1:03d}",
            condition_role="replay",
            items=visible,
            reader=actual_reader,
            prepare=partial(
                _materialized_context,
                assemble=replay_policy.assemble,
                budget=Budget(policy_budget_tokens),
            ),
            timer=timer,
        )
        for repeat_index in range(replay_repeats)
    )
    replay_scores = tuple(condition.score for condition in replay_conditions)
    replay = ReplayObservation(
        policy_name=strongest[0],
        repeats=replay_conditions,
        scores=replay_scores,
        mean=fmean(replay_scores),
        variance=pvariance(replay_scores),
        standard_deviation=pstdev(replay_scores),
        reader_calls=sum(condition.reader_calls for condition in replay_conditions),
        reader_input_tokens=sum(condition.reader_input_tokens for condition in replay_conditions),
        reader_output_tokens=sum(condition.reader_output_tokens for condition in replay_conditions),
        wall_seconds=sum(condition.wall_seconds for condition in replay_conditions),
    )
    observations = (
        *fixed,
        *search_space,
        full_context,
        no_context,
        gold_only,
        bounded_oracle,
        gold_drop,
        counterfactual,
        *replay_conditions,
    )
    observed_calls = sum(condition.reader_calls for condition in observations)
    expected_calls = (len(fixed) + len(search_space) + 6 + replay_repeats) * expected_items
    if observed_calls != expected_calls:
        raise RuntimeError("hard causal gate did not make exactly one call per item-condition")
    models = tuple(
        sorted(
            {
                item.response_model
                for condition in observations
                for item in condition.items
                if item.response_model is not None
            }
        )
    )
    profile_values = tuple(task_profile.value for task_profile in task_profiles)
    strata = _strata((search_by_name[strongest[0]],))
    difficulty_results = _assess_difficulty(
        profiles=profile_values,
        search_space=search_space,
        no_context=no_context,
        gold_only=gold_only,
        bounded_oracle=bounded_oracle,
        full_context=full_context,
        gold_drop=gold_drop,
        counterfactual=counterfactual,
        strata=strata,
        replay_standard_deviation=replay.standard_deviation,
    )
    return HardCausalGateResult(
        schema_version=2,
        started_at=timestamp,
        reader_profile_id=profile.id,
        reader_profile_hash=profile.profile_hash,
        reader_implementation=(
            f"{type(actual_reader).__module__}.{type(actual_reader).__qualname__}"
        ),
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        observed_response_models=models,
        dataset_fingerprint=dataset.fingerprint,
        dataset_seed_hash=hashlib.sha256(dataset_seed.encode()).hexdigest(),
        qualification_profile_hash=_qualification_profile_hash(
            profile_hash=profile.profile_hash,
            dataset_fingerprint=dataset.fingerprint,
            tokenizer_id=tokenizer_id,
            source_tokens=source_tokens,
            source_min=source_min,
            source_max=source_max,
            policy_budget_tokens=policy_budget_tokens,
            task_profiles=profile_values,
            fixed_policy_names=tuple(spec.name for spec in fixed_specs),
            policy_spec_hashes=tuple(sorted(policy_spec_v1_hashes().items())),
            counterfactual_fingerprint=counterfactual_fingerprint,
            replay_repeats=replay_repeats,
        ),
        split="visible",
        requested_target_tokens=source_tokens,
        source_target_tokens_min=source_min,
        source_target_tokens_max=source_max,
        target_token_tolerance=dataset.target_token_tolerance,
        policy_budget_target_tokens=policy_budget_tokens,
        tokenizer_id=tokenizer_id,
        max_output_tokens=output_limit,
        items_per_profile=items_per_profile,
        task_profiles=profile_values,
        replay_repeats=replay_repeats,
        policy_spec_v1_hashes=tuple(sorted(policy_spec_v1_hashes().items())),
        fixed_policies=fixed,
        policy_search_space=search_space,
        strongest_non_oracle_policies=(strongest[0], strongest[1]),
        strongest_policy_item_disagreement=disagreement,
        full_context=full_context,
        no_context=no_context,
        gold_only=gold_only,
        bounded_oracle=bounded_oracle,
        gold_drop=gold_drop,
        gold_drop_raw_delta=raw_gold_drop_delta,
        gold_drop_decrease=max(0.0, raw_gold_drop_delta),
        counterfactual=counterfactual,
        counterfactual_rewrite_audits=rewrite_audits,
        counterfactual_fingerprint=counterfactual_fingerprint,
        counterfactual_following=counterfactual.score,
        strata=strata,
        replay=replay,
        reader_calls=observed_calls,
        reader_input_tokens=sum(condition.reader_input_tokens for condition in observations),
        reader_output_tokens=sum(condition.reader_output_tokens for condition in observations),
        wall_seconds=sum(condition.wall_seconds for condition in observations),
        qualification_only=True,
        difficulty_assessment=(
            "passed" if all(passed for _, passed, _ in difficulty_results) else "failed"
        ),
        difficulty_results=difficulty_results,
    )


def write_hard_causal_gate(result: HardCausalGateResult, path: str | Path) -> None:
    """Write one immutable visible qualification artifact."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def counterfactual_evaluation_item(
    private_item: HardPrivateItem,
    token_counter: Callable[[str], int],
) -> EvaluationItem:
    """Rewrite one supported answer in all answer-bearing gold evidence, or fail closed."""

    transformed, _ = _counterfactual_evaluation_item(private_item, token_counter)
    return transformed


def _counterfactual_evaluation_item(
    private_item: HardPrivateItem,
    token_counter: Callable[[str], int],
) -> tuple[EvaluationItem, CounterfactualRewriteAudit]:

    if not callable(token_counter):
        raise TypeError("token_counter must be callable")
    item = private_item.evaluation_item
    match = _OPAQUE_ANSWER.fullmatch(item.answer)
    if match is None:
        raise ValueError("counterfactual task answer does not use a supported opaque identifier")
    replacement = _counterfactual_answer(item, match.group("prefix"))
    original_gold_occurrences = sum(
        chunk.text.count(item.answer)
        for chunk in item.artifact.chunks
        if chunk.chunk_id in item.gold_chunk_ids
    )
    if original_gold_occurrences < 1:
        raise ValueError("counterfactual task has no answer-bearing gold evidence")
    original_query_occurrences = item.query.count(item.answer)
    original_nongold_occurrences = sum(
        chunk.text.count(item.answer)
        for chunk in item.artifact.chunks
        if chunk.chunk_id not in item.gold_chunk_ids
    )
    chunks = tuple(
        _rewrite_chunk(chunk, item.answer, replacement, token_counter)
        if chunk.chunk_id in item.gold_chunk_ids
        else chunk
        for chunk in item.artifact.chunks
    )
    transformed_query = item.query.replace(item.answer, replacement)
    transformed_gold_chunks = tuple(
        chunk for chunk in chunks if chunk.chunk_id in item.gold_chunk_ids
    )
    transformed_nongold_chunks = tuple(
        chunk for chunk in chunks if chunk.chunk_id not in item.gold_chunk_ids
    )
    transformed_query_original = transformed_query.count(item.answer)
    transformed_gold_original = sum(
        chunk.text.count(item.answer) for chunk in transformed_gold_chunks
    )
    transformed_query_new = transformed_query.count(replacement)
    transformed_gold_new = sum(chunk.text.count(replacement) for chunk in transformed_gold_chunks)
    if transformed_query_original + transformed_gold_original != 0 or (
        transformed_query_new + transformed_gold_new
        != original_query_occurrences + original_gold_occurrences
    ):
        raise RuntimeError("counterfactual gold rewrite was incomplete")
    original_nongold_chunks = tuple(
        chunk for chunk in item.artifact.chunks if chunk.chunk_id not in item.gold_chunk_ids
    )
    transformed = EvaluationItem(
        item_id=item.item_id,
        query=transformed_query,
        answer=replacement,
        artifact=Artifact(item.artifact.document_id, chunks, item.artifact.notes),
        gold_chunk_ids=item.gold_chunk_ids,
    )
    audit = CounterfactualRewriteAudit(
        item_id=item.item_id,
        task_profile=private_item.task_profile.value,
        evidence_position=private_item.evidence_position.value,
        original_query_occurrences=original_query_occurrences,
        original_gold_occurrences=original_gold_occurrences,
        original_nongold_occurrences=original_nongold_occurrences,
        transformed_query_original_occurrences=transformed_query_original,
        transformed_gold_original_occurrences=transformed_gold_original,
        transformed_query_new_occurrences=transformed_query_new,
        transformed_gold_new_occurrences=transformed_gold_new,
        transformed_nongold_original_occurrences=sum(
            chunk.text.count(item.answer) for chunk in transformed_nongold_chunks
        ),
        nongold_unchanged=transformed_nongold_chunks == original_nongold_chunks,
    )
    if (
        audit.transformed_nongold_original_occurrences != original_nongold_occurrences
        or not audit.nongold_unchanged
    ):
        raise RuntimeError("counterfactual rewrite modified non-gold evidence")
    return transformed, audit


def _counterfactual_answer(item: EvaluationItem, prefix: str) -> str:
    source = "\n".join((item.query, *(chunk.text for chunk in item.artifact.chunks)))
    for attempt in range(256):
        digest = hashlib.sha256(
            f"hard-causal-v1\x00{item.item_id}\x00{item.answer}\x00{attempt}".encode()
        ).hexdigest()[:12]
        candidate = f"{prefix}-{digest}"
        if candidate != item.answer and candidate not in source:
            return candidate
    raise RuntimeError("could not derive a collision-free counterfactual answer")


def _counterfactual_fingerprint(items: tuple[EvaluationItem, ...]) -> str:
    canonical = [
        {
            "answer_hash": hashlib.sha256(item.answer.encode()).hexdigest(),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "text_hash": hashlib.sha256(chunk.text.encode()).hexdigest(),
                    "token_count": chunk.token_count,
                }
                for chunk in item.artifact.chunks
            ],
            "item_id": item.item_id,
            "query_hash": hashlib.sha256(item.query.encode()).hexdigest(),
        }
        for item in items
    ]
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _rewrite_chunk(
    chunk: DocumentChunk,
    original: str,
    replacement: str,
    token_counter: Callable[[str], int],
) -> DocumentChunk:
    text = chunk.text.replace(original, replacement)
    token_count = token_counter(text)
    if isinstance(token_count, bool) or not isinstance(token_count, int) or token_count <= 0:
        raise ValueError("target tokenizer counts must be positive integers")
    return DocumentChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        start=chunk.start,
        end=chunk.end,
        text=text,
        token_count=token_count,
        role=chunk.role,
    )


def _fixed_policies(policy_budget_tokens: int) -> tuple[_FixedPolicy, ...]:
    budget = Budget(policy_budget_tokens)
    return (
        _FixedPolicy(
            "head-8k",
            lambda item: TruncationPolicy("head").assemble(
                item.evaluation_item.artifact, item.evaluation_item.query, budget
            ),
        ),
        _FixedPolicy(
            "head-tail-8k",
            lambda item: TruncationPolicy("head_tail").assemble(
                item.evaluation_item.artifact, item.evaluation_item.query, budget
            ),
        ),
        _FixedPolicy(
            "lexical-8k",
            lambda item: LexicalPolicy().assemble(
                item.evaluation_item.artifact, item.evaluation_item.query, budget
            ),
        ),
    )


def _all_context(item: EvaluationItem) -> ContextPack:
    return ContextPack(
        spans=item.artifact.chunks,
        ordering=tuple(chunk.chunk_id for chunk in item.artifact.chunks),
        token_count=sum(chunk.token_count for chunk in item.artifact.chunks),
    )


def _fixed_context(
    private_item: HardPrivateItem,
    *,
    assemble: Callable[[HardPrivateItem], ContextPack],
) -> tuple[EvaluationItem, ContextPack]:
    return private_item.evaluation_item, assemble(private_item)


def _materialized_context(
    private_item: HardPrivateItem,
    *,
    assemble: Callable[[Artifact, str, Budget], ContextPack],
    budget: Budget,
) -> tuple[EvaluationItem, ContextPack]:
    item = private_item.evaluation_item
    return item, assemble(item.artifact, item.query, budget)


def _no_context(private_item: HardPrivateItem) -> tuple[EvaluationItem, ContextPack]:
    return private_item.evaluation_item, ContextPack()


def _gold_context(
    private_item: HardPrivateItem, *, budget_tokens: int, fill: bool
) -> tuple[EvaluationItem, ContextPack]:
    item = private_item.evaluation_item
    return item, gold_context_pack(item, budget_tokens, fill=fill)


def _gold_drop(private_item: HardPrivateItem) -> tuple[EvaluationItem, ContextPack]:
    item = private_item.evaluation_item
    chunks = tuple(
        chunk for chunk in item.artifact.chunks if chunk.chunk_id not in item.gold_chunk_ids
    )
    dropped = EvaluationItem(
        item_id=item.item_id,
        query=item.query,
        answer=item.answer,
        artifact=Artifact(item.artifact.document_id, chunks),
        gold_chunk_ids=frozenset(),
    )
    return dropped, _all_context(dropped)


def _stored_counterfactual_context(
    private_item: HardPrivateItem,
    *,
    transformed: dict[str, EvaluationItem],
) -> tuple[EvaluationItem, ContextPack]:
    item = transformed[private_item.evaluation_item.item_id]
    return item, _all_context(item)


def _evaluate(
    *,
    condition_name: str,
    condition_role: ConditionRole,
    items: tuple[HardPrivateItem, ...],
    reader: FrozenReader,
    prepare: Callable[[HardPrivateItem], tuple[EvaluationItem, ContextPack]],
    timer: Callable[[], float],
    policy_config: tuple[tuple[str, str | int], ...] = (),
) -> CausalConditionObservation:
    observations: list[CausalItemObservation] = []
    for private_item in items:
        evaluation_item, context = prepare(private_item)
        context.validate(evaluation_item.artifact, Budget(context.token_count))
        if context.abstain or context.request_reread is not None:
            raise ValueError("causal conditions must make exactly one target-reader call")
        before = timer()
        output = reader.read(evaluation_item.query, context)
        wall_seconds = _elapsed(timer() - before)
        if not isinstance(output, ReaderOutput):
            raise TypeError("reader must return ReaderOutput")
        selected_ids = frozenset(span.chunk_id for span in context.spans)
        gold_ids = private_item.evaluation_item.gold_chunk_ids
        observations.append(
            CausalItemObservation(
                item_id=evaluation_item.item_id,
                task_profile=private_item.task_profile.value,
                evidence_position=private_item.evidence_position.value,
                prediction=output.answer,
                score=exact_match(output.answer, evaluation_item.answer),
                gold_recall=len(selected_ids & gold_ids) / len(gold_ids),
                context_tokens=context.token_count,
                reader_input_tokens=output.input_tokens,
                reader_output_tokens=output.output_tokens,
                reader_calls=1,
                wall_seconds=wall_seconds,
                response_id=output.response_id,
                response_model=output.response_model,
            )
        )
    result = tuple(observations)
    profiles = _profile_observations(result)
    return CausalConditionObservation(
        condition_name=condition_name,
        condition_role=condition_role,
        policy_config=policy_config,
        score=fmean(item.score for item in result),
        mean_gold_recall=fmean(item.gold_recall for item in result),
        items=result,
        profiles=profiles,
        reader_calls=sum(item.reader_calls for item in result),
        reader_input_tokens=sum(item.reader_input_tokens for item in result),
        reader_output_tokens=sum(item.reader_output_tokens for item in result),
        wall_seconds=sum(item.wall_seconds for item in result),
    )


def _profile_observations(
    items: tuple[CausalItemObservation, ...],
) -> tuple[CausalProfileObservation, ...]:
    profiles: list[CausalProfileObservation] = []
    for task_profile in HardTaskProfile:
        selected = tuple(item for item in items if item.task_profile == task_profile.value)
        if not selected:
            continue
        profiles.append(
            CausalProfileObservation(
                task_profile=task_profile.value,
                score=fmean(item.score for item in selected),
                mean_gold_recall=fmean(item.gold_recall for item in selected),
                items=selected,
                reader_calls=sum(item.reader_calls for item in selected),
                reader_input_tokens=sum(item.reader_input_tokens for item in selected),
                reader_output_tokens=sum(item.reader_output_tokens for item in selected),
                wall_seconds=sum(item.wall_seconds for item in selected),
            )
        )
    return tuple(profiles)


def _item_disagreement(
    first: CausalConditionObservation,
    second: CausalConditionObservation,
) -> float:
    first_scores = {item.item_id: item.score for item in first.items}
    second_scores = {item.item_id: item.score for item in second.items}
    if first_scores.keys() != second_scores.keys():
        raise RuntimeError("fixed policies did not evaluate identical item IDs")
    return fmean(first_scores[item_id] != second_scores[item_id] for item_id in first_scores)


def _strata(
    fixed: tuple[CausalConditionObservation, ...],
) -> tuple[CausalStratumObservation, ...]:
    result: list[CausalStratumObservation] = []
    for condition in fixed:
        for task_profile in HardTaskProfile:
            for position in EvidencePosition:
                items = tuple(
                    item
                    for item in condition.items
                    if item.task_profile == task_profile.value
                    and item.evidence_position == position.value
                )
                if not items:
                    continue
                scores = tuple(item.score for item in items)
                result.append(
                    CausalStratumObservation(
                        policy_name=condition.condition_name,
                        task_profile=task_profile.value,
                        evidence_position=position.value,
                        item_ids=tuple(item.item_id for item in items),
                        item_scores=scores,
                        item_count=len(items),
                        score=fmean(scores),
                    )
                )
    return tuple(result)


def _qualification_profile_hash(
    *,
    profile_hash: str,
    dataset_fingerprint: str,
    tokenizer_id: str,
    source_tokens: int,
    source_min: int,
    source_max: int,
    policy_budget_tokens: int,
    task_profiles: tuple[str, ...],
    fixed_policy_names: tuple[str, ...],
    policy_spec_hashes: tuple[tuple[str, str], ...],
    counterfactual_fingerprint: str,
    replay_repeats: int,
) -> str:
    canonical = {
        "counterfactual": "replace-answer-in-gold-union-and-query-occurrence-audited-v1",
        "counterfactual_fingerprint": counterfactual_fingerprint,
        "dataset_fingerprint": dataset_fingerprint,
        "fixed_policies": fixed_policy_names,
        "gold_drop": "full-source-minus-all-gold-v1",
        "policy_budget_tokens": policy_budget_tokens,
        "policy_spec_v1_hashes": policy_spec_hashes,
        "reader_profile_hash": profile_hash,
        "replay_repeats": replay_repeats,
        "requested_target_tokens": source_tokens,
        "source_target_tokens_min": source_min,
        "source_target_tokens_max": source_max,
        "task_profiles": task_profiles,
        "tokenizer_id": tokenizer_id,
    }
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _validate_configuration(
    *,
    dataset_seed: str,
    items_per_profile: int,
    task_profiles: tuple[HardTaskProfile, ...],
    source_tokens: int,
    policy_budget_tokens: int,
    replay_repeats: int,
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
    for field_name, value in (
        ("items_per_profile", items_per_profile),
        ("source_tokens", source_tokens),
        ("policy_budget_tokens", policy_budget_tokens),
        ("replay_repeats", replay_repeats),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer")
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
    if replay_repeats < 3:
        raise ValueError("replay_repeats must be at least 3")
    if policy_budget_tokens > source_tokens:
        raise ValueError("policy budget cannot exceed the source length")
    if (
        not task_profiles
        or len(task_profiles) != len(set(task_profiles))
        or any(not isinstance(task_profile, HardTaskProfile) for task_profile in task_profiles)
    ):
        raise ValueError("task_profiles must be non-empty and unique HardTaskProfile values")
    if HardTaskProfile.INSUFFICIENT_EVIDENCE in task_profiles:
        raise ValueError("abstention tasks cannot support answer-rewrite counterfactuals")


def _elapsed(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("hard causal gate timer returned an invalid duration")
    return value


def _profile_score(condition: CausalConditionObservation, profile: str) -> float:
    for observation in condition.profiles:
        if observation.task_profile == profile:
            return observation.score
    raise RuntimeError(f"missing profile observation: {profile}")


def _median_meaningful_delta(scores: tuple[float, ...]) -> float:
    unique = tuple(sorted(set(scores)))
    if len(unique) < 2:
        return 0.25
    gaps = [unique[index + 1] - unique[index] for index in range(len(unique) - 1)]
    gaps.sort()
    median = gaps[len(gaps) // 2]
    return median if median > 0 else 0.25


def _profile_score_vector(condition: CausalConditionObservation, profile: str) -> tuple[float, ...]:
    return tuple(item.score for item in condition.items if item.task_profile == profile)


def _assess_difficulty(
    *,
    profiles: tuple[str, ...],
    search_space: tuple[CausalConditionObservation, ...],
    no_context: CausalConditionObservation,
    gold_only: CausalConditionObservation,
    bounded_oracle: CausalConditionObservation,
    full_context: CausalConditionObservation,
    gold_drop: CausalConditionObservation,
    counterfactual: CausalConditionObservation,
    strata: tuple[CausalStratumObservation, ...],
    replay_standard_deviation: float,
) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for profile in profiles:
        ranked = tuple(
            sorted(
                search_space,
                key=lambda condition: (
                    -_profile_score(condition, profile),
                    condition.condition_name,
                ),
            )
        )
        non_oracle = tuple(
            (condition.condition_name, _profile_score(condition, profile)) for condition in ranked
        )
        scores = tuple(score for _, score in non_oracle)
        drop = max(0.0, _profile_score(full_context, profile) - _profile_score(gold_drop, profile))
        stratum_scores = tuple(
            (stratum.evidence_position, stratum.score)
            for stratum in strata
            if stratum.task_profile == profile
        )
        measured = DifficultyMeasurements(
            profile=profile,
            chance_accuracy=0.0,
            gold_only_accuracy=_profile_score(gold_only, profile),
            bounded_oracle_accuracy=_profile_score(bounded_oracle, profile),
            no_context_accuracy=_profile_score(no_context, profile),
            non_oracle_scores=non_oracle,
            strongest_policy_disagreement=clone_aware_item_disagreement(
                tuple(_profile_score_vector(condition, profile) for condition in ranked)
            ),
            gold_drop=drop,
            counterfactual_following=_profile_score(counterfactual, profile),
            stratum_scores=stratum_scores,
            replay_standard_deviation=replay_standard_deviation,
            median_meaningful_delta=_median_meaningful_delta(scores),
        )
        verdict = evaluate_difficulty(measured)
        results.append((verdict.profile, verdict.passed, verdict.failures))
    return tuple(results)
