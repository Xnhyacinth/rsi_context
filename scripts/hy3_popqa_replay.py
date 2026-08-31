#!/usr/bin/env python3
"""Qualify hy3 on repeated real PopQA k1000 policy evaluation before RSI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.campaign.autonomous_dynamic import public_visible_items_fingerprint
from rsicontext.datasets import load_helmet_kilt_items
from rsicontext.eval import extractive_span_match
from rsicontext.eval.core import PolicyFactory
from rsicontext.experiment import (
    build_operational_replay_contract,
    load_api_profiles,
    operational_record_sha256,
    resolve_api_endpoint,
    run_operational_api_replay,
    write_operational_record,
    write_operational_replay_contract,
    write_operational_replay_result,
)
from rsicontext.experiment.hy3_popqa import (
    POPQA_SOURCE as _DEFAULT_SOURCE,
)
from rsicontext.experiment.hy3_popqa import (
    POPQA_SOURCE_ID as _SOURCE_ID,
)
from rsicontext.experiment.hy3_popqa import (
    POPQA_SOURCE_REVISION as _SOURCE_REVISION,
)
from rsicontext.experiment.hy3_popqa import (
    POPQA_SOURCE_SHA256 as _SOURCE_SHA256,
)
from rsicontext.experiment.hy3_popqa import (
    QWEN_TOKENIZER as _DEFAULT_TOKENIZER,
)
from rsicontext.experiment.hy3_popqa import (
    QWEN_TOKENIZER_FILES as _TOKENIZER_FILES,
)
from rsicontext.experiment.hy3_popqa import (
    QWEN_TOKENIZER_REVISION as _TOKENIZER_REVISION,
)
from rsicontext.experiment.hy3_popqa import (
    load_qwen_tokenizer as _load_tokenizer,
)
from rsicontext.experiment.hy3_popqa import (
    source_token_summary as _source_token_summary,
)
from rsicontext.experiment.offline_provenance import (
    file_sha256,
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.experiment.operational_replay import (
    OperationalReplayExecutionError,
    OperationalReplayResult,
)
from rsicontext.experiment.rsi_run import (
    contract_file_sha256,
    validate_contract_file_unchanged,
)
from rsicontext.policy import Budget, ContextPolicy, LexicalPolicy, TruncationPolicy
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRODUCER_FILES = (
    Path("scripts/hy3_popqa_replay.py"),
    *tuple(
        path.relative_to(_REPO_ROOT)
        for path in sorted((_REPO_ROOT / "src" / "rsicontext").rglob("*.py"))
    ),
)


def _head_policy() -> ContextPolicy:
    return TruncationPolicy("head")


def _middle_policy() -> ContextPolicy:
    return TruncationPolicy("middle")


def _tail_policy() -> ContextPolicy:
    return TruncationPolicy("tail")


_POLICIES: dict[str, PolicyFactory] = {
    "head": _head_policy,
    "lexical": LexicalPolicy,
    "middle": _middle_policy,
    "tail": _tail_policy,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, default=_DEFAULT_TOKENIZER)
    parser.add_argument("--profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--profile", default="tencent-copilot-hy3-ioa")
    parser.add_argument("--policy", choices=tuple(_POLICIES), default="lexical")
    parser.add_argument("--max-items", type=int, default=40)
    parser.add_argument("--min-gold-rank", type=int, default=200)
    parser.add_argument("--pack-tokens", type=int, default=8192)
    parser.add_argument("--reader-max-output-tokens", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--canary-repetitions", type=int, default=3)
    return parser


def _write_failure(
    path: Path,
    contract_sha256: str,
    error: Exception,
    *,
    contract_integrity: bool,
) -> None:
    attempted_reader_calls = (
        error.attempted_reader_calls if isinstance(error, OperationalReplayExecutionError) else 0
    )
    payload = {
        "attempted_reader_calls": attempted_reader_calls,
        "completed_transport_calls": (
            error.completed_transport_calls
            if isinstance(error, OperationalReplayExecutionError)
            else 0
        ),
        "contract_integrity": contract_integrity,
        "contract_sha256": contract_sha256,
        "cost_accounting_complete": False,
        "error_phase": (
            error.phase if isinstance(error, OperationalReplayExecutionError) else "setup"
        ),
        "error_type": (
            error.cause_type
            if isinstance(error, OperationalReplayExecutionError)
            else type(error).__name__
        ),
        "qualification_only": True,
        "reader_usage_accounting_complete": False,
        "schema_version": 1,
    }
    write_operational_record(payload, path)


def main() -> int:
    args = _parser().parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"replay output directory already exists: {args.output_dir}")
    producer_before = producer_attestation(
        _REPO_ROOT,
        _PRODUCER_FILES,
        package_names=("rsibench-context", "transformers"),
    )
    require_clean_producer(producer_before)
    producer_revision = producer_before.get("git_revision")
    if not isinstance(producer_revision, str):
        raise RuntimeError("producer attestation returned no Git revision")
    producer_attestation_sha256 = operational_record_sha256(producer_before)
    profile = load_api_profiles(args.profiles).get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    source_sha256 = file_sha256(_DEFAULT_SOURCE)
    if source_sha256 != _SOURCE_SHA256:
        raise RuntimeError("pinned PopQA source digest mismatch")
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    token_axis_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"
    tokenizer = _load_tokenizer(args.tokenizer_path)
    items = load_helmet_kilt_items(
        _DEFAULT_SOURCE,
        item_prefix="popqa-k1000",
        limit=args.max_items,
        tokenizer=tokenizer,
        unique_queries=True,
        min_gold_passage_index=args.min_gold_rank,
    )
    if file_sha256(_DEFAULT_SOURCE) != _SOURCE_SHA256:
        raise RuntimeError("pinned PopQA source changed during item compilation")
    if verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES) != tokenizer_snapshot:
        raise RuntimeError("canonical tokenizer snapshot changed during item compilation")
    budget = Budget(args.pack_tokens)
    cell_id = f"helmet-rag-popqa-k1000-to-{args.pack_tokens}-token-pack"
    dataset_fingerprint = public_visible_items_fingerprint(
        cell_id=f"{cell_id}-unique1-minrank{args.min_gold_rank}",
        items=items,
        pack_budget_tokens=args.pack_tokens,
        scorer_name="extractive_span_match",
        token_axis_id=token_axis_id,
    )
    policy_factory = _POLICIES[args.policy]
    contract = build_operational_replay_contract(
        task_id=f"{cell_id}/{args.policy}",
        dataset_fingerprint=dataset_fingerprint,
        items=items,
        profile=profile,
        endpoint=endpoint.endpoint,
        policy_factory=policy_factory,
        scorer=extractive_span_match,
        budget=budget,
        token_axis_id=token_axis_id,
        source_id=_SOURCE_ID,
        source_revision=_SOURCE_REVISION,
        source_sha256=_SOURCE_SHA256,
        repetitions=args.repetitions,
        canary_repetitions=args.canary_repetitions,
        max_score_standard_deviation=0.0,
        max_item_flip_rate=0.0,
        reader_max_output_tokens=args.reader_max_output_tokens,
        producer_git_revision=producer_revision,
        producer_attestation_sha256=producer_attestation_sha256,
    )
    producer_attestation_path = args.output_dir / "producer_attestation.json"
    write_operational_record(producer_before, producer_attestation_path)
    contract_path = args.output_dir / "run_contract.json"
    write_operational_replay_contract(contract, contract_path)
    contract_bytes_sha256 = contract_file_sha256(contract_path)

    def contract_guard() -> None:
        validate_contract_file_unchanged(contract_path, contract_bytes_sha256)

    result: OperationalReplayResult | None = None
    try:
        result = run_operational_api_replay(
            contract,
            items=items,
            profile=profile,
            endpoint=endpoint.endpoint,
            api_key=endpoint.api_key,
            policy_factory=policy_factory,
            scorer=extractive_span_match,
            budget=budget,
            persisted_contract_path=contract_path,
            persisted_contract_sha256=contract_bytes_sha256,
            persisted_producer_attestation_path=producer_attestation_path,
        )
        contract_guard()
        if file_sha256(_DEFAULT_SOURCE) != _SOURCE_SHA256:
            raise RuntimeError("pinned PopQA source changed during replay")
        if verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES) != tokenizer_snapshot:
            raise RuntimeError("canonical tokenizer snapshot changed during replay")
        producer_after = producer_attestation(
            _REPO_ROOT,
            _PRODUCER_FILES,
            package_names=("rsibench-context", "transformers"),
        )
        require_clean_producer(producer_after)
        require_stable_attestation(producer_before, producer_after)
        write_operational_replay_result(result, args.output_dir / "replay_result.json")
    except Exception as error:
        recorded_error = error
        if result is not None and not isinstance(error, OperationalReplayExecutionError):
            recorded_error = OperationalReplayExecutionError(
                result.reader_calls,
                result.reader_calls,
                "post-run-artifact",
                error,
            )
        try:
            contract_guard()
            contract_integrity = True
        except (RuntimeError, ValueError, OSError):
            contract_integrity = False
        _write_failure(
            args.output_dir / "failure.json",
            contract.contract_sha256,
            recorded_error,
            contract_integrity=contract_integrity,
        )
        if recorded_error is error:
            raise
        raise recorded_error from error
    if result is None:
        raise RuntimeError("operational replay returned no result")
    summary = {
        "aggregate_scores": result.aggregate_scores,
        "cell_id": cell_id,
        "contract_sha256": result.contract_sha256,
        "dataset_fingerprint": dataset_fingerprint,
        "evidence_tier": contract.evidence_tier,
        "failures": result.failures,
        "item_count": len(items),
        "item_flip_rate": result.item_flip_rate,
        "item_flip_rate_upper_95": result.item_flip_rate_upper_95,
        "meaningful_policy_delta": result.meaningful_policy_delta,
        "operational_block_passed": result.operational_block_passed,
        "output_dir": str(args.output_dir),
        "policy": args.policy,
        "qualification_only": True,
        "reader_calls": result.reader_calls,
        "score_standard_deviation": result.score_standard_deviation,
        "task_input_tokens_total": result.task_input_tokens_total,
        "task_latency_seconds_mean": result.task_latency_seconds_mean,
        "task_latency_seconds_total": result.task_latency_seconds_total,
        "task_output_tokens_total": result.task_output_tokens_total,
        "policy_pack_tokens_total": result.policy_pack_tokens_total,
        "rsi_launch_eligible": result.rsi_launch_eligible,
        "source_tokens": _source_token_summary(items),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.operational_block_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
