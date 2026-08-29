#!/usr/bin/env python3
"""Run visible-only hard-context fixed baselines and evaluator instruments."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from rsicontext.campaign.hard_baseline_gate import (
    DEFAULT_HARD_DATASET_SEED,
    DEFAULT_HARD_PROFILES,
    run_hard_baseline_gate,
    write_hard_baseline_gate,
)
from rsicontext.datasets import HardTaskProfile
from rsicontext.experiment import load_api_profiles, resolve_api_endpoint


class _Tokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-seed", default=DEFAULT_HARD_DATASET_SEED)
    parser.add_argument("--items-per-profile", type=int, default=4)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--tokenizer-id", required=True)
    parser.add_argument(
        "--task-profile",
        action="append",
        choices=(
            HardTaskProfile.COMPOSITIONAL_MULTI_HOP.value,
            HardTaskProfile.DENSE_GLOBAL_COMPARISON.value,
            HardTaskProfile.TEMPORAL_STATE_RESOLUTION.value,
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    task_profiles: tuple[HardTaskProfile, ...] = (
        tuple(HardTaskProfile(value) for value in args.task_profile)
        if args.task_profile
        else DEFAULT_HARD_PROFILES
    )
    transformers = importlib.import_module("transformers")
    auto_tokenizer = transformers.AutoTokenizer
    tokenizer = cast(
        _Tokenizer,
        auto_tokenizer.from_pretrained(args.tokenizer_path, local_files_only=True),
    )

    def token_counter(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    typed_counter: Callable[[str], int] = token_counter
    result = run_hard_baseline_gate(
        profile,
        endpoint=endpoint.endpoint,
        api_key=endpoint.api_key,
        token_counter=typed_counter,
        tokenizer_id=args.tokenizer_id,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        task_profiles=task_profiles,
    )
    write_hard_baseline_gate(result, args.output)
    print(
        json.dumps(
            {
                "conditions": {
                    observation.condition_name: {
                        "gold_recall": observation.mean_gold_recall,
                        "role": observation.condition_role,
                        "score": observation.score,
                    }
                    for observation in result.conditions
                },
                "dataset_fingerprint": result.dataset_fingerprint,
                "difficulty_assessment": result.difficulty_assessment,
                "output": str(args.output),
                "qualification_only": result.qualification_only,
                "reader_calls": result.reader_calls,
                "split": result.split,
                "source_target_tokens": {
                    "min": result.source_target_tokens_min,
                    "max": result.source_target_tokens_max,
                },
                "tokenizer_id": result.tokenizer_id,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
