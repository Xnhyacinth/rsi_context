#!/usr/bin/env python3
"""Replay one frozen candidate on visible dynamic items; not a sealed evaluation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    dynamic_reader_output_limit,
)
from rsicontext.campaign.autonomous_dynamic import DynamicReaderIdentity
from rsicontext.campaign.dynamic_replay import (
    run_dynamic_candidate_replay,
    write_dynamic_candidate_replay,
)
from rsicontext.experiment import build_profile_reader, load_api_profiles, resolve_api_endpoint
from rsicontext.registry import load_registry, load_serving_profiles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--entrypoint", default="policy.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="tencent-copilot-hy3-ioa")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--local-serving-profile")
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument(
        "--serving-profiles",
        type=Path,
        default=Path("configs/serving_profiles.json"),
    )
    parser.add_argument("--dataset-seed", default="autonomous-dynamic-visible-v1")
    parser.add_argument("--items-per-profile", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    return parser


def main() -> int:
    args = _parser().parse_args()
    serving = None
    if args.local_serving_profile:
        registry = load_registry(args.registry)
        serving = load_serving_profiles(args.serving_profiles, registry).get(
            args.local_serving_profile
        )
        model = next(entry for entry in registry.entries if entry.id == serving.model_id)
        profile = build_local_vllm_profile(
            serving,
            model,
            vllm_version=importlib.metadata.version("vllm"),
        )
        endpoint = resolve_api_endpoint(
            profile,
            endpoint=serving.chat_completions_endpoint,
            environ={},
        )
    else:
        profile = load_api_profiles(args.profiles).get(args.profile)
        endpoint = resolve_api_endpoint(profile)
    output_limit = dynamic_reader_output_limit(profile)
    reader = build_profile_reader(
        profile,
        endpoint,
        max_tokens=output_limit,
    )
    result = run_dynamic_candidate_replay(
        candidate_policy_directory=args.candidate,
        reader=reader,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        repeats=args.repeats,
        reader_identity=DynamicReaderIdentity.from_profile(
            profile,
            max_output_tokens=output_limit,
            serving_profile=serving,
        ),
        entrypoint=args.entrypoint,
    )
    write_dynamic_candidate_replay(result, args.output)
    print(
        json.dumps(
            {
                "candidate_sha256": result.candidate_sha256,
                "dataset_fingerprint": result.dataset_fingerprint,
                "output": str(args.output),
                "qualification_only": result.qualification_only,
                "reader_calls": result.reader_calls,
                "repeat_scores": [observation.score for observation in result.observations],
                "split": result.split,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
