"""Scorer-aware replay qualification for configuration-frozen API readers."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import statistics
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rsicontext.eval import EvaluationItem, EvaluationResult, ReaderOutput, evaluate
from rsicontext.eval.core import FrozenReader, PolicyFactory, Scorer
from rsicontext.eval.openai_compatible import (
    _SYSTEM_PROMPT,
    OpenAICompatibleReader,
    Transport,
    _urlopen_transport,
)
from rsicontext.experiment.api import (
    APICanaryResult,
    APIProfile,
    ResolvedAPIEndpoint,
    build_profile_reader,
    run_api_canary,
)
from rsicontext.policy import Budget, ContextPack

_CANARY_ANSWER = "amber"
_EVIDENCE_TIER = "configuration-frozen-black-box-v1"
_TEST_EVIDENCE_TIER = "non-public-test-transport-v1"
_SCHEDULE = "pre-canary/task-first-half/mid-canary/task-second-half/post-canary"
_TIMEOUT_SECONDS = 30.0
_PUBLIC_MIN_ITEMS = 40
_PUBLIC_MIN_REPETITIONS = 5
_PUBLIC_MIN_CANARY_REPETITIONS = 3
_PUBLIC_TIMER_NAME = "time.perf_counter"


class OperationalReplayExecutionError(RuntimeError):
    """Execution failed after a known number of endpoint attempts."""

    def __init__(
        self,
        attempted_reader_calls: int,
        completed_transport_calls: int,
        phase: str,
        cause: Exception,
    ) -> None:
        super().__init__(f"operational replay execution failed: {cause}")
        self.attempted_reader_calls = attempted_reader_calls
        self.completed_transport_calls = completed_transport_calls
        self.phase = phase
        self.cause_type = type(cause).__name__


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _callable_identity(function: Callable[..., object]) -> tuple[str, str, str]:
    name = f"{function.__module__}.{function.__qualname__}"
    try:
        source = inspect.getsource(function).encode()
        module = inspect.getmodule(function)
        if module is None:
            raise ValueError(f"callable module is unavailable: {name}")
        module_source = inspect.getsource(module).encode()
    except (OSError, TypeError) as exc:
        raise ValueError(f"callable source is unavailable: {name}") from exc
    return name, hashlib.sha256(source).hexdigest(), hashlib.sha256(module_source).hexdigest()


def _evaluation_items_sha256(items: tuple[EvaluationItem, ...]) -> str:
    payload = []
    for item in items:
        payload.append(
            {
                "answer": item.answer,
                "artifact": {
                    "document_id": item.artifact.document_id,
                    "chunks": [asdict(chunk) for chunk in item.artifact.chunks],
                    "notes": [asdict(note) for note in item.artifact.notes],
                },
                "gold_chunk_ids": sorted(item.gold_chunk_ids),
                "item_id": item.item_id,
                "query": item.query,
            }
        )
    return _canonical_sha256(payload)


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class OperationalReplayContract:
    """Immutable allocation and identity contract for one API A/A replay block."""

    task_id: str
    dataset_fingerprint: str
    evaluation_items_sha256: str
    item_count: int
    ordered_item_ids_sha256: str
    profile_id: str
    profile_hash: str
    endpoint_sha256: str
    requested_model: str
    provider_revision: str | None
    policy_name: str
    policy_sha256: str
    policy_module_sha256: str
    scorer_name: str
    scorer_sha256: str
    scorer_module_sha256: str
    token_axis_id: str
    source_id: str
    source_revision: str
    source_sha256: str
    producer_git_revision: str | None
    producer_attestation_sha256: str | None
    reader_class_name: str
    reader_class_sha256: str
    reader_module_sha256: str
    reader_builder_name: str
    reader_builder_sha256: str
    reader_builder_module_sha256: str
    default_transport_name: str
    default_transport_sha256: str
    default_transport_module_sha256: str
    runner_name: str
    runner_sha256: str
    runner_module_sha256: str
    system_prompt_sha256: str
    chat_template_enable_thinking: bool | None
    timeout_seconds: float
    timer_name: str
    budget: Budget
    reader_max_output_tokens: int
    repetitions: int
    canary_repetitions: int
    max_reader_calls: int
    max_score_standard_deviation: float
    max_item_flip_rate: float
    test_transport_allowed: bool = False
    require_input_token_stability: bool = True
    schedule: str = _SCHEDULE
    evidence_tier: str = _EVIDENCE_TIER
    qualification_only: bool = True
    hidden_weights_attested: bool = False
    request_profile_frozen: bool = True
    schema_version: int = 1

    def __post_init__(self) -> None:
        for field in (
            "dataset_fingerprint",
            "evaluation_items_sha256",
            "ordered_item_ids_sha256",
            "profile_hash",
            "endpoint_sha256",
            "policy_sha256",
            "policy_module_sha256",
            "scorer_sha256",
            "scorer_module_sha256",
            "source_sha256",
            "reader_class_sha256",
            "reader_module_sha256",
            "reader_builder_sha256",
            "reader_builder_module_sha256",
            "default_transport_sha256",
            "default_transport_module_sha256",
            "runner_sha256",
            "runner_module_sha256",
            "system_prompt_sha256",
        ):
            _require_digest(getattr(self, field), field)
        for field in (
            "task_id",
            "profile_id",
            "requested_model",
            "policy_name",
            "scorer_name",
            "token_axis_id",
            "source_id",
            "source_revision",
            "reader_class_name",
            "reader_builder_name",
            "default_transport_name",
            "runner_name",
            "timer_name",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        for field in (
            "item_count",
            "reader_max_output_tokens",
            "repetitions",
            "canary_repetitions",
            "max_reader_calls",
        ):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if not isinstance(self.budget, Budget) or self.budget.max_tokens <= 0:
            raise ValueError("budget must be a positive Budget")
        expected_calls = self.item_count * self.repetitions + 3 * self.canary_repetitions
        if self.max_reader_calls != expected_calls:
            raise ValueError("max_reader_calls must equal task replays plus three canary blocks")
        for field in ("max_score_standard_deviation", "max_item_flip_rate"):
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{field} must be finite and within [0, 1]")
        if not isinstance(self.test_transport_allowed, bool):
            raise TypeError("test_transport_allowed must be a boolean")
        expected_tier = _TEST_EVIDENCE_TIER if self.test_transport_allowed else _EVIDENCE_TIER
        if self.evidence_tier != expected_tier:
            raise ValueError("unsupported operational replay evidence tier")
        if self.schedule != _SCHEDULE:
            raise ValueError("unsupported operational replay schedule")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if not isinstance(self.require_input_token_stability, bool):
            raise TypeError("require_input_token_stability must be a boolean")
        if self.chat_template_enable_thinking is not None and not isinstance(
            self.chat_template_enable_thinking, bool
        ):
            raise TypeError("chat_template_enable_thinking must be a boolean or null")
        if not self.test_transport_allowed:
            if self.item_count < _PUBLIC_MIN_ITEMS:
                raise ValueError("public qualification requires at least 40 task items")
            if self.repetitions < _PUBLIC_MIN_REPETITIONS:
                raise ValueError("public qualification requires at least five task replays")
            if self.canary_repetitions < _PUBLIC_MIN_CANARY_REPETITIONS:
                raise ValueError("public qualification requires at least three canary replays")
            if self.max_score_standard_deviation != 0.0 or self.max_item_flip_rate != 0.0:
                raise ValueError("public qualification stability thresholds are locked to zero")
            if (
                self.producer_git_revision is None
                or len(self.producer_git_revision) != 40
                or any(
                    character not in "0123456789abcdef" for character in self.producer_git_revision
                )
            ):
                raise ValueError("public qualification requires a committed producer revision")
            if self.producer_attestation_sha256 is None:
                raise ValueError("public qualification requires a producer attestation digest")
            _require_digest(self.producer_attestation_sha256, "producer_attestation_sha256")
        elif self.producer_git_revision is not None or self.producer_attestation_sha256 is not None:
            raise ValueError("test replay cannot claim producer attestation")
        if (
            self.qualification_only is not True
            or self.hidden_weights_attested is not False
            or self.request_profile_frozen is not True
            or self.schema_version != 1
        ):
            raise ValueError("operational replay is qualification-only and does not attest weights")

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OperationalItemReplay:
    item_id_sha256: str
    scores: tuple[float, ...]
    prediction_sha256: tuple[str, ...]
    input_tokens: tuple[int, ...]
    output_tokens: tuple[int, ...]
    latency_seconds: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class OperationalAnchorSummary:
    phase: str
    started_at: str
    repetitions: int
    canonical_correct_count: int
    task_scorer_correct_count: int
    raw_answer_distinct_count: int
    input_tokens: tuple[int, ...]
    output_tokens: tuple[int, ...]
    latency_mean_seconds: float
    observed_models: tuple[str, ...]
    response_ids_sha256: str


@dataclass(frozen=True, slots=True)
class OperationalReplayResult:
    contract_sha256: str
    reader_calls: int
    aggregate_scores: tuple[float, ...]
    score_standard_deviation: float
    item_count: int
    item_flip_count: int
    item_flip_rate: float
    item_flip_rate_upper_95: float
    semantic_canary_passed: bool
    raw_canary_answer_stable: bool
    input_usage_stable: bool
    output_usage_stable: bool
    observed_model_stable: bool
    anchor_summaries: tuple[OperationalAnchorSummary, ...]
    item_replays: tuple[OperationalItemReplay, ...]
    failures: tuple[str, ...]
    operational_block_passed: bool
    qualification_only: bool = True
    rsi_launch_eligible: bool = False
    meaningful_policy_delta: float | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("item_replays")
        return payload


@dataclass(slots=True)
class _ObservedCall:
    output: ReaderOutput
    latency_seconds: float


class _RecordingReader:
    def __init__(self, reader: FrozenReader, timer: Callable[[], float]) -> None:
        self._reader = reader
        self._timer = timer
        self.calls: list[_ObservedCall] = []

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        before = self._timer()
        output = self._reader.read(query, context)
        latency = self._timer() - before
        if not math.isfinite(latency) or latency < 0:
            raise RuntimeError("operational replay timer returned an invalid duration")
        self.calls.append(_ObservedCall(output, latency))
        return output


def build_operational_replay_contract(
    *,
    task_id: str,
    dataset_fingerprint: str,
    items: tuple[EvaluationItem, ...],
    profile: APIProfile,
    endpoint: str,
    policy_factory: PolicyFactory,
    scorer: Scorer,
    budget: Budget,
    token_axis_id: str,
    source_id: str,
    source_revision: str,
    source_sha256: str,
    repetitions: int,
    canary_repetitions: int,
    max_score_standard_deviation: float,
    max_item_flip_rate: float,
    reader_max_output_tokens: int | None = None,
    test_transport_allowed: bool = False,
    producer_git_revision: str | None = None,
    producer_attestation_sha256: str | None = None,
) -> OperationalReplayContract:
    """Bind a real task replay block before any endpoint call."""

    if not items:
        raise ValueError("operational replay requires at least one item")
    item_ids = tuple(item.item_id for item in items)
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("operational replay item ids must be unique")
    _require_digest(dataset_fingerprint, "dataset_fingerprint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint must be a non-empty string")
    output_tokens = (
        profile.max_output_tokens if reader_max_output_tokens is None else reader_max_output_tokens
    )
    if (
        not isinstance(output_tokens, int)
        or isinstance(output_tokens, bool)
        or output_tokens <= 0
        or output_tokens > profile.max_output_tokens
    ):
        raise ValueError("reader_max_output_tokens must fit the API profile")
    policy_name, policy_sha256, policy_module_sha256 = _callable_identity(policy_factory)
    scorer_name, scorer_sha256, scorer_module_sha256 = _callable_identity(scorer)
    reader_class_name, reader_class_sha256, reader_module_sha256 = _callable_identity(
        OpenAICompatibleReader
    )
    reader_builder_name, reader_builder_sha256, reader_builder_module_sha256 = _callable_identity(
        build_profile_reader
    )
    default_transport_name, default_transport_sha256, default_transport_module_sha256 = (
        _callable_identity(_urlopen_transport)
    )
    runner_name, runner_sha256, runner_module_sha256 = _callable_identity(
        run_operational_api_replay
    )
    _require_digest(source_sha256, "source_sha256")
    return OperationalReplayContract(
        task_id=task_id,
        dataset_fingerprint=dataset_fingerprint,
        evaluation_items_sha256=_evaluation_items_sha256(items),
        item_count=len(items),
        ordered_item_ids_sha256=_canonical_sha256(item_ids),
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        endpoint_sha256=hashlib.sha256(endpoint.encode()).hexdigest(),
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        policy_name=policy_name,
        policy_sha256=policy_sha256,
        policy_module_sha256=policy_module_sha256,
        scorer_name=scorer_name,
        scorer_sha256=scorer_sha256,
        scorer_module_sha256=scorer_module_sha256,
        token_axis_id=token_axis_id,
        source_id=source_id,
        source_revision=source_revision,
        source_sha256=source_sha256,
        producer_git_revision=producer_git_revision,
        producer_attestation_sha256=producer_attestation_sha256,
        reader_class_name=reader_class_name,
        reader_class_sha256=reader_class_sha256,
        reader_module_sha256=reader_module_sha256,
        reader_builder_name=reader_builder_name,
        reader_builder_sha256=reader_builder_sha256,
        reader_builder_module_sha256=reader_builder_module_sha256,
        default_transport_name=default_transport_name,
        default_transport_sha256=default_transport_sha256,
        default_transport_module_sha256=default_transport_module_sha256,
        runner_name=runner_name,
        runner_sha256=runner_sha256,
        runner_module_sha256=runner_module_sha256,
        system_prompt_sha256=hashlib.sha256(_SYSTEM_PROMPT.encode()).hexdigest(),
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        timeout_seconds=_TIMEOUT_SECONDS,
        timer_name=_PUBLIC_TIMER_NAME,
        budget=budget,
        reader_max_output_tokens=output_tokens,
        repetitions=repetitions,
        canary_repetitions=canary_repetitions,
        max_reader_calls=len(items) * repetitions + 3 * canary_repetitions,
        max_score_standard_deviation=max_score_standard_deviation,
        max_item_flip_rate=max_item_flip_rate,
        test_transport_allowed=test_transport_allowed,
        evidence_tier=_TEST_EVIDENCE_TIER if test_transport_allowed else _EVIDENCE_TIER,
    )


def run_operational_api_replay(
    contract: OperationalReplayContract,
    *,
    items: tuple[EvaluationItem, ...],
    profile: APIProfile,
    endpoint: str,
    api_key: str | None,
    policy_factory: PolicyFactory,
    scorer: Scorer,
    budget: Budget,
    transport: Transport | None = None,
    timer: Callable[[], float] = time.perf_counter,
    persisted_contract_path: str | Path | None = None,
    persisted_contract_sha256: str | None = None,
    persisted_producer_attestation_path: str | Path | None = None,
    test_contract_guard: Callable[[], None] | None = None,
) -> OperationalReplayResult:
    """Execute pre/mid/post canaries and task A/A replays under one contract."""

    observed_contract = build_operational_replay_contract(
        task_id=contract.task_id,
        dataset_fingerprint=contract.dataset_fingerprint,
        items=items,
        profile=profile,
        endpoint=endpoint,
        policy_factory=policy_factory,
        scorer=scorer,
        budget=budget,
        token_axis_id=contract.token_axis_id,
        source_id=contract.source_id,
        source_revision=contract.source_revision,
        source_sha256=contract.source_sha256,
        repetitions=contract.repetitions,
        canary_repetitions=contract.canary_repetitions,
        max_score_standard_deviation=contract.max_score_standard_deviation,
        max_item_flip_rate=contract.max_item_flip_rate,
        reader_max_output_tokens=contract.reader_max_output_tokens,
        test_transport_allowed=contract.test_transport_allowed,
        producer_git_revision=contract.producer_git_revision,
        producer_attestation_sha256=contract.producer_attestation_sha256,
    )
    if observed_contract != contract:
        raise RuntimeError("operational replay contract does not match dataset or item payload")

    integrity_guard: Callable[[], None] | None
    if transport is not None and not contract.test_transport_allowed:
        raise RuntimeError("custom transport is forbidden for public operational replay")
    if not contract.test_transport_allowed:
        if timer is not time.perf_counter:
            raise RuntimeError("public operational replay uses the contracted monotonic timer")
        if (
            persisted_contract_path is None
            or persisted_contract_sha256 is None
            or persisted_producer_attestation_path is None
        ):
            raise RuntimeError("public operational replay requires persisted contract attestation")
        _require_digest(persisted_contract_sha256, "persisted_contract_sha256")
        producer_attestation_digest = contract.producer_attestation_sha256
        if producer_attestation_digest is None:
            raise RuntimeError("public operational replay contract has no producer attestation")

        def integrity_guard() -> None:
            _validate_persisted_contract(
                contract,
                Path(persisted_contract_path),
                persisted_contract_sha256,
            )
            _validate_persisted_record(
                Path(persisted_producer_attestation_path),
                producer_attestation_digest,
                label="producer attestation",
            )

    else:
        if (
            persisted_contract_path is not None
            or persisted_contract_sha256 is not None
            or persisted_producer_attestation_path is not None
        ):
            raise RuntimeError("test replay cannot claim public persisted-contract attestation")
        integrity_guard = test_contract_guard

    attempted_reader_calls = 0
    completed_transport_calls = 0
    phase = "setup"
    base_transport = _urlopen_transport if transport is None else transport

    def counting_transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal attempted_reader_calls, completed_transport_calls
        if integrity_guard is not None:
            integrity_guard()
        attempted_reader_calls += 1
        payload = base_transport(request, timeout)
        completed_transport_calls += 1
        if integrity_guard is not None:
            integrity_guard()
        return payload

    try:
        phase = "pre-canary"
        pre_canary = run_api_canary(
            profile,
            endpoint=endpoint,
            api_key=api_key,
            repetitions=contract.canary_repetitions,
            transport=counting_transport,
            timer=timer,
        )
        phase = "reader-construction"
        reader = build_profile_reader(
            profile,
            ResolvedAPIEndpoint(endpoint, api_key),
            max_tokens=contract.reader_max_output_tokens,
            timeout_seconds=contract.timeout_seconds,
            transport=counting_transport,
        )
        recording_reader = _RecordingReader(reader, timer)
        evaluations: list[EvaluationResult] = []
        split = (contract.repetitions + 1) // 2
        for repetition in range(contract.repetitions):
            phase = f"task-replay-{repetition}"
            evaluations.append(evaluate(policy_factory, items, recording_reader, budget, scorer))
            if repetition + 1 == split:
                phase = "mid-canary"
                mid_canary = run_api_canary(
                    profile,
                    endpoint=endpoint,
                    api_key=api_key,
                    repetitions=contract.canary_repetitions,
                    transport=counting_transport,
                    timer=timer,
                )
        phase = "post-canary"
        post_canary = run_api_canary(
            profile,
            endpoint=endpoint,
            api_key=api_key,
            repetitions=contract.canary_repetitions,
            transport=counting_transport,
            timer=timer,
        )
        phase = "final-integrity"
        if integrity_guard is not None:
            integrity_guard()
    except Exception as exc:
        raise OperationalReplayExecutionError(
            attempted_reader_calls,
            completed_transport_calls,
            phase,
            exc,
        ) from exc

    try:
        phase = "result-reconciliation"
        task_call_count = len(recording_reader.calls)
        reader_calls = attempted_reader_calls
        if task_call_count != contract.item_count * contract.repetitions:
            raise RuntimeError("task reader calls do not match the replay contract")
        if reader_calls != contract.max_reader_calls:
            raise RuntimeError("total reader calls do not match the replay contract")

        frozen_evaluations = tuple(evaluations)
        item_replays = _item_replays(items, frozen_evaluations, tuple(recording_reader.calls))
        aggregate_scores = tuple(evaluation.score for evaluation in frozen_evaluations)
        score_standard_deviation = statistics.pstdev(aggregate_scores)
        item_flip_count = sum(len(set(item.scores)) > 1 for item in item_replays)
        item_flip_rate = item_flip_count / len(item_replays)
        anchors = (
            _anchor_summary("pre", pre_canary, scorer),
            _anchor_summary("mid", mid_canary, scorer),
            _anchor_summary("post", post_canary, scorer),
        )
        semantic_canary_passed = all(
            anchor.canonical_correct_count == anchor.repetitions for anchor in anchors
        )
        canary_answers = (*pre_canary.answers, *mid_canary.answers, *post_canary.answers)
        raw_canary_answer_stable = len(set(canary_answers)) == 1

        canary_input = (
            *pre_canary.input_tokens,
            *mid_canary.input_tokens,
            *post_canary.input_tokens,
        )
        canary_output = (
            *pre_canary.output_tokens,
            *mid_canary.output_tokens,
            *post_canary.output_tokens,
        )
        task_input_stable = all(len(set(item.input_tokens)) == 1 for item in item_replays)
        task_output_stable = all(len(set(item.output_tokens)) == 1 for item in item_replays)
        input_usage_stable = len(set(canary_input)) == 1 and task_input_stable
        output_usage_stable = len(set(canary_output)) == 1 and task_output_stable
        observed_models = tuple(
            model for anchor in anchors for model in anchor.observed_models
        ) + tuple(call.output.response_model or "<missing>" for call in recording_reader.calls)
        observed_model_stable = set(observed_models) == {profile.model}

        failures: list[str] = []
        if not semantic_canary_passed:
            failures.append("canonical semantic canary failed")
        if score_standard_deviation > contract.max_score_standard_deviation:
            failures.append("task score standard deviation exceeds contract")
        if item_flip_rate > contract.max_item_flip_rate:
            failures.append("item score flip rate exceeds contract")
        if contract.require_input_token_stability and not input_usage_stable:
            failures.append("input token usage drifted within the replay block")
        if not observed_model_stable:
            failures.append("observed response model does not match the contracted alias")
        return OperationalReplayResult(
            contract_sha256=contract.contract_sha256,
            reader_calls=reader_calls,
            aggregate_scores=aggregate_scores,
            score_standard_deviation=score_standard_deviation,
            item_count=len(item_replays),
            item_flip_count=item_flip_count,
            item_flip_rate=item_flip_rate,
            item_flip_rate_upper_95=_wilson_upper_95(item_flip_count, len(item_replays)),
            semantic_canary_passed=semantic_canary_passed,
            raw_canary_answer_stable=raw_canary_answer_stable,
            input_usage_stable=input_usage_stable,
            output_usage_stable=output_usage_stable,
            observed_model_stable=observed_model_stable,
            anchor_summaries=anchors,
            item_replays=item_replays,
            failures=tuple(failures),
            operational_block_passed=not failures,
        )
    except Exception as exc:
        raise OperationalReplayExecutionError(
            attempted_reader_calls,
            completed_transport_calls,
            phase,
            exc,
        ) from exc


def _canonical_canary_correct(answer: str) -> bool:
    normalized = answer.strip().casefold()
    if normalized.endswith("."):
        normalized = normalized[:-1].rstrip()
    return normalized == _CANARY_ANSWER


def _anchor_summary(
    phase: str, canary: APICanaryResult, scorer: Scorer
) -> OperationalAnchorSummary:
    return OperationalAnchorSummary(
        phase=phase,
        started_at=canary.started_at,
        repetitions=len(canary.answers),
        canonical_correct_count=sum(_canonical_canary_correct(answer) for answer in canary.answers),
        task_scorer_correct_count=sum(
            float(scorer(answer, _CANARY_ANSWER)) == 1.0 for answer in canary.answers
        ),
        raw_answer_distinct_count=len(set(canary.answers)),
        input_tokens=canary.input_tokens,
        output_tokens=canary.output_tokens,
        latency_mean_seconds=statistics.fmean(canary.latency_seconds),
        observed_models=canary.observed_models,
        response_ids_sha256=_canonical_sha256(canary.response_ids),
    )


def _wilson_upper_95(successes: int, trials: int) -> float:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Wilson interval requires 0 <= successes <= positive trials")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = proportion + z * z / (2.0 * trials)
    radius = z * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4 * trials**2))
    return min(1.0, (center + radius) / denominator)


def _validate_persisted_contract(
    contract: OperationalReplayContract,
    path: Path,
    expected_file_sha256: str,
) -> None:
    try:
        payload = path.read_bytes()
        observed = hashlib.sha256(payload).hexdigest()
        decoded: object = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("persisted operational contract cannot be verified") from exc
    if observed != expected_file_sha256 or decoded != contract.to_dict():
        raise RuntimeError("persisted operational contract changed")


def _validate_persisted_record(path: Path, expected_sha256: str, *, label: str) -> None:
    try:
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError(f"persisted {label} cannot be verified") from exc
    if observed != expected_sha256:
        raise RuntimeError(f"persisted {label} changed")


def _item_replays(
    items: tuple[EvaluationItem, ...],
    evaluations: tuple[EvaluationResult, ...],
    calls: tuple[_ObservedCall, ...],
) -> tuple[OperationalItemReplay, ...]:
    item_count = len(items)
    rows: list[OperationalItemReplay] = []
    for item_index, item in enumerate(items):
        item_calls = tuple(
            calls[repeat * item_count + item_index] for repeat in range(len(evaluations))
        )
        predictions = tuple(evaluation.predictions[item_index] for evaluation in evaluations)
        rows.append(
            OperationalItemReplay(
                item_id_sha256=hashlib.sha256(item.item_id.encode()).hexdigest(),
                scores=tuple(evaluation.item_scores[item_index] for evaluation in evaluations),
                prediction_sha256=tuple(
                    hashlib.sha256(prediction.encode()).hexdigest() for prediction in predictions
                ),
                input_tokens=tuple(call.output.input_tokens for call in item_calls),
                output_tokens=tuple(call.output.output_tokens for call in item_calls),
                latency_seconds=tuple(call.latency_seconds for call in item_calls),
            )
        )
    return tuple(rows)


def _record_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode()


def operational_record_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_record_bytes(payload)).hexdigest()


def write_operational_record(payload: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    encoded = _record_bytes(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    published = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        published = True
        directory_descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        if published:
            destination.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def _write_exclusive(payload: dict[str, Any], path: Path) -> None:
    write_operational_record(payload, path)


def write_operational_replay_contract(
    contract: OperationalReplayContract, path: str | Path
) -> None:
    _write_exclusive(contract.to_dict(), Path(path))


def write_operational_replay_result(result: OperationalReplayResult, path: str | Path) -> None:
    _write_exclusive(result.to_dict(), Path(path))
