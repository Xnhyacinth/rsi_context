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
            # Reviewer 2.2's end-to-end pin: a PASSING S1 must ALSO be
            # crash-free. Without this, "S1 strategy crashed and fell
            # back to the fixed heuristic" is indistinguishable from
            # "the strategy genuinely did not help" — the exact
            # mis-attribution a researcher-authored run cannot afford.
            assert variant.get("strategy_errors") == [], variant
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


def test_crashing_strategy_is_recorded_not_swallowed(tmp_path: Path) -> None:
    # Reviewer 2.2: a strategy whose body raises on every exec must be
    # NAMED in the branch records (strategy_errors), never silently
    # indistinguishable from "no strategy supplied". A broken researcher
    # edit reports as a crash, not as "the improvement did not transfer".
    # Exercise the hook directly (same class, same code path) instead
    # of monkeypatching the CLI's strategy text.
    import sys

    sys.path.insert(0, str(_REPO_ROOT / "src"))
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    from trajectory_v3 import TrajectoryHook

    crashing = "raise ValueError('researcher edit crashed')\n"
    hook = TrajectoryHook(
        {}, None, offline=True, offline_answers={"Survey": "x"}, strategy_text=crashing
    )
    assert hook.strategy_errors == []
    assert hook.choose_plan() == "aurora"  # fixed fallback still works
    assert hook.strategy_errors and "ValueError" in hook.strategy_errors[0]


def test_clean_strategy_records_no_errors(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(_REPO_ROOT / "src"))
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    from trajectory_v3 import TrajectoryHook

    clean = "STRATEGY_RERVERIFY = True\n"
    hook = TrajectoryHook({}, None, offline=True, offline_answers={}, strategy_text=clean)
    hook.choose_plan()
    assert hook.strategy_errors == []


def test_researcher_mode_is_live_only() -> None:
    # --researcher with --offline is refused: the researcher is a real
    # model; a fake-reader researcher round would be a fabrication.
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "trajectory_v3.py"),
            "--offline",
            "--researcher",
            "--output",
            str(_REPO_ROOT / "tmp" / "never-written.json"),
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 2
    assert "live-only" in result.stderr


def test_stub_strategy_is_the_fixed_baseline() -> None:
    # The researcher-mode S1 stub (STRATEGY_RERVERIFY = False) is the
    # fixed arm's behavior — so a researcher that changes nothing, or a
    # failed round falling back to the stub, is exactly the no-change
    # baseline the S0-vs-S1 contrast measures against.
    import sys

    sys.path.insert(0, str(_REPO_ROOT / "src"))
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    from trajectory_v3 import _STRATEGY_STUB, TrajectoryHook

    hook = TrajectoryHook({}, None, offline=True, offline_answers={}, strategy_text=_STRATEGY_STUB)
    assert hook.choose_plan()  # fixed fallback; no strategy errors
    assert hook.strategy_errors == []
    assert "STRATEGY_RERVERIFY = False" in _STRATEGY_STUB
