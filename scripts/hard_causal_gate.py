#!/usr/bin/env python3
"""Run the visible-only hard-context causal and replay qualification."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from rsicontext.campaign.hard_baseline_gate import DEFAULT_HARD_PROFILES
from rsicontext.campaign.hard_causal_gate import (
    DEFAULT_CAUSAL_DATASET_SEED,
    DEFAULT_REPLAY_REPEATS,
    run_hard_causal_gate,
    write_hard_causal_gate,
)
from rsicontext.datasets import HardTaskProfile
from rsicontext.experiment import load_api_profiles


class _Tokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-seed", default=DEFAULT_CAUSAL_DATASET_SEED)
    parser.add_argument("--items-per-profile", type=int, default=16)
    parser.add_argument("--replay-repeats", type=int, default=DEFAULT_REPLAY_REPEATS)
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
    endpoint = os.environ.get(profile.endpoint_env)
    api_key = os.environ.get(profile.api_key_env)
    if not endpoint:
        raise RuntimeError(f"missing endpoint environment variable: {profile.endpoint_env}")
    if not api_key:
        raise RuntimeError(f"missing API key environment variable: {profile.api_key_env}")
    task_profiles: tuple[HardTaskProfile, ...] = (
        tuple(HardTaskProfile(value) for value in args.task_profile)
        if args.task_profile
        else DEFAULT_HARD_PROFILES
    )
    transformers = importlib.import_module("transformers")
    tokenizer = cast(
        _Tokenizer,
        transformers.AutoTokenizer.from_pretrained(
            args.tokenizer_path,
            local_files_only=True,  # nosec B615
        ),
    )

    def token_counter(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    typed_counter: Callable[[str], int] = token_counter
    result = run_hard_causal_gate(
        profile,
        endpoint=endpoint,
        api_key=api_key,
        token_counter=typed_counter,
        tokenizer_id=args.tokenizer_id,
        dataset_seed=args.dataset_seed,
        items_per_profile=args.items_per_profile,
        task_profiles=task_profiles,
        replay_repeats=args.replay_repeats,
    )
    write_hard_causal_gate(result, args.output)
    print(
        json.dumps(
            {
                "counterfactual_following": result.counterfactual_following,
                "dataset_fingerprint": result.dataset_fingerprint,
                "difficulty_assessment": result.difficulty_assessment,
                "gold_drop_decrease": result.gold_drop_decrease,
                "output": str(args.output),
                "qualification_only": result.qualification_only,
                "reader_calls": result.reader_calls,
                "replay_policy": result.replay.policy_name,
                "replay_standard_deviation": result.replay.standard_deviation,
                "split": result.split,
                "strongest_non_oracle_policies": result.strongest_non_oracle_policies,
                "strongest_policy_item_disagreement": (result.strongest_policy_item_disagreement),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
