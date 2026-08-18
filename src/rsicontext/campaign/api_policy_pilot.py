"""Small API-backed policy qualification with a known dynamic score shape."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsicontext.analysis import ReplaySummary, TrajectoryMetrics, replay_summary, trajectory_metrics
from rsicontext.eval import (
    EvaluationItem,
    FrozenReader,
    OpenAICompatibleReader,
    ReaderOutput,
    evaluate,
    replay,
)
from rsicontext.experiment import APIProfile
from rsicontext.experiment.api_length import calibrated_noise_words
from rsicontext.policy import (
    Artifact,
    Budget,
    ContextPack,
    ContextPolicy,
    DocumentChunk,
    LexicalPolicy,
    TruncationPolicy,
)

_ANSWER = "AURORA-7319"
_QUERY = "What is the unique access code? Return only the code."
_CHUNK_TOKENS = 4_096
_SOURCE_TOKENS = 32_768
_POLICY_TOKENS = 8_192


@dataclass(frozen=True, slots=True)
class APIPolicyObservation:
    policy_name: str
    context_budget_tokens: int
    score: float
    item_scores: tuple[float, ...]
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class APIPolicyPilotResult:
    schema_version: int
    started_at: str
    profile_id: str
    profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    version_pinned: bool
    source_tokens: int
    policy_budget_tokens: int
    item_ids: tuple[str, ...]
    policies: tuple[APIPolicyObservation, ...]
    trajectory: TrajectoryMetrics
    replay: ReplaySummary
    replay_reader_calls: int
    replay_reader_input_tokens: int
    replay_reader_output_tokens: int
    replay_wall_seconds: float
    qualification_only: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_api_policy_pilot(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str,
    reader: FrozenReader | None = None,
    timer: Callable[[], float] = time.perf_counter,
    started_at: str | None = None,
) -> APIPolicyPilotResult:
    """Compare fixed policies; this qualifies the locus but is not agent discovery."""

    actual_reader: FrozenReader = reader or OpenAICompatibleReader(
        endpoint=endpoint,
        model=profile.model,
        max_tokens=min(16, profile.max_output_tokens),
        max_model_len=profile.evaluation_max_model_len,
        seed=profile.seed,
        stream=True,
        require_response_model=True,
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        allowed_hosts=(profile.allowed_host,),
        api_key=api_key,
    )
    accounted_reader = _AccountingReader(actual_reader)
    items = _items()
    candidates: tuple[
        tuple[str, Callable[[], ContextPolicy], Budget],
        ...,
    ] = (
        ("head-8k", lambda: TruncationPolicy("head"), Budget(_POLICY_TOKENS)),
        ("lexical-8k", LexicalPolicy, Budget(_POLICY_TOKENS)),
        ("tail-8k", lambda: TruncationPolicy("tail"), Budget(_POLICY_TOKENS)),
        ("head-tail-8k", lambda: TruncationPolicy("head_tail"), Budget(_POLICY_TOKENS)),
        ("full-32k", lambda: TruncationPolicy("head"), Budget(_SOURCE_TOKENS)),
    )
    observations: list[APIPolicyObservation] = []
    for name, policy_factory, budget in candidates:
        before = timer()
        result = evaluate(policy_factory, items, accounted_reader, budget)
        elapsed = _elapsed(timer() - before)
        observations.append(
            APIPolicyObservation(
                policy_name=name,
                context_budget_tokens=budget.max_tokens,
                score=result.score,
                item_scores=result.item_scores,
                reader_input_tokens=sum(result.reader_input_tokens),
                reader_output_tokens=sum(result.reader_output_tokens),
                wall_seconds=elapsed,
            )
        )
    replay_start_calls = accounted_reader.calls
    replay_start_input_tokens = accounted_reader.input_tokens
    replay_start_output_tokens = accounted_reader.output_tokens
    before = timer()
    fixed_replay = replay(
        LexicalPolicy,
        items,
        accounted_reader,
        Budget(_POLICY_TOKENS),
        repeats=3,
    )
    replay_wall_seconds = _elapsed(timer() - before)
    timestamp = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    policy_results = tuple(observations)
    trajectory_scores = tuple(observation.score for observation in policy_results[:3])
    return APIPolicyPilotResult(
        schema_version=2,
        started_at=timestamp,
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        version_pinned=profile.version_pinned,
        source_tokens=_SOURCE_TOKENS,
        policy_budget_tokens=_POLICY_TOKENS,
        item_ids=tuple(item.item_id for item in items),
        policies=policy_results,
        trajectory=trajectory_metrics(trajectory_scores),
        replay=replay_summary(fixed_replay.scores),
        replay_reader_calls=accounted_reader.calls - replay_start_calls,
        replay_reader_input_tokens=(accounted_reader.input_tokens - replay_start_input_tokens),
        replay_reader_output_tokens=(accounted_reader.output_tokens - replay_start_output_tokens),
        replay_wall_seconds=replay_wall_seconds,
        qualification_only=True,
    )


def write_api_policy_pilot(result: APIPolicyPilotResult, path: str | Path) -> None:
    """Write one immutable policy-pilot record without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _elapsed(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("policy pilot timer returned an invalid duration")
    return value


class _AccountingReader:
    def __init__(self, reader: FrozenReader) -> None:
        self.reader = reader
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        output = self.reader.read(query, context)
        self.calls += 1
        self.input_tokens += output.input_tokens
        self.output_tokens += output.output_tokens
        return output


def _items() -> tuple[EvaluationItem, ...]:
    needle_chunk = {"front": 0, "middle": 4, "tail": 7}
    items: list[EvaluationItem] = []
    for position, needle_index in needle_chunk.items():
        document_id = f"policy-pilot-{position}"
        chunks: list[DocumentChunk] = []
        offset = 0
        for index in range(8):
            words = list(calibrated_noise_words(_CHUNK_TOKENS))
            if index == needle_index:
                words.insert(len(words) // 2, f"The unique access code is {_ANSWER}.")
            text = " ".join(words)
            chunk = DocumentChunk(
                chunk_id=f"{document_id}-c{index}",
                document_id=document_id,
                start=offset,
                end=offset + len(text),
                text=text,
                token_count=_CHUNK_TOKENS,
            )
            chunks.append(chunk)
            offset = chunk.end + 1
        gold_chunk_id = chunks[needle_index].chunk_id
        items.append(
            EvaluationItem(
                item_id=f"api-policy-{position}",
                query=_QUERY,
                answer=_ANSWER,
                artifact=Artifact(document_id, tuple(chunks)),
                gold_chunk_ids=frozenset({gold_chunk_id}),
            )
        )
    return tuple(items)
