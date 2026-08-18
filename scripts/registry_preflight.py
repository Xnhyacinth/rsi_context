#!/usr/bin/env python3
"""Run read-only host checks for selected registry artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.registry import build_download_plan, load_registry, run_preflight


def parse_args() -> argparse.Namespace:
    """Parse preflight arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="Registry ids; default is every entry")
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument("--destination", type=Path, default=Path.cwd())
    parser.add_argument("--expected-gpus", type=int, default=8)
    parser.add_argument("--expected-gpu-name", default="H200")
    parser.add_argument("--reserve-bytes", type=int, default=0)
    parser.add_argument(
        "--hold-wrapper",
        type=Path,
        default=Path("/workspace/wynckeliao/ops/gpu/hold.sh"),
    )
    return parser.parse_args()


def main() -> int:
    """Print observations without changing GPU hold state or the filesystem."""
    args = parse_args()
    registry = load_registry(args.registry)
    selected = registry.select(args.ids or None)
    plan = build_download_plan(selected, args.destination)
    report = run_preflight(
        args.destination,
        required_bytes=plan.known_size_bytes + args.reserve_bytes,
        expected_gpus=args.expected_gpus,
        expected_gpu_name=args.expected_gpu_name,
        hf_auth_required=any(entry.access == "gated" for entry in selected),
        hold_wrapper=args.hold_wrapper,
    )
    output = report.as_dict()
    output["unknown_size_count"] = plan.unknown_size_count
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
