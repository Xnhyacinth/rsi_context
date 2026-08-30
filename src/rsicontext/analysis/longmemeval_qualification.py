"""Aggregate-only qualification for real LongMemEval-V2 trajectory histories."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass

from rsicontext.analysis.difficulty import DifficultyGateResult
from rsicontext.datasets.longmemeval_v2 import LongMemEvalOfflineDataset, LongMemEvalTier

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_DETERMINISTIC_EVALUATORS = frozenset(
    {
        "mc_choice_match",
        "mc_choice_set_match",
        "norm_phrase_set_match",
        "norm_phrase_set_match_ordered",
    }
)
_WEAK_EVALUATORS = frozenset({"llm_abstention_checker"})
_EXPECTED_EVALUATOR_COUNTS = (
    ("llm_abstention_checker", 128),
    ("mc_choice_match", 68),
    ("mc_choice_set_match", 1),
    ("norm_phrase_set_match", 199),
    ("norm_phrase_set_match_ordered", 26),
)
LONGMEMEVAL_V2_SOURCE_REVISION = "f152293e235517d504809563c833d7190b8c713b"
LONGMEMEVAL_V2_TOKENIZER_ID = (
    "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
    "#tokenizer-files-sha256:8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290"
)
LONGMEMEVAL_V2_SMALL_RELEASED_FILES = (
    (
        "haystacks/lme_v2_small.json",
        "9b5301defb23a088a5f06e45ff8d5f35e569d78305a66d492046a9fff9b46593",
    ),
    ("questions.jsonl", "0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7"),
    (
        "trajectories.jsonl",
        "363cec9a8e87aa8d9101ce4e600aadbf7031d674056ebe4f969e8424abc5f3c6",
    ),
)


def _positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _rate(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be finite and within [0, 1]")
    return numeric


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _count_table(
    values: tuple[tuple[str, int], ...], field: str, expected_total: int
) -> tuple[tuple[str, int], ...]:
    if not values:
        raise ValueError(f"{field} must not be empty")
    names: list[str] = []
    total = 0
    for name, count in values:
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field} names must be non-empty strings")
        names.append(name)
        total += _positive_integer(count, f"{field} count")
    if names != sorted(set(names)):
        raise ValueError(f"{field} names must be unique and sorted")
    if total != expected_total:
        raise ValueError(f"{field} counts must sum to item_count")
    return values


def _file_table(values: tuple[tuple[str, str], ...], field: str) -> tuple[tuple[str, str], ...]:
    if not values:
        raise ValueError(f"{field} must not be empty")
    paths: list[str] = []
    for path, digest in values:
        if not isinstance(path, str) or not path:
            raise ValueError(f"{field} paths must be non-empty strings")
        paths.append(path)
        _sha256(digest, f"{field} digest")
    if paths != sorted(set(paths)):
        raise ValueError(f"{field} paths must be unique and sorted")
    return values


@dataclass(frozen=True, slots=True)
class LongMemEvalOfflineMeasurements:
    """Dataset-level long-memory evidence without IDs, labels, or item scores."""

    tier: LongMemEvalTier
    item_count: int
    deterministic_item_count: int
    weak_judge_item_count: int
    excluded_image_item_count: int
    unique_artifact_count: int
    domain_counts: tuple[tuple[str, int], ...]
    question_type_counts: tuple[tuple[str, int], ...]
    evaluator_name_counts: tuple[tuple[str, int], ...]
    haystack_size_min: int
    haystack_size_max: int
    source_token_min: int
    source_token_median: float
    source_token_p95: int
    source_token_max: int
    state_count_min: int
    state_count_median: float
    state_count_p95: int
    state_count_max: int
    single_chunk_token_max: int
    binding_32k_rate: float
    binding_128k_rate: float
    binding_256k_rate: float
    source_revision: str
    source_fingerprint: str
    dataset_fingerprint: str
    tokenizer_id: str
    source_file_sha256: tuple[tuple[str, str], ...]
    released_file_sha256: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.tier not in {"small", "medium"}:
            raise ValueError(f"unsupported LongMemEval tier: {self.tier!r}")
        _positive_integer(self.item_count, "item_count")
        for field, value in (
            ("deterministic_item_count", self.deterministic_item_count),
            ("weak_judge_item_count", self.weak_judge_item_count),
            ("excluded_image_item_count", self.excluded_image_item_count),
        ):
            _nonnegative_integer(value, field)
        _positive_integer(self.unique_artifact_count, "unique_artifact_count")
        if self.deterministic_item_count + self.weak_judge_item_count != self.item_count:
            raise ValueError("evaluator strata must sum to item_count")
        _count_table(self.domain_counts, "domain_counts", self.item_count)
        _count_table(self.question_type_counts, "question_type_counts", self.item_count)
        _count_table(self.evaluator_name_counts, "evaluator_name_counts", self.item_count)
        _positive_integer(self.haystack_size_min, "haystack_size_min")
        _positive_integer(self.haystack_size_max, "haystack_size_max")
        if self.haystack_size_min > self.haystack_size_max:
            raise ValueError("haystack size statistics must be non-decreasing")
        self._validate_distribution(
            "source token",
            self.source_token_min,
            self.source_token_median,
            self.source_token_p95,
            self.source_token_max,
        )
        self._validate_distribution(
            "state count",
            self.state_count_min,
            self.state_count_median,
            self.state_count_p95,
            self.state_count_max,
        )
        _positive_integer(self.single_chunk_token_max, "single_chunk_token_max")
        _rate(self.binding_32k_rate, "binding_32k_rate")
        _rate(self.binding_128k_rate, "binding_128k_rate")
        _rate(self.binding_256k_rate, "binding_256k_rate")
        if not (self.binding_32k_rate >= self.binding_128k_rate >= self.binding_256k_rate):
            raise ValueError("binding rates must be non-increasing with context length")
        if not isinstance(self.source_revision, str) or len(self.source_revision) != 40:
            raise ValueError("source_revision must be a 40-character revision")
        _sha256(self.source_fingerprint, "source_fingerprint")
        _sha256(self.dataset_fingerprint, "dataset_fingerprint")
        if not isinstance(self.tokenizer_id, str) or not self.tokenizer_id:
            raise ValueError("tokenizer_id must be non-empty")
        _file_table(self.source_file_sha256, "source_file_sha256")
        _file_table(self.released_file_sha256, "released_file_sha256")

    @staticmethod
    def _validate_distribution(
        field: str, minimum: int, median: float, p95: int, maximum: int
    ) -> None:
        ordered = (
            float(_positive_integer(minimum, f"{field}_min")),
            float(median),
            float(_positive_integer(p95, f"{field}_p95")),
            float(_positive_integer(maximum, f"{field}_max")),
        )
        if not math.isfinite(ordered[1]) or ordered[1] <= 0:
            raise ValueError(f"{field}_median must be positive and finite")
        if ordered != tuple(sorted(ordered)):
            raise ValueError(f"{field} statistics must be non-decreasing")

    @property
    def source_files_match_release(self) -> bool:
        """Whether every consumed file digest matches the released manifest."""

        return self.source_file_sha256 == self.released_file_sha256


def _p95(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def measure_longmemeval_dataset(
    dataset: LongMemEvalOfflineDataset,
    *,
    released_file_sha256: tuple[tuple[str, str], ...],
) -> LongMemEvalOfflineMeasurements:
    """Measure a compiled text-only tier without retaining evaluator labels."""

    items = dataset.evaluator_items()
    if not items:
        raise ValueError("LongMemEval qualification requires evaluator items")
    domain_counts: Counter[str] = Counter()
    question_type_counts: Counter[str] = Counter()
    evaluator_counts: Counter[str] = Counter()
    source_tokens: list[int] = []
    state_counts: list[int] = []
    chunk_tokens: list[int] = []
    haystack_sizes: list[int] = []
    artifact_ids: set[str] = set()
    deterministic = 0
    weak_judge = 0
    for item in items:
        policy_item = item.policy_item
        eval_name = item.eval_function.split("|", 1)[0]
        domain_counts[policy_item.domain] += 1
        question_type_counts[policy_item.question_type] += 1
        evaluator_counts[eval_name] += 1
        if eval_name in _WEAK_EVALUATORS:
            weak_judge += 1
        elif eval_name in _DETERMINISTIC_EVALUATORS:
            deterministic += 1
        else:
            raise ValueError(f"unsupported LongMemEval evaluator family: {eval_name!r}")
        chunks = policy_item.artifact.chunks
        source_tokens.append(sum(chunk.token_count for chunk in chunks))
        state_counts.append(sum(chunk.role == "trajectory_state" for chunk in chunks))
        chunk_tokens.extend(chunk.token_count for chunk in chunks)
        haystack_sizes.append(policy_item.full_haystack_size)
        artifact_ids.add(policy_item.artifact.document_id)
    n_items = len(items)
    source_file_sha256 = tuple(
        sorted((record.relative_path, record.sha256) for record in dataset.source.files)
    )
    return LongMemEvalOfflineMeasurements(
        tier=dataset.tier,
        item_count=n_items,
        deterministic_item_count=deterministic,
        weak_judge_item_count=weak_judge,
        excluded_image_item_count=dataset.excluded_image_question_count,
        unique_artifact_count=len(artifact_ids),
        domain_counts=tuple(sorted(domain_counts.items())),
        question_type_counts=tuple(sorted(question_type_counts.items())),
        evaluator_name_counts=tuple(sorted(evaluator_counts.items())),
        haystack_size_min=min(haystack_sizes),
        haystack_size_max=max(haystack_sizes),
        source_token_min=min(source_tokens),
        source_token_median=float(statistics.median(source_tokens)),
        source_token_p95=_p95(source_tokens),
        source_token_max=max(source_tokens),
        state_count_min=min(state_counts),
        state_count_median=float(statistics.median(state_counts)),
        state_count_p95=_p95(state_counts),
        state_count_max=max(state_counts),
        single_chunk_token_max=max(chunk_tokens),
        binding_32k_rate=sum(value > 32_768 for value in source_tokens) / n_items,
        binding_128k_rate=sum(value > 131_072 for value in source_tokens) / n_items,
        binding_256k_rate=sum(value > 262_144 for value in source_tokens) / n_items,
        source_revision=dataset.source.revision,
        source_fingerprint=dataset.source.fingerprint,
        dataset_fingerprint=dataset.fingerprint,
        tokenizer_id=dataset.tokenizer_id,
        source_file_sha256=source_file_sha256,
        released_file_sha256=tuple(sorted(released_file_sha256)),
    )


def evaluate_longmemeval_offline_qualification(
    measurements: LongMemEvalOfflineMeasurements,
) -> DifficultyGateResult:
    """Apply preregistered small-tier gates before any reader or researcher call."""

    failures: list[str] = []
    if measurements.tier != "small":
        failures.append("primary qualification requires the LongMemEval-V2 small tier")
    if measurements.item_count != 422:
        failures.append("text-only LongMemEval-V2 profile must contain exactly 422 items")
    if measurements.deterministic_item_count != 294:
        failures.append("deterministic evaluator stratum must contain exactly 294 items")
    if measurements.weak_judge_item_count != 128:
        failures.append("weak LLM-judge stratum must contain exactly 128 items")
    if measurements.evaluator_name_counts != _EXPECTED_EVALUATOR_COUNTS:
        failures.append("evaluator-family counts do not match the pinned text-only release")
    if measurements.source_revision != LONGMEMEVAL_V2_SOURCE_REVISION:
        failures.append("source revision does not match the preregistered release")
    if measurements.tokenizer_id != LONGMEMEVAL_V2_TOKENIZER_ID:
        failures.append("tokenizer identity does not match the preregistered reader tokenizer")
    if measurements.released_file_sha256 != LONGMEMEVAL_V2_SMALL_RELEASED_FILES:
        failures.append("released file manifest does not match the preregistered small tier")
    if measurements.excluded_image_item_count != 29:
        failures.append("text-only profile must exclude exactly 29 image items")
    if measurements.unique_artifact_count < 2:
        failures.append("profile has fewer than two shared histories")
    if measurements.haystack_size_min != 100 or measurements.haystack_size_max != 100:
        failures.append("small tier must expose exactly 100 trajectories per question")
    if measurements.binding_128k_rate < 0.95:
        failures.append("fewer than 95% of text-only sources are binding beyond 128K tokens")
    if not measurements.source_files_match_release:
        failures.append("consumed source files do not match the released file checksums")
    return DifficultyGateResult(
        profile="longmemeval-v2-small-text-only",
        passed=not failures,
        failures=tuple(failures),
    )
