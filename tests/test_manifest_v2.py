import copy
import json
from pathlib import Path

import pytest

from rsicontext.artifacts import (
    ImprovementCostV2,
    Manifest,
    ManifestError,
    ParticipantV2,
    load_manifest,
    write_manifest_atomic,
)


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


def full_participant_v2() -> dict[str, object]:
    return {
        "participant_id": "p-open-s-001",
        "arm": "open_s_cli",
        "seed_id": "seed-1",
        "state_schema": "b" * 64,
        "improvement_cost": {
            "improve_input_tokens": 5000,
            "improve_output_tokens": 900,
            "improve_wall_seconds": 42.0,
            "improve_dollar_estimate": 1.25,
        },
        "pool_tier": "T1_ANCHOR",
        "state_transcript_ref": "sessions/visible/state-transcript.json",
        "task_order_seed": 7,
    }


def test_v1_manifest_still_parses_unchanged() -> None:
    manifest = Manifest.from_dict(valid_manifest_dict())

    assert manifest.schema_version == 1
    assert manifest.participant_v2 is None
    # v1 serialization keeps the exact pre-v2 key set: no participant_v2 key.
    assert set(manifest.to_dict()) == {
        "candidate_name",
        "cost",
        "evidence",
        "mechanisms",
        "parent_artifact_id",
        "predictions",
        "promotion",
        "schema_version",
    }


def test_v2_full_participant_block_parses_with_typed_fields() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = full_participant_v2()

    manifest = Manifest.from_dict(raw)

    assert manifest.schema_version == 2
    participant = manifest.participant_v2
    assert isinstance(participant, ParticipantV2)
    assert participant.participant_id == "p-open-s-001"
    assert participant.arm == "open_s_cli"
    assert participant.seed_id == "seed-1"
    assert participant.state_schema == "b" * 64
    cost = participant.improvement_cost
    assert isinstance(cost, ImprovementCostV2)
    assert cost.improve_input_tokens == 5000
    assert cost.improve_output_tokens == 900
    assert cost.improve_wall_seconds == 42.0
    assert cost.improve_dollar_estimate == 1.25
    assert participant.pool_tier == "T1_ANCHOR"
    assert participant.state_transcript_ref == "sessions/visible/state-transcript.json"
    assert participant.task_order_seed == 7


def test_v2_minimal_block_parses_with_other_fields_none() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = {"participant_id": "p-fixed-001", "arm": "fixed"}

    manifest = Manifest.from_dict(raw)

    participant = manifest.participant_v2
    assert isinstance(participant, ParticipantV2)
    assert participant.participant_id == "p-fixed-001"
    assert participant.arm == "fixed"
    assert participant.seed_id is None
    assert participant.state_schema is None
    assert participant.improvement_cost is None
    assert participant.pool_tier is None
    assert participant.state_transcript_ref is None
    assert participant.task_order_seed is None


def test_v2_round_trip_through_dump_and_load(tmp_path: Path) -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = full_participant_v2()
    manifest = Manifest.from_dict(raw)

    assert manifest.to_dict() == raw

    destination = tmp_path / "candidate" / "manifest.json"
    write_manifest_atomic(destination, manifest)
    assert load_manifest(destination) == manifest
    assert json.loads(destination.read_text(encoding="utf-8")) == raw


def test_v2_minimal_block_round_trip_keeps_only_present_keys() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = {"participant_id": "p-fixed-001", "arm": "fixed"}
    manifest = Manifest.from_dict(raw)

    assert manifest.to_dict()["participant_v2"] == {
        "participant_id": "p-fixed-001",
        "arm": "fixed",
    }


def test_v2_rejects_invalid_state_schema() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    invalid = full_participant_v2()
    assert isinstance(invalid, dict)
    invalid["state_schema"] = "not-a-hex-digest"
    raw["participant_v2"] = invalid

    with pytest.raises(ManifestError, match="state_schema"):
        Manifest.from_dict(raw)


