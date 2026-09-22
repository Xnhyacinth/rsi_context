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
    vf = payload.get("variance_floor")
    if isinstance(vf, dict):
        print(
            f"  variance-floor[{vf.get('cell')}]: repeats={vf.get('repeats')} "
            f"sd={vf.get('sd')} flip={vf.get('flip_rate')} "
            f"within_ceiling={vf.get('within_ceiling')}"
        )
    av = payload.get("author_variance")
    if isinstance(av, dict):
        print(
            f"  author-variance: repeats={av.get('repeats')} scores={av.get('variant_scores')} "
            f"sd={av.get('sd')} flip={av.get('flip_rate')}"
        )
        for variant in av.get("variants", []):
            if isinstance(variant, dict):
                print(
                    f"    draw {variant.get('repeat')}: {variant.get('outcome')} "
                    f"score={variant.get('score')}"
                )
    failed = payload.get("failed_rounds")
    if failed:
        print(f"  FAILED ROUNDS: {failed}")

    def table(name: str, branches: dict) -> None:
        rows: list[tuple[str, str]] = []
        gate_counts: list[int] = []
        for branch in ("continuation", "new_world", "regression"):
            variants = branches.get(branch, [])
            passed = sum(1 for v in variants if _cell_pass(v) is True)
            ran = sum(1 for v in variants if _cell_pass(v) is not None)
            expected = len(variants)
            for variant in variants:
                counts = variant.get("gate_failure_counts")
                if isinstance(counts, list):
                    gate_counts.extend(count for count in counts if isinstance(count, int))
            # An unrun/failed cell set is n/a, never 0/N: a wiring
            # failure must not read as "nothing passed" (code-review C1).
            if expected and not ran:
                rows.append((branch, "n/a"))
            elif expected and ran != expected:
                rows.append((branch, f"{passed}/{ran} of {expected}"))
            else:
                rows.append((branch, f"{passed}/{ran}"))
        joined = " | ".join(f"{b}: {c}" for b, c in rows)
        graded = f" | gate-failures: {sum(gate_counts)}" if gate_counts else ""
        crashes = sum(
            1
            for variants in (
                branches.get(b, []) for b in ("continuation", "new_world", "regression")
            )
            for v in variants
            if v.get("strategy_errors")
        )
        print(
            f"  {name}: {joined}{graded}" + (f" | strategy-crashes: {crashes}" if crashes else "")
        )

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
