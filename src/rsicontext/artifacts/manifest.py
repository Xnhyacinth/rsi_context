"""Strict schema for researcher predictions and promotion recommendations."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, cast

_SCHEMA_VERSION: Final = 1
_SUPPORTED_SCHEMA_VERSIONS: Final = (1, 2)
_PROBABILITY_TOLERANCE: Final = 1e-9


class ManifestError(ValueError):
    """Raised when a manifest violates the benchmark schema."""


def _nonempty(value: str, *, field: str) -> None:
    if not value or value != value.strip():
        raise ManifestError(f"{field} must be a non-empty, trimmed string")


def _finite(value: object, *, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ManifestError(f"{field} must be finite")


def _probability(value: float, *, field: str) -> None:
    _finite(value, field=field)
    if not 0.0 <= value <= 1.0:
        raise ManifestError(f"{field} must be between zero and one")


def _policy_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not value or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"policy path must be safe and relative: {value!r}")


@dataclass(frozen=True, slots=True)
class FlipProbabilities:
    """Predicted probability that an item improves, stays unchanged, or regresses."""

    improve: float
    unchanged: float
    regress: float

    def __post_init__(self) -> None:
        for name, value in (
            ("improve", self.improve),
            ("unchanged", self.unchanged),
            ("regress", self.regress),
        ):
            _probability(value, field=f"probabilities.{name}")
        if not math.isclose(
            self.improve + self.unchanged + self.regress,
            1.0,
            rel_tol=0.0,
            abs_tol=_PROBABILITY_TOLERANCE,
        ):
            raise ManifestError("per-question probabilities must sum to exactly one")


@dataclass(frozen=True, slots=True)
class MechanismClaim:
    """A falsifiable mechanism that the policy change is expected to use."""

    mechanism_id: str
    description: str
    policy_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _nonempty(self.mechanism_id, field="mechanism_id")
        _nonempty(self.description, field="mechanism.description")
        if not self.policy_paths or len(self.policy_paths) != len(set(self.policy_paths)):
            raise ManifestError("mechanism policy_paths must be non-empty and unique")
        for path in self.policy_paths:
            _policy_path(path)


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    """Evidence from a visible trace, metric, span, or previous policy diff."""

    evidence_id: str
    kind: str
    reference: str
    claim: str

    def __post_init__(self) -> None:
        _nonempty(self.evidence_id, field="evidence_id")
        _nonempty(self.kind, field="evidence.kind")
        _nonempty(self.reference, field="evidence.reference")
        _nonempty(self.claim, field="evidence.claim")


@dataclass(frozen=True, slots=True)
class QuestionPrediction:
    """A calibrated flip prediction for one benchmark item."""

    item_id: str
    probabilities: FlipProbabilities
    mechanism_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _nonempty(self.item_id, field="prediction.item_id")
        if not self.mechanism_ids or len(self.mechanism_ids) != len(set(self.mechanism_ids)):
            raise ManifestError("prediction mechanism_ids must be non-empty and unique")
        if not self.evidence_ids or len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ManifestError("prediction evidence_ids must be non-empty and unique")
        for mechanism_id in self.mechanism_ids:
            _nonempty(mechanism_id, field="prediction.mechanism_id")
        for evidence_id in self.evidence_ids:
            _nonempty(evidence_id, field="prediction.evidence_id")


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Predicted researcher and evaluator cost for the candidate."""

    researcher_input_tokens: int
    researcher_output_tokens: int
    evaluation_input_tokens: int
    evaluation_output_tokens: int
    gpu_seconds: float
    wall_seconds: float

    def __post_init__(self) -> None:
        for token_name, token_value in (
            ("researcher_input_tokens", self.researcher_input_tokens),
            ("researcher_output_tokens", self.researcher_output_tokens),
            ("evaluation_input_tokens", self.evaluation_input_tokens),
            ("evaluation_output_tokens", self.evaluation_output_tokens),
        ):
            if isinstance(token_value, bool) or not isinstance(token_value, int) or token_value < 0:
                raise ManifestError(f"cost.{token_name} must be a non-negative integer")
        for duration_name, duration_value in (
            ("gpu_seconds", self.gpu_seconds),
            ("wall_seconds", self.wall_seconds),
        ):
            _finite(duration_value, field=f"cost.{duration_name}")
            if duration_value < 0:
                raise ManifestError(f"cost.{duration_name} must be non-negative")


