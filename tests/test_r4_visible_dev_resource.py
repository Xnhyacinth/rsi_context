"""Portable R3 development feedback contains only its visible A-dev slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_portable_feedback_matches_preflight_and_excludes_evaluator_rows() -> None:
    path = ROOT / "resources/r3_visible_dev_7052c06/a-dev-feedback.json"
    raw = path.read_bytes()
    manifest = json.loads((ROOT / "configs/r3_gate1_offline_preflight_v3.json").read_text())
    assert (
        hashlib.sha256(raw).hexdigest()
        == manifest["visible_resource_sha256"]["a-dev-feedback.json"]
    )
    feedback = json.loads(raw)
    assert set(feedback) == {
        "schema_version",
        "source_sha256",
        "group",
        "phase",
        "instance_id",
        "decisions",
        "failures",
    }
    assert feedback["group"] == "A"
    assert feedback["phase"] == "dev"
    assert "eval" not in raw.decode().lower()
    assert "model_transcript" not in raw.decode()
    assert "gold_evidence_ids" not in raw.decode()


def test_portable_bc_call_projection_is_pinned_and_label_free() -> None:
    path = ROOT / "resources/r4_bc_scripted_calls_v1.json"
    raw = path.read_bytes()
    contract = json.loads((ROOT / "configs/r4_bc_dev_budget_v2.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == contract["source_admission_sha256"]
    data = json.loads(raw)
    assert data["mode"] == "portable_projection_of_offline_admission"
    assert data["model_api_calls"] == 0
    assert set(data["groups"]) == {"B", "C"}
    for forbidden in ("legal_plans", "verification_oracle", "gold_evidence_ids", "decisions"):
        assert forbidden not in raw.decode()
