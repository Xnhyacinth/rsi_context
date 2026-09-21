#!/usr/bin/env python3
"""Summarize replication-matrix artifacts: per-snapshot-per-surface pass rates.

Reads one or more trajectory_v3 --rounds artifacts and prints the cell
table: for each artifact, seed, snapshot (S0..SN / F0), and surface
(main / variants), the pass rate over recorded final_checks. Honest
caveats printed with the table: variant surfaces are ONE parent world
pair, cells within a snapshot share the run's history, and at this
matrix size the numbers are screens-with-repetition, not powered
estimates — the table exists to make variance VISIBLE, not to claim
significance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _cell_pass(variant: dict) -> bool | None:
    checks = variant.get("final_checks", [])
    if not checks:
        return None
    return all(entry["passed"] for entry in checks)


def summarize(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    label = payload.get("mode"), payload.get("seed"), payload.get("rounds")
    print(f"\n=== {path.name} (mode={label[0]} seed={label[1]} rounds={label[2]}) ===")
    arm = payload["ds_arm"]
    fixed = payload["fixed_arm"]

    def table(name: str, branches: dict) -> None:
        rows: list[tuple[str, int, int]] = []
        for branch in ("continuation", "new_world", "regression"):
            variants = branches.get(branch, [])
            passed = sum(1 for v in variants if _cell_pass(v) is True)
            ran = sum(1 for v in variants if _cell_pass(v) is not None)
            rows.append((branch, passed, ran))
        joined = " | ".join(f"{b}: {p}/{r}" for b, p, r in rows)
        crashes = sum(
            1
            for variants in (
                branches.get(b, []) for b in ("continuation", "new_world", "regression")
            )
            for v in variants
            if v.get("strategy_errors")
        )
        print(f"  {name}: {joined}" + (f" | strategy-crashes: {crashes}" if crashes else ""))

    table("F0 (fixed)", fixed["branches"])
    snapshot_branches = arm.get("snapshot_branches")
    if snapshot_branches is None:
        # Legacy single-round shape: s0_branches / s1_branches.
        snapshot_branches = {}
        if "s0_branches" in arm:
            snapshot_branches["S0"] = arm["s0_branches"]
        if "s1_branches" in arm:
            snapshot_branches["S1"] = arm["s1_branches"]
    for snapshot_id in sorted(snapshot_branches, key=_snapshot_order):
        table(snapshot_id, snapshot_branches[snapshot_id])
    rounds = arm.get("rounds")
    if rounds is None:
        improvement = arm.get("improvement", {})
        rr = improvement.get("researcher_record")
        if rr:
            print(f"  round 0: {rr.get('round_outcome', 'n/a')}")
    else:
        for round_record in rounds:
            rr = round_record.get("researcher_record")
            if rr:
                print(f"  round {round_record['round']}: {rr.get('round_outcome', 'n/a')}")


def _snapshot_order(snapshot_id: str) -> tuple[int, str]:
    if snapshot_id == "F0":
        return (-1, snapshot_id)
    digits = "".join(ch for ch in snapshot_id if ch.isdigit()) or "0"
    return (int(digits), snapshot_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.artifacts:
        summarize(path)
    print(
        "\nCaveats: variant surfaces = one parent world pair; cells within a "
        "snapshot share the run's history; at this size these are "
        "screens-with-repetition — variance is made visible, not estimated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
