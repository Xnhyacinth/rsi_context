#!/usr/bin/env python3
"""Reader T0-public landscape on a cell that already passed the offline screen.

Does not start formal A2. Does not overwrite synthetic Repair landscapes.
Official HELMET scores are not claimed.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from rsicontext.analysis.public_difficulty import (
    PublicReaderMeasurements,
    evaluate_public_reader_difficulty,
    packer_item_disagreement,
)
from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.datasets.helmet_rag import (
    EncodedWindowTokenizer,
    compile_helmet_rag,
    relabel_ruler_qa_gold,
    ruler_qa_record,
    split_encoded_windows,
)
from rsicontext.datasets.longmemeval_transfer import spec_v1_pack
from rsicontext.eval import (
    EvaluationItem,
    OpenAICompatibleReader,
    extractive_span_match,
    gold_context_pack,
)
from rsicontext.policy import Budget, ContextPack, LexicalPolicy, TruncationPolicy

_MODEL = "Qwen/Qwen3.6-27B"
_ENDPOINT = "http://127.0.0.1:8017/v1/chat/completions"


@dataclass(frozen=True, slots=True)
class _ReaderCell:
    cell_id: str
    source: Path
    pack_budget: int
    item_prefix: str


_CELLS: dict[str, _ReaderCell] = {
    "helmet-recall-qa2-128k-to-8k": _ReaderCell(
        "helmet-recall-qa2-128k-to-8k",
        Path("data/helmet-data/data/ruler/qa_2/validation_131072.jsonl"),
        8192,
        "qa2-128k",
    ),
    "helmet-recall-qa2-128k-to-4k": _ReaderCell(
        "helmet-recall-qa2-128k-to-4k",
        Path("data/helmet-data/data/ruler/qa_2/validation_131072.jsonl"),
        4096,
        "qa2-128k",
    ),
    "helmet-recall-qa1-128k-to-4k": _ReaderCell(
        "helmet-recall-qa1-128k-to-4k",
        Path("data/helmet-data/data/ruler/qa_1/validation_131072.jsonl"),
        4096,
        "qa1-128k",
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell", choices=tuple(_CELLS), default="helmet-recall-qa2-128k-to-8k")
    parser.add_argument("--max-items", type=int, default=16)
    parser.add_argument("--endpoint", default=_ENDPOINT)
    parser.add_argument("--tokenizer-path", type=Path, default=Path("models/qwen3.6-27b"))
    parser.add_argument("--replay-repeats", type=int, default=5)
    parser.add_argument("--skip-replay-if-failed", action="store_true", default=True)
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
    cell: _ReaderCell,
    limit: int,
    tokenizer: EncodedWindowTokenizer,
) -> tuple[EvaluationItem, ...]:
    counter = _token_counter(tokenizer)

    def split_parts(text: str) -> tuple[str, ...]:
        return split_encoded_windows(text, tokenizer, 512)

    items: list[EvaluationItem] = []
    with cell.source.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            record = ruler_qa_record(json.loads(line), item_id=f"{cell.item_prefix}-{index:04d}")
            compiled = compile_helmet_rag(record, token_counter=counter, split_parts=split_parts)
            items.append(relabel_ruler_qa_gold(compiled, record.passages[0]))
            if len(items) >= limit:
                break
    if len(items) < 16:
        raise ValueError("reader T0 requires at least 16 items")
    return tuple(items)


def _gold_only_pack(item: EvaluationItem) -> ContextPack:
    gold_tokens = sum(
        chunk.token_count for chunk in item.artifact.chunks if chunk.chunk_id in item.gold_chunk_ids
    )
    if gold_tokens <= 0:
        return ContextPack()
    return gold_context_pack(item, gold_tokens, fill=False)


def _condition_packs(item: EvaluationItem, pack_budget: int) -> dict[str, ContextPack]:
    budget = Budget(max_tokens=pack_budget)
    return {
        "no-context": ContextPack(),
        "gold-only": _gold_only_pack(item),
        "head": TruncationPolicy("head").assemble(item.artifact, item.query, budget),
        "lexical": LexicalPolicy().assemble(item.artifact, item.query, budget),
        HAND_HYBRID_NAME: spec_v1_pack(item.artifact, item.query, budget, HAND_HYBRID_SPEC_V1),
    }


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("score must be numeric")
    return float(value)


def _score_pack(
    reader: OpenAICompatibleReader,
    item: EvaluationItem,
    pack: ContextPack,
) -> dict[str, object]:
    output = reader.read(item.query, pack)
    return {
        "item_id": item.item_id,
        "prediction": output.answer,
        "score": extractive_span_match(output.answer, item.answer),
        "pack_tokens": pack.token_count,
        "reader_input_tokens": output.input_tokens,
        "reader_output_tokens": output.output_tokens,
        "response_model": output.response_model,
    }


def main() -> int:
    args = _parser().parse_args()
    cell = _CELLS[args.cell]
    tokenizer = _load_tokenizer(args.tokenizer_path)
    items = _load_items(cell=cell, limit=args.max_items, tokenizer=tokenizer)
    reader = OpenAICompatibleReader(
        endpoint=args.endpoint,
        model=_MODEL,
        max_tokens=32,
        max_model_len=131072,
        seed=42,
        stream=True,
        require_response_model=True,
        chat_template_enable_thinking=False,
        timeout_seconds=180.0,
        allowed_hosts=("127.0.0.1", "localhost"),
    )
    condition_names = ("no-context", "gold-only", "head", "lexical", HAND_HYBRID_NAME)
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in condition_names}
    for index, item in enumerate(items):
        packs = _condition_packs(item, cell.pack_budget)
        print(f"item {index + 1}/{len(items)} {item.item_id}", flush=True)
        for name in condition_names:
            row = _score_pack(reader, item, packs[name])
            rows[name].append(row)
            print(
                f"  {name} score={row['score']} pred={str(row['prediction'])[:80]!r}",
                flush=True,
            )

    def mean_score(name: str) -> float:
        return sum(_as_float(row["score"]) for row in rows[name]) / len(items)

    packer_names = ("head", "lexical", HAND_HYBRID_NAME)
    packer_scores = tuple((name, mean_score(name)) for name in packer_names)
    vectors = tuple(tuple(_as_float(row["score"]) for row in rows[name]) for name in packer_names)
    replay_scores: list[float] = [mean_score("lexical")]
    strongest = max(packer_scores, key=lambda pair: pair[1])[0]
    measurements = PublicReaderMeasurements(
        cell_id=cell.cell_id,
        n_items=len(items),
        gold_only_accuracy=mean_score("gold-only"),
        no_context_accuracy=mean_score("no-context"),
        packer_scores=packer_scores,
        packer_disagreement=packer_item_disagreement(vectors),
        replay_standard_deviation=0.0,
        median_meaningful_delta=max(
            0.01, max(s for _, s in packer_scores) - min(s for _, s in packer_scores)
        ),
    )
    pre_replay = evaluate_public_reader_difficulty(measurements)
    do_replay = args.replay_repeats > 1 and (not args.skip_replay_if_failed or pre_replay.passed)
    if do_replay:
        extra = args.replay_repeats - 1
        print(f"replaying {strongest} {extra} extra times", flush=True)
        for repeat in range(extra):
            hits: list[float] = []
            for item in items:
                pack = _condition_packs(item, cell.pack_budget)[strongest]
                hits.append(_as_float(_score_pack(reader, item, pack)["score"]))
            replay_scores.append(sum(hits) / len(hits))
            print(f"  replay {repeat + 2}/{args.replay_repeats} {replay_scores[-1]}", flush=True)
        packer_min = min(score for _, score in packer_scores)
        packer_max = max(score for _, score in packer_scores)
        measurements = PublicReaderMeasurements(
            cell_id=cell.cell_id,
            n_items=len(items),
            gold_only_accuracy=mean_score("gold-only"),
            no_context_accuracy=mean_score("no-context"),
            packer_scores=packer_scores,
            packer_disagreement=packer_item_disagreement(vectors),
            replay_standard_deviation=(
                float(statistics.pstdev(replay_scores)) if len(replay_scores) > 1 else 0.0
            ),
            median_meaningful_delta=max(0.01, packer_max - packer_min),
        )
    verdict = evaluate_public_reader_difficulty(measurements)
    calls = sum(len(rows[name]) for name in condition_names) + (
        (args.replay_repeats - 1) * len(items) if do_replay else 0
    )
    payload = {
        "cell_id": cell.cell_id,
        "n_items": len(items),
        "official_helmet_score": False,
        "qualification_only": True,
        "measurements": asdict(measurements),
        "passed": verdict.passed,
        "failures": list(verdict.failures),
        "replay_scores": replay_scores,
        "replayed_packer": strongest if do_replay else None,
        "reader_calls": calls,
        "rows": rows,
        "tokenizer_id": "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b",
        "scorer": "extractive_span_match",
        "synthetic_t0_unchanged": True,
        "gold_provenance": "ruler_supporting_documents",
        "pack_budget_tokens": cell.pack_budget,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "passed": verdict.passed,
                "failures": list(verdict.failures),
            },
            indent=2,
        )
    )
    return 0 if verdict.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
