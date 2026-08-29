#!/usr/bin/env python3
"""Run visible-only dynamic 32K baselines against a pinned local vLLM reader."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    run_api_dynamic_gate,
    write_api_dynamic_gate,
)
from rsicontext.registry import load_registry, load_serving_profiles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--serving-profile",
        default="qwen3.6-27b-128k-bf16-h200x8",
    )
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument(
        "--serving-profiles",
        type=Path,
        default=Path("configs/serving_profiles.json"),
    )
    parser.add_argument("--dataset-seed", default="api-dynamic-visible-v1")
    parser.add_argument("--items-per-profile", type=int, default=2)
    return parser


def main() -> int:
    args = _parser().parse_args()
    registry = load_registry(args.registry)
    serving = load_serving_profiles(args.serving_profiles, registry).get(args.serving_profile)
    model = next(entry for entry in registry.entries if entry.id == serving.model_id)
    profile = build_local_vllm_profile(
        serving,
        model,
        vllm_version=importlib.metadata.version("vllm"),
    )
    result = run_api_dynamic_gate(
        profile,
        endpoint=serving.chat_completions_endpoint,
        api_key=None,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        serving_profile_id=serving.id,
        serving_profile_hash=serving.profile_hash,
    )
    write_api_dynamic_gate(result, args.output)
    print(
        json.dumps(
            {
                "dataset_fingerprint": result.dataset_fingerprint,
                "output": str(args.output),
                "profile_hash": result.profile_hash,
                "reader_calls": result.reader_calls,
                "serving_profile_hash": result.serving_profile_hash,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
