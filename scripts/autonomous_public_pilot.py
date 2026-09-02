#!/usr/bin/env python3
"""Visible-only public-cell RSI analog. Not a sealed A2 claim or official HELMET score."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
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
from rsicontext.campaign.loop import (
    FEEDBACK_SCORE_COST,
    FEEDBACK_SCORE_ONLY,
    FEEDBACK_VISIBLE_GOLD,
    LINEAGE_FROM_SEED,
    LINEAGE_LAST_VALID,
    SEARCH_NORMAL,
    SEARCH_SELECTION_BLIND,
)
from rsicontext.datasets.helmet_rag import (
    EncodedWindowTokenizer,
    load_helmet_kilt_items,
)
from rsicontext.eval import EvaluationItem, extractive_span_match
from rsicontext.experiment import build_profile_reader, load_api_profiles, resolve_api_endpoint
from rsicontext.open_s import (
    OPEN_S_VISIBLE_CELL_ID,
    OPEN_S_VISIBLE_FEEDBACK_SCHEMA,
    OPEN_S_VISIBLE_ITEM_OFFSET,
    OPEN_S_VISIBLE_MAX_ITEMS,
    OPEN_S_VISIBLE_MIN_GOLD_RANK,
    OPEN_S_VISIBLE_PACK_ENVELOPE,
    OPEN_S_VISIBLE_READER_OUTPUT_TOKENS,
    OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS,
    OPEN_S_VISIBLE_ROUNDS,
    OPEN_S_VISIBLE_SEARCH_MODE,
    PACK_ENVELOPE_READER_WINDOW,
    PACK_ENVELOPE_SELECTION_BINDING,
    resolve_pack_budget_tokens,
)
from rsicontext.policy import Budget
from rsicontext.registry import load_registry, load_serving_profiles
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot
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
_TOKENIZER_REVISION = "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
_TOKENIZER_FILES = (
    (
        "merges.txt",
        "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
    ),
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
    ("vocab.json", "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"),
)
_TOKENIZER_CLASS = "transformers.models.qwen2.tokenization_qwen2.Qwen2Tokenizer"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell", choices=tuple(_CELLS), default=OPEN_S_VISIBLE_CELL_ID)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--unique-queries", action="store_true", default=True)
    parser.add_argument("--no-unique-queries", action="store_false", dest="unique_queries")
    parser.add_argument("--min-gold-rank", type=int, default=None)
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
    parser.add_argument(
        "--policy-track",
        choices=("restricted", "open-s"),
        default="restricted",
    )
    parser.add_argument("--item-offset", type=int, default=None)
    parser.add_argument("--reader-max-output-tokens", type=int)
    parser.add_argument("--reader-timeout-seconds", type=float)
    parser.add_argument("--researcher", choices=("api", "codex", "claude"), default="api")
    parser.add_argument("--researcher-executable")
    parser.add_argument("--researcher-model")
    parser.add_argument(
        "--researcher-profile",
        default="tencent-copilot-hy3-ioa-researcher",
    )
    parser.add_argument("--researcher-env", action="append", default=[])
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--researcher-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--pack-tokens", type=int, default=None)
    parser.add_argument(
        "--pack-envelope",
        choices=(PACK_ENVELOPE_READER_WINDOW, PACK_ENVELOPE_SELECTION_BINDING),
        default=None,
        help="Frozen pack envelope: selection-binding=8192, reader-window fills the model.",
    )
    parser.add_argument(
        "--lineage-rule",
        choices=(LINEAGE_LAST_VALID, LINEAGE_FROM_SEED),
        default=None,
        help="Research parent after a valid slot. selection-blind requires next-from-seed.",
    )
    parser.add_argument(
        "--search-mode",
        choices=(SEARCH_NORMAL, SEARCH_SELECTION_BLIND),
        default=None,
        help="normal returns scores to the next prompt; selection-blind withholds them.",
    )
    parser.add_argument(
        "--feedback-schema",
        choices=(FEEDBACK_VISIBLE_GOLD, FEEDBACK_SCORE_COST, FEEDBACK_SCORE_ONLY),
        default=None,
        help="Search-visible metrics. Gold spans are optional, not the default required by SLE.",
    )
    return parser


def _load_tokenizer(tokenizer_path: Path) -> EncodedWindowTokenizer:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(tokenizer_path),
        local_files_only=True,  # nosec B615
    )
    tokenizer_class = f"{type(tokenizer).__module__}.{type(tokenizer).__qualname__}"
    if tokenizer_class != _TOKENIZER_CLASS:
        raise RuntimeError(f"unexpected canonical tokenizer class: {tokenizer_class}")
    init_kwargs = tokenizer.init_kwargs
    for field, filename in (("vocab_file", "vocab.json"), ("merges_file", "merges.txt")):
        observed = init_kwargs.get(field)
        if (
            not isinstance(observed, str)
            or Path(observed).resolve() != (tokenizer_path / filename).resolve()
        ):
            raise RuntimeError(f"canonical tokenizer did not bind {filename}")
    if init_kwargs.get("tokenizer_file") is not None:
        raise RuntimeError("canonical tokenizer unexpectedly uses tokenizer_file")
    return cast(EncodedWindowTokenizer, tokenizer)


def _load_items(
    *,
    cell_id: str,
    limit: int,
    tokenizer: EncodedWindowTokenizer,
    unique_queries: bool,
    min_gold_rank: int,
    offset: int = 0,
) -> tuple[EvaluationItem, ...]:
    source, prefix = _CELLS[cell_id]
    return load_helmet_kilt_items(
        source,
        item_prefix=prefix,
        limit=limit,
        tokenizer=tokenizer,
        unique_queries=unique_queries,
        min_gold_passage_index=min_gold_rank,
        offset=offset,
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
    open_s = args.policy_track == "open-s"
    max_items = (
        args.max_items
        if args.max_items is not None
        else (OPEN_S_VISIBLE_MAX_ITEMS if open_s else 8)
    )
    item_offset = (
        args.item_offset
        if args.item_offset is not None
        else (OPEN_S_VISIBLE_ITEM_OFFSET if open_s else 0)
    )
    min_gold_rank = (
        args.min_gold_rank if args.min_gold_rank is not None else OPEN_S_VISIBLE_MIN_GOLD_RANK
    )
    rounds = args.rounds if args.rounds is not None else (OPEN_S_VISIBLE_ROUNDS if open_s else 5)
    output_limit = args.reader_max_output_tokens
    if output_limit is None:
        output_limit = (
            OPEN_S_VISIBLE_READER_OUTPUT_TOKENS if open_s else dynamic_reader_output_limit(profile)
        )
    pack_envelope = args.pack_envelope
    if pack_envelope is None and open_s:
        pack_envelope = OPEN_S_VISIBLE_PACK_ENVELOPE
    pack_tokens = resolve_pack_budget_tokens(
        pack_tokens=args.pack_tokens,
        policy_track=args.policy_track,
        max_model_len=profile.evaluation_max_model_len,
        max_output_tokens=output_limit,
        pack_envelope=pack_envelope,
    )
    if args.search_mode is not None:
        search_mode = args.search_mode
    elif open_s:
        search_mode = OPEN_S_VISIBLE_SEARCH_MODE
    else:
        search_mode = SEARCH_NORMAL
    if args.lineage_rule is None:
        lineage_rule = (
            LINEAGE_FROM_SEED if search_mode == SEARCH_SELECTION_BLIND else LINEAGE_LAST_VALID
        )
    else:
        lineage_rule = args.lineage_rule
    if args.feedback_schema is not None:
        feedback_schema = args.feedback_schema
    elif open_s:
        feedback_schema = OPEN_S_VISIBLE_FEEDBACK_SCHEMA
    else:
        feedback_schema = FEEDBACK_VISIBLE_GOLD
    reader_timeout = args.reader_timeout_seconds
    if reader_timeout is None:
        reader_timeout = OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS if open_s else 180.0
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    tokenizer_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"
    tokenizer = _load_tokenizer(args.tokenizer_path)
    items = _load_items(
        cell_id=args.cell,
        limit=max_items,
        tokenizer=tokenizer,
        unique_queries=args.unique_queries,
        min_gold_rank=min_gold_rank,
        offset=item_offset,
    )
    if verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES) != tokenizer_snapshot:
        raise RuntimeError("canonical tokenizer snapshot changed during item compilation")
    fingerprint = public_visible_items_fingerprint(
        cell_id=(
            f"{args.cell}-unique{int(args.unique_queries)}-minrank{min_gold_rank}"
            f"-offset{item_offset}-track{args.policy_track}-pack{pack_tokens}"
            f"-lineage{lineage_rule}-search{search_mode}-feedback{feedback_schema}"
        ),
        items=items,
        pack_budget_tokens=pack_tokens,
        scorer_name="extractive_span_match",
        token_axis_id=tokenizer_id,
    )
    reader = build_profile_reader(
        profile,
        endpoint,
        max_tokens=output_limit,
        timeout_seconds=reader_timeout,
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
        rounds=rounds,
        budget=Budget(pack_tokens),
        process_limits=ProcessLimits(timeout_seconds=args.researcher_timeout_seconds),
        reader_identity=DynamicReaderIdentity.from_profile(
            profile,
            max_output_tokens=output_limit,
            serving_profile=serving,
        ),
        require_attested_identities=True,
        token_axis_identity={
            "attested": True,
            "label": "qwen-canonical-token-axis",
            "tokenizer_id": tokenizer_id,
        },
        policy_track=args.policy_track,
        lineage_rule=lineage_rule,
        search_mode=search_mode,
        feedback_schema=feedback_schema,
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
                "run_contract_sha256": result.run_contract_sha256,
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
