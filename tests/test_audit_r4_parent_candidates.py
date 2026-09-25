"""Candidate-only source lineage inventory without evaluator disclosures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_r4_parent_candidates as audit


def test_candidate_inventory_is_hash_only_and_does_not_qualify_parents() -> None:
    result = audit.inventory()
    rows = result["candidates"]
    assert result["summary"] == {
        "new_candidate_parent_lineages": 2,
        "qualified_independent_parents": 0,
        "qualified_groups": [],
        "model_api_calls": 0,
    }
    assert [(row["group"], row["parent_lineage"]) for row in rows] == [
        ("A", "otel-db-migration"),
        ("C", "k8s-sidecar-rollout"),
    ]
    assert rows[0]["material_sha256"] == (
        "73175e8a9424b8898404080db7e877ab3e0d1ec16881fa00456657a664e8cc8d"
    )
    assert rows[0]["evaluator_world_sha256"] == (
        "99bebe5143d37270bfe26ad40ed3e9fee666a8ea877d7f7f36bcc5a9471704ab"
    )
    assert rows[1]["evaluator_world_sha256"] == (
        "9409175713220777bc7ec70683dd3270cead3ac00afd9b431e0cf98fd4b94de7"
    )
    assert all(row["qualified"] is False for row in rows)
    assert all(row["answer_literal_in_stage_prompt"] is False for row in rows)
    assert all(row["source_whitespace_words"] > 0 for row in rows)
    exported = json.dumps(result)
    for forbidden in (
        "gold_evidence_ids",
        "verification_oracle",
        "legal_plans",
        "expected_state_delta",
        "database/dup",
        "native-sidecar-with-probe",
    ):
        assert forbidden not in exported


def test_source_manifest_drift_rejects_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = json.loads(audit.SOURCE_MANIFEST.read_text())
    manifest["sources"].pop()
    changed = tmp_path / "source.json"
    changed.write_text(json.dumps(manifest))
    monkeypatch.setattr(audit, "SOURCE_MANIFEST", changed)
    with pytest.raises(ValueError, match="entries changed"):
        audit.inventory()
