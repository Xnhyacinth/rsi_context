"""r3 unified-entry acceptance tests — the three-group artifact shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ARM_KEYS = {
    "baseline",
    "unassisted_update",
    "non_adaptive_search",
    "recuris_s0_matched",
    "recuris_adapted",
}


def _artifact() -> dict:
    artifact = Path("artifacts/rsi-core-v1/r3-comparison.json")
    if not artifact.exists():
        import subprocess

        subprocess.run(
            [
                sys.executable,
                "scripts/r3_compare.py",
                "--offline",
                "--output",
                str(artifact),
            ],
            check=True,
            capture_output=True,
        )
    return json.loads(artifact.read_text())


def test_r3_artifact_shape() -> None:
    payload = _artifact()
    assert set(payload["groups"]) == {"A", "B", "C"}
    for group_id, group in payload["groups"].items():
        assert set(group["arms"]) == ARM_KEYS, (group_id, group["arms"].keys())
        # Every eval cell carries the GroupRun contract fields.
        for arm, cells in group["arms"].items():
            run = cells["eval"]
            for field in (
                "passed",
                "decisions",
                "model_calls",
                "model_tokens_in",
                "model_tokens_out",
                "policy_errors",
            ):
                assert field in run, (group_id, arm, field)
        # Per-group deltas + four-outcome; the aggregate is a CONJUNCTION.
        assert set(group["deltas"]) == {
            "update_vs_baseline",
            "search_vs_baseline",
            "recuris_vs_s0matched",
        }
        assert group["four_outcome"] in ("improves", "ties", "regresses")
    assert payload["aggregate_four_outcome"] in ("improves", "ties", "regresses")


def test_r3_group_shapes_and_decision_keys() -> None:
    payload = _artifact()
    assert payload["groups"]["A"]["shape"] == "lifecycle"
    assert payload["groups"]["B"]["shape"] == "sequence"
    assert payload["groups"]["C"]["shape"] == "sequence"
    # A: three decisions; B: six; C: two (per-session recovery).
    assert set(payload["groups"]["A"]["arms"]["baseline"]["eval"]["decisions"]) == {
        "award",
        "followup_1",
        "followup_2",
    }
    b_dec = payload["groups"]["B"]["arms"]["baseline"]["eval"]["decisions"]
    assert set(b_dec) == {
        "s1_award",
        "s2_calibration",
        "s2_currency",
        "s2_reaward_fresh",
        "s3_award",
        "s3_calibration",
    }
    assert set(payload["groups"]["C"]["arms"]["baseline"]["eval"]["decisions"]) == {
        "c1_recovery",
        "c2_recovery",
    }


def test_r3_offline_all_arms_recorded_with_cost() -> None:
    payload = _artifact()
    for group_id, group in payload["groups"].items():
        # The improver's rounds + meta attempts + internal dev runs are
        # recorded per group (the cost ledger the contract governs).
        rec = group["arms"]["recuris_adapted"]["improver_record"]
        assert len(rec["rounds"]) == 2
        assert "meta_attempts" in rec and "dev_runs_internal" in rec
        assert "final_package" in group["arms"]["recuris_adapted"]
        # Search candidates recorded with usability.
        candidates = group["arms"]["non_adaptive_search"]["candidates"]
        assert len(candidates) == 3


def test_r3_live_mode_requires_key() -> None:
    import os
    import subprocess

    env = dict(os.environ)
    env.pop("SIFLOW_API_KEY", None)
    out = Path("artifacts/rsi-core-v1/tmp-r3-skip.json")
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [sys.executable, "scripts/r3_compare.py", "--output", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert not out.exists()
