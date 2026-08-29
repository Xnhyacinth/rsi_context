#!/usr/bin/env python3
"""Pack HELMET-style RAG JSONL with frozen H baselines. Not an official HELMET score."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.datasets.helmet_rag import HelmetRagRecord, compile_helmet_rag, helmet_kilt_record
from rsicontext.datasets.longmemeval_transfer import compare_offline_pack, spec_v1_pack
from rsicontext.policy import Budget, LexicalPolicy, TruncationPolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--budget-tokens", type=int, default=8192)
    parser.add_argument("--tokenizer-path", type=Path)
    return parser


def _word_tokens(text: str) -> int:
    return len(text.split())


def _load_records(path: Path, limit: int) -> tuple[HelmetRagRecord, ...]:
    records: list[HelmetRagRecord] = []
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise TypeError("HELMET JSONL records must be objects")
            if "passages" in raw:
                records.append(
                    HelmetRagRecord(
                        item_id=str(raw["item_id"]),
                        query=str(raw["query"]),
                        answer=str(raw["answer"]),
                        passages=tuple(str(passage) for passage in raw["passages"]),
                    )
                )
            else:
                records.append(helmet_kilt_record(raw, item_id=f"{path.stem}-{index:04d}"))
            if len(records) >= limit:
                break
    if not records:
        raise ValueError("HELMET RAG JSONL contained no records")
    return tuple(records)


def main() -> int:
    args = _parser().parse_args()
    budget = Budget(max_tokens=args.budget_tokens)
    if args.tokenizer_path is None:
        counter: Callable[[str], int] = _word_tokens
        tokenizer_id = "whitespace-words"
    else:
        import importlib

        transformers = importlib.import_module("transformers")
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            args.tokenizer_path,
            local_files_only=True,  # nosec B615
        )

        def counter(text: str) -> int:
            return len(tokenizer.encode(text, add_special_tokens=False))

        tokenizer_id = str(args.tokenizer_path)
    rows = []
    for record in _load_records(args.jsonl, args.max_items):
        item = compile_helmet_rag(record, token_counter=counter)
        packers = {
            "head-8k": TruncationPolicy("head").assemble(item.artifact, item.query, budget),
            "lexical-8k": LexicalPolicy().assemble(item.artifact, item.query, budget),
            HAND_HYBRID_NAME: spec_v1_pack(item.artifact, item.query, budget, HAND_HYBRID_SPEC_V1),
        }
        for name, pack in packers.items():
            comparison = compare_offline_pack(
                policy_name=name,
                question_id=item.item_id,
                pack=pack,
                answer=item.answer,
            )
            rows.append(
                {
                    "answer_string_present": comparison.answer_string_present,
                    "item_id": comparison.question_id,
                    "packed_chunks": comparison.packed_chunks,
                    "policy_name": comparison.policy_name,
                    "token_count": comparison.token_count,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "items": rows,
        "official_helmet_score": False,
        "qualification_only": True,
        "source": str(args.jsonl),
        "tokenizer_id": tokenizer_id,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(rows), "output": str(args.output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
