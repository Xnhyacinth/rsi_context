#!/usr/bin/env python3
"""Run a visible-only autonomous 32K micro pilot; this is not a sealed claim."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    dynamic_reader_output_limit,
)
from rsicontext.campaign.autonomous_dynamic import (
    DynamicReaderIdentity,
    run_autonomous_dynamic_pilot,
)
from rsicontext.experiment import build_profile_reader, load_api_profiles, resolve_api_endpoint
from rsicontext.registry import load_registry, load_serving_profiles
from rsicontext.researcher import ProcessLimits


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--initial-policy", type=Path, default=Path("policy"))
    parser.add_argument("--researcher", choices=("api", "codex", "claude"), default="api")
    parser.add_argument("--researcher-executable")
    parser.add_argument("--researcher-model")
    parser.add_argument(
        "--researcher-profile",
        default="tencent-copilot-hy3-ioa-researcher",
    )
    parser.add_argument("--researcher-env", action="append", default=[])
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--dataset-seed", default="autonomous-dynamic-visible-v1")
    parser.add_argument("--items-per-profile", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--researcher-timeout-seconds", type=float, default=1800.0)
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
    researcher_profile = None
    researcher_endpoint_sha256 = None
    researcher_environment = tuple(args.researcher_env)
    researcher_model = args.researcher_model
    if args.researcher == "api":
        if args.researcher_env:
            raise ValueError("API researcher environment is fixed by its profile")
        if args.max_budget_usd is not None:
            raise ValueError("API researcher does not accept a CLI dollar budget")
        researcher_profile = load_api_profiles(args.profiles).get(args.researcher_profile)
        researcher_endpoint = resolve_api_endpoint(researcher_profile)
        researcher_endpoint_sha256 = hashlib.sha256(
            researcher_endpoint.endpoint.encode()
        ).hexdigest()
        researcher_environment = (
            researcher_profile.endpoint_env,
            researcher_profile.api_key_env,
        )
        researcher_model = researcher_model or researcher_profile.model
    executable = args.researcher_executable or (
        sys.executable if args.researcher == "api" else shutil.which(args.researcher)
    )
    if not executable:
        raise RuntimeError(f"researcher executable is unavailable: {args.researcher}")
    output_limit = dynamic_reader_output_limit(profile)
    reader = build_profile_reader(
        profile,
        endpoint,
        max_tokens=output_limit,
    )
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=args.initial_policy,
        output_directory=args.output,
        reader=reader,
        researcher_kind=args.researcher,
        researcher_executable=executable,
        researcher_model=researcher_model,
        researcher_environment_allowlist=researcher_environment,
        researcher_api_profiles_path=args.profiles if researcher_profile is not None else None,
        researcher_api_profile_id=(
            researcher_profile.id if researcher_profile is not None else None
        ),
        researcher_endpoint_sha256=researcher_endpoint_sha256,
        max_budget_usd=args.max_budget_usd,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        rounds=args.rounds,
        process_limits=ProcessLimits(timeout_seconds=args.researcher_timeout_seconds),
        reader_identity=DynamicReaderIdentity.from_profile(
            profile,
            max_output_tokens=output_limit,
            serving_profile=serving,
        ),
    )
    print(
        json.dumps(
            {
                "artifact_summary": result.to_dict()["artifact_summary"],
                "baseline_score": result.baseline_score,
                "output": str(args.output),
                "qualification_only": result.qualification_only,
                "reader_calls": result.reader_calls,
                "researcher": args.researcher,
                "round_scores": [round_.score for round_ in result.campaign.rounds],
                "split": result.split,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