def test_v2_rejects_unknown_key_inside_participant_block() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    invalid = full_participant_v2()
    assert isinstance(invalid, dict)
    invalid["unregistered"] = True
    raw["participant_v2"] = invalid

    with pytest.raises(ManifestError, match="extra"):
        Manifest.from_dict(raw)


def test_v2_rejects_unknown_key_inside_improvement_cost() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    invalid = full_participant_v2()
    cost_block = invalid["improvement_cost"]
    assert isinstance(cost_block, dict)
    cost_block["unregistered"] = 0
    raw["participant_v2"] = invalid

    with pytest.raises(ManifestError, match="extra"):
        Manifest.from_dict(raw)


@pytest.mark.parametrize(
    "block",
    [
        {"arm": "fixed"},
        {"participant_id": "p-fixed-001"},
        {},
    ],
)
def test_v2_block_requires_participant_id_and_arm(block: dict[str, object]) -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = block

    with pytest.raises(ManifestError, match="missing"):
        Manifest.from_dict(raw)


@pytest.mark.parametrize("arm", ["random", "open_s_researcher", ""])
def test_v2_rejects_unknown_arm(arm: str) -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    raw["participant_v2"] = {"participant_id": "p-fixed-001", "arm": arm}

    with pytest.raises(ManifestError, match="arm"):
        Manifest.from_dict(raw)


def test_v2_rejects_unknown_pool_tier() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    invalid = full_participant_v2()
    assert isinstance(invalid, dict)
    invalid["pool_tier"] = "T4"
    raw["participant_v2"] = invalid

    with pytest.raises(ManifestError, match="pool_tier"):
        Manifest.from_dict(raw)


def test_v1_rejects_participant_block_and_v2_block_requires_version_two() -> None:
    raw = valid_manifest_dict()
    raw["participant_v2"] = full_participant_v2()

    # v1 (schema_version 1) rejects the block as an unknown top-level field.
    with pytest.raises(ManifestError, match="extra"):
        Manifest.from_dict(raw)

    version_mismatch = copy.deepcopy(raw)
    version_mismatch["schema_version"] = 2
    manifest = Manifest.from_dict(version_mismatch)
    assert manifest.participant_v2 is not None


def test_schema_version_three_is_rejected() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 3

    with pytest.raises(ManifestError, match="schema_version"):
        Manifest.from_dict(raw)


def test_v2_allows_null_dollar_estimate_in_improvement_cost() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    block = full_participant_v2()
    cost_block = block["improvement_cost"]
    assert isinstance(cost_block, dict)
    cost_block["improve_dollar_estimate"] = None
    raw["participant_v2"] = block

    manifest = Manifest.from_dict(raw)

    cost = manifest.participant_v2
    assert cost is not None
    assert cost.improvement_cost is not None
    assert cost.improvement_cost.improve_dollar_estimate is None


def test_v2_empty_improvement_cost_object_parses_as_all_none() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    block = full_participant_v2()
    block["improvement_cost"] = {}
    raw["participant_v2"] = block

    manifest = Manifest.from_dict(raw)

    participant = manifest.participant_v2
    assert participant is not None
    cost = participant.improvement_cost
    assert isinstance(cost, ImprovementCostV2)
    assert cost.improve_input_tokens is None
    assert cost.improve_output_tokens is None
    assert cost.improve_wall_seconds is None
    assert cost.improve_dollar_estimate is None


def test_v2_rejects_negative_improvement_cost() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    block = full_participant_v2()
    cost_block = block["improvement_cost"]
    assert isinstance(cost_block, dict)
    cost_block["improve_input_tokens"] = -1
    raw["participant_v2"] = block

    with pytest.raises(ManifestError, match="improve_input_tokens"):
        Manifest.from_dict(raw)


def test_v2_rejects_non_integer_task_order_seed() -> None:
    raw = valid_manifest_dict()
    raw["schema_version"] = 2
    block = full_participant_v2()
    block["task_order_seed"] = "seven"
    raw["participant_v2"] = block

    with pytest.raises(ManifestError, match="task_order_seed"):
        Manifest.from_dict(raw)
