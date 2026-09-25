"""Gate 1 B/C offline admission and live fail-closed checks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import r3_bc_researcher_pilot as pilot


def _preflight(path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    manifest = {
        "status": "offline_preflight_only",
        "baseline_commit": pilot.EXPECTED_BASE,
        "live_gate": {"enabled": False},
        "candidate_pilot": pilot.PILOT_CONTRACT,
        "tracked_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in pilot.REQUIRED_TRACKED_HASHES
        },
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_offline_admission_records_causal_wiring_and_infeasible_cap(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    _preflight(preflight)
    output = tmp_path / "admission.json"
    result = pilot.run_offline_admission(output, preflight)

    assert result["status"] == "complete"
    assert cast(dict[str, Any], result["run_identity_end"])["matches_start"] is True
    assert result["model_api_calls"] == 0
    assert result["planned_attempts"] == {"B": 2, "C": 2}
    assert result["actual_researcher_attempts"] == {"B": 0, "C": 0}
    live_gate = cast(dict[str, Any], result["live_gate"])
    assert live_gate["enabled"] is False
    assert live_gate["frozen_v1_worker_cap_feasible"] is False
    assert cast(dict[str, Any], result["profile_conflict"])["unreconciled"] is True

    groups = cast(dict[str, dict[str, Any]], result["groups"])
    assert groups["B"]["project_continuity"] == {
        "first_two_share_project": True,
        "last_is_new_project": True,
    }
    assert groups["C"]["project_continuity"]["first_two_share_project"] is True
    assert groups["B"]["baseline_scripted"]["worker_calls_by_session"] == [9, 11, 11]
    assert groups["C"]["baseline_scripted"]["worker_calls_by_session"] == [9, 9]
    for group in groups.values():
        assert group["synthetic_failure_probe"]["dev_feedback"]["failures"]
        assert group["synthetic_candidate"]["audit"]["safe"] is True
        assert group["synthetic_candidate"]["loadable"] is True
        assert group["recuris_delivery"]["passed"] is True
        assert all(
            session["act_verify_memory_delivered"]
            and session["act_verify_prompt_contains_card"]
            and session["survey_prompt_excludes_card"]
            for session in group["recuris_delivery"]["sessions"]
        )
    assert json.loads(output.read_text())["status"] == "complete"


def test_candidate_audit_blocks_load_and_is_byte_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loads: list[str] = []

    def load(policy: str) -> bool:
        loads.append(policy)
        return True

    monkeypatch.setattr(pilot, "_policy_loadable", load)
    rejected = pilot._save_and_admit("import os\ndef on_turn(turn):\n    pass\n", tmp_path / "bad")
    assert cast(dict[str, Any], rejected["audit"])["safe"] is False
    assert rejected["loadable"] is False
    assert loads == []
    accepted_source = "def on_turn(turn):\n    return {'pack_text': 'ok'}\n"
    accepted = pilot._save_and_admit(accepted_source, tmp_path / "good")
    assert cast(dict[str, Any], accepted["audit"])["hashes_match"] is True
    assert cast(dict[str, Any], accepted["audit"])["safe"] is True
    assert accepted["loadable"] is True
    assert loads == [accepted_source]
    assert [path.name for path in (tmp_path / "good").iterdir()] == ["policy.py"]


def test_live_entry_fails_before_any_provider_or_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "live.json"
    monkeypatch.setattr(sys, "argv", ["pilot", "--live", "--output", str(output)])
    monkeypatch.setattr(
        pilot, "run_offline_admission", lambda *_args, **_kwargs: pytest.fail("admission ran")
    )
    with pytest.raises(SystemExit) as exc:
        pilot.main()
    assert exc.value.code == 2
    assert not output.exists()


def test_preflight_rejects_resource_drift(tmp_path: Path) -> None:
    path = tmp_path / "preflight.json"
    _preflight(path)
    manifest: dict[str, Any] = json.loads(path.read_text())
    manifest["tracked_sha256"]["uv.lock"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=r"resource hash mismatch: uv\.lock"):
        pilot._preflight(path)