@dataclass(frozen=True, slots=True)
class PromotionRecommendation:
    """Researcher's pre-evaluation recommendation; the benchmark remains authoritative."""

    decision: Literal["promote", "hold", "reject"]
    expected_score_delta: float
    max_regression_probability: float
    rationale: str

    def __post_init__(self) -> None:
        if self.decision not in {"promote", "hold", "reject"}:
            raise ManifestError("promotion.decision must be promote, hold, or reject")
        _finite(self.expected_score_delta, field="promotion.expected_score_delta")
        _probability(
            self.max_regression_probability,
            field="promotion.max_regression_probability",
        )
        _nonempty(self.rationale, field="promotion.rationale")


@dataclass(frozen=True, slots=True)
class ImprovementCostV2:
    """Two-column cost split: the improvement loop's own accounted cost (C_improve)."""

    improve_input_tokens: int | None = None
    improve_output_tokens: int | None = None
    improve_wall_seconds: float | None = None
    improve_dollar_estimate: float | None = None

    def __post_init__(self) -> None:
        for token_name, token_value in (
            ("improve_input_tokens", self.improve_input_tokens),
            ("improve_output_tokens", self.improve_output_tokens),
        ):
            if token_value is None:
                continue
            if isinstance(token_value, bool) or not isinstance(token_value, int) or token_value < 0:
                raise ManifestError(
                    f"participant_v2.improvement_cost.{token_name} must be a non-negative integer"
                )
        for duration_name, duration_value in (
            ("improve_wall_seconds", self.improve_wall_seconds),
            ("improve_dollar_estimate", self.improve_dollar_estimate),
        ):
            if duration_value is None:
                continue
            _finite(duration_value, field=f"participant_v2.improvement_cost.{duration_name}")
            if duration_value < 0:
                raise ManifestError(
                    f"participant_v2.improvement_cost.{duration_name} must be non-negative"
                )


