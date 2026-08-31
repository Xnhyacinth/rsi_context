"""Matched, interleaved policy signal diagnostic for black-box API readers."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import random
import statistics
import time
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rsicontext.eval import EvaluationItem, ReaderOutput
from rsicontext.eval.core import PolicyFactory, Scorer
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
from rsicontext.experiment.operational_replay import (
    OperationalAnchorSummary,
    OperationalReplayExecutionError,
    operational_record_sha256,
    summarize_operational_anchor,
    write_operational_record,
)
from rsicontext.policy import Budget

_TIMEOUT_SECONDS = 30.0
_PUBLIC_ITEM_COUNT = 40
_PUBLIC_REPETITIONS = 3
_PUBLIC_CANARY_REPETITIONS = 3
_PUBLIC_SCHEDULE_SEED = 1729
_PUBLIC_BOOTSTRAP_SEED = 20260831
_PUBLIC_BOOTSTRAP_SAMPLES = 10_000
_PUBLIC_MINIMUM_MEAN_DELTA = 0.2
_PUBLIC_MAXIMUM_POLICY_INSTABILITY = 0.1
_PUBLIC_MAXIMUM_EXACT_P_VALUE = 0.05
_PRIOR_ITEM_FLIP_RATE = 0.05
_PRIOR_ITEM_FLIP_UPPER_95 = 0.1650387736914096
_PRIOR_RESULT_SHA256 = "23cb05483f4023be803765ab966875d8c5c91b496767b034c3c85e6bc35271e7"
_PRIOR_CONTRACT_SHA256 = "a3eb98fd0a97ff4f0860ec39bb73944ee211d95c63b3ae1990d7a5d8d2c960c2"
_PUBLIC_TIMER_NAME = "time.perf_counter"
_PUBLIC_TASK_ID = "helmet-rag-popqa-k1000-to-8192-token-pack/lexical-vs-head"
_PUBLIC_DATASET_FINGERPRINT = "07f96c10b8f9fff7f7516480b443c4324b99092edf3d004c79a75dc71f1d3b23"
_PUBLIC_ITEMS_SHA256 = "f30bd33e7f92da8e2bf4deb994973216caa0aaf4c92d4a146be6d0fded380e79"
_PUBLIC_PROFILE_ID = "tencent-copilot-hy3-ioa"
_PUBLIC_PROFILE_SHA256 = "4b6628b16beedd447cb58c551178d9bea8263257736577b8a14f673103ec7082"
_PUBLIC_MODEL = "hy3-ioa"
_PUBLIC_TOKEN_AXIS_ID = (
    "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
    "#tokenizer-files-sha256:334e59dfe0a9dd0b853259dc85b9c13242f8e6b90ee0489f252dfe93f210525c"
)
_PUBLIC_SOURCE_ID = "princeton-nlp/HELMET/popqa_test_1000_k1000_dep6.jsonl"
_PUBLIC_SOURCE_REVISION = "bc560a6b8165c696ad4bc3d1612c64b5794ba328"
_PUBLIC_SOURCE_SHA256 = "ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f"
_PUBLIC_PREREGISTRATION_SHA256 = "f4386f27260a989504b1d281d6f9083f2aef03f817de7e822beed1e356ad9f87"
_PUBLIC_REFERENCE_IDENTITY = (
    "rsicontext.policy.baselines.LexicalPolicy",
    "8df6db1bdc22005203503a88e8e990d3aafecb200eb4a4916f0efc7654020518",
    "7e005b767c97c4fe545c1484b20bd6c99c5e533f3dd3cea1a372eec622dfb10a",
)
_PUBLIC_COMPARATOR_IDENTITY = (
    "rsicontext.experiment.hy3_popqa.head_policy",
    "817e6d425fc132450ec8f9b75cea87d63fea1ca53c34fbb721c3cdfdbcab22a4",
    "ce6a0dfb6bb7502e2e1aa229f8d22777ac826144928121e6bcbf6225f007c345",
)
_PUBLIC_SCORER_IDENTITY = (
    "rsicontext.eval.core.extractive_span_match",
    "bc9cb4f4b42e729149c6dc79e25ed4c1d2494c69cf22f20632a323e87c9c96ef",
    "a47e2d776514af27b223140218783a8d7ea2fd744c40d058575ea869b7c79775",
)
_EVIDENCE_TIER = "configuration-frozen-black-box-paired-diagnostic-v1"
_TEST_EVIDENCE_TIER = "non-public-paired-test-transport-v1"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


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


def _items_sha256(items: tuple[EvaluationItem, ...]) -> str:
    return _canonical_sha256(
        tuple(
            {
                "answer": item.answer,
                "artifact": asdict(item.artifact),
                "gold_chunk_ids": sorted(item.gold_chunk_ids),
                "item_id": item.item_id,
                "query": item.query,
            }
            for item in items
        )
    )


@dataclass(frozen=True, slots=True)
class PairedCall:
    repetition: int
    item_index: int
    policy_id: int


def _schedule_payload(schedule: tuple[PairedCall, ...]) -> tuple[dict[str, int], ...]:
    return tuple(asdict(call) for call in schedule)


def paired_call_schedule(*, item_count: int, repetitions: int, seed: int) -> tuple[PairedCall, ...]:
    """Generate deterministic item and within-item policy randomization."""

    for value, field in ((item_count, "item_count"), (repetitions, "repetitions")):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("schedule seed must be a non-negative integer")
    generator = random.Random(seed)
    calls: list[PairedCall] = []
    for repetition in range(repetitions):
        item_order = list(range(item_count))
        generator.shuffle(item_order)
        for item_index in item_order:
            policy_order = [0, 1]
            generator.shuffle(policy_order)
            calls.extend(PairedCall(repetition, item_index, policy) for policy in policy_order)
    return tuple(calls)


@dataclass(frozen=True, slots=True)
class PairedPolicyDiagnosticContract:
    task_id: str
    dataset_fingerprint: str
    evaluation_items_sha256: str
    item_count: int
    profile_id: str
    profile_hash: str
    endpoint_sha256: str
    requested_model: str
    provider_revision: str | None
    reference_policy_id: str
    reference_policy_name: str
    reference_policy_sha256: str
    reference_policy_module_sha256: str
    comparator_policy_id: str
    comparator_policy_name: str
    comparator_policy_sha256: str
    comparator_policy_module_sha256: str
    scorer_name: str
    scorer_sha256: str
    scorer_module_sha256: str
    reader_class_sha256: str
    reader_builder_sha256: str
    default_transport_sha256: str
    runner_sha256: str
    runner_module_sha256: str
    system_prompt_sha256: str
    chat_template_enable_thinking: bool | None
    timeout_seconds: float
    timer_name: str
    token_axis_id: str
    source_id: str
    source_revision: str
    source_sha256: str
    preregistration_sha256: str
    prior_result_sha256: str
    prior_contract_sha256: str
    prior_item_flip_rate: float
    prior_item_flip_upper_95: float
    producer_git_revision: str | None
    producer_attestation_sha256: str | None
    budget: Budget
    reader_max_output_tokens: int
    repetitions: int
    canary_repetitions: int
    schedule_seed: int
    schedule_sha256: str
    bootstrap_seed: int
    bootstrap_samples: int
    minimum_mean_delta: float
    maximum_policy_instability: float
    maximum_exact_p_value: float
    max_reader_calls: int
    test_transport_allowed: bool = False
    evidence_tier: str = _EVIDENCE_TIER
    qualification_only: bool = True
    hidden_weights_attested: bool = False
    request_profile_frozen: bool = True
    rsi_launch_eligible: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        for field in (
            "dataset_fingerprint",
            "evaluation_items_sha256",
            "profile_hash",
            "endpoint_sha256",
            "reference_policy_sha256",
            "reference_policy_module_sha256",
            "comparator_policy_sha256",
            "comparator_policy_module_sha256",
            "scorer_sha256",
            "scorer_module_sha256",
            "reader_class_sha256",
            "reader_builder_sha256",
            "default_transport_sha256",
            "runner_sha256",
            "runner_module_sha256",
            "system_prompt_sha256",
            "source_sha256",
            "preregistration_sha256",
            "prior_result_sha256",
            "prior_contract_sha256",
            "schedule_sha256",
        ):
            _require_digest(getattr(self, field), field)
        for field in (
            "task_id",
            "profile_id",
            "requested_model",
            "reference_policy_id",
            "reference_policy_name",
            "comparator_policy_id",
            "comparator_policy_name",
            "scorer_name",
            "token_axis_id",
            "source_id",
            "source_revision",
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
            "bootstrap_samples",
            "max_reader_calls",
        ):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if self.reference_policy_id == self.comparator_policy_id:
            raise ValueError("paired policies must have distinct ids")
        if not isinstance(self.budget, Budget) or self.budget.max_tokens <= 0:
            raise ValueError("budget must be positive")
        if self.reader_max_output_tokens <= 0:
            raise ValueError("reader output limit must be positive")
        expected_calls = self.item_count * self.repetitions * 2 + 3 * self.canary_repetitions
        if self.max_reader_calls != expected_calls:
            raise ValueError("paired diagnostic call cap does not match the schedule")
        expected_schedule = paired_call_schedule(
            item_count=self.item_count, repetitions=self.repetitions, seed=self.schedule_seed
        )
        if self.schedule_sha256 != _canonical_sha256(_schedule_payload(expected_schedule)):
            raise ValueError("paired diagnostic schedule digest is invalid")
        for field in (
            "prior_item_flip_rate",
            "prior_item_flip_upper_95",
            "minimum_mean_delta",
            "maximum_policy_instability",
            "maximum_exact_p_value",
        ):
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{field} must be finite and within [0, 1]")
        expected_tier = _TEST_EVIDENCE_TIER if self.test_transport_allowed else _EVIDENCE_TIER
        if self.evidence_tier != expected_tier:
            raise ValueError("unsupported paired diagnostic evidence tier")
        if not self.test_transport_allowed:
            if self.item_count != _PUBLIC_ITEM_COUNT:
                raise ValueError("public paired diagnostic requires exactly 40 items")
            if self.repetitions != _PUBLIC_REPETITIONS:
                raise ValueError("public paired diagnostic requires exactly three repetitions")
            if self.canary_repetitions != _PUBLIC_CANARY_REPETITIONS:
                raise ValueError("public paired diagnostic requires three canary repetitions")
            expected_public_values = (
                (self.schedule_seed, _PUBLIC_SCHEDULE_SEED, "schedule_seed"),
                (self.bootstrap_seed, _PUBLIC_BOOTSTRAP_SEED, "bootstrap_seed"),
                (self.bootstrap_samples, _PUBLIC_BOOTSTRAP_SAMPLES, "bootstrap_samples"),
                (self.minimum_mean_delta, _PUBLIC_MINIMUM_MEAN_DELTA, "minimum_mean_delta"),
                (
                    self.maximum_policy_instability,
                    _PUBLIC_MAXIMUM_POLICY_INSTABILITY,
                    "maximum_policy_instability",
                ),
                (
                    self.maximum_exact_p_value,
                    _PUBLIC_MAXIMUM_EXACT_P_VALUE,
                    "maximum_exact_p_value",
                ),
                (self.prior_item_flip_rate, _PRIOR_ITEM_FLIP_RATE, "prior_item_flip_rate"),
                (
                    self.prior_item_flip_upper_95,
                    _PRIOR_ITEM_FLIP_UPPER_95,
                    "prior_item_flip_upper_95",
                ),
            )
            if any(observed != expected for observed, expected, _ in expected_public_values):
                mismatches = [
                    field
                    for observed, expected, field in expected_public_values
                    if observed != expected
                ]
                raise ValueError(f"public paired diagnostic thresholds are locked: {mismatches}")
            if self.reference_policy_id != "lexical" or self.comparator_policy_id != "head":
                raise ValueError("public paired diagnostic policies are locked")
            if (
                self.prior_result_sha256 != _PRIOR_RESULT_SHA256
                or self.prior_contract_sha256 != _PRIOR_CONTRACT_SHA256
            ):
                raise ValueError("public paired diagnostic prior replay artifacts are locked")
            public_identity = (
                self.task_id,
                self.dataset_fingerprint,
                self.evaluation_items_sha256,
                self.profile_id,
                self.profile_hash,
                self.requested_model,
                self.token_axis_id,
                self.source_id,
                self.source_revision,
                self.source_sha256,
                self.preregistration_sha256,
            )
            expected_public_identity = (
                _PUBLIC_TASK_ID,
                _PUBLIC_DATASET_FINGERPRINT,
                _PUBLIC_ITEMS_SHA256,
                _PUBLIC_PROFILE_ID,
                _PUBLIC_PROFILE_SHA256,
                _PUBLIC_MODEL,
                _PUBLIC_TOKEN_AXIS_ID,
                _PUBLIC_SOURCE_ID,
                _PUBLIC_SOURCE_REVISION,
                _PUBLIC_SOURCE_SHA256,
                _PUBLIC_PREREGISTRATION_SHA256,
            )
            if public_identity != expected_public_identity:
                raise ValueError("public paired diagnostic experiment identity is locked")
            if self.budget != Budget(8192) or self.reader_max_output_tokens != 64:
                raise ValueError("public paired diagnostic reader budget is locked")
            if (
                (
                    self.reference_policy_name,
                    self.reference_policy_sha256,
                    self.reference_policy_module_sha256,
                )
                != _PUBLIC_REFERENCE_IDENTITY
                or (
                    self.comparator_policy_name,
                    self.comparator_policy_sha256,
                    self.comparator_policy_module_sha256,
                )
                != _PUBLIC_COMPARATOR_IDENTITY
                or (self.scorer_name, self.scorer_sha256, self.scorer_module_sha256)
                != _PUBLIC_SCORER_IDENTITY
            ):
                raise ValueError("public paired diagnostic callable identities are locked")
            if (
                self.producer_git_revision is None
                or len(self.producer_git_revision) != 40
                or any(
                    character not in "0123456789abcdef" for character in self.producer_git_revision
                )
            ):
                raise ValueError("public paired diagnostic requires a producer revision")
            if self.producer_attestation_sha256 is None:
                raise ValueError("public paired diagnostic requires producer attestation")
            _require_digest(self.producer_attestation_sha256, "producer_attestation_sha256")
        elif self.producer_git_revision is not None or self.producer_attestation_sha256 is not None:
            raise ValueError("test diagnostic cannot claim producer attestation")
        if (
            self.qualification_only is not True
            or self.hidden_weights_attested is not False
            or self.rsi_launch_eligible is not False
            or self.request_profile_frozen is not True
            or self.schema_version != 1
        ):
            raise ValueError("paired diagnostic is qualification-only and cannot launch RSI")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if self.chat_template_enable_thinking is not None and not isinstance(
            self.chat_template_enable_thinking, bool
        ):
            raise TypeError("chat_template_enable_thinking must be a boolean or null")

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PairedPolicySummary:
    policy_id: str
    repetition_scores: tuple[float, ...]
    pairwise_disagreement: float
    unstable_item_count: int
    unstable_item_rate: float
    unstable_item_rate_upper_95: float
    input_tokens_total: int
    output_tokens_total: int
    policy_pack_tokens_total: int
    latency_seconds_total: float
    latency_seconds_mean: float


@dataclass(frozen=True, slots=True)
class PairedPolicyDiagnosticResult:
    contract_sha256: str
    reference: PairedPolicySummary
    comparator: PairedPolicySummary
    repetition_deltas: tuple[float, ...]
    paired_mean_delta: float
    bootstrap_lower_95: float
    bootstrap_upper_95: float
    worst_case_paired_delta: float
    reference_better_count: int
    comparator_better_count: int
    tied_count: int
    exact_p_value: float
    prior_item_flip_upper_95: float
    task_reader_calls: int
    total_reader_calls: int
    semantic_canary_passed: bool
    input_usage_stable: bool
    output_usage_stable: bool
    observed_model_stable: bool
    anchor_summaries: tuple[OperationalAnchorSummary, ...]
    private_ledger_sha256: str
    failures: tuple[str, ...]
    diagnostic_passed: bool
    qualification_only: bool = True
    hidden_weights_attested: bool = False
    rsi_launch_eligible: bool = False
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_paired_policy_diagnostic_contract(
    *,
    task_id: str,
    dataset_fingerprint: str,
    items: tuple[EvaluationItem, ...],
    profile: APIProfile,
    endpoint: str,
    reference_policy_id: str,
    reference_policy_factory: PolicyFactory,
    comparator_policy_id: str,
    comparator_policy_factory: PolicyFactory,
    scorer: Scorer,
    budget: Budget,
    token_axis_id: str,
    source_id: str,
    source_revision: str,
    source_sha256: str,
    preregistration_sha256: str,
    prior_result_sha256: str,
    prior_contract_sha256: str,
    prior_item_flip_rate: float,
    prior_item_flip_upper_95: float,
    repetitions: int,
    canary_repetitions: int,
    schedule_seed: int,
    bootstrap_seed: int,
    bootstrap_samples: int,
    minimum_mean_delta: float,
    maximum_policy_instability: float,
    maximum_exact_p_value: float,
    reader_max_output_tokens: int = 64,
    producer_git_revision: str | None = None,
    producer_attestation_sha256: str | None = None,
    test_transport_allowed: bool = False,
) -> PairedPolicyDiagnosticContract:
    if not items:
        raise ValueError("paired diagnostic requires items")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("paired diagnostic endpoint must be a non-empty string")
    if len({item.item_id for item in items}) != len(items):
        raise ValueError("paired diagnostic item ids must be unique")
    _require_digest(dataset_fingerprint, "dataset_fingerprint")
    _require_digest(source_sha256, "source_sha256")
    _require_digest(preregistration_sha256, "preregistration_sha256")
    _require_digest(prior_result_sha256, "prior_result_sha256")
    _require_digest(prior_contract_sha256, "prior_contract_sha256")
    if reader_max_output_tokens > profile.max_output_tokens:
        raise ValueError("reader output limit exceeds the profile")
    reference_name, reference_sha, reference_module_sha = _callable_identity(
        reference_policy_factory
    )
    comparator_name, comparator_sha, comparator_module_sha = _callable_identity(
        comparator_policy_factory
    )
    scorer_name, scorer_sha, scorer_module_sha = _callable_identity(scorer)
    _, reader_class_sha, _ = _callable_identity(OpenAICompatibleReader)
    _, reader_builder_sha, _ = _callable_identity(build_profile_reader)
    _, transport_sha, _ = _callable_identity(_urlopen_transport)
    _, runner_sha, runner_module_sha = _callable_identity(run_paired_policy_diagnostic)
    schedule = paired_call_schedule(
        item_count=len(items), repetitions=repetitions, seed=schedule_seed
    )
    return PairedPolicyDiagnosticContract(
        task_id=task_id,
        dataset_fingerprint=dataset_fingerprint,
        evaluation_items_sha256=_items_sha256(items),
        item_count=len(items),
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        endpoint_sha256=hashlib.sha256(endpoint.encode()).hexdigest(),
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        reference_policy_id=reference_policy_id,
        reference_policy_name=reference_name,
        reference_policy_sha256=reference_sha,
        reference_policy_module_sha256=reference_module_sha,
        comparator_policy_id=comparator_policy_id,
        comparator_policy_name=comparator_name,
        comparator_policy_sha256=comparator_sha,
        comparator_policy_module_sha256=comparator_module_sha,
        scorer_name=scorer_name,
        scorer_sha256=scorer_sha,
        scorer_module_sha256=scorer_module_sha,
        reader_class_sha256=reader_class_sha,
        reader_builder_sha256=reader_builder_sha,
        default_transport_sha256=transport_sha,
        runner_sha256=runner_sha,
        runner_module_sha256=runner_module_sha,
        system_prompt_sha256=hashlib.sha256(_SYSTEM_PROMPT.encode()).hexdigest(),
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        timeout_seconds=_TIMEOUT_SECONDS,
        timer_name=_PUBLIC_TIMER_NAME,
        token_axis_id=token_axis_id,
        source_id=source_id,
        source_revision=source_revision,
        source_sha256=source_sha256,
        preregistration_sha256=preregistration_sha256,
        prior_result_sha256=prior_result_sha256,
        prior_contract_sha256=prior_contract_sha256,
        prior_item_flip_rate=prior_item_flip_rate,
        prior_item_flip_upper_95=prior_item_flip_upper_95,
        producer_git_revision=producer_git_revision,
        producer_attestation_sha256=producer_attestation_sha256,
        budget=budget,
        reader_max_output_tokens=reader_max_output_tokens,
        repetitions=repetitions,
        canary_repetitions=canary_repetitions,
        schedule_seed=schedule_seed,
        schedule_sha256=_canonical_sha256(_schedule_payload(schedule)),
        bootstrap_seed=bootstrap_seed,
        bootstrap_samples=bootstrap_samples,
        minimum_mean_delta=minimum_mean_delta,
        maximum_policy_instability=maximum_policy_instability,
        maximum_exact_p_value=maximum_exact_p_value,
        max_reader_calls=len(schedule) + 3 * canary_repetitions,
        test_transport_allowed=test_transport_allowed,
        evidence_tier=_TEST_EVIDENCE_TIER if test_transport_allowed else _EVIDENCE_TIER,
    )


@dataclass(frozen=True, slots=True)
class _TaskObservation:
    score: float
    answer: str
    input_tokens: int
    output_tokens: int
    pack_tokens: int
    response_id: str | None
    latency_seconds: float
    response_model: str | None


def run_paired_policy_diagnostic(
    contract: PairedPolicyDiagnosticContract,
    *,
    items: tuple[EvaluationItem, ...],
    profile: APIProfile,
    endpoint: str,
    api_key: str | None,
    reference_policy_factory: PolicyFactory,
    comparator_policy_factory: PolicyFactory,
    scorer: Scorer,
    budget: Budget,
    transport: Transport | None = None,
    timer: Callable[[], float] = time.perf_counter,
    persisted_contract_path: str | Path | None = None,
    persisted_contract_sha256: str | None = None,
    persisted_producer_attestation_path: str | Path | None = None,
    private_ledger_path: str | Path,
    test_contract_guard: Callable[[], None] | None = None,
) -> PairedPolicyDiagnosticResult:
    observed_contract = build_paired_policy_diagnostic_contract(
        task_id=contract.task_id,
        dataset_fingerprint=contract.dataset_fingerprint,
        items=items,
        profile=profile,
        endpoint=endpoint,
        reference_policy_id=contract.reference_policy_id,
        reference_policy_factory=reference_policy_factory,
        comparator_policy_id=contract.comparator_policy_id,
        comparator_policy_factory=comparator_policy_factory,
        scorer=scorer,
        budget=budget,
        token_axis_id=contract.token_axis_id,
        source_id=contract.source_id,
        source_revision=contract.source_revision,
        source_sha256=contract.source_sha256,
        preregistration_sha256=contract.preregistration_sha256,
        prior_result_sha256=contract.prior_result_sha256,
        prior_contract_sha256=contract.prior_contract_sha256,
        prior_item_flip_rate=contract.prior_item_flip_rate,
        prior_item_flip_upper_95=contract.prior_item_flip_upper_95,
        repetitions=contract.repetitions,
        canary_repetitions=contract.canary_repetitions,
        schedule_seed=contract.schedule_seed,
        bootstrap_seed=contract.bootstrap_seed,
        bootstrap_samples=contract.bootstrap_samples,
        minimum_mean_delta=contract.minimum_mean_delta,
        maximum_policy_instability=contract.maximum_policy_instability,
        maximum_exact_p_value=contract.maximum_exact_p_value,
        reader_max_output_tokens=contract.reader_max_output_tokens,
        producer_git_revision=contract.producer_git_revision,
        producer_attestation_sha256=contract.producer_attestation_sha256,
        test_transport_allowed=contract.test_transport_allowed,
    )
    if observed_contract != contract:
        raise RuntimeError("paired diagnostic contract does not match runtime inputs")
    integrity_guard: Callable[[], None] | None
    if not contract.test_transport_allowed:
        if transport is not None:
            raise RuntimeError("custom transport is forbidden for public paired diagnostic")
        if timer is not time.perf_counter:
            raise RuntimeError("public paired diagnostic uses the contracted timer")
        if (
            persisted_contract_path is None
            or persisted_contract_sha256 is None
            or persisted_producer_attestation_path is None
            or contract.producer_attestation_sha256 is None
        ):
            raise RuntimeError("public paired diagnostic requires persisted attestations")
        _require_digest(persisted_contract_sha256, "persisted_contract_sha256")
        producer_digest = contract.producer_attestation_sha256

        def integrity_guard() -> None:
            _validate_contract_file(
                contract, Path(persisted_contract_path), persisted_contract_sha256
            )
            _validate_file_digest(
                Path(persisted_producer_attestation_path),
                producer_digest,
                label="producer attestation",
            )

    else:
        if any(
            value is not None
            for value in (
                persisted_contract_path,
                persisted_contract_sha256,
                persisted_producer_attestation_path,
            )
        ):
            raise RuntimeError("test diagnostic cannot claim public persisted attestations")
        integrity_guard = test_contract_guard

    attempted_calls = 0
    completed_calls = 0
    task_reader_calls = 0
    phase = "setup"
    base_transport = _urlopen_transport if transport is None else transport

    def counting_transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal attempted_calls, completed_calls
        if attempted_calls >= contract.max_reader_calls:
            raise RuntimeError("paired diagnostic reader-call cap exhausted")
        if integrity_guard is not None:
            integrity_guard()
        attempted_calls += 1
        payload = base_transport(request, timeout)
        completed_calls += 1
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
        reader = build_profile_reader(
            profile,
            ResolvedAPIEndpoint(endpoint, api_key),
            max_tokens=contract.reader_max_output_tokens,
            timeout_seconds=contract.timeout_seconds,
            transport=counting_transport,
        )
        factories = (reference_policy_factory, comparator_policy_factory)
        observations: list[list[list[_TaskObservation | None]]] = [
            [[None for _ in items] for _ in range(contract.repetitions)] for _ in range(2)
        ]
        seen_policies: list[object] = []
        schedule = paired_call_schedule(
            item_count=len(items), repetitions=contract.repetitions, seed=contract.schedule_seed
        )
        private_task_ledger: list[dict[str, Any]] = []
        midpoint = len(schedule) // 2
        mid_canary = None
        for planned in schedule:
            if task_reader_calls == midpoint:
                phase = "mid-canary"
                mid_canary = run_api_canary(
                    profile,
                    endpoint=endpoint,
                    api_key=api_key,
                    repetitions=contract.canary_repetitions,
                    transport=counting_transport,
                    timer=timer,
                )
            phase = f"task-{planned.repetition}-{planned.item_index}-{planned.policy_id}"
            item = items[planned.item_index]
            policy = factories[planned.policy_id]()
            if any(policy is previous for previous in seen_policies):
                raise ValueError("policy factories must return fresh policy instances")
            seen_policies.append(policy)
            context = policy.assemble(item.artifact, item.query, budget)
            context.validate(item.artifact, budget)
            if context.abstain or context.request_reread is not None:
                raise ValueError("paired single-reader policies must issue exactly one call")
            before = timer()
            output = reader.read(item.query, context)
            elapsed = timer() - before
            if not math.isfinite(elapsed) or elapsed < 0:
                raise RuntimeError("paired diagnostic timer returned an invalid duration")
            task_reader_calls += 1
            numeric_score = _score_output(output, item.answer, scorer)
            observations[planned.policy_id][planned.repetition][planned.item_index] = (
                _TaskObservation(
                    score=numeric_score,
                    answer=output.answer,
                    input_tokens=output.input_tokens,
                    output_tokens=output.output_tokens,
                    pack_tokens=context.token_count,
                    response_id=output.response_id,
                    latency_seconds=elapsed,
                    response_model=output.response_model,
                )
            )
            private_task_ledger.append(
                {
                    "answer": output.answer,
                    "input_tokens": output.input_tokens,
                    "item_id": item.item_id,
                    "item_index": planned.item_index,
                    "latency_seconds": elapsed,
                    "output_tokens": output.output_tokens,
                    "pack_member_ids": list(context.ordering),
                    "pack_tokens": context.token_count,
                    "policy_id": planned.policy_id,
                    "reference_answer": item.answer,
                    "repetition": planned.repetition,
                    "response_id": output.response_id,
                    "response_model": output.response_model,
                    "score": numeric_score,
                }
            )
        if mid_canary is None:
            raise RuntimeError("paired diagnostic did not execute its mid canary")
        phase = "post-canary"
        post_canary = run_api_canary(
            profile,
            endpoint=endpoint,
            api_key=api_key,
            repetitions=contract.canary_repetitions,
            transport=counting_transport,
            timer=timer,
        )
        phase = "result-reconciliation"
        if integrity_guard is not None:
            integrity_guard()
        if (
            task_reader_calls != len(schedule)
            or attempted_calls != contract.max_reader_calls
            or completed_calls != contract.max_reader_calls
            or len(private_task_ledger) != len(schedule)
        ):
            raise RuntimeError("paired diagnostic call accounting mismatch")
        frozen = _freeze_observations(observations)
        private_ledger = {
            "anchor_calls": {
                "mid": _private_canary_payload(mid_canary),
                "post": _private_canary_payload(post_canary),
                "pre": _private_canary_payload(pre_canary),
            },
            "contract_sha256": contract.contract_sha256,
            "schedule": _schedule_payload(schedule),
            "schema_version": 1,
            "task_calls": private_task_ledger,
        }
        private_ledger_sha256 = operational_record_sha256(private_ledger)
        write_operational_record(private_ledger, private_ledger_path)
        _validate_file_digest(
            Path(private_ledger_path), private_ledger_sha256, label="private evaluator ledger"
        )
        return _summarize_result(
            contract,
            frozen,
            pre_canary=pre_canary,
            mid_canary=mid_canary,
            post_canary=post_canary,
            scorer=scorer,
            profile=profile,
            task_reader_calls=task_reader_calls,
            total_reader_calls=attempted_calls,
            private_ledger_sha256=private_ledger_sha256,
        )
    except Exception as exc:
        raise OperationalReplayExecutionError(
            attempted_calls,
            completed_calls,
            phase,
            exc,
        ) from exc


def _score_output(output: ReaderOutput, answer: str, scorer: Scorer) -> float:
    value = scorer(output.answer, answer)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("paired diagnostic scorer must return a number")
    numeric = float(value)
    if numeric not in (0.0, 1.0):
        raise ValueError("paired diagnostic requires a binary task scorer")
    return numeric


def _private_canary_payload(canary: APICanaryResult) -> dict[str, Any]:
    payload = canary.to_dict()
    endpoint = payload.pop("endpoint")
    if not isinstance(endpoint, str):
        raise RuntimeError("API canary endpoint identity is invalid")
    payload["endpoint_sha256"] = hashlib.sha256(endpoint.encode()).hexdigest()
    return payload


def _freeze_observations(
    values: list[list[list[_TaskObservation | None]]],
) -> tuple[tuple[tuple[_TaskObservation, ...], ...], ...]:
    frozen_policies: list[tuple[tuple[_TaskObservation, ...], ...]] = []
    for policy in values:
        frozen_repetitions: list[tuple[_TaskObservation, ...]] = []
        for repetition in policy:
            if any(value is None for value in repetition):
                raise RuntimeError("paired diagnostic observation matrix is incomplete")
            frozen_repetitions.append(tuple(value for value in repetition if value is not None))
        frozen_policies.append(tuple(frozen_repetitions))
    return tuple(frozen_policies)


def _majority_scores(
    observations: tuple[tuple[_TaskObservation, ...], ...],
) -> tuple[float, ...]:
    item_count = len(observations[0])
    majority_threshold = len(observations) / 2
    return tuple(
        float(sum(repetition[item].score for repetition in observations) > majority_threshold)
        for item in range(item_count)
    )


def _pairwise_disagreement(
    observations: tuple[tuple[_TaskObservation, ...], ...],
) -> float:
    comparisons: list[float] = []
    for item in range(len(observations[0])):
        scores = tuple(repetition[item].score for repetition in observations)
        for left in range(len(scores)):
            for right in range(left + 1, len(scores)):
                comparisons.append(float(scores[left] != scores[right]))
    return statistics.fmean(comparisons)


def _unstable_item_flags(
    observations: tuple[tuple[_TaskObservation, ...], ...],
) -> tuple[bool, ...]:
    return tuple(
        len({repetition[item].score for repetition in observations}) > 1
        for item in range(len(observations[0]))
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


def _bootstrap_interval(
    deltas: tuple[float, ...], *, seed: int, samples: int
) -> tuple[float, float]:
    generator = random.Random(seed)
    estimates = sorted(
        statistics.fmean(deltas[generator.randrange(len(deltas))] for _ in deltas)
        for _ in range(samples)
    )
    lower = estimates[int(0.025 * samples)]
    upper = estimates[math.ceil(0.975 * samples) - 1]
    return lower, upper


def _exact_mcnemar(reference_better: int, comparator_better: int) -> float:
    discordant = reference_better + comparator_better
    if discordant == 0:
        return 1.0
    tail = min(reference_better, comparator_better)
    probability: float = (
        sum(math.comb(discordant, count) for count in range(tail + 1)) / 2**discordant
    )
    return min(1.0, 2.0 * probability)


def _policy_summary(
    policy_id: str,
    observations: tuple[tuple[_TaskObservation, ...], ...],
) -> PairedPolicySummary:
    flattened = tuple(value for repetition in observations for value in repetition)
    latencies = tuple(value.latency_seconds for value in flattened)
    unstable_item_count = sum(_unstable_item_flags(observations))
    item_count = len(observations[0])
    return PairedPolicySummary(
        policy_id=policy_id,
        repetition_scores=tuple(
            statistics.fmean(value.score for value in repetition) for repetition in observations
        ),
        pairwise_disagreement=_pairwise_disagreement(observations),
        unstable_item_count=unstable_item_count,
        unstable_item_rate=unstable_item_count / item_count,
        unstable_item_rate_upper_95=_wilson_upper_95(unstable_item_count, item_count),
        input_tokens_total=sum(value.input_tokens for value in flattened),
        output_tokens_total=sum(value.output_tokens for value in flattened),
        policy_pack_tokens_total=sum(value.pack_tokens for value in flattened),
        latency_seconds_total=sum(latencies),
        latency_seconds_mean=statistics.fmean(latencies),
    )


def _summarize_result(
    contract: PairedPolicyDiagnosticContract,
    observations: tuple[tuple[tuple[_TaskObservation, ...], ...], ...],
    *,
    pre_canary: APICanaryResult,
    mid_canary: APICanaryResult,
    post_canary: APICanaryResult,
    scorer: Scorer,
    profile: APIProfile,
    task_reader_calls: int,
    total_reader_calls: int,
    private_ledger_sha256: str,
) -> PairedPolicyDiagnosticResult:
    reference_observations, comparator_observations = observations
    reference = _policy_summary(contract.reference_policy_id, reference_observations)
    comparator = _policy_summary(contract.comparator_policy_id, comparator_observations)
    repetition_deltas = tuple(
        left - right
        for left, right in zip(
            reference.repetition_scores, comparator.repetition_scores, strict=True
        )
    )
    reference_majority = _majority_scores(reference_observations)
    comparator_majority = _majority_scores(comparator_observations)
    item_deltas = tuple(
        left - right for left, right in zip(reference_majority, comparator_majority, strict=True)
    )
    paired_mean_delta = statistics.fmean(item_deltas)
    lower, upper = _bootstrap_interval(
        item_deltas, seed=contract.bootstrap_seed, samples=contract.bootstrap_samples
    )
    reference_better = sum(delta > 0 for delta in item_deltas)
    comparator_better = sum(delta < 0 for delta in item_deltas)
    ties = len(item_deltas) - reference_better - comparator_better
    exact_p_value = _exact_mcnemar(reference_better, comparator_better)
    reference_unstable = _unstable_item_flags(reference_observations)
    comparator_unstable = _unstable_item_flags(comparator_observations)
    worst_case_paired_delta = statistics.fmean(
        -1.0 if reference_unstable[item] or comparator_unstable[item] else item_deltas[item]
        for item in range(contract.item_count)
    )
    anchors = (
        summarize_operational_anchor("pre", pre_canary, scorer),
        summarize_operational_anchor("mid", mid_canary, scorer),
        summarize_operational_anchor("post", post_canary, scorer),
    )
    semantic_canary_passed = all(
        anchor.canonical_correct_count == anchor.repetitions for anchor in anchors
    )
    task_input_usage_stable = all(
        len(
            {
                observations[policy][repetition][item].input_tokens
                for repetition in range(contract.repetitions)
            }
        )
        == 1
        for policy in range(2)
        for item in range(contract.item_count)
    )
    input_usage_stable = task_input_usage_stable and all(
        len(set(anchor.input_tokens)) == 1 for anchor in anchors
    )
    task_output_usage_stable = all(
        len(
            {
                observations[policy][repetition][item].output_tokens
                for repetition in range(contract.repetitions)
            }
        )
        == 1
        for policy in range(2)
        for item in range(contract.item_count)
    )
    output_usage_stable = task_output_usage_stable and all(
        len(set(anchor.output_tokens)) == 1 for anchor in anchors
    )
    observed_model_stable = all(
        value.response_model == profile.model
        for policy in observations
        for repetition in policy
        for value in repetition
    ) and all(model == profile.model for anchor in anchors for model in anchor.observed_models)
    failures: list[str] = []
    if paired_mean_delta < contract.minimum_mean_delta:
        failures.append("paired mean policy delta is below the preregistered minimum")
    if any(delta <= contract.prior_item_flip_upper_95 for delta in repetition_deltas):
        failures.append("a repetition policy delta does not exceed the replay sensitivity bound")
    if lower <= contract.prior_item_flip_upper_95:
        failures.append("paired bootstrap lower bound does not exceed the replay sensitivity bound")
    if exact_p_value > contract.maximum_exact_p_value:
        failures.append("exact paired p-value exceeds the preregistered maximum")
    if reference.unstable_item_rate > contract.maximum_policy_instability:
        failures.append("reference unstable-item rate exceeds the preregistered maximum")
    if comparator.unstable_item_rate > contract.maximum_policy_instability:
        failures.append("comparator unstable-item rate exceeds the preregistered maximum")
    if worst_case_paired_delta <= contract.prior_item_flip_upper_95:
        failures.append("worst-case policy delta does not exceed the replay sensitivity bound")
    if not semantic_canary_passed:
        failures.append("canonical semantic canary failed")
    if not input_usage_stable:
        failures.append("task input usage drifted within an item-policy cell")
    if not observed_model_stable:
        failures.append("observed response model does not match the contracted alias")
    return PairedPolicyDiagnosticResult(
        contract_sha256=contract.contract_sha256,
        reference=reference,
        comparator=comparator,
        repetition_deltas=repetition_deltas,
        paired_mean_delta=paired_mean_delta,
        bootstrap_lower_95=lower,
        bootstrap_upper_95=upper,
        worst_case_paired_delta=worst_case_paired_delta,
        reference_better_count=reference_better,
        comparator_better_count=comparator_better,
        tied_count=ties,
        exact_p_value=exact_p_value,
        prior_item_flip_upper_95=contract.prior_item_flip_upper_95,
        task_reader_calls=task_reader_calls,
        total_reader_calls=total_reader_calls,
        semantic_canary_passed=semantic_canary_passed,
        input_usage_stable=input_usage_stable,
        output_usage_stable=output_usage_stable,
        observed_model_stable=observed_model_stable,
        anchor_summaries=anchors,
        private_ledger_sha256=private_ledger_sha256,
        failures=tuple(failures),
        diagnostic_passed=not failures,
    )


def _validate_contract_file(
    contract: PairedPolicyDiagnosticContract, path: Path, expected_sha256: str
) -> None:
    try:
        payload = path.read_bytes()
        decoded: object = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("persisted paired diagnostic contract cannot be verified") from exc
    if hashlib.sha256(payload).hexdigest() != expected_sha256 or decoded != contract.to_dict():
        raise RuntimeError("persisted paired diagnostic contract changed")


def _validate_file_digest(path: Path, expected_sha256: str, *, label: str) -> None:
    try:
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError(f"persisted {label} cannot be verified") from exc
    if observed != expected_sha256:
        raise RuntimeError(f"persisted {label} changed")


def write_paired_policy_diagnostic_contract(
    contract: PairedPolicyDiagnosticContract, path: str | Path
) -> None:
    write_operational_record(contract.to_dict(), path)


def write_paired_policy_diagnostic_result(
    result: PairedPolicyDiagnosticResult, path: str | Path
) -> None:
    write_operational_record(result.to_dict(), path)
