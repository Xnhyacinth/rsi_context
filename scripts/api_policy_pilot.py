#!/usr/bin/env python3
"""Run and persist a small API-backed context-policy qualification trajectory."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rsicontext.campaign import run_api_policy_pilot, write_api_policy_pilot
from rsicontext.experiment import load_api_profiles, resolve_api_endpoint


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    result = run_api_policy_pilot(
        profile,
        endpoint=endpoint.endpoint,
        api_key=endpoint.api_key,
    )
    write_api_policy_pilot(result, args.output)
    scores = {observation.policy_name: observation.score for observation in result.policies}
    passed = (
        scores["lexical-8k"] > scores["head-8k"]
        and scores["lexical-8k"] > scores["tail-8k"]
        and result.replay.standard_deviation == 0.0
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "passed": passed,
                "qualification_only": result.qualification_only,
                "replay_standard_deviation": result.replay.standard_deviation,
                "scores": scores,
                "trajectory": asdict(result.trajectory),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
