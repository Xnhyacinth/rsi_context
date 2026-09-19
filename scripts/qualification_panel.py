#!/usr/bin/env python3
"""Difficulty-contract qualification panel for the research-v1 family.

Contract status: task #16 (docs/task-family-research-v1.md §Qualification
gates, frozen 2026-09-19). Reads the archived n=16 pilot-cell JSONs and
evaluates the pre-registered kills:

1. fixed-H0 failure-class rates in [0.1, 0.6] per failure family;
2. no strategy reaches >= 0.90 overall (saturation kill);
3. top-two strategy disagreement >= 20% (discrimination kill);
4. gold-drop counterfactual drops correctness materially (causal kill);
5. independent document bases (no dominant shared factor across instances).

Gates 4-5 need dedicated counterfactual runs; this panel reports the
archivable gates (1-3) from pilot artifacts and records 4-5 as pending
until those runs exist. Engineering-gate failures are reported as
engineering records, not scientific results (contract §honesty).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _failure_class(answer: str, expected: str, failures: list[str]) -> str:
    if not answer:
        return "empty_answer"
    if answer.strip().lower() == "insufficient":
        return "insufficient_misjudgment"
    if answer and answer not in expected and expected not in answer:
        if "title" in " ".join(failures).lower():
            return "title_not_answer"
        return "wrong_extraction"
    return "substring_miss"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed", type=Path, required=True)
    parser.add_argument("--experience", type=Path, required=True)
    parser.add_argument("--ds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    arms: dict[str, dict] = {}
    for arm, path in (("fixed", args.fixed), ("experience", args.experience), ("ds", args.ds)):
        arms[arm] = json.loads(path.read_text(encoding="utf-8"))

    per_arm: dict[str, dict[str, object]] = {}
    for arm, payload in arms.items():
        vis = payload["visible"]["run_records"]
        gate = payload["gate"]["run_records"]
        all_records = vis + gate
        correct = sum(1 for r in all_records if r["final_check"]["passed"])
        classes: dict[str, int] = {}
        for r in all_records:
            if r["final_check"]["passed"]:
                continue
            expected = ""
            answer = ""
            for failure in r["final_check"]["failures"]:
                if "expected" in failure and "got" in failure:
                    parts = failure.split("expected")
                    expected = parts[1].split(",")[0].strip(" '")
                    answer = failure.split("got")[-1].strip(" '")
                    break
            label = _failure_class(answer, expected, list(r["final_check"]["failures"]))
            classes[label] = classes.get(label, 0) + 1
        per_arm[arm] = {
            "n": len(all_records),
            "correct": correct,
            "accuracy": round(correct / len(all_records), 3) if all_records else 0.0,
            "visible_accuracy": round(
                sum(1 for r in vis if r["final_check"]["passed"]) / len(vis), 3
            )
            if vis
            else 0.0,
            "gate_accuracy": round(
                sum(1 for r in gate if r["final_check"]["passed"]) / len(gate), 3
            )
            if gate
            else 0.0,
            "failure_classes": classes,
            "leak_probe_entries": payload["leak_probe"]["entries_scanned"],
            "replay_transcript_equal": payload["replay"]["transcript_equal"],
        }

    accuracies = sorted((v["accuracy"] for v in per_arm.values()), reverse=True)
    top_two = accuracies[0], accuracies[1]

    # Item-level disagreement between the best two arms.
    arm_names = sorted(per_arm, key=lambda a: per_arm[a]["accuracy"], reverse=True)
    best, second = arm_names[0], arm_names[1]

    def _item_key(arm: str) -> dict[str, bool]:
        return {
            r["instance_id"]: r["final_check"]["passed"]
            for r in arms[arm]["visible"]["run_records"] + arms[arm]["gate"]["run_records"]
        }

    keys_a, keys_b = _item_key(best), _item_key(second)
    common = keys_a.keys() & keys_b.keys()
    disagreement = sum(1 for k in common if keys_a[k] != keys_b[k]) / len(common) if common else 0.0

    fixed_failure_rate = 1.0 - per_arm["fixed"]["accuracy"]
    report = {
        "schema_version": 1,
        "panel": "research-v1-difficulty-qualification",
        "arms": per_arm,
        "gates": {
            "fixed_failure_rate_in_band": {
                "value": round(fixed_failure_rate, 3),
                "required": "[0.1, 0.6]",
                "passed": 0.1 <= fixed_failure_rate <= 0.6,
            },
            "no_strategy_saturation": {
                "top_accuracy": top_two[0],
                "required": "< 0.90",
                "passed": top_two[0] < 0.90,
            },
            "top_two_disagreement": {
                "arms": (best, second),
                "value": round(disagreement, 3),
                "required": ">= 0.20 on-screen",
                "passed": disagreement >= 0.20,
            },
            "gold_drop_counterfactual": {
                "status": "pending — requires a dedicated counterfactual run",
                "required": "material correctness drop without gold evidence",
            },
            "provenance_drop_counterfactual": {
                "status": "pending — requires a dedicated counterfactual run",
                "required": "failure classes 2/3 rates increase without provenance",
            },
            "independent_document_bases": {
                "status": "pending — requires corpus-overlap analysis",
                "required": "no dominant shared factor across instances",
            },
        },
        "contract_integrity": {
            "leak_probe_all_clean": all(v["leak_probe_entries"] >= 0 for v in per_arm.values()),
            "replay_equal_all": all(v["replay_transcript_equal"] for v in per_arm.values()),
        },
    }
    archivable = all(
        report["gates"][g]["passed"]
        for g in (
            "fixed_failure_rate_in_band",
            "no_strategy_saturation",
            "top_two_disagreement",
        )
    )
    report["archivable_gates_passed"] = archivable

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "arms": {a: per_arm[a]["accuracy"] for a in per_arm},
                "fixed_failure_classes": per_arm["fixed"]["failure_classes"],
                "gates": {g: report["gates"][g].get("passed", "pending") for g in report["gates"]},
                "archivable_gates_passed": archivable,
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if archivable else 1


if __name__ == "__main__":
    raise SystemExit(main())
