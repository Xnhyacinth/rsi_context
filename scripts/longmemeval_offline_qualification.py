#!/usr/bin/env python3
"""Qualify full text-only LongMemEval-V2 histories without reader calls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rsicontext.analysis.longmemeval_qualification import (
    LONGMEMEVAL_V2_SOURCE_REVISION,
    evaluate_longmemeval_offline_qualification,
    measure_longmemeval_dataset,
)
from rsicontext.datasets.longmemeval_v2 import LongMemEvalTier, load_longmemeval_v2
from rsicontext.experiment.offline_provenance import (
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
    require_unchanged_file,
)
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_ROOT = Path(__file__).parents[1]
_DEFAULT_DATA_ROOT = Path("data/longmemeval-v2-data")
_DEFAULT_TOKENIZER = Path("models/qwen3.6-27b")
_TOKENIZER_REVISION = "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_COMMON_RELEASED_FILES = (
    ("questions.jsonl", "0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7"),
    (
        "trajectories.jsonl",
        "363cec9a8e87aa8d9101ce4e600aadbf7031d674056ebe4f969e8424abc5f3c6",
    ),
)
_HAYSTACK_SHA256 = {
    "small": "9b5301defb23a088a5f06e45ff8d5f35e569d78305a66d492046a9fff9b46593",
    "medium": "4756d5126347f0d18f045bb6c47b08cb3b23e9db24386cc48a9b2879e7969b59",
}
_PRODUCER_FILES = (
    Path("configs/registry.json"),
    Path("scripts/longmemeval_offline_qualification.py"),
    Path("src/rsicontext/analysis/longmemeval_qualification.py"),
    Path("src/rsicontext/datasets/longmemeval_v2.py"),
    Path("src/rsicontext/experiment/offline_provenance.py"),
    Path("src/rsicontext/registry/tokenizer.py"),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_DEFAULT_DATA_ROOT)
    parser.add_argument("--tokenizer-path", type=Path, default=_DEFAULT_TOKENIZER)
    parser.add_argument("--tier", choices=("small", "medium"), default="small")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _released_checksums(tier: LongMemEvalTier) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                *_COMMON_RELEASED_FILES,
                (f"haystacks/lme_v2_{tier}.json", _HAYSTACK_SHA256[tier]),
            )
        )
    )


def main() -> int:
    args = _parser().parse_args()
    if args.output.exists():
        raise FileExistsError(f"qualification output already exists: {args.output}")
    tier: LongMemEvalTier = args.tier
    producer_before = producer_attestation(
        _ROOT,
        _PRODUCER_FILES,
        package_names=("tokenizers", "transformers"),
    )
    require_clean_producer(producer_before)
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    tokenizer_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(args.tokenizer_path),
        local_files_only=True,  # nosec B615
    )

    def token_count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    released_checksums = _released_checksums(tier)
    dataset = load_longmemeval_v2(
        args.root,
        source_revision=LONGMEMEVAL_V2_SOURCE_REVISION,
        token_counter=token_count,
        tokenizer_id=tokenizer_id,
        tier=tier,
    )
    measurements = measure_longmemeval_dataset(
        dataset,
        released_file_sha256=released_checksums,
    )
    for relative_path, expected_sha256 in measurements.source_file_sha256:
        require_unchanged_file(
            args.root / relative_path,
            expected_sha256,
            label=f"LongMemEval source {relative_path}",
        )
    final_tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    if final_tokenizer_snapshot != tokenizer_snapshot:
        raise RuntimeError("tokenizer snapshot changed during qualification")
    producer_after = producer_attestation(
        _ROOT,
        _PRODUCER_FILES,
        package_names=("tokenizers", "transformers"),
    )
    require_clean_producer(producer_after)
    require_stable_attestation(producer_before, producer_after)
    verdict = evaluate_longmemeval_offline_qualification(measurements)
    payload = {
        "schema_version": 1,
        "qualification_only": True,
        "formal_benchmark_eligible": False,
        "official_score": False,
        "reader_calls": 0,
        "auxiliary_calls": 0,
        "item_level_labels_emitted": False,
        "producer_attestation": producer_before,
        "measurements": asdict(measurements),
        "source_files_match_release": measurements.source_files_match_release,
        "passed": verdict.passed,
        "failures": list(verdict.failures),
        "next_required": [
            "freeze the 294-item deterministic primary evaluator stratum",
            "qualify frozen-reader full-trace and 32K/64K/128K policy baselines",
            "report the 128-item LLM-judge stratum separately as weak evaluation",
            "keep live long-horizon policy-on/off transfer outside the RSI search loop",
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
