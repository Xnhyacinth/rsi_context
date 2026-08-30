#!/usr/bin/env python3
"""Qualify native MuSiQue for causal long-context use without reader calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import cast

from rsicontext.analysis.musique_qualification import (
    evaluate_musique_offline_qualification,
    measure_musique_evaluator_items,
    measure_musique_records,
)
from rsicontext.datasets.musique import (
    MuSiQueEvaluatorItem,
    MuSiQueRecord,
    musique_answerable_record,
)
from rsicontext.datasets.musique_long_context import (
    MuSiQueGoldPosition,
    gold_position_matches,
    pack_musique_long_context,
)
from rsicontext.experiment.offline_provenance import (
    file_sha256,
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
    require_unchanged_file,
)
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_DEFAULT_INPUT = Path("data/musique-answerable-data-qualification/musique_ans_v1.0_dev.jsonl")
_DEFAULT_TOKENIZER = Path("models/qwen3.6-27b")
_EXPECTED_SHA256 = "15fa63794d18a94ce12411aca6e2327e65b6e83b0b1490efab3f1962e48abf3b"
_SOURCE_REVISION = "763b65f844118a148e92bb88e7de5cb191b4c5dc"
_TOKENIZER_REVISION = "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_ROOT = Path(__file__).parents[1]
_PRODUCER_FILES = (
    Path("configs/registry.json"),
    Path("scripts/musique_offline_qualification.py"),
    Path("src/rsicontext/analysis/musique_qualification.py"),
    Path("src/rsicontext/datasets/musique.py"),
    Path("src/rsicontext/datasets/musique_long_context.py"),
    Path("src/rsicontext/experiment/offline_provenance.py"),
    Path("src/rsicontext/registry/tokenizer.py"),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, default=_DEFAULT_TOKENIZER)
    parser.add_argument("--pack-budget-tokens", type=int, default=8192)
    parser.add_argument("--packed-items", type=int, default=0)
    parser.add_argument("--target-source-tokens", type=int, default=32768)
    parser.add_argument("--construction-seed", type=int, default=20260830)
    return parser


def _producer_attestation() -> dict[str, object]:
    return producer_attestation(
        _ROOT,
        _PRODUCER_FILES,
        package_names=("tokenizers", "transformers"),
    )


def _require_clean_producer(attestation: dict[str, object]) -> None:
    require_clean_producer(attestation)


def _require_stable_attestation(
    before: dict[str, object],
    after: dict[str, object],
) -> None:
    require_stable_attestation(before, after)


def _require_unchanged_source(path: Path, expected_sha256: str) -> None:
    require_unchanged_file(path, expected_sha256, label="MuSiQue qualification source")


def _records(path: Path) -> Iterator[MuSiQueRecord]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL row at line {line_number}")
            raw: object = json.loads(line)
            if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
                raise ValueError(f"JSONL row {line_number} must be an object with string keys")
            yield musique_answerable_record(cast(dict[str, object], raw))


def _token_counter(tokenizer_path: Path) -> Callable[[str], int]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(tokenizer_path),
        local_files_only=True,  # nosec B615
    )

    def count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    return count


def _packed_profile(
    records: tuple[MuSiQueRecord, ...],
    *,
    token_counter: Callable[[str], int],
    n_items: int,
    target_source_tokens: int,
    construction_seed: int,
) -> tuple[tuple[MuSiQueEvaluatorItem, ...], dict[str, object]]:
    if n_items < 1:
        raise ValueError("packed-items must be positive when packing is enabled")
    by_hop = {
        hop_count: [record for record in records if len(record.steps) == hop_count]
        for hop_count in (2, 3, 4)
    }
    cursors = {hop_count: 0 for hop_count in by_hop}
    positions: tuple[MuSiQueGoldPosition, ...] = (
        "front",
        "middle",
        "tail",
        "distributed",
    )
    packed: list[MuSiQueEvaluatorItem] = []
    selection_identity: list[tuple[str, str, int]] = []
    position_counts: Counter[str] = Counter()
    position_matches = 0
    skipped_native_causal_leakage = 0
    for slot in range(n_items):
        hop_count = (2, 3, 4)[slot % 3]
        position = positions[slot % len(positions)]
        bucket = by_hop[hop_count]
        while cursors[hop_count] < len(bucket):
            target = bucket[cursors[hop_count]]
            cursors[hop_count] += 1
            seed = construction_seed + slot
            try:
                item = pack_musique_long_context(
                    target,
                    records,
                    token_counter=token_counter,
                    target_source_tokens=target_source_tokens,
                    position=position,
                    seed=seed,
                )
            except ValueError as exc:
                if str(exc) != (
                    "target final or intermediate answer appears in native non-supporting evidence"
                ):
                    raise
                skipped_native_causal_leakage += 1
                continue
            if not gold_position_matches(item, position):
                raise ValueError(
                    f"compiled gold evidence does not satisfy requested {position!r} token stratum"
                )
            packed.append(item)
            position_counts[position] += 1
            position_matches += 1
            selection_identity.append((target.item_id, position, seed))
            break
        else:
            raise ValueError(f"insufficient clean {hop_count}-hop targets")
    selection_payload = json.dumps(
        selection_identity,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return tuple(packed), {
        "construction_seed": construction_seed,
        "packed_items": n_items,
        "position_counts": dict(sorted(position_counts.items())),
        "position_match_rate": position_matches / n_items,
        "selection_sha256": hashlib.sha256(selection_payload).hexdigest(),
        "skipped_native_causal_leakage": skipped_native_causal_leakage,
        "target_source_tokens": target_source_tokens,
    }


def main() -> int:
    args = _parser().parse_args()
    if args.output.exists():
        raise FileExistsError(f"qualification output already exists: {args.output}")
    producer_attestation = _producer_attestation()
    _require_clean_producer(producer_attestation)
    source_sha256 = file_sha256(args.input)
    if source_sha256 != _EXPECTED_SHA256:
        raise ValueError(
            "MuSiQue qualification source digest mismatch: "
            f"expected {_EXPECTED_SHA256}, observed {source_sha256}"
        )
    tokenizer_snapshot_sha256 = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    tokenizer_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot_sha256}"
    token_counter = _token_counter(args.tokenizer_path)
    construction: dict[str, object] | None = None
    if args.packed_items:
        records = tuple(_records(args.input))
        packed, construction = _packed_profile(
            records,
            token_counter=token_counter,
            n_items=args.packed_items,
            target_source_tokens=args.target_source_tokens,
            construction_seed=args.construction_seed,
        )
        measurements = measure_musique_evaluator_items(
            packed,
            pack_budget_tokens=args.pack_budget_tokens,
            source_sha256=source_sha256,
            source_revision=_SOURCE_REVISION,
            official_source_sha256=None,
            tokenizer_id=tokenizer_id,
        )
    else:
        measurements = measure_musique_records(
            _records(args.input),
            token_counter=token_counter,
            pack_budget_tokens=args.pack_budget_tokens,
            source_sha256=source_sha256,
            source_revision=_SOURCE_REVISION,
            official_source_sha256=None,
            tokenizer_id=tokenizer_id,
        )
    _require_unchanged_source(args.input, source_sha256)
    final_tokenizer_snapshot_sha256 = verify_tokenizer_snapshot(
        args.tokenizer_path, _TOKENIZER_FILES
    )
    if final_tokenizer_snapshot_sha256 != tokenizer_snapshot_sha256:
        raise RuntimeError("tokenizer snapshot changed during qualification")
    final_producer_attestation = _producer_attestation()
    _require_clean_producer(final_producer_attestation)
    _require_stable_attestation(producer_attestation, final_producer_attestation)
    verdict = evaluate_musique_offline_qualification(measurements)
    payload = {
        "schema_version": 2,
        "qualification_only": True,
        "formal_benchmark_eligible": False,
        "official_source_byte_match": measurements.official_source_byte_match,
        "reader_calls": 0,
        "item_level_labels_emitted": False,
        "producer_attestation": producer_attestation,
        "construction": construction,
        "measurements": asdict(measurements),
        "passed": verdict.passed,
        "failures": list(verdict.failures),
        "next_required": [
            "byte-match the mirror files to the author-distributed archive",
            "retain only profiles that pass deterministic answer-clean 32K packing",
            "rerun the offline gate before any reader or researcher call",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if verdict.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
