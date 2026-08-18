#!/usr/bin/env python3
"""Run a visible-only autonomous 32K micro pilot; this is not a sealed claim."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
from pathlib import Path

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    dynamic_reader_output_limit,
)
from rsicontext.campaign.autonomous_dynamic import (
    DynamicReaderIdentity,
    run_autonomous_dynamic_pilot,
)
from rsicontext.eval import OpenAICompatibleReader
from rsicontext.experiment import load_api_profiles
from rsicontext.registry import load_registry, load_serving_profiles
from rsicontext.researcher import ProcessLimits


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="tencent-copilot-hy3-ioa")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--local-serving-profile")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8017/v1/chat/completions",
    )
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument(
        "--serving-profiles",
        type=Path,
        default=Path("configs/serving_profiles.json"),
    )
    parser.add_argument("--initial-policy", type=Path, default=Path("policy"))
    parser.add_argument("--researcher", choices=("codex", "claude"), default="codex")
    parser.add_argument("--researcher-executable")
    parser.add_argument("--researcher-model")
    parser.add_argument("--researcher-env", action="append", default=[])
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--dataset-seed", default="autonomous-dynamic-visible-v1")
    parser.add_argument("--items-per-profile", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--researcher-timeout-seconds", type=float, default=1800.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    serving_profile_id: str | None = None
    serving_profile_hash: str | None = None
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
        endpoint = args.endpoint
        api_key = None
        serving_profile_id = serving.id
        serving_profile_hash = serving.profile_hash
    else:
        profile = load_api_profiles(args.profiles).get(args.profile)
        endpoint = os.environ.get(profile.endpoint_env)
        api_key = os.environ.get(profile.api_key_env)
        if not endpoint:
            raise RuntimeError(f"missing endpoint environment variable: {profile.endpoint_env}")
        if not api_key:
            raise RuntimeError(f"missing API key environment variable: {profile.api_key_env}")
    executable = args.researcher_executable or shutil.which(args.researcher)
    if not executable:
        raise RuntimeError(f"researcher executable is unavailable: {args.researcher}")
    reader = OpenAICompatibleReader(
        endpoint=endpoint,
        model=profile.model,
        max_tokens=dynamic_reader_output_limit(profile),
        max_model_len=profile.evaluation_max_model_len,
        seed=profile.seed,
        stream=True,
        require_response_model=True,
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        allowed_hosts=(profile.allowed_host,),
        api_key=api_key,
    )
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=args.initial_policy,
        output_directory=args.output,
        reader=reader,
        researcher_kind=args.researcher,
        researcher_executable=executable,
        researcher_model=args.researcher_model,
        researcher_environment_allowlist=tuple(args.researcher_env),
        max_budget_usd=args.max_budget_usd,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        rounds=args.rounds,
        process_limits=ProcessLimits(timeout_seconds=args.researcher_timeout_seconds),
        reader_identity=DynamicReaderIdentity(
            profile_id=profile.id,
            profile_hash=profile.profile_hash,
            provider=profile.provider,
            requested_model=profile.model,
            provider_revision=profile.provider_revision,
            max_model_len=profile.evaluation_max_model_len,
            max_output_tokens=dynamic_reader_output_limit(profile),
            seed=profile.seed,
            temperature=profile.temperature,
            chat_template_enable_thinking=profile.chat_template_enable_thinking,
            serving_profile_id=serving_profile_id,
            serving_profile_hash=serving_profile_hash,
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
