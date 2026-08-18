#!/usr/bin/env python3
"""Print an external-artifact acquisition plan without executing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.registry import build_download_plan, load_registry


def parse_args() -> argparse.Namespace:
    """Parse read-only planner arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="Registry ids; default is every entry")
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument("--destination", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    """Validate the manifest and emit a JSON dry-run plan."""
    args = parse_args()
    registry = load_registry(args.registry)
    selected = registry.select(args.ids or None)
    plan = build_download_plan(selected, args.destination)
    print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
