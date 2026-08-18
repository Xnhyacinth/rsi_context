#!/usr/bin/env python3
"""Visible-only public-cell RSI analog. Not a sealed A2 claim or official HELMET score."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
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
from rsicontext.eval import EvaluationItem, OpenAICompatibleReader, extractive_span_match
from rsicontext.experiment import load_api_profiles
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
        timeout_seconds=180.0,
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
        visible_items=items,
        dataset_fingerprint=fingerprint,
        scorer=extractive_span_match,
        rounds=args.rounds,
        budget=Budget(args.pack_tokens),
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
