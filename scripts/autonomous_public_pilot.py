#!/usr/bin/env python3
"""Visible-only public-cell RSI analog. Not a sealed A2 claim or official HELMET score."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    dynamic_reader_output_limit,
)
from rsicontext.campaign.autonomous_dynamic import (
    DynamicReaderIdentity,
    public_visible_items_fingerprint,
    run_autonomous_dynamic_pilot,
)
from rsicontext.datasets.helmet_rag import (
    EncodedWindowTokenizer,
    HelmetRagRecord,
    compile_helmet_rag,
    helmet_kilt_record,
    select_helmet_kilt_records,
    split_encoded_windows,
)
from rsicontext.eval import EvaluationItem, extractive_span_match
from rsicontext.experiment import build_profile_reader, load_api_profiles, resolve_api_endpoint
from rsicontext.policy import Budget
from rsicontext.registry import load_registry, load_serving_profiles
from rsicontext.researcher import ProcessLimits

_CELLS: dict[str, tuple[Path, str]] = {
    "helmet-rag-hotpot-k1000-to-8k": (
        Path("data/helmet-data/data/kilt/hotpotqa-dev-multikilt_1000_k1000_dep3.jsonl"),
        "hotpot-k1000",
    ),
    "helmet-rag-nq-k1000-to-8k": (
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k1000_dep6.jsonl"),
        "nq-k1000",
    ),
    "helmet-rag-popqa-k1000-to-8k": (
        Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl"),
        "popqa-k1000",
    ),
    "helmet-rag-trivia-k1000-to-8k": (
        Path("data/helmet-data/data/kilt/triviaqa-dev-multikilt_1000_k1000_dep6.jsonl"),
        "trivia-k1000",
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell", choices=tuple(_CELLS), default="helmet-rag-popqa-k1000-to-8k")
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--unique-queries", action="store_true", default=True)
    parser.add_argument("--no-unique-queries", action="store_false", dest="unique_queries")
    parser.add_argument("--min-gold-rank", type=int, default=200)
    parser.add_argument("--tokenizer-path", type=Path, default=Path("models/qwen3.6-27b"))
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
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--researcher-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--pack-tokens", type=int, default=8192)
    return parser


def _load_tokenizer(tokenizer_path: Path) -> EncodedWindowTokenizer:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(tokenizer_path),
        local_files_only=True,  # nosec B615
    )
    return cast(EncodedWindowTokenizer, tokenizer)


def _token_counter(tokenizer: EncodedWindowTokenizer) -> Callable[[str], int]:
    def counter(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    return counter


def _load_items(
    *,
    cell_id: str,
    limit: int,
    tokenizer: EncodedWindowTokenizer,
    unique_queries: bool,
    min_gold_rank: int,
) -> tuple[EvaluationItem, ...]:
    source, prefix = _CELLS[cell_id]
    counter = _token_counter(tokenizer)

    def split_parts(text: str) -> tuple[str, ...]:
        return split_encoded_windows(text, tokenizer, 512)

    def records() -> Iterator[HelmetRagRecord]:
        with source.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                yield helmet_kilt_record(json.loads(line), item_id=f"{prefix}-{index:04d}")

    selected = select_helmet_kilt_records(
        records(),
        limit=limit,
        unique_queries=unique_queries,
        min_gold_passage_index=min_gold_rank,
    )
    return tuple(
        compile_helmet_rag(record, token_counter=counter, split_parts=split_parts)
        for record in selected
    )


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
    tokenizer = _load_tokenizer(args.tokenizer_path)
    items = _load_items(
        cell_id=args.cell,
        limit=args.max_items,
        tokenizer=tokenizer,
        unique_queries=args.unique_queries,
        min_gold_rank=args.min_gold_rank,
    )
    fingerprint = public_visible_items_fingerprint(
        cell_id=f"{args.cell}-unique{int(args.unique_queries)}-minrank{args.min_gold_rank}",
        items=items,
        pack_budget_tokens=args.pack_tokens,
        scorer_name="extractive_span_match",
    )
    output_limit = dynamic_reader_output_limit(profile)
    reader = build_profile_reader(
        profile,
        endpoint,
        max_tokens=output_limit,
        timeout_seconds=180.0,
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
        visible_items=items,
        dataset_fingerprint=fingerprint,
        scorer=extractive_span_match,
        rounds=args.rounds,
        budget=Budget(args.pack_tokens),
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
                "cell_id": args.cell,
                "dataset_fingerprint": result.dataset_fingerprint,
                "formal_sealed_isolation": result.formal_sealed_isolation,
                "n_items": len(items),
                "official_helmet_score": False,
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
