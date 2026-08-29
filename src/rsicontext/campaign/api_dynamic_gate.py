"""API-backed fixed-policy qualification on the visible dynamic 32K panel."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsicontext.datasets import (
    DYNAMIC_CONTEXT_TOKENS,
    DynamicPrivateItem,
    DynamicTaskProfile,
    generate_dynamic_long_context_dataset,
)
from rsicontext.eval import FrozenReader, ReaderOutput, exact_match
from rsicontext.experiment.api import (
    APIProfile,
    ResolvedAPIEndpoint,
    build_profile_reader,
)
from rsicontext.policy import (
    Budget,
    ContextPack,
    ContextPolicy,
    LexicalPolicy,
    TruncationPolicy,
)
from rsicontext.registry import RegistryEntry, ServingProfile
from rsicontext.registry.schema import RegistryError

_POLICY_TOKENS = 8_192
_DYNAMIC_OUTPUT_TOKENS = 512
_DEFAULT_DATASET_SEED = "api-dynamic-visible-v1"
_DEFAULT_ITEMS_PER_PROFILE = 2


@dataclass(frozen=True, slots=True)
class DynamicProfileObservation:
    task_profile: str
    score: float
    item_ids: tuple[str, ...]
    item_scores: tuple[float, ...]
    gold_recall: tuple[float, ...]
    mean_gold_recall: float
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class DynamicPolicyObservation:
    policy_name: str
    context_budget_tokens: int
    score: float
    mean_gold_recall: float
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    profiles: tuple[DynamicProfileObservation, ...]


@dataclass(frozen=True, slots=True)
class APIDynamicGateResult:
    schema_version: int
    started_at: str
    profile_id: str
    profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    version_pinned: bool
    dataset_fingerprint: str
    split: str
    source_tokens: int
    policy_budget_tokens: int
    max_output_tokens: int
    items_per_profile: int
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    policies: tuple[DynamicPolicyObservation, ...]
    qualification_only: bool
    serving_profile_id: str | None
    serving_profile_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dynamic_reader_output_limit(profile: APIProfile) -> int:
    """Reserve enough output for aggregation before the final short answer."""

    return min(_DYNAMIC_OUTPUT_TOKENS, profile.max_output_tokens)


def build_local_vllm_profile(
    serving_profile: ServingProfile,
    model: RegistryEntry,
    *,
    vllm_version: str,
) -> APIProfile:
    """Bind a local API identity to one pinned model and serving profile."""

    if model.kind != "model" or model.id != serving_profile.model_id:
        raise RegistryError("serving profile does not match the registered model")
    if model.revision is None:
        raise RegistryError("local dynamic evaluation requires a pinned model revision")
    model_name = model.url.removeprefix("https://huggingface.co/").rstrip("/")
    return APIProfile(
        id=f"local-{serving_profile.id}",
        provider=f"vllm-{vllm_version}",
        endpoint_env="RSICONTEXT_LOCAL_VLLM_ENDPOINT",
        api_key_env="RSICONTEXT_LOCAL_VLLM_API_KEY",
        allowed_host="127.0.0.1",
        model=model_name,
        protocol="chat-completions-sse",
        evaluation_max_model_len=serving_profile.max_model_len,
        max_output_tokens=_DYNAMIC_OUTPUT_TOKENS,
        seed=serving_profile.seed,
        temperature=0.0,
        provider_revision=model.revision,
        chat_template_enable_thinking=False,
        api_key_required=False,
    )


def run_api_dynamic_gate(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str | None,
    reader: FrozenReader | None = None,
    dataset_seed: str = _DEFAULT_DATASET_SEED,
    items_per_profile: int = _DEFAULT_ITEMS_PER_PROFILE,
    timer: Callable[[], float] = time.perf_counter,
    started_at: str | None = None,
    serving_profile_id: str | None = None,
    serving_profile_hash: str | None = None,
) -> APIDynamicGateResult:
    """Evaluate fixed baselines on visible items; this is not researcher discovery."""

    if (serving_profile_id is None) != (serving_profile_hash is None):
        raise ValueError("serving profile id and hash must be supplied together")

    dataset = generate_dynamic_long_context_dataset(
        seed=dataset_seed,
        items_per_profile=items_per_profile,
    )
    actual_reader: FrozenReader = reader or build_profile_reader(
        profile,
        ResolvedAPIEndpoint(endpoint=endpoint, api_key=api_key),
        max_tokens=dynamic_reader_output_limit(profile),
    )
    candidates: tuple[
        tuple[str, Callable[[], ContextPolicy], Budget],
        ...,
    ] = (
        ("head-8k", lambda: TruncationPolicy("head"), Budget(_POLICY_TOKENS)),
        ("head-tail-8k", lambda: TruncationPolicy("head_tail"), Budget(_POLICY_TOKENS)),
        ("lexical-8k", LexicalPolicy, Budget(_POLICY_TOKENS)),
        ("full-32k", lambda: TruncationPolicy("head"), Budget(DYNAMIC_CONTEXT_TOKENS)),
    )
    visible = dataset.visible_items()
    observations: list[DynamicPolicyObservation] = []
    for policy_name, policy_factory, budget in candidates:
        profile_observations = tuple(
            _evaluate_profile(
                task_profile=task_profile,
                private_items=tuple(item for item in visible if item.task_profile is task_profile),
                policy_factory=policy_factory,
                budget=budget,
                reader=actual_reader,
                timer=timer,
            )
            for task_profile in DynamicTaskProfile
        )
        observations.append(
            DynamicPolicyObservation(
                policy_name=policy_name,
                context_budget_tokens=budget.max_tokens,
                score=_weighted_mean(
                    tuple(
                        (observation.score, len(observation.item_scores))
                        for observation in profile_observations
                    )
                ),
                mean_gold_recall=_weighted_mean(
                    tuple(
                        (observation.mean_gold_recall, len(observation.gold_recall))
                        for observation in profile_observations
                    )
                ),
                reader_input_tokens=sum(
                    observation.reader_input_tokens for observation in profile_observations
                ),
                reader_output_tokens=sum(
                    observation.reader_output_tokens for observation in profile_observations
                ),
                wall_seconds=sum(observation.wall_seconds for observation in profile_observations),
                profiles=profile_observations,
            )
        )
    policies = tuple(observations)
    timestamp = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return APIDynamicGateResult(
        schema_version=2,
        started_at=timestamp,
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        version_pinned=profile.version_pinned,
        dataset_fingerprint=dataset.fingerprint,
        split="visible",
        source_tokens=DYNAMIC_CONTEXT_TOKENS,
        policy_budget_tokens=_POLICY_TOKENS,
        max_output_tokens=dynamic_reader_output_limit(profile),
        items_per_profile=items_per_profile,
        reader_calls=sum(
            len(observation.item_scores) for policy in policies for observation in policy.profiles
        ),
        reader_input_tokens=sum(policy.reader_input_tokens for policy in policies),
        reader_output_tokens=sum(policy.reader_output_tokens for policy in policies),
        wall_seconds=sum(policy.wall_seconds for policy in policies),
        policies=policies,
        qualification_only=True,
        serving_profile_id=serving_profile_id,
        serving_profile_hash=serving_profile_hash,
    )


def write_api_dynamic_gate(result: APIDynamicGateResult, path: str | Path) -> None:
    """Write one immutable dynamic-gate record without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _evaluate_profile(
    *,
    task_profile: DynamicTaskProfile,
    private_items: tuple[DynamicPrivateItem, ...],
    policy_factory: Callable[[], ContextPolicy],
    budget: Budget,
    reader: FrozenReader,
    timer: Callable[[], float],
) -> DynamicProfileObservation:
    if not private_items:
        raise ValueError("dynamic profile evaluation items must be non-empty")
    item_ids: list[str] = []
    item_scores: list[float] = []
    gold_recall: list[float] = []
    reader_input_tokens = 0
    reader_output_tokens = 0
    before = timer()
    for private_item in private_items:
        item = private_item.evaluation_item
        context = policy_factory().assemble(item.artifact, item.query, budget)
        context.validate(item.artifact, budget)
        if context.abstain or context.request_reread is not None:
            raise ValueError("fixed dynamic baselines must make exactly one reader call")
        output = reader.read(item.query, context)
        if not isinstance(output, ReaderOutput):
            raise TypeError("reader must return ReaderOutput")
        selected_ids = _selected_source_ids(context)
        item_ids.append(item.item_id)
        item_scores.append(exact_match(output.answer, item.answer))
        gold_recall.append(len(selected_ids & item.gold_chunk_ids) / len(item.gold_chunk_ids))
        reader_input_tokens += output.input_tokens
        reader_output_tokens += output.output_tokens
    wall_seconds = _elapsed(timer() - before)
    return DynamicProfileObservation(
        task_profile=task_profile.value,
        score=sum(item_scores) / len(item_scores),
        item_ids=tuple(item_ids),
        item_scores=tuple(item_scores),
        gold_recall=tuple(gold_recall),
        mean_gold_recall=sum(gold_recall) / len(gold_recall),
        reader_input_tokens=reader_input_tokens,
        reader_output_tokens=reader_output_tokens,
        wall_seconds=wall_seconds,
    )


def _selected_source_ids(context: ContextPack) -> frozenset[str]:
    return frozenset(
        (
            *(span.chunk_id for span in context.spans),
            *(source_id for note in context.notes for source_id in note.source_chunk_ids),
        )
    )


def _weighted_mean(values: tuple[tuple[float, int], ...]) -> float:
    total_weight = sum(weight for _, weight in values)
    if total_weight < 1:
        raise ValueError("weighted mean requires positive total weight")
    return sum(value * weight for value, weight in values) / total_weight


def _elapsed(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("dynamic gate timer returned an invalid duration")
    return value
