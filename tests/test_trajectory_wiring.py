"""Wiring tests for the S0->S1 trajectory script (offline mode).

Pins the trajectory's CONTRACT, not its live behavior: the reference
executor passes; the fixed arm's commits are refused with the stale-
revision error (the designed weakness); the DS S1's branches run; the
artifact carries the three evidence classes separated (reference /
fixed-control / ds-arm with S0 and S1). Runs the script's offline mode
end-to-end (fake reader, zero API calls) as a subprocess so the CLI
surface is what is tested.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_offline_trajectory_closes_the_loop(tmp_path: Path) -> None:
    output = tmp_path / "trajectory.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "trajectory_v3.py"),
            "--offline",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "offline"
    assert payload["world"] == "research-v3-main-0001"

    # Reference executor: the task is solvable (a capability-free check).
    assert payload["reference_executor"]["final_check_passed"] is True
    assert payload["reference_executor"]["committed_plan"] == "aurora"

    def _final_check_passed(variant: dict) -> bool:
        checks = variant.get("final_checks", [])
        return bool(checks) and all(entry["passed"] for entry in checks)

    # Fixed arm: every branch's final check FAILS, naming the stale
    # in-scope verification (the designed weakness, now visible through
    # the evaluator gate rather than an apply-time refusal).
    for branch in ("continuation", "new_world", "regression"):
        for variant in payload["fixed_arm"]["branches"][branch]:
            if variant.get("error"):
                assert "stale" in variant["error"], variant
            else:
                assert not _final_check_passed(variant), variant
                failures = [
                    failure
                    for entry in variant.get("final_checks", [])
                    for failure in entry["failures"]
                ]
                assert any("stale" in failure for failure in failures), variant

    # DS arm: S1's branches PASS with the scope-aware strategy; S0's
    # share the fixed arm's stale-evidence failure signature.
    for branch in ("continuation", "new_world", "regression"):
        for variant in payload["ds_arm"]["s1_branches"][branch]:
            assert variant["ran"] is True, variant
            assert _final_check_passed(variant), variant
        for variant in payload["ds_arm"]["s0_branches"][branch]:
            if variant.get("error"):
                assert "stale" in variant["error"], variant
            else:
                assert not _final_check_passed(variant), variant

    # The improvement record is inspectable: strategy text + state update.
    improvement = payload["ds_arm"]["improvement"]
    assert "STRATEGY_RERVERIFY" in improvement["strategy_text"]
    assert isinstance(improvement["state_update"], dict)

    # Evidence classes stay separated in the artifact.
    assert set(payload) >= {
        "reference_executor",
        "fixed_arm",
        "ds_arm",
        "elapsed_seconds",
    }
