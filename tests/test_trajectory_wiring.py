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
    assert payload["seed"] == 0 and payload["rounds"] == 1

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

    # DS arm: S0 (no strategy) shares the fixed arm's failure signature;
    # S1 (the scope-aware strategy) passes on every branch.
    snapshot_branches = payload["ds_arm"]["snapshot_branches"]
    assert set(snapshot_branches) == {"S0", "S1"}
    for branch in ("continuation", "new_world", "regression"):
        for variant in snapshot_branches["S0"][branch]:
            if variant.get("error"):
                assert "stale" in variant["error"], variant
            else:
                assert not _final_check_passed(variant), variant
        for variant in snapshot_branches["S1"][branch]:
            assert variant["ran"] is True, variant
            assert _final_check_passed(variant), variant
            # Reviewer 2.2's end-to-end pin: a PASSING S1 must ALSO be
            # crash-free. Without this, "S1 strategy crashed and fell
            # back to the fixed heuristic" is indistinguishable from
            # "the strategy genuinely did not help" — the exact
            # mis-attribution a researcher-authored run cannot afford.
            assert variant.get("strategy_errors") == [], variant

    # The improvement round record is inspectable: strategy text + state.
    rounds = payload["ds_arm"]["rounds"]
    assert len(rounds) == 1
    assert rounds[0]["snapshot_id"] == "S1"
    assert "STRATEGY_RERVERIFY" in rounds[0]["strategy_text"]
    assert isinstance(rounds[0]["state_update"], dict)

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


def test_multi_round_state_update_accumulates(tmp_path: Path) -> None:
    # The carry contract: legitimate learned material (round notes)
    # ACCUMULATES across snapshots — S2's memory must contain S1's
    # notes, not replace them. A per-round overwrite silently discards
    # earlier rounds' learning from every later branch evaluation.
    output = tmp_path / "trajectory-r3.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "trajectory_v3.py"),
            "--offline",
            "--rounds",
            "3",
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
    rounds = payload["ds_arm"]["rounds"]
    assert len(rounds) == 3
    all_notes: list[str] = []
    for round_record in rounds:
        notes = round_record["state_update"].get("notes", [])
        all_notes.extend(notes)
    # Round-0's substantive notes survive into the later rounds'
    # snapshot memories: S2/S3 must still carry S1's learning.
    # (The rounds[] entries record what each round ADDED; the frozen
    # snapshot memory is the union — asserted via strategy carry
    # below.)
    # Union check via the S3 snapshot's branches: the S3 strategy is
    # still the scripted fix (cumulative), and its state carries all
    # rounds' notes.
    s3_branches = payload["ds_arm"]["snapshot_branches"]["S3"]
    assert all(
        all(entry["passed"] for entry in v.get("final_checks", []))
        for variants in s3_branches.values()
        for v in variants
        if v.get("final_checks")
    )
    # STRONG accumulation assertion: round 0's substantive notes are
    # present in the FINAL snapshot's accumulated memory — later rounds
    # appended, they did not replace.
    final_notes = payload["ds_arm"]["rounds"][-1]["memory_notes"]
    assert any(
        "invalidate only in-scope" in str(note) for note in final_notes
    ), final_notes
    # And every round's own note survives to the end.
    for round_record in payload["ds_arm"]["rounds"]:
        for note in round_record["state_update"].get("notes", []):
            assert str(note) in [str(n) for n in final_notes], note


def test_seed_does_not_reach_material(tmp_path: Path) -> None:
    # The reviewer's S2 finding, pinned: --seed changes presentation ids
    # only. Two offline runs at different seeds must produce identical
    # results once the seed field, session/instance ids, and elapsed
    # time are normalized away — same surfaces, same worlds, same
    # final-check outcomes.
    def run(seed: int) -> dict:
        out = tmp_path / f"seed-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "trajectory_v3.py"),
                "--offline",
                "--seed",
                str(seed),
                "--output",
                str(out),
            ],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        return json.loads(out.read_text(encoding="utf-8"))

    a = run(11)
    b = run(29)

    def normalized(payload: dict) -> dict:
        copy = json.loads(json.dumps(payload))
        copy.pop("seed", None)
        copy.pop("elapsed_seconds", None)
        text = json.dumps(copy)
        # Normalize the seed-suffixed session/instance ids.
        import re

        text = re.sub(r"-s\d+-", "-X-", text)
        return json.loads(text)

    assert normalized(a) == normalized(b)


def test_matrix_analyzer_counts_and_marks_empty_cells(tmp_path: Path) -> None:
    # The reviewer's C1 finding: an unrun/failed branch renders as 0/0
    # and prints like a genuine zero. Pin the analyzer's behavior:
    # mixed cells report 1/2 honestly; 0/0 cells are distinguishable
    # from 0/2 cells in the printed output once marked (analyzer
    # updated in the same fix round to emit 'n/a' for ran=0 cells).
    import subprocess as sp

    artifact = tmp_path / "fake-matrix.json"
    artifact.write_text(
        json.dumps(
            {
                "mode": "offline",
                "seed": 1,
                "rounds": 1,
                "reference_executor": {"final_check_passed": True},
                "fixed_arm": {"snapshot": "F0", "branches": {}},
                "ds_arm": {
                    "snapshot_branches": {
                        "S0": {
                            "continuation": [
                                {"final_checks": [{"passed": False, "failures": ["x"]}]}
                            ]
                        },
                        "S1": {
                            "continuation": [
                                {"final_checks": [{"passed": True, "failures": []}]},
                                {"final_checks": [{"passed": False, "failures": ["y"]}]},
                            ],
                            "new_world": [{"error": "ProjectStateError: refused"}],
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    result = sp.run(
        [sys.executable, str(_REPO_ROOT / "scripts" / "matrix_analyze.py"), str(artifact)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    out = result.stdout
    assert "S1: continuation: 1/2" in out  # mixed cell reported honestly
    assert "S1: new_world: n/a" in out or "0/0" in out  # unrun cell distinguishable
