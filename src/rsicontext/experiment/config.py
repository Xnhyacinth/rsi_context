from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from rsicontext.policy import Budget


class Split(StrEnum):
    """Dataset visibility boundary."""

    VISIBLE = "visible"
    GATE = "gate"
    SEALED = "sealed"


class Track(StrEnum):
    """Compute contract for a policy evaluation."""

    SINGLE_READER = "single_reader"
    ADAPTIVE = "adaptive"
    KV = "kv"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    revision: str
    tokenizer_revision: str
    max_model_len: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("model_id", self.model_id),
            ("revision", self.revision),
            ("tokenizer_revision", self.tokenizer_revision),
        ):
            _require_nonempty_string(value, field_name)
        if self.revision.casefold() in {"head", "latest", "main", "master"}:
            raise ValueError("model revision must not be a mutable branch name")
        if self.tokenizer_revision.casefold() in {"head", "latest", "main", "master"}:
            raise ValueError("tokenizer revision must not be a mutable branch name")
        if not isinstance(self.max_model_len, int) or isinstance(self.max_model_len, bool):
            raise TypeError("max_model_len must be an integer")
        if self.max_model_len <= 0:
            raise ValueError("max_model_len must be positive")


def _require_nonempty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _require_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _require_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _require_optional_boolean(value: object, field_name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise TypeError(f"{field_name} must be a boolean or null")


def _reject_unknown_fields(
    value: Mapping[str, object],
    field_name: str,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    keys = set(value)
    missing = required - keys
    unexpected = keys - required - optional
    if missing:
        raise ValueError(f"{field_name} missing fields: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"{field_name} has unexpected fields: {', '.join(sorted(unexpected))}")


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{field} must be a string-keyed mapping")
    return dict(value)


@dataclass(frozen=True, slots=True)
class BudgetSpec:
    context_tokens: int
    output_tokens: int
    target_calls: int
    auxiliary_calls: int = 0
    wall_time_seconds: float = 300.0
    free_text_tokens: int = 0
    max_chunks: int | None = None

    def __post_init__(self) -> None:
        _require_integer(self.context_tokens, "context_tokens")
        _require_integer(self.output_tokens, "output_tokens")
        _require_integer(self.target_calls, "target_calls")
        _require_integer(self.auxiliary_calls, "auxiliary_calls")
        _require_number(self.wall_time_seconds, "wall_time_seconds")
        _require_integer(self.free_text_tokens, "free_text_tokens")
        if self.max_chunks is not None:
            _require_integer(self.max_chunks, "max_chunks")
        if self.context_tokens <= 0 or self.output_tokens <= 0:
            raise ValueError("token budgets must be positive")
        if self.target_calls <= 0 or self.auxiliary_calls < 0:
            raise ValueError("call budgets are invalid")
        if self.wall_time_seconds <= 0:
            raise ValueError("wall-time budget must be positive")
        if not 0 <= self.free_text_tokens <= self.context_tokens:
            raise ValueError("free-text budget must be within the context budget")
        if self.max_chunks is not None and self.max_chunks < 0:
            raise ValueError("max_chunks must be non-negative")


@dataclass(frozen=True, slots=True)
class RunSpec:
    """All scientific inputs that must remain fixed for one evaluation run."""

    experiment: str
    dataset_revision: str
    evaluator_revision: str
    policy_hash: str
    serving_profile_hash: str
    reader_profile_hash: str
    chat_template_enable_thinking: bool | None
    model: ModelSpec
    budget: BudgetSpec
    split: Split
    track: Track
    seed: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("experiment", self.experiment),
            ("dataset_revision", self.dataset_revision),
            ("evaluator_revision", self.evaluator_revision),
            ("policy_hash", self.policy_hash),
            ("serving_profile_hash", self.serving_profile_hash),
            ("reader_profile_hash", self.reader_profile_hash),
        ):
            _require_nonempty_string(value, field_name)
        if self.chat_template_enable_thinking is not None and not isinstance(
            self.chat_template_enable_thinking, bool
        ):
            raise TypeError("chat_template_enable_thinking must be a boolean or null")
        seed = _require_integer(self.seed, "seed")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        if not isinstance(self.model, ModelSpec) or not isinstance(self.budget, BudgetSpec):
            raise TypeError("model and budget must use their typed specifications")
        if not isinstance(self.split, Split) or not isinstance(self.track, Track):
            raise TypeError("split and track must use their enum types")
        if self.track is not Track.SINGLE_READER:
            raise ValueError(f"track {self.track.value!r} is not implemented")
        if self.track is Track.SINGLE_READER and self.budget.target_calls != 1:
            raise ValueError("single-reader track requires exactly one target call")
        required_tokens = self.budget.context_tokens + self.budget.output_tokens
        if required_tokens > self.model.max_model_len:
            raise ValueError("context and output budget exceed model length")

    @property
    def run_id(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:20]

    @property
    def policy_budget(self) -> Budget:
        """Derive the only policy budget valid for this run."""

        return Budget(
            max_tokens=self.budget.context_tokens,
            max_free_text_tokens=self.budget.free_text_tokens,
            max_chunks=self.budget.max_chunks,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["split"] = self.split.value
        result["track"] = self.track.value
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RunSpec:
        run_value = _mapping(value, "run")
        _reject_unknown_fields(
            run_value,
            "run",
            required=frozenset(
                {
                    "experiment",
                    "dataset_revision",
                    "evaluator_revision",
                    "policy_hash",
                    "serving_profile_hash",
                    "reader_profile_hash",
                    "chat_template_enable_thinking",
                    "model",
                    "budget",
                    "split",
                    "track",
                    "seed",
                }
            ),
        )
        model_value = _mapping(run_value["model"], "model")
        _reject_unknown_fields(
            model_value,
            "model",
            required=frozenset({"model_id", "revision", "tokenizer_revision", "max_model_len"}),
        )
        budget_value = _mapping(run_value["budget"], "budget")
        _reject_unknown_fields(
            budget_value,
            "budget",
            required=frozenset({"context_tokens", "output_tokens", "target_calls"}),
            optional=frozenset(
                {"auxiliary_calls", "wall_time_seconds", "free_text_tokens", "max_chunks"}
            ),
        )
        return cls(
            experiment=_require_nonempty_string(run_value["experiment"], "experiment"),
            dataset_revision=_require_nonempty_string(
                run_value["dataset_revision"], "dataset_revision"
            ),
            evaluator_revision=_require_nonempty_string(
                run_value["evaluator_revision"], "evaluator_revision"
            ),
            policy_hash=_require_nonempty_string(run_value["policy_hash"], "policy_hash"),
            serving_profile_hash=_require_nonempty_string(
                run_value["serving_profile_hash"], "serving_profile_hash"
            ),
            reader_profile_hash=_require_nonempty_string(
                run_value["reader_profile_hash"], "reader_profile_hash"
            ),
            chat_template_enable_thinking=_require_optional_boolean(
                run_value["chat_template_enable_thinking"],
                "chat_template_enable_thinking",
            ),
            model=ModelSpec(
                model_id=_require_nonempty_string(model_value["model_id"], "model_id"),
                revision=_require_nonempty_string(model_value["revision"], "revision"),
                tokenizer_revision=_require_nonempty_string(
                    model_value["tokenizer_revision"], "tokenizer_revision"
                ),
                max_model_len=_require_integer(model_value["max_model_len"], "max_model_len"),
            ),
            budget=BudgetSpec(
                context_tokens=_require_integer(budget_value["context_tokens"], "context_tokens"),
                output_tokens=_require_integer(budget_value["output_tokens"], "output_tokens"),
                target_calls=_require_integer(budget_value["target_calls"], "target_calls"),
                auxiliary_calls=_require_integer(
                    budget_value.get("auxiliary_calls", 0), "auxiliary_calls"
                ),
                wall_time_seconds=_require_number(
                    budget_value.get("wall_time_seconds", 300.0), "wall_time_seconds"
                ),
                free_text_tokens=_require_integer(
                    budget_value.get("free_text_tokens", 0), "free_text_tokens"
                ),
                max_chunks=(
                    None
                    if budget_value.get("max_chunks") is None
                    else _require_integer(budget_value["max_chunks"], "max_chunks")
                ),
            ),
            split=Split(_require_nonempty_string(run_value["split"], "split")),
            track=Track(_require_nonempty_string(run_value["track"], "track")),
            seed=_require_integer(run_value["seed"], "seed"),
        )
