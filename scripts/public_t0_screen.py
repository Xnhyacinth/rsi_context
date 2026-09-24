#!/usr/bin/env python3
"""Offline T0-public screen: real HELMET/RULER cells, no reader calls.

Does not score official HELMET. Does not start A2. Does not overwrite synthetic
Repair A/B/C landscapes. Packing must be binding and unsaturated before any
reader landscape is allowed. Pack envelopes are not limited to 32K→8K.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from rsicontext.analysis.public_difficulty import (
    PublicOfflineMeasurements,
    answer_in_haystack,
    evaluate_public_offline_difficulty,
    packer_item_disagreement,
)
from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.datasets.helmet_rag import (
    EncodedWindowTokenizer,
    HelmetRagRecord,
    compile_helmet_rag,
    helmet_kilt_record,
    ruler_qa_record,
    select_helmet_kilt_records,
    split_encoded_windows,
)
from rsicontext.datasets.longmemeval_transfer import spec_v1_pack
from rsicontext.datasets.ruler_niah import compile_ruler_niah, json_kv_record, ruler_niah_record
from rsicontext.eval import EvaluationItem
from rsicontext.policy import Budget, ContextPack, LexicalPolicy, TruncationPolicy

CellKind = Literal["ruler", "kilt", "json_kv", "qa"]


@dataclass(frozen=True, slots=True)
class PublicCell:
    cell_id: str
    kind: CellKind
    path: Path
    budget_tokens: int


_CELLS: tuple[PublicCell, ...] = (
    PublicCell(
        "helmet-recall-niah-mk2-32k-to-8k",
        "ruler",
        Path("data/helmet-data/data/ruler/niah_multikey_2/validation_32768.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-niah-mk2-128k-to-8k",
        "ruler",
        Path("data/helmet-data/data/ruler/niah_multikey_2/validation_131072.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-niah-mk2-128k-to-32k",
        "ruler",
        Path("data/helmet-data/data/ruler/niah_multikey_2/validation_131072.jsonl"),
        32768,
    ),
    PublicCell(
        "helmet-recall-jsonkv-k1800-to-8k",
        "json_kv",
        Path("data/helmet-data/data/json_kv/test_k1800_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-nq-k50-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k50_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-nq-k220-to-4k",
        "kilt",
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k220_dep6.jsonl"),
        4096,
    ),
    PublicCell(
        "helmet-rag-nq-k220-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k220_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-nq-k440-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k440_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-hotpot-k220-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/hotpotqa-dev-multikilt_1000_k220_dep3.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-trivia-k220-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/triviaqa-dev-multikilt_1000_k220_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-hotpot-k1000-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/hotpotqa-dev-multikilt_1000_k1000_dep3.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-nq-k1000-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/nq-dev-multikilt_1000_k1000_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-popqa-k1000-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-rag-trivia-k1000-to-8k",
        "kilt",
        Path("data/helmet-data/data/kilt/triviaqa-dev-multikilt_1000_k1000_dep6.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-qa2-32k-to-8k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_2/validation_32768.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-qa2-128k-to-8k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_2/validation_131072.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-qa2-128k-to-4k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_2/validation_131072.jsonl"),
        4096,
    ),
    PublicCell(
        "helmet-recall-qa2-256k-to-8k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_2/validation_262144.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-qa1-128k-to-8k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_1/validation_131072.jsonl"),
        8192,
    ),
    PublicCell(
        "helmet-recall-qa1-128k-to-4k",
        "qa",
        Path("data/helmet-data/data/ruler/qa_1/validation_131072.jsonl"),
        4096,
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=32)
    parser.add_argument("--tokenizer-path", type=Path, default=Path("models/qwen3.6-27b"))
    parser.add_argument("--only", action="append", default=[], help="substring filter on cell_id")
    parser.add_argument("--unique-queries", action="store_true")
    parser.add_argument("--min-gold-rank", type=int, default=0)
    return parser


def _load_tokenizer(tokenizer_path: Path) -> EncodedWindowTokenizer:
    from transformers import AutoTokenizer  # type: ignore[import-not-found]  # optional tokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(tokenizer_path),
        local_files_only=True,  # nosec B615
    )
    return cast(EncodedWindowTokenizer, tokenizer)


def _token_counter(tokenizer: EncodedWindowTokenizer) -> Callable[[str], int]:
    def counter(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    return counter


def _split_parts(
    tokenizer: EncodedWindowTokenizer, tokens_per_chunk: int
) -> Callable[[str], tuple[str, ...]]:
    def splitter(text: str) -> tuple[str, ...]:
        return split_encoded_windows(text, tokenizer, tokens_per_chunk)

    return splitter


def _load_items(
    *,
    kind: CellKind,
    path: Path,
    limit: int,
    counter: Callable[[str], int],
    split_parts: Callable[[str], tuple[str, ...]],
    unique_queries: bool,
    min_gold_rank: int,
) -> tuple[EvaluationItem, ...]:
    if kind == "kilt":

        def records() -> Iterator[HelmetRagRecord]:
            with path.open(encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    if not line.strip():
                        continue
                    yield helmet_kilt_record(json.loads(line), item_id=f"{path.stem}-{index:04d}")

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

    items: list[EvaluationItem] = []
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            raw = json.loads(line)
            if kind == "ruler":
                niah = ruler_niah_record(raw, item_id=f"{path.stem}-{index:04d}")
                items.append(
                    compile_ruler_niah(niah, token_counter=counter, split_parts=split_parts)
                )
            elif kind == "json_kv":
                kv_record = json_kv_record(raw, item_id=f"{path.stem}-{index:04d}")
                items.append(
                    compile_ruler_niah(kv_record, token_counter=counter, split_parts=split_parts)
                )
            else:
                qa_record = ruler_qa_record(raw, item_id=f"{path.stem}-{index:04d}")
                items.append(
                    compile_helmet_rag(qa_record, token_counter=counter, split_parts=split_parts)
                )
            if len(items) >= limit:
                break
    if len(items) < 16:
        raise ValueError(f"{path} yielded fewer than 16 items")
    return tuple(items)


def _packers(budget: Budget) -> dict[str, Callable[[EvaluationItem], ContextPack]]:
    def head(item: EvaluationItem) -> ContextPack:
        return TruncationPolicy("head").assemble(item.artifact, item.query, budget)

    def lexical(item: EvaluationItem) -> ContextPack:
        return LexicalPolicy().assemble(item.artifact, item.query, budget)

    def hybrid(item: EvaluationItem) -> ContextPack:
        return spec_v1_pack(item.artifact, item.query, budget, HAND_HYBRID_SPEC_V1)

    return {"head": head, "lexical": lexical, HAND_HYBRID_NAME: hybrid}


def _screen_cell(
    items: tuple[EvaluationItem, ...],
    *,
    cell_id: str,
    budget_tokens: int,
    kind: CellKind,
) -> dict[str, object]:
    budget = Budget(max_tokens=budget_tokens)
    source_tokens = [sum(chunk.token_count for chunk in item.artifact.chunks) for item in items]
    use_gold_chunks = kind == "kilt" and all(item.gold_chunk_ids for item in items)
    answer_in_source = [
        (
            bool(item.gold_chunk_ids)
            if use_gold_chunks
            else any(answer_in_haystack(chunk.text, item.answer) for chunk in item.artifact.chunks)
        )
        for item in items
    ]
    packers = _packers(budget)
    present: dict[str, list[float]] = {name: [] for name in packers}
    gold_hits: list[float] = []
    for item in items:
        packed_gold = False
        for name, packer in packers.items():
            pack = packer(item)
            packed_ids = {span.chunk_id for span in pack.spans}
            if use_gold_chunks:
                present[name].append(float(bool(item.gold_chunk_ids & packed_ids)))
            else:
                haystack = "\n".join(pack.ordered_text())
                present[name].append(float(answer_in_haystack(haystack, item.answer)))
            if item.gold_chunk_ids & packed_ids:
                packed_gold = True
        gold_hits.append(float(packed_gold))
    rates = tuple((name, sum(values) / len(values)) for name, values in present.items())
    vectors = tuple(tuple(present[name]) for name in present)
    measurements = PublicOfflineMeasurements(
        cell_id=cell_id,
        n_items=len(items),
        pack_budget_tokens=budget_tokens,
        median_source_tokens=float(statistics.median(source_tokens)),
        pack_binding_rate=sum(token > budget_tokens for token in source_tokens) / len(items),
        answer_in_source_rate=sum(answer_in_source) / len(items),
        packer_answer_rates=rates,
        packer_answer_disagreement=packer_item_disagreement(vectors),
    )
    verdict = evaluate_public_offline_difficulty(measurements)
    return {
        "measurements": asdict(measurements),
        "passed": verdict.passed,
        "failures": list(verdict.failures),
        "source_token_min": min(source_tokens),
        "source_token_max": max(source_tokens),
        "gold_chunk_rate": sum(bool(item.gold_chunk_ids) for item in items) / len(items),
        "gold_chunk_in_any_packer_rate": sum(gold_hits) / len(items),
    }


def main() -> int:
    args = _parser().parse_args()
    tokenizer = _load_tokenizer(args.tokenizer_path)
    counter = _token_counter(tokenizer)
    split_parts = _split_parts(tokenizer, 512)
    selected = [
        spec
        for spec in _CELLS
        if not args.only or any(fragment in spec.cell_id for fragment in args.only)
    ]
    cells = []
    for spec in selected:
        print(f"screening {spec.cell_id}", flush=True)
        if not spec.path.is_file():
            cells.append({"cell_id": spec.cell_id, "skipped": True, "reason": "missing file"})
            continue
        items = _load_items(
            kind=spec.kind,
            path=spec.path,
            limit=args.max_items,
            counter=counter,
            split_parts=split_parts,
            unique_queries=args.unique_queries,
            min_gold_rank=args.min_gold_rank,
        )
        result = _screen_cell(
            items,
            cell_id=spec.cell_id,
            budget_tokens=spec.budget_tokens,
            kind=spec.kind,
        )
        cells.append(result)
        print(
            json.dumps(
                {
                    "cell_id": spec.cell_id,
                    "passed": result["passed"],
                    "failures": result["failures"],
                    "packer_answer_rates": result["measurements"]["packer_answer_rates"]
                    if isinstance(result["measurements"], dict)
                    else None,
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
    payload = {
        "cells": cells,
        "max_items": args.max_items,
        "official_helmet_score": False,
        "reader_calls": 0,
        "synthetic_t0_unchanged": True,
        "tokenizer_id": "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cells": len(cells)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
