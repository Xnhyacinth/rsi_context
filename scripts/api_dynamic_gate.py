#!/usr/bin/env python3
"""Run visible-only dynamic 32K fixed baselines against an API reader."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.campaign.api_dynamic_gate import (
    run_api_dynamic_gate,
    write_api_dynamic_gate,
)
from rsicontext.experiment import load_api_profiles, resolve_api_endpoint


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-seed", default="api-dynamic-visible-v1")
    parser.add_argument("--items-per-profile", type=int, default=2)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    result = run_api_dynamic_gate(
        profile,
        endpoint=endpoint.endpoint,
        api_key=endpoint.api_key,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
    )
    write_api_dynamic_gate(result, args.output)
    policies = {
        observation.policy_name: {
            profile_result.task_profile: {
                "gold_recall": profile_result.mean_gold_recall,
                "score": profile_result.score,
            }
            for profile_result in observation.profiles
        }
        for observation in result.policies
    }
    print(
        json.dumps(
            {
                "dataset_fingerprint": result.dataset_fingerprint,
                "output": str(args.output),
                "policies": policies,
                "qualification_only": result.qualification_only,
                "reader_calls": result.reader_calls,
                "split": result.split,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
