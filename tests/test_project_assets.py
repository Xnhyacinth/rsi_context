from __future__ import annotations

import json
from pathlib import Path

from rsicontext.security import PolicyAuditor

ROOT = Path(__file__).parents[1]


def test_seed_policy_passes_static_capability_audit() -> None:
    report = PolicyAuditor().audit_tree(ROOT / "policy")

    assert report.safe
    assert report.files == ("seed.py",)


def test_manifest_json_schema_matches_runtime_top_level_fields() -> None:
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "candidate_name",
        "cost",
        "evidence",
        "mechanisms",
        "parent_artifact_id",
        "predictions",
        "promotion",
        "schema_version",
    }
