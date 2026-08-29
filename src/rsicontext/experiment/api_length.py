"""Recorded length/position replay gate for external API readers."""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, build_profile_reader
from rsicontext.policy import ContextPack, DocumentChunk

LengthPosition = Literal["front", "middle", "tail"]
_POSITIONS = frozenset({"front", "middle", "tail"})
_QUERY = "What is the unique access code? Return only the code."
_ANSWER = "AURORA-7319"
_NEEDLE = "The unique access code is AURORA-7319."
_PROMPT_RESERVE_WORDS = 128
_HAYSTACK_WORDS_PER_TARGET_TOKEN = 0.79
_HAYSTACK_WORDS = tuple(
    [
        "The",
        "grass",
        "is",
        "green.",
        "The",
        "sky",
        "is",
        "blue.",
        "The",
        "sun",
        "is",
        "yellow.",
        "Here",
        "we",
        "go.",
        "There",
        "and",
        "back",
        "again.",
    ]
)


@dataclass(frozen=True, slots=True)
class APILengthObservation:
    target_tokens: int
    position: LengthPosition
    repetition: int
    answer: str
    correct: bool
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    response_id: str
    observed_model: str


@dataclass(frozen=True, slots=True)
class APILengthCellSummary:
    target_tokens: int
    position: LengthPosition
    repetitions: int
    accuracy: float
    score_standard_deviation: float
    answer_stable: bool
    usage_stable: bool
    input_tokens_mean: float
    input_tokens_span: int
    output_tokens_mean: float
    latency_mean_seconds: float


