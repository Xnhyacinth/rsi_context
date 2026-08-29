#!/usr/bin/env python3
"""Run and persist a credential-free repeated canary for an API reader profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.experiment import (
    load_api_profiles,
    resolve_api_endpoint,
    run_api_canary,
    write_api_canary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    result = run_api_canary(
        profile,
        endpoint=endpoint.endpoint,
        api_key=endpoint.api_key,
        repetitions=args.repetitions,
    )
    write_api_canary(result, args.output)
    summary = {
        "answer_correct": result.answer_correct,
        "answer_stable": result.answer_stable,
        "output": str(args.output),
        "profile_hash": result.profile_hash,
        "requested_model": result.requested_model,
        "unobservable_runtime_fields": result.unobservable_runtime_fields,
        "usage_stable": result.usage_stable,
        "version_pinned": result.version_pinned,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.answer_correct and result.answer_stable and result.usage_stable else 2


if __name__ == "__main__":
    raise SystemExit(main())
