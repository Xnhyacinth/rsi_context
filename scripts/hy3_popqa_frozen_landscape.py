#!/usr/bin/env python3
"""Frozen open-S H0 vs head vs handwritten PopQA landscape. Qualification only."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_SPEC_V1
from rsicontext.campaign.autonomous_dynamic import public_visible_items_fingerprint
from rsicontext.datasets import load_helmet_kilt_items
from rsicontext.eval import AuditedPolicyBundle, FreshProcessPolicyFactory, extractive_span_match
from rsicontext.experiment import build_profile_reader, load_api_profiles, resolve_api_endpoint
from rsicontext.experiment.frozen_policy_landscape import (
    build_interleaved_schedule,
    run_frozen_policy_landscape,
)
from rsicontext.experiment.hy3_popqa import (
    POPQA_SOURCE,
    POPQA_SOURCE_SHA256,
    QWEN_TOKENIZER,
    QWEN_TOKENIZER_FILES,
    QWEN_TOKENIZER_REVISION,
    load_qwen_tokenizer,
    source_token_summary,
)
from rsicontext.experiment.offline_provenance import file_sha256
from rsicontext.open_s import repository_open_s_seed
from rsicontext.policy import Budget, ContextPolicy, PolicySpecV1Interpreter, TruncationPolicy
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_PRIOR_PANEL = 40
_ITEM_COUNT = 16
_MIN_GOLD_RANK = 200
_PACK_TOKENS = 8_192
_OUTPUT_TOKENS = 64
_SCHEDULE_SEED = 20260901
_POLICY_NAMES = ("open-s-h0", "head", "head-tail", "hand-hybrid")
_PROFILE_ID = "tencent-copilot-hy3-ioa"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=POPQA_SOURCE)
    parser.add_argument("--tokenizer-path", type=Path, default=QWEN_TOKENIZER)
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--profile", default=_PROFILE_ID)
    parser.add_argument("--open-s-seed", type=Path, default=None)
    parser.add_argument("--offset", type=int, default=_PRIOR_PANEL)
    parser.add_argument("--max-items", type=int, default=_ITEM_COUNT)
    return parser


def _open_s_factory(seed: Path) -> FreshProcessPolicyFactory:
    bundle = AuditedPolicyBundle.from_directory(seed, entrypoint="policy.py")
    return FreshProcessPolicyFactory(bundle, timeout_seconds=120.0)


def main() -> int:
    args = _parser().parse_args()
    if args.output.exists():
        raise FileExistsError(f"landscape output already exists: {args.output}")
    if not os.environ.get("COPILOT_API_KEY") or not os.environ.get("COPILOT_BASE_URL"):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "qualification_only": True,
            "reason": "credentials_missing",
            "rsi_launch_eligible": False,
        }
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    source_sha = file_sha256(args.source)
    if source_sha != POPQA_SOURCE_SHA256:
        raise RuntimeError("PopQA source bytes do not match the pinned SHA-256")
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, QWEN_TOKENIZER_FILES)
    tokenizer = load_qwen_tokenizer(args.tokenizer_path)
    items = load_helmet_kilt_items(
        args.source,
        item_prefix="popqa",
        limit=args.max_items,
        tokenizer=tokenizer,
        unique_queries=True,
        min_gold_passage_index=_MIN_GOLD_RANK,
        offset=args.offset,
    )
    seed = args.open_s_seed or repository_open_s_seed()
    factories: dict[str, Callable[[], ContextPolicy]] = {
        "open-s-h0": _open_s_factory(seed),
        "head": lambda: TruncationPolicy("head"),
        "head-tail": lambda: TruncationPolicy("head_tail"),
        "hand-hybrid": lambda: PolicySpecV1Interpreter().materialize(HAND_HYBRID_SPEC_V1),
    }
    schedule = build_interleaved_schedule(
        tuple(item.item_id for item in items),
        _POLICY_NAMES,
        seed=_SCHEDULE_SEED,
    )
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    reader = build_profile_reader(
        profile,
        endpoint,
        max_tokens=_OUTPUT_TOKENS,
        timeout_seconds=180.0,
    )
    result = run_frozen_policy_landscape(
        items=items,
        factories=factories,
        reader=reader,
        scorer=extractive_span_match,
        budget=Budget(_PACK_TOKENS),
        schedule=schedule,
    )
    tokenizer_id = f"{QWEN_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"
    fingerprint = public_visible_items_fingerprint(
        cell_id=(
            f"helmet-rag-popqa-k1000-to-8k-unique1-minrank{_MIN_GOLD_RANK}"
            f"-offset{args.offset}-n{args.max_items}"
        ),
        items=items,
        pack_budget_tokens=_PACK_TOKENS,
        scorer_name="extractive_span_match",
        token_axis_id=tokenizer_id,
    )
    payload = {
        **result.to_dict(),
        "dataset_fingerprint": fingerprint,
        "offset": args.offset,
        "open_s_seed": str(seed),
        "pack_tokens": _PACK_TOKENS,
        "profile_id": profile.id,
        "reader_max_output_tokens": _OUTPUT_TOKENS,
        "schedule_seed": _SCHEDULE_SEED,
        "source_sha256": source_sha,
        "source_tokens": source_token_summary(items),
        "tokenizer_id": tokenizer_id,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
