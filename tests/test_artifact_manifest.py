import copy
import json
from pathlib import Path

import pytest

from rsicontext.artifacts import Manifest, ManifestError, load_manifest, write_manifest_atomic


def valid_manifest_dict() -> dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_name": "round-2-hybrid",
        "parent_artifact_id": "a" * 64,
        "mechanisms": [
            {
                "mechanism_id": "position-aware-selection",
                "description": "Preserve evidence near document boundaries.",
                "policy_paths": ["policy/select.py", "policy/order.py"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "trace-item-7",
                "kind": "failure_trace",
                "reference": "visible/item-7/round-1.json",
                "claim": "The relevant chunk was selected but placed in the middle.",
            }
        ],
        "predictions": [
            {
                "item_id": "item-7",
                "probabilities": {"improve": 0.7, "unchanged": 0.2, "regress": 0.1},
                "mechanism_ids": ["position-aware-selection"],
                "evidence_ids": ["trace-item-7"],
            }
        ],
        "cost": {
            "researcher_input_tokens": 1200,
            "researcher_output_tokens": 300,
            "evaluation_input_tokens": 4000,
            "evaluation_output_tokens": 80,
            "gpu_seconds": 12.5,
            "wall_seconds": 15.0,
        },
        "promotion": {
            "decision": "promote",
            "expected_score_delta": 0.03,
            "max_regression_probability": 0.1,
            "rationale": "Expected gain exceeds the pre-registered margin.",
        },
    }


def test_manifest_round_trip_and_atomic_write(tmp_path: Path) -> None:
    manifest = Manifest.from_dict(valid_manifest_dict())
    destination = tmp_path / "candidate" / "manifest.json"
    write_manifest_atomic(destination, manifest)

    assert load_manifest(destination) == manifest
    assert json.loads(destination.read_text(encoding="utf-8")) == manifest.to_dict()
    assert not list(destination.parent.glob(".manifest.json.*"))


@pytest.mark.parametrize(
    ("probabilities", "message"),
    [
        ({"improve": 0.6, "unchanged": 0.3, "regress": 0.2}, "sum"),
        ({"improve": 1.1, "unchanged": 0.0, "regress": -0.1}, "between"),
    ],
)
def test_manifest_rejects_invalid_per_question_probabilities(
    probabilities: dict[str, float], message: str
) -> None:
    raw = valid_manifest_dict()
    predictions = raw["predictions"]
    assert isinstance(predictions, list)
    prediction = predictions[0]
    assert isinstance(prediction, dict)
    prediction["probabilities"] = probabilities

    with pytest.raises(ManifestError, match=message):
        Manifest.from_dict(raw)


def test_manifest_rejects_extra_fields_and_unknown_references() -> None:
    extra = valid_manifest_dict()
    extra["unregistered"] = True
    with pytest.raises(ManifestError, match="extra"):
        Manifest.from_dict(extra)

    unknown = copy.deepcopy(valid_manifest_dict())
    predictions = unknown["predictions"]
    assert isinstance(predictions, list)
    prediction = predictions[0]
    assert isinstance(prediction, dict)
    prediction["evidence_ids"] = ["not-declared"]
    with pytest.raises(ManifestError, match="unknown evidence"):
        Manifest.from_dict(unknown)


def test_manifest_loader_rejects_duplicate_keys_and_nonfinite_numbers(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate"):
        load_manifest(duplicate)

    raw = valid_manifest_dict()
    cost = raw["cost"]
    assert isinstance(cost, dict)
    cost["gpu_seconds"] = float("nan")
    with pytest.raises(ManifestError, match="finite"):
        Manifest.from_dict(raw)


def test_manifest_predictions_must_cover_the_evaluator_item_set_exactly() -> None:
    manifest = Manifest.from_dict(valid_manifest_dict())

    manifest.validate_for_items(["item-7"])
    with pytest.raises(ManifestError, match=r"missing=.*item-8"):
        manifest.validate_for_items(["item-7", "item-8"])
    with pytest.raises(ManifestError, match=r"extra=.*item-7"):
        manifest.validate_for_items(["different-item"])


def test_promotion_max_regression_matches_item_predictions() -> None:
    raw = valid_manifest_dict()
    predictions = raw["predictions"]
    assert isinstance(predictions, list)
    prediction = predictions[0]
    assert isinstance(prediction, dict)
    prediction["probabilities"] = {"improve": 0.6, "unchanged": 0.2, "regress": 0.2}

    with pytest.raises(ManifestError, match="max_regression_probability"):
        Manifest.from_dict(raw)
