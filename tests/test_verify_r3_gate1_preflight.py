"""Pinned-input checks for the offline R3 Gate-1 workspaces."""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_r3_gate1_preflight import (
    BASELINE_COMMIT,
    EXPECTED_PILOT,
    TRACKED_INPUTS,
    verify_inputs,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    repo = tmp_path / "repo"
    resources = tmp_path / "resources"
    repo.mkdir(parents=True)
    resources.mkdir()
    for relative in TRACKED_INPUTS:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"locked")
    (resources / "a-dev-feedback.json").write_bytes(b"visible")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "offline_preflight_only",
        "baseline_commit": BASELINE_COMMIT,
        "tracked_sha256": {relative: _digest(b"locked") for relative in TRACKED_INPUTS},
        "visible_resource_sha256": {"a-dev-feedback.json": _digest(b"visible")},
        "candidate_pilot": copy.deepcopy(EXPECTED_PILOT),
        "live_gate": {
            "enabled": False,
            "requires_actual_isolated_executor": True,
            "requires_reader_profile_reconciliation": True,
            "requires_qualified_parent_manifest": True,
            "requires_versioned_bc_worker_cap": True,
        },
    }
    return repo, resources, manifest


def test_offline_preflight_checks_exact_bytes_and_reports_infeasible_cap(tmp_path: Path) -> None:
    repo, resources, manifest = _fixture(tmp_path)

    result = verify_inputs(manifest, repo_root=repo, resource_root=resources)

    assert result["status"] == "offline_inputs_verified"
    assert result["worker_call_cap_feasible"] is False
    assert result["live_ready"] is False
    checked = result["checked_sha256"]
    assert isinstance(checked, dict)
    assert set(checked) == {f"tracked:{name}" for name in TRACKED_INPUTS} | {
        "visible:a-dev-feedback.json"
    }

    (resources / "a-dev-feedback.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="visible input hash mismatch"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)


def test_preflight_rejects_missing_inputs_and_changed_settings(tmp_path: Path) -> None:
    repo, resources, manifest = _fixture(tmp_path)
    tracked = manifest["tracked_sha256"]
    assert isinstance(tracked, dict)
    tracked.pop("configs/registry.json")
    with pytest.raises(ValueError, match="input file set"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)

    repo, resources, manifest = _fixture(tmp_path / "second")
    pilot = manifest["candidate_pilot"]
    assert isinstance(pilot, dict)
    pilot["researcher_model"] = "different-model"
    with pytest.raises(ValueError, match="differs from Gate-1 v1 settings"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)


def test_preflight_rejects_traversal_symlink_and_live_enablement(tmp_path: Path) -> None:
    repo, resources, manifest = _fixture(tmp_path)

    manifest["visible_resource_sha256"] = {"../outside": _digest(b"visible")}
    with pytest.raises(ValueError, match="input file set"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)

    (resources / "a-dev-feedback.json").unlink()
    (resources / "a-dev-feedback.json").symlink_to(repo / "uv.lock")
    manifest["visible_resource_sha256"] = {"a-dev-feedback.json": _digest(b"locked")}
    with pytest.raises(ValueError, match="non-regular manifest input"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)

    (resources / "a-dev-feedback.json").unlink()
    (resources / "a-dev-feedback.json").write_bytes(b"visible")
    manifest["visible_resource_sha256"] = {"a-dev-feedback.json": _digest(b"visible")}
    live_gate = manifest["live_gate"]
    assert isinstance(live_gate, dict)
    live_gate["enabled"] = True
    with pytest.raises(ValueError, match="cannot authorize live"):
        verify_inputs(manifest, repo_root=repo, resource_root=resources)
