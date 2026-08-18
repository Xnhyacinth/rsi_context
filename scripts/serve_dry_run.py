#!/usr/bin/env python3
"""Print one validated, hold-wrapped vLLM command without executing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.registry import build_serve_command, load_registry, load_serving_profiles


def parse_args() -> argparse.Namespace:
    """Parse dry-run profile selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument("--profiles", type=Path, default=Path("configs/serving_profiles.json"))
    parser.add_argument(
        "--hold-wrapper",
        type=Path,
        default=Path("/workspace/wynckeliao/ops/gpu/hold.sh"),
    )
    return parser.parse_args()


def main() -> int:
    """Validate references and print the command as JSON."""
    args = parse_args()
    registry = load_registry(args.registry)
    profiles = load_serving_profiles(args.profiles, registry)
    profile = profiles.get(args.profile)
    model = registry.select([profile.model_id])[0]
    output = {
        "command": build_serve_command(profile, model, hold_wrapper=args.hold_wrapper),
        "dry_run": True,
        "profile": profile.id,
        "profile_hash": profile.profile_hash,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
