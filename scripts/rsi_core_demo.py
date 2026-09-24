#!/usr/bin/env python3
"""RSI core v1 demo — the policy-surface arms over the CALIBRATION pool.

Runs the strong-fixed baseline policy (on_turn surface, metered tools,
receipt-driven) across the main + authored-variant + Option-2 worlds,
next to the reference executor, and reports per-world outcomes with
world identity + tool ledgers. This is the Part 5.6 offline end-to-end:
it demonstrates the closed loop (act -> receipts -> react) works on
real worlds, and pins the honest-control baseline's floor.

Run from the repo root:
    .venv/bin/python scripts/rsi_core_demo.py [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.material_v3_segment import build_option2_world
from rsicontext.lifecycle.material_v3_variant import build_research_v3_variant
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.strong_fixed_policy import strong_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget

# The calibration pool: main + 2 authored variants + 6 Option-2 worlds.
_WORLDS: list[tuple[str, Callable[[], LifecycleInstance]]] = [
    ("main", build_research_v3_instance),
    ("orinoco", lambda: build_research_v3_variant("orinoco")),
    ("parana", lambda: build_research_v3_variant("parana")),
    *[
        (wid, lambda wid=wid: build_option2_world(wid))
        for wid in ("zephyr", "quill", "atlas", "lumen", "swift", "mirror")
    ],
]


def _world_identity(inst: LifecycleInstance) -> dict[str, str]:
    import hashlib

    payload = [stage.to_dict() for stage in inst.stages]
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "instance_id": inst.instance_id,
        "family": inst.family,
        "material_sha256": hashlib.sha256(blob).hexdigest()[:16],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/demo-offline.json"),
    )
    args = parser.parse_args()
    started = time.monotonic()

    rows: list[dict[str, object]] = []
    total_tool_calls = 0
    for world_id, build in _WORLDS:
        inst = build()
        env = ProjectState()
        budget = ToolBudget()
        hook = PolicyHook({}, strong_fixed_policy_text(), tool_budget=budget)
        hook.bind_env(env)
        record = run_lifecycle(inst, hook, env)
        tool_ledger = budget.ledger()
        tool_calls = tool_ledger["tool_calls"]
        assert isinstance(tool_calls, int)
        total_tool_calls += tool_calls
        rows.append(
            {
                "world": world_id,
                "identity": _world_identity(inst),
                "passed": record.final_check.passed,
                "failures": list(record.final_check.failures)[:6],
                "policy_errors": list(hook.policy_errors),
                "tool_ledger": tool_ledger,
            }
        )

    payload = {
        "mode": "offline",
        "surface": "policy-v1 (on_turn + tools + receipts)",
        "arm": "strong-fixed (competent, static — never updates)",
        "worlds": rows,
        "summary": {
            "passed": sum(1 for row in rows if row["passed"]),
            "total": len(rows),
            "tool_calls": total_tool_calls,
        },
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(json.dumps(payload["summary"], indent=1))
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
