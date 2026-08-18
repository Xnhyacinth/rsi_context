#!/usr/bin/env python3
"""Run and persist an API reader length/position replay gate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import cast

from rsicontext.experiment import load_api_profiles
from rsicontext.experiment.api_length import (
    LengthPosition,
    run_api_length_canary,
    write_api_length_canary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lengths", nargs="+", type=int, default=(8_192, 32_768))
    parser.add_argument(
        "--positions",
        nargs="+",
        choices=("front", "middle", "tail"),
        default=("front", "middle", "tail"),
    )
    parser.add_argument("--repetitions", type=int, default=3)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = os.environ.get(profile.endpoint_env)
    api_key = os.environ.get(profile.api_key_env)
    if not endpoint:
        raise RuntimeError(f"missing endpoint environment variable: {profile.endpoint_env}")
    if not api_key:
        raise RuntimeError(f"missing API key environment variable: {profile.api_key_env}")
    positions = cast(tuple[LengthPosition, ...], tuple(args.positions))
    result = run_api_length_canary(
        profile,
        endpoint=endpoint,
        api_key=api_key,
        target_lengths=tuple(args.lengths),
        positions=positions,
        repetitions=args.repetitions,
    )
    write_api_length_canary(result, args.output)
    cells = [
        {
            "accuracy": summary.accuracy,
            "answer_stable": summary.answer_stable,
            "input_tokens_mean": summary.input_tokens_mean,
            "latency_mean_seconds": summary.latency_mean_seconds,
            "position": summary.position,
            "score_standard_deviation": summary.score_standard_deviation,
            "target_tokens": summary.target_tokens,
            "usage_stable": summary.usage_stable,
        }
        for summary in result.summaries
    ]
    passed = all(
        cell.accuracy == 1.0
        and cell.score_standard_deviation == 0.0
        and cell.answer_stable
        and cell.usage_stable
        for cell in result.summaries
    )
    print(
        json.dumps(
            {"cells": cells, "output": str(args.output), "passed": passed},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