@dataclass(frozen=True, slots=True)
class ParticipantV2:
    """v2 participant registration block (participant-interface-v1.md §Manifest extensions)."""

    participant_id: str
    arm: Literal["fixed", "experience_accumulation", "open_s_cli", "stateful_control"]
    seed_id: str | None = None
    state_schema: str | None = None
    improvement_cost: ImprovementCostV2 | None = None
    pool_tier: Literal["T1_ANCHOR", "T2_VERSIONED_API", "T3_COMPATIBILITY"] | None = None
    state_transcript_ref: str | None = None
    task_order_seed: int | None = None

    def __post_init__(self) -> None:
        if self.arm not in {"fixed", "experience_accumulation", "open_s_cli", "stateful_control"}:
            raise ManifestError("participant_v2.arm must be one of the v2 registration arms")
        _nonempty(self.participant_id, field="participant_v2.participant_id")
        if self.seed_id is not None:
            _nonempty(self.seed_id, field="participant_v2.seed_id")
        if self.state_schema is not None and not _is_digest(self.state_schema):
            raise ManifestError(
                "participant_v2.state_schema must be a lowercase SHA-256-style 64-hex digest"
            )
        if self.pool_tier is not None and self.pool_tier not in {
            "T1_ANCHOR",
            "T2_VERSIONED_API",
            "T3_COMPATIBILITY",
        }:
            raise ManifestError(
                "participant_v2.pool_tier must be T1_ANCHOR, T2_VERSIONED_API, or T3_COMPATIBILITY"
            )
        if self.state_transcript_ref is not None:
            _nonempty(self.state_transcript_ref, field="participant_v2.state_transcript_ref")
        if self.task_order_seed is not None and (
            isinstance(self.task_order_seed, bool) or self.task_order_seed < 0
        ):
            raise ManifestError("participant_v2.task_order_seed must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class Manifest:
    """Strict manifest attached to one candidate policy artifact."""

    candidate_name: str
    parent_artifact_id: str | None
    predictions: tuple[QuestionPrediction, ...]
    mechanisms: tuple[MechanismClaim, ...]
    evidence: tuple[EvidenceClaim, ...]
    cost: CostEstimate
    promotion: PromotionRecommendation
    schema_version: int = _SCHEMA_VERSION
    participant_v2: ParticipantV2 | None = None

    def __post_init__(self) -> None:
        if self.schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise ManifestError(f"schema_version must be one of {list(_SUPPORTED_SCHEMA_VERSIONS)}")
        if self.schema_version == _SCHEMA_VERSION and self.participant_v2 is not None:
            raise ManifestError("participant_v2 requires schema_version 2")
        _nonempty(self.candidate_name, field="candidate_name")
        if self.parent_artifact_id is not None and not _is_digest(self.parent_artifact_id):
            raise ManifestError("parent_artifact_id must be null or a lowercase SHA-256 digest")
        if not self.predictions or not self.mechanisms or not self.evidence:
            raise ManifestError("predictions, mechanisms, and evidence must all be non-empty")

        item_ids = [prediction.item_id for prediction in self.predictions]
        mechanism_ids = [mechanism.mechanism_id for mechanism in self.mechanisms]
        evidence_ids = [claim.evidence_id for claim in self.evidence]
        for values, label in (
            (item_ids, "prediction item ids"),
            (mechanism_ids, "mechanism ids"),
            (evidence_ids, "evidence ids"),
        ):
            if len(values) != len(set(values)):
                raise ManifestError(f"{label} must be unique")

        known_mechanisms = set(mechanism_ids)
        known_evidence = set(evidence_ids)
        for prediction in self.predictions:
            unknown_mechanisms = set(prediction.mechanism_ids) - known_mechanisms
            unknown_evidence = set(prediction.evidence_ids) - known_evidence
            if unknown_mechanisms:
                raise ManifestError(
                    f"prediction references unknown mechanisms: {sorted(unknown_mechanisms)}"
                )
            if unknown_evidence:
                raise ManifestError(
                    f"prediction references unknown evidence: {sorted(unknown_evidence)}"
                )
        predicted_max = max(prediction.probabilities.regress for prediction in self.predictions)
        if not math.isclose(
            self.promotion.max_regression_probability,
            predicted_max,
            rel_tol=0.0,
            abs_tol=_PROBABILITY_TOLERANCE,
        ):
            raise ManifestError(
                "promotion.max_regression_probability must match the maximum "
                "per-question regression probability"
            )

    def validate_for_items(self, expected_item_ids: Sequence[str]) -> None:
        """Bind calibration to the evaluator-owned item set for this round."""

        expected = tuple(expected_item_ids)
        for item_id in expected:
            _nonempty(item_id, field="expected item_id")
        if len(expected) != len(set(expected)):
            raise ManifestError("expected item ids must be unique")
        predicted = {prediction.item_id for prediction in self.predictions}
        expected_set = set(expected)
        if predicted != expected_set:
            missing = sorted(expected_set - predicted)
            extra = sorted(predicted - expected_set)
            raise ManifestError(f"prediction coverage mismatch; missing={missing}, extra={extra}")

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> Manifest:
        """Validate a decoded JSON object without coercing values."""

        expected_fields = {
            "candidate_name",
            "cost",
            "evidence",
            "mechanisms",
            "parent_artifact_id",
            "predictions",
            "promotion",
            "schema_version",
        }
        if raw.get("schema_version") == 2 and "participant_v2" in raw:
            expected_fields = expected_fields | {"participant_v2"}
        _require_fields(raw, expected_fields, field="manifest")
        schema_version = _as_int(raw["schema_version"], field="schema_version")
        candidate_name = _as_str(raw["candidate_name"], field="candidate_name")
        parent_raw = raw["parent_artifact_id"]
        if parent_raw is not None and not isinstance(parent_raw, str):
            raise ManifestError("parent_artifact_id must be a string or null")

        mechanisms = tuple(
            _parse_mechanism(value) for value in _as_sequence(raw["mechanisms"], field="mechanisms")
        )
        evidence = tuple(
            _parse_evidence(value) for value in _as_sequence(raw["evidence"], field="evidence")
        )
        predictions = tuple(
            _parse_prediction(value)
            for value in _as_sequence(raw["predictions"], field="predictions")
        )
        participant_v2 = (
            _parse_participant_v2(raw["participant_v2"])
            if schema_version == 2 and "participant_v2" in raw
            else None
        )
        return cls(
            candidate_name=candidate_name,
            parent_artifact_id=parent_raw,
            predictions=predictions,
            mechanisms=mechanisms,
            evidence=evidence,
            cost=_parse_cost(raw["cost"]),
            promotion=_parse_promotion(raw["promotion"]),
            schema_version=schema_version,
            participant_v2=participant_v2,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible representation."""

        result: dict[str, object] = {
            "candidate_name": self.candidate_name,
            "cost": {
                "evaluation_input_tokens": self.cost.evaluation_input_tokens,
                "evaluation_output_tokens": self.cost.evaluation_output_tokens,
                "gpu_seconds": self.cost.gpu_seconds,
                "researcher_input_tokens": self.cost.researcher_input_tokens,
                "researcher_output_tokens": self.cost.researcher_output_tokens,
                "wall_seconds": self.cost.wall_seconds,
            },
            "evidence": [
                {
                    "claim": claim.claim,
                    "evidence_id": claim.evidence_id,
                    "kind": claim.kind,
                    "reference": claim.reference,
                }
                for claim in self.evidence
            ],
            "mechanisms": [
                {
                    "description": mechanism.description,
                    "mechanism_id": mechanism.mechanism_id,
                    "policy_paths": list(mechanism.policy_paths),
                }
                for mechanism in self.mechanisms
            ],
            "parent_artifact_id": self.parent_artifact_id,
            "predictions": [
                {
                    "evidence_ids": list(prediction.evidence_ids),
                    "item_id": prediction.item_id,
                    "mechanism_ids": list(prediction.mechanism_ids),
                    "probabilities": {
                        "improve": prediction.probabilities.improve,
                        "regress": prediction.probabilities.regress,
                        "unchanged": prediction.probabilities.unchanged,
                    },
                }
                for prediction in self.predictions
            ],
            "promotion": {
                "decision": self.promotion.decision,
                "expected_score_delta": self.promotion.expected_score_delta,
                "max_regression_probability": self.promotion.max_regression_probability,
                "rationale": self.promotion.rationale,
            },
            "schema_version": self.schema_version,
        }
        if self.participant_v2 is not None:
            result["participant_v2"] = _participant_v2_to_dict(self.participant_v2)
        return result


def load_manifest(path: str | Path) -> Manifest:
    """Load a manifest while rejecting duplicate JSON keys and non-finite numbers."""

    def reject_constant(value: str) -> object:
        raise ManifestError(f"manifest contains non-finite number: {value}")

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ManifestError(f"manifest contains duplicate key: {key}")
            result[key] = value
        return result

    try:
        raw: object = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load manifest: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError("manifest root must be an object")
    return Manifest.from_dict(raw)


def write_manifest_atomic(path: str | Path, manifest: Manifest) -> None:
    """Atomically write a canonical manifest in the destination filesystem."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            manifest.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _as_mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{field} must be an object")
    return value


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _as_sequence(value: object, *, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be an array")
    return value


def _as_str(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{field} must be a string")
    return value


def _as_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{field} must be an integer")
    return value


def _as_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{field} must be a number")
    return float(value)


def _str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    return tuple(_as_str(item, field=field) for item in _as_sequence(value, field=field))


def _require_fields(raw: Mapping[str, object], expected: set[str], *, field: str) -> None:
    actual = set(raw)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ManifestError(f"{field} fields mismatch; missing={missing}, extra={extra}")


def _allow_fields(
    raw: Mapping[str, object], *, allowed: set[str], required: set[str], field: str
) -> None:
    actual = set(raw)
    missing = sorted(required - actual)
    extra = sorted(actual - allowed)
    if missing or extra:
        raise ManifestError(f"{field} fields mismatch; missing={missing}, extra={extra}")


def _parse_mechanism(value: object) -> MechanismClaim:
    raw = _as_mapping(value, field="mechanism")
    _require_fields(raw, {"description", "mechanism_id", "policy_paths"}, field="mechanism")
    return MechanismClaim(
        mechanism_id=_as_str(raw["mechanism_id"], field="mechanism_id"),
        description=_as_str(raw["description"], field="mechanism.description"),
        policy_paths=_str_tuple(raw["policy_paths"], field="mechanism.policy_paths"),
    )


def _parse_evidence(value: object) -> EvidenceClaim:
    raw = _as_mapping(value, field="evidence")
    _require_fields(raw, {"claim", "evidence_id", "kind", "reference"}, field="evidence")
    return EvidenceClaim(
        evidence_id=_as_str(raw["evidence_id"], field="evidence_id"),
        kind=_as_str(raw["kind"], field="evidence.kind"),
        reference=_as_str(raw["reference"], field="evidence.reference"),
        claim=_as_str(raw["claim"], field="evidence.claim"),
    )


def _parse_prediction(value: object) -> QuestionPrediction:
    raw = _as_mapping(value, field="prediction")
    _require_fields(
        raw,
        {"evidence_ids", "item_id", "mechanism_ids", "probabilities"},
        field="prediction",
    )
    probability_raw = _as_mapping(raw["probabilities"], field="prediction.probabilities")
    _require_fields(
        probability_raw,
        {"improve", "regress", "unchanged"},
        field="prediction.probabilities",
    )
    return QuestionPrediction(
        item_id=_as_str(raw["item_id"], field="prediction.item_id"),
        probabilities=FlipProbabilities(
            improve=_as_float(probability_raw["improve"], field="probabilities.improve"),
            unchanged=_as_float(probability_raw["unchanged"], field="probabilities.unchanged"),
            regress=_as_float(probability_raw["regress"], field="probabilities.regress"),
        ),
        mechanism_ids=_str_tuple(raw["mechanism_ids"], field="prediction.mechanism_ids"),
        evidence_ids=_str_tuple(raw["evidence_ids"], field="prediction.evidence_ids"),
    )


def _parse_cost(value: object) -> CostEstimate:
    raw = _as_mapping(value, field="cost")
    _require_fields(
        raw,
        {
            "evaluation_input_tokens",
            "evaluation_output_tokens",
            "gpu_seconds",
            "researcher_input_tokens",
            "researcher_output_tokens",
            "wall_seconds",
        },
        field="cost",
    )
    return CostEstimate(
        researcher_input_tokens=_as_int(
            raw["researcher_input_tokens"], field="cost.researcher_input_tokens"
        ),
        researcher_output_tokens=_as_int(
            raw["researcher_output_tokens"], field="cost.researcher_output_tokens"
        ),
        evaluation_input_tokens=_as_int(
            raw["evaluation_input_tokens"], field="cost.evaluation_input_tokens"
        ),
        evaluation_output_tokens=_as_int(
            raw["evaluation_output_tokens"], field="cost.evaluation_output_tokens"
        ),
        gpu_seconds=_as_float(raw["gpu_seconds"], field="cost.gpu_seconds"),
        wall_seconds=_as_float(raw["wall_seconds"], field="cost.wall_seconds"),
    )


def _parse_promotion(value: object) -> PromotionRecommendation:
    raw = _as_mapping(value, field="promotion")
    _require_fields(
        raw,
        {"decision", "expected_score_delta", "max_regression_probability", "rationale"},
        field="promotion",
    )
    decision = _as_str(raw["decision"], field="promotion.decision")
    if decision not in {"promote", "hold", "reject"}:
        raise ManifestError("promotion.decision must be promote, hold, or reject")
    return PromotionRecommendation(
        decision=cast(Literal["promote", "hold", "reject"], decision),
        expected_score_delta=_as_float(
            raw["expected_score_delta"], field="promotion.expected_score_delta"
        ),
        max_regression_probability=_as_float(
            raw["max_regression_probability"],
            field="promotion.max_regression_probability",
        ),
        rationale=_as_str(raw["rationale"], field="promotion.rationale"),
    )


def _parse_participant_v2(value: object) -> ParticipantV2:
    raw = _as_mapping(value, field="participant_v2")
    _allow_fields(
        raw,
        allowed={
            "arm",
            "improvement_cost",
            "participant_id",
            "pool_tier",
            "seed_id",
            "state_schema",
            "state_transcript_ref",
            "task_order_seed",
        },
        required={"arm", "participant_id"},
        field="participant_v2",
    )
    arm = _as_str(raw["arm"], field="participant_v2.arm")
    if arm not in {"fixed", "experience_accumulation", "open_s_cli", "stateful_control"}:
        raise ManifestError("participant_v2.arm must be one of the v2 registration arms")
    pool_tier = _optional_str(raw, "pool_tier", field="participant_v2.pool_tier")
    if pool_tier is not None and pool_tier not in {
        "T1_ANCHOR",
        "T2_VERSIONED_API",
        "T3_COMPATIBILITY",
    }:
        raise ManifestError(
            "participant_v2.pool_tier must be T1_ANCHOR, T2_VERSIONED_API, or T3_COMPATIBILITY"
        )
    return ParticipantV2(
        participant_id=_as_str(raw["participant_id"], field="participant_v2.participant_id"),
        arm=cast(
            Literal["fixed", "experience_accumulation", "open_s_cli", "stateful_control"],
            arm,
        ),
        seed_id=_optional_str(raw, "seed_id", field="participant_v2.seed_id"),
        state_schema=_optional_str(raw, "state_schema", field="participant_v2.state_schema"),
        improvement_cost=(
            _parse_improvement_cost(raw["improvement_cost"]) if "improvement_cost" in raw else None
        ),
        pool_tier=cast(
            Literal["T1_ANCHOR", "T2_VERSIONED_API", "T3_COMPATIBILITY"] | None,
            pool_tier,
        ),
        state_transcript_ref=_optional_str(
            raw, "state_transcript_ref", field="participant_v2.state_transcript_ref"
        ),
        task_order_seed=_optional_int(
            raw, "task_order_seed", field="participant_v2.task_order_seed"
        ),
    )


def _parse_improvement_cost(value: object) -> ImprovementCostV2:
    raw = _as_mapping(value, field="participant_v2.improvement_cost")
    _allow_fields(
        raw,
        allowed={
            "improve_dollar_estimate",
            "improve_input_tokens",
            "improve_output_tokens",
            "improve_wall_seconds",
        },
        required=set(),
        field="participant_v2.improvement_cost",
    )
    return ImprovementCostV2(
        improve_input_tokens=_optional_int(
            raw,
            "improve_input_tokens",
            field="participant_v2.improvement_cost.improve_input_tokens",
        ),
        improve_output_tokens=_optional_int(
            raw,
            "improve_output_tokens",
            field="participant_v2.improvement_cost.improve_output_tokens",
        ),
        improve_wall_seconds=_optional_float(
            raw,
            "improve_wall_seconds",
            field="participant_v2.improvement_cost.improve_wall_seconds",
        ),
        improve_dollar_estimate=_as_optional_float(
            raw.get("improve_dollar_estimate"),
            field="participant_v2.improvement_cost.improve_dollar_estimate",
        ),
    )


def _optional_str(raw: Mapping[str, object], key: str, *, field: str) -> str | None:
    if key not in raw:
        return None
    return _as_str(raw[key], field=field)


def _optional_int(raw: Mapping[str, object], key: str, *, field: str) -> int | None:
    if key not in raw:
        return None
    return _as_int(raw[key], field=field)


def _optional_float(raw: Mapping[str, object], key: str, *, field: str) -> float | None:
    if key not in raw:
        return None
    return _as_float(raw[key], field=field)


def _as_optional_float(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    return _as_float(value, field=field)


def _participant_v2_to_dict(participant: ParticipantV2) -> dict[str, object]:
    result: dict[str, object] = {
        "participant_id": participant.participant_id,
        "arm": participant.arm,
    }
    if participant.seed_id is not None:
        result["seed_id"] = participant.seed_id
    if participant.state_schema is not None:
        result["state_schema"] = participant.state_schema
    if participant.improvement_cost is not None:
        cost = participant.improvement_cost
        improvement_cost: dict[str, object] = {}
        if cost.improve_input_tokens is not None:
            improvement_cost["improve_input_tokens"] = cost.improve_input_tokens
        if cost.improve_output_tokens is not None:
            improvement_cost["improve_output_tokens"] = cost.improve_output_tokens
        if cost.improve_wall_seconds is not None:
            improvement_cost["improve_wall_seconds"] = cost.improve_wall_seconds
        if cost.improve_dollar_estimate is not None:
            improvement_cost["improve_dollar_estimate"] = cost.improve_dollar_estimate
        result["improvement_cost"] = improvement_cost
    if participant.pool_tier is not None:
        result["pool_tier"] = participant.pool_tier
    if participant.state_transcript_ref is not None:
        result["state_transcript_ref"] = participant.state_transcript_ref
    if participant.task_order_seed is not None:
        result["task_order_seed"] = participant.task_order_seed
    return result
