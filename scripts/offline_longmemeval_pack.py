#!/usr/bin/env python3
"""Compare 8K LongMemEval packs by answer-string presence. Not an official score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.datasets.longmemeval_transfer import (
    OfflinePackComparison,
    compare_offline_pack,
    full_trace_pack,
    last_k_pack,
    lexical_pack,
    random_trajectory_pack,
    spec_v1_pack,
)
from rsicontext.datasets.longmemeval_v2 import load_longmemeval_v2
from rsicontext.experiment.ledger import SpendCaps, SpendLedger
from rsicontext.policy import Budget
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_HF_DATA_REVISION = "f152293e235517d504809563c833d7190b8c713b"
_DEFAULT_TOKENIZER = Path("models/qwen3.6-27b")
_TOKENIZER_REVISION = "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_POLICY_NAMES = ("last-k", "lexical", "random", HAND_HYBRID_NAME, "full-trace-unbudgeted")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", default=_HF_DATA_REVISION)
    parser.add_argument("--tokenizer-path", type=Path, default=_DEFAULT_TOKENIZER)
    parser.add_argument("--tier", choices=("small", "medium"), default="small")
    parser.add_argument("--question-limit", type=int, default=12)
    parser.add_argument("--trajectories-per-question", type=int, default=2)
    parser.add_argument("--pack-tokens", type=int, default=8_192)
    parser.add_argument("--last-k", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main() -> int:
    args = _parser().parse_args()
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    from transformers import AutoTokenizer

    # The exact local tokenizer files were hash-verified immediately above.
    tokenizer = AutoTokenizer.from_pretrained(
        str(args.tokenizer_path),
        local_files_only=True,  # nosec B615
    )

    def token_count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    tokenizer_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"
    ledger = SpendLedger(
        SpendCaps(
            max_reader_calls=1,
            max_reader_input_tokens=1,
            max_cost_usd=0.0,
            max_gpu_seconds=1.0,
            max_wall_seconds=1.0,
            max_retries=0,
        )
    )
    dataset = load_longmemeval_v2(
        args.root,
        source_revision=args.source_revision,
        token_counter=token_count,
        tokenizer_id=tokenizer_id,
        tier=args.tier,
        question_limit=args.question_limit,
        trajectories_per_question=args.trajectories_per_question,
    )
    budget = Budget(max_tokens=args.pack_tokens)
    comparisons: list[OfflinePackComparison] = []
    for item in dataset.evaluator_items():
        packs = (
            ("last-k", last_k_pack(item.policy_item.artifact, budget, k=args.last_k)),
            ("lexical", lexical_pack(item.policy_item.artifact, item.policy_item.query, budget)),
            (
                "random",
                random_trajectory_pack(
                    item.policy_item.artifact,
                    budget,
                    seed=args.seed,
                    chunk_count=args.last_k,
                ),
            ),
            (
                HAND_HYBRID_NAME,
                spec_v1_pack(
                    item.policy_item.artifact,
                    item.policy_item.query,
                    budget,
                    HAND_HYBRID_SPEC_V1,
                ),
            ),
            ("full-trace-unbudgeted", full_trace_pack(item.policy_item.artifact)),
        )
        for name, pack in packs:
            comparisons.append(
                compare_offline_pack(
                    policy_name=name,
                    question_id=item.policy_item.question_id,
                    pack=pack,
                    answer=item.answer,
                )
            )
    snapshot = ledger.snapshot()
    payload = {
        "official_score": False,
        "metric": "answer_string_present",
        "qualification_only": True,
        "tier": args.tier,
        "source_revision": args.source_revision,
        "dataset_fingerprint": dataset.fingerprint,
        "question_limit": args.question_limit,
        "trajectories_per_question": args.trajectories_per_question,
        "pack_tokens": args.pack_tokens,
        "excluded_image_question_count": dataset.excluded_image_question_count,
        "loaded_trajectory_count": len(dataset.loaded_trajectory_ids),
        "item_count": len(dataset.evaluator_items()),
        "spend": dict(snapshot.to_ledger_pairs()),
        "comparisons": [
            {
                "policy_name": row.policy_name,
                "question_id": row.question_id,
                "packed_chunks": row.packed_chunks,
                "token_count": row.token_count,
                "answer_string_present": row.answer_string_present,
            }
            for row in comparisons
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    present = {
        name: sum(row.answer_string_present for row in comparisons if row.policy_name == name)
        for name in _POLICY_NAMES
    }
    print(
        json.dumps(
            {
                "official_score": False,
                "output": str(args.output),
                "item_count": payload["item_count"],
                "answer_string_present_counts": present,
                "reader_calls": snapshot.reader_calls,
                "cost_usd": snapshot.researcher_cost_usd,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