@dataclass(frozen=True, slots=True)
class APILengthCanaryResult:
    schema_version: int
    canary_id: str
    started_at: str
    endpoint: str
    profile_id: str
    profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    version_pinned: bool
    seed: int
    temperature: float
    target_lengths: tuple[int, ...]
    positions: tuple[LengthPosition, ...]
    repetitions: int
    expected_answer: str
    observations: tuple[APILengthObservation, ...]
    summaries: tuple[APILengthCellSummary, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_api_length_canary(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str | None,
    target_lengths: tuple[int, ...] = (8_192, 32_768),
    positions: tuple[LengthPosition, ...] = ("front", "middle", "tail"),
    repetitions: int = 3,
    transport: Transport | None = None,
    timer: Any = time.perf_counter,
    started_at: str | None = None,
) -> APILengthCanaryResult:
    """Run a deterministic single-needle matrix and preserve every observation."""

    _validate_matrix(profile, target_lengths, positions, repetitions)
    reader = build_profile_reader(
        profile,
        ResolvedAPIEndpoint(endpoint=endpoint, api_key=api_key),
        max_tokens=min(16, profile.max_output_tokens),
        transport=transport,
    )
    observations: list[APILengthObservation] = []
    for target_tokens in target_lengths:
        for position in positions:
            context = _length_context(target_tokens, position)
            for repetition in range(repetitions):
                before = timer()
                output = reader.read(_QUERY, context)
                latency = timer() - before
                if not isinstance(latency, (int, float)) or not math.isfinite(latency):
                    raise RuntimeError("API length canary timer returned an invalid duration")
                if latency < 0:
                    raise RuntimeError("API length canary timer returned an invalid duration")
                if output.response_id is None or output.response_model is None:
                    raise RuntimeError("strict API length reader returned no response identity")
                observations.append(
                    APILengthObservation(
                        target_tokens=target_tokens,
                        position=position,
                        repetition=repetition,
                        answer=output.answer,
                        correct=output.answer.strip().casefold() == _ANSWER.casefold(),
                        input_tokens=output.input_tokens,
                        output_tokens=output.output_tokens,
                        latency_seconds=float(latency),
                        response_id=output.response_id,
                        observed_model=output.response_model,
                    )
                )
    timestamp = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    frozen_observations = tuple(observations)
    return APILengthCanaryResult(
        schema_version=1,
        canary_id="single-needle-noise-v3",
        started_at=timestamp,
        endpoint=endpoint,
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        version_pinned=profile.version_pinned,
        seed=profile.seed,
        temperature=profile.temperature,
        target_lengths=target_lengths,
        positions=positions,
        repetitions=repetitions,
        expected_answer=_ANSWER,
        observations=frozen_observations,
        summaries=_summaries(frozen_observations, target_lengths, positions),
    )


def write_api_length_canary(result: APILengthCanaryResult, path: str | Path) -> None:
    """Write one immutable length-gate record without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _validate_matrix(
    profile: APIProfile,
    target_lengths: tuple[int, ...],
    positions: tuple[LengthPosition, ...],
    repetitions: int,
) -> None:
    if not isinstance(target_lengths, tuple) or not target_lengths:
        raise TypeError("target_lengths must be a non-empty tuple")
    if any(
        not isinstance(length, int)
        or isinstance(length, bool)
        or length <= _PROMPT_RESERVE_WORDS
        or length + profile.max_output_tokens >= profile.evaluation_max_model_len
        for length in target_lengths
    ):
        raise ValueError("target lengths must fit inside the registered evaluation limit")
    if len(target_lengths) != len(set(target_lengths)):
        raise ValueError("target lengths must be unique")
    if not isinstance(positions, tuple) or not positions:
        raise TypeError("positions must be a non-empty tuple")
    if any(position not in _POSITIONS for position in positions):
        raise ValueError("positions must be front, middle, or tail")
    if len(positions) != len(set(positions)):
        raise ValueError("positions must be unique")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")


def _length_context(target_tokens: int, position: LengthPosition) -> ContextPack:
    filler = list(calibrated_noise_words(target_tokens))
    filler_count = len(filler)
    insertion = {
        "front": 0,
        "middle": filler_count // 2,
        "tail": filler_count,
    }[position]
    words = (*filler[:insertion], _NEEDLE, *filler[insertion:])
    text = " ".join(words)
    chunk = DocumentChunk(
        chunk_id=f"length-{target_tokens}-{position}",
        document_id=f"length-{target_tokens}",
        start=0,
        end=len(text),
        text=text,
        token_count=target_tokens,
    )
    return ContextPack(spans=(chunk,), ordering=(chunk.chunk_id,), token_count=chunk.token_count)


def calibrated_noise_words(target_tokens: int) -> tuple[str, ...]:
    """Return deterministic RULER-style noise calibrated to API-reported tokens."""

    if (
        not isinstance(target_tokens, int)
        or isinstance(target_tokens, bool)
        or target_tokens <= _PROMPT_RESERVE_WORDS
    ):
        raise ValueError("target_tokens must exceed the prompt reserve")
    filler_count = max(
        int((target_tokens - _PROMPT_RESERVE_WORDS) * _HAYSTACK_WORDS_PER_TARGET_TOKEN),
        1,
    )
    return tuple(_HAYSTACK_WORDS[index % len(_HAYSTACK_WORDS)] for index in range(filler_count))


def _summaries(
    observations: tuple[APILengthObservation, ...],
    target_lengths: tuple[int, ...],
    positions: tuple[LengthPosition, ...],
) -> tuple[APILengthCellSummary, ...]:
    summaries: list[APILengthCellSummary] = []
    for target_tokens in target_lengths:
        for position in positions:
            cell = tuple(
                observation
                for observation in observations
                if observation.target_tokens == target_tokens and observation.position == position
            )
            scores = tuple(float(observation.correct) for observation in cell)
            answers = tuple(observation.answer for observation in cell)
            input_tokens = tuple(observation.input_tokens for observation in cell)
            output_tokens = tuple(observation.output_tokens for observation in cell)
            summaries.append(
                APILengthCellSummary(
                    target_tokens=target_tokens,
                    position=position,
                    repetitions=len(cell),
                    accuracy=statistics.fmean(scores),
                    score_standard_deviation=statistics.pstdev(scores),
                    answer_stable=len(set(answers)) == 1,
                    usage_stable=(len(set(input_tokens)) == 1 and len(set(output_tokens)) == 1),
                    input_tokens_mean=statistics.fmean(input_tokens),
                    input_tokens_span=max(input_tokens) - min(input_tokens),
                    output_tokens_mean=statistics.fmean(output_tokens),
                    latency_mean_seconds=statistics.fmean(
                        observation.latency_seconds for observation in cell
                    ),
                )
            )
    return tuple(summaries)
