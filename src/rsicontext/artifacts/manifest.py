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

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ManifestError(f"schema_version must be {_SCHEMA_VERSION}")
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

        _require_fields(
            raw,
            {
                "candidate_name",
                "cost",
                "evidence",
                "mechanisms",
                "parent_artifact_id",
                "predictions",
                "promotion",
                "schema_version",
            },
            field="manifest",
        )
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
        return cls(
            candidate_name=candidate_name,
            parent_artifact_id=parent_raw,
            predictions=predictions,
            mechanisms=mechanisms,
            evidence=evidence,
            cost=_parse_cost(raw["cost"]),
            promotion=_parse_promotion(raw["promotion"]),
            schema_version=schema_version,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible representation."""

        return {
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
