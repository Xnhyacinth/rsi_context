#!/usr/bin/env python3
"""Run the preregistered lexical-versus-head hy3 signal diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

from rsicontext.campaign.autonomous_dynamic import public_visible_items_fingerprint
from rsicontext.datasets import load_helmet_kilt_items
from rsicontext.eval import extractive_span_match
from rsicontext.experiment import (
    PairedPolicyDiagnosticResult,
    build_paired_policy_diagnostic_contract,
    load_api_profiles,
    operational_record_sha256,
    resolve_api_endpoint,
    run_paired_policy_diagnostic,
    write_operational_record,
    write_paired_policy_diagnostic_contract,
    write_paired_policy_diagnostic_result,
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
    head_policy as _head_policy,
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
from rsicontext.experiment.operational_replay import OperationalReplayExecutionError
from rsicontext.experiment.rsi_run import (
    contract_file_sha256,
    validate_contract_file_unchanged,
)
from rsicontext.policy import Budget, LexicalPolicy
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PUBLIC_RESULTS_ROOT = _REPO_ROOT / "results"
_PREREGISTRATION = Path("docs/hy3-paired-signal-diagnostic-preregistration.md")
_DEFAULT_PRIOR_RESULT = Path("results/hy3-popqa-replay-e23f845-20260831/replay_result.json")
_PRIOR_RESULT_SHA256 = "23cb05483f4023be803765ab966875d8c5c91b496767b034c3c85e6bc35271e7"
_PRIOR_CONTRACT_SHA256 = "a3eb98fd0a97ff4f0860ec39bb73944ee211d95c63b3ae1990d7a5d8d2c960c2"
_PROFILE_ID = "tencent-copilot-hy3-ioa"
_PROFILE_SHA256 = "4b6628b16beedd447cb58c551178d9bea8263257736577b8a14f673103ec7082"
_ITEM_COUNT = 40
_MIN_GOLD_RANK = 200
_PACK_TOKENS = 8192
_READER_MAX_OUTPUT_TOKENS = 64
_REPETITIONS = 3
_CANARY_REPETITIONS = 3
_SCHEDULE_SEED = 1729
_BOOTSTRAP_SEED = 20260831
_BOOTSTRAP_SAMPLES = 10_000
_MINIMUM_MEAN_DELTA = 0.2
_MAXIMUM_POLICY_INSTABILITY = 0.1
_MAXIMUM_EXACT_P_VALUE = 0.05
_PRODUCER_FILES = (
    Path("scripts/hy3_paired_signal_diagnostic.py"),
    _PREREGISTRATION,
    *tuple(
        path.relative_to(_REPO_ROOT)
        for path in sorted((_REPO_ROOT / "src" / "rsicontext").rglob("*.py"))
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--private-evaluator-dir", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, default=_DEFAULT_TOKENIZER)
    return parser


def _prepare_run_directories(output_dir: Path, private_dir: Path) -> tuple[Path, Path]:
    output = output_dir.absolute()
    private = private_dir.absolute()
    repository = _REPO_ROOT.resolve()
    public_results_root = _PUBLIC_RESULTS_ROOT.resolve()
    for candidate, label in ((output, "public output"), (private, "private evaluator")):
        if candidate.exists() or candidate.is_symlink():
            raise FileExistsError(f"{label} directory already exists: {candidate}")
        parent = candidate.parent
        if not parent.is_dir() or parent.is_symlink() or parent.resolve() != parent.absolute():
            raise RuntimeError(f"{label} parent must be an existing non-symlink directory")
    if private.is_relative_to(repository):
        raise RuntimeError("private evaluator directory must be outside the repository")
    if not output.is_relative_to(public_results_root):
        raise RuntimeError("public output directory must be under the ignored results root")
    if private == output or private.is_relative_to(output) or output.is_relative_to(private):
        raise RuntimeError("public and private diagnostic directories must not overlap")
    os.mkdir(output, mode=0o700)
    try:
        os.mkdir(private, mode=0o700)
    except Exception:
        output.rmdir()
        raise
    for candidate, label in ((output, "public output"), (private, "private evaluator")):
        metadata = candidate.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.getuid()
        ):
            raise RuntimeError(f"{label} directory identity or permissions are unsafe")
    return output, private


def _load_prior_replay(path: Path) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("prior replay result cannot be loaded") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("prior replay result must be an object")
    expected = {
        "contract_sha256": _PRIOR_CONTRACT_SHA256,
        "item_flip_rate": 0.05,
        "item_flip_rate_upper_95": 0.1650387736914096,
    }
    if any(payload.get(field) != value for field, value in expected.items()):
        raise RuntimeError("prior replay result does not match the preregistered evidence")
    return payload


def _write_failure(
    path: Path,
    contract_sha256: str,
    error: Exception,
    *,
    contract_integrity: bool,
) -> None:
    execution_error = error if isinstance(error, OperationalReplayExecutionError) else None
    payload = {
        "attempted_reader_calls": (
            execution_error.attempted_reader_calls if execution_error is not None else 0
        ),
        "completed_transport_calls": (
            execution_error.completed_transport_calls if execution_error is not None else 0
        ),
        "contract_integrity": contract_integrity,
        "contract_sha256": contract_sha256,
        "cost_accounting_complete": False,
        "error_phase": execution_error.phase if execution_error is not None else "setup",
        "error_type": execution_error.cause_type
        if execution_error is not None
        else type(error).__name__,
        "qualification_only": True,
        "reader_usage_accounting_complete": False,
        "rsi_launch_eligible": False,
        "schema_version": 1,
    }
    write_operational_record(payload, path)


def main() -> int:
    args = _parser().parse_args()
    output_dir, private_evaluator_dir = _prepare_run_directories(
        args.output_dir, args.private_evaluator_dir
    )
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
    profile = load_api_profiles(Path("configs/api_profiles.json")).get(_PROFILE_ID)
    if profile.profile_hash != _PROFILE_SHA256:
        raise RuntimeError("hy3 request profile does not match the preregistered identity")
    endpoint = resolve_api_endpoint(profile)
    if file_sha256(_DEFAULT_SOURCE) != _SOURCE_SHA256:
        raise RuntimeError("pinned PopQA source digest mismatch")
    if file_sha256(_DEFAULT_PRIOR_RESULT) != _PRIOR_RESULT_SHA256:
        raise RuntimeError("prior replay result digest mismatch")
    prior_replay = _load_prior_replay(_DEFAULT_PRIOR_RESULT)
    preregistration_sha256 = file_sha256(_PREREGISTRATION)
    tokenizer_snapshot = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    token_axis_id = f"{_TOKENIZER_REVISION}#tokenizer-files-sha256:{tokenizer_snapshot}"
    tokenizer = _load_tokenizer(args.tokenizer_path)
    items = load_helmet_kilt_items(
        _DEFAULT_SOURCE,
        item_prefix="popqa-k1000",
        limit=_ITEM_COUNT,
        tokenizer=tokenizer,
        unique_queries=True,
        min_gold_passage_index=_MIN_GOLD_RANK,
    )
    if len(items) != _ITEM_COUNT:
        raise RuntimeError("pinned PopQA panel did not compile exactly 40 items")
    if file_sha256(_DEFAULT_SOURCE) != _SOURCE_SHA256:
        raise RuntimeError("pinned PopQA source changed during item compilation")
    if verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES) != tokenizer_snapshot:
        raise RuntimeError("canonical tokenizer snapshot changed during item compilation")
    budget = Budget(_PACK_TOKENS)
    cell_id = "helmet-rag-popqa-k1000-to-8192-token-pack"
    dataset_fingerprint = public_visible_items_fingerprint(
        cell_id=f"{cell_id}-unique1-minrank{_MIN_GOLD_RANK}",
        items=items,
        pack_budget_tokens=_PACK_TOKENS,
        scorer_name="extractive_span_match",
        token_axis_id=token_axis_id,
    )
    contract = build_paired_policy_diagnostic_contract(
        task_id=f"{cell_id}/lexical-vs-head",
        dataset_fingerprint=dataset_fingerprint,
        items=items,
        profile=profile,
        endpoint=endpoint.endpoint,
        reference_policy_id="lexical",
        reference_policy_factory=LexicalPolicy,
        comparator_policy_id="head",
        comparator_policy_factory=_head_policy,
        scorer=extractive_span_match,
        budget=budget,
        token_axis_id=token_axis_id,
        source_id=_SOURCE_ID,
        source_revision=_SOURCE_REVISION,
        source_sha256=_SOURCE_SHA256,
        preregistration_sha256=preregistration_sha256,
        prior_result_sha256=_PRIOR_RESULT_SHA256,
        prior_contract_sha256=_PRIOR_CONTRACT_SHA256,
        prior_item_flip_rate=float(prior_replay["item_flip_rate"]),
        prior_item_flip_upper_95=float(prior_replay["item_flip_rate_upper_95"]),
        repetitions=_REPETITIONS,
        canary_repetitions=_CANARY_REPETITIONS,
        schedule_seed=_SCHEDULE_SEED,
        bootstrap_seed=_BOOTSTRAP_SEED,
        bootstrap_samples=_BOOTSTRAP_SAMPLES,
        minimum_mean_delta=_MINIMUM_MEAN_DELTA,
        maximum_policy_instability=_MAXIMUM_POLICY_INSTABILITY,
        maximum_exact_p_value=_MAXIMUM_EXACT_P_VALUE,
        reader_max_output_tokens=_READER_MAX_OUTPUT_TOKENS,
        producer_git_revision=producer_revision,
        producer_attestation_sha256=producer_attestation_sha256,
    )
    producer_attestation_path = output_dir / "producer_attestation.json"
    write_operational_record(producer_before, producer_attestation_path)
    contract_path = output_dir / "run_contract.json"
    write_paired_policy_diagnostic_contract(contract, contract_path)
    contract_bytes_sha256 = contract_file_sha256(contract_path)

    def contract_guard() -> None:
        validate_contract_file_unchanged(contract_path, contract_bytes_sha256)

    result: PairedPolicyDiagnosticResult | None = None
    try:
        result = run_paired_policy_diagnostic(
            contract,
            items=items,
            profile=profile,
            endpoint=endpoint.endpoint,
            api_key=endpoint.api_key,
            reference_policy_factory=LexicalPolicy,
            comparator_policy_factory=_head_policy,
            scorer=extractive_span_match,
            budget=budget,
            persisted_contract_path=contract_path,
            persisted_contract_sha256=contract_bytes_sha256,
            persisted_producer_attestation_path=producer_attestation_path,
            private_ledger_path=private_evaluator_dir / "private_evaluator_ledger.json",
        )
        contract_guard()
        if file_sha256(_DEFAULT_SOURCE) != _SOURCE_SHA256:
            raise RuntimeError("pinned PopQA source changed during diagnostic")
        if file_sha256(_DEFAULT_PRIOR_RESULT) != _PRIOR_RESULT_SHA256:
            raise RuntimeError("prior replay result changed during diagnostic")
        if verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES) != tokenizer_snapshot:
            raise RuntimeError("canonical tokenizer snapshot changed during diagnostic")
        producer_after = producer_attestation(
            _REPO_ROOT,
            _PRODUCER_FILES,
            package_names=("rsibench-context", "transformers"),
        )
        require_clean_producer(producer_after)
        require_stable_attestation(producer_before, producer_after)
        write_paired_policy_diagnostic_result(result, output_dir / "diagnostic_result.json")
    except Exception as error:
        recorded_error = error
        if result is not None and not isinstance(error, OperationalReplayExecutionError):
            recorded_error = OperationalReplayExecutionError(
                result.total_reader_calls,
                result.total_reader_calls,
                "post-run-artifact",
                error,
            )
        try:
            contract_guard()
            contract_integrity = True
        except (RuntimeError, ValueError, OSError):
            contract_integrity = False
        _write_failure(
            output_dir / "failure.json",
            contract.contract_sha256,
            recorded_error,
            contract_integrity=contract_integrity,
        )
        if recorded_error is error:
            raise
        raise recorded_error from error
    if result is None:
        raise RuntimeError("paired diagnostic returned no result")
    summary = {
        "bootstrap_interval_95": [result.bootstrap_lower_95, result.bootstrap_upper_95],
        "cell_id": cell_id,
        "comparator_instability": result.comparator.unstable_item_rate,
        "contract_sha256": result.contract_sha256,
        "diagnostic_passed": result.diagnostic_passed,
        "failures": result.failures,
        "item_count": len(items),
        "paired_mean_delta": result.paired_mean_delta,
        "private_ledger_sha256": result.private_ledger_sha256,
        "qualification_only": True,
        "reference_instability": result.reference.unstable_item_rate,
        "repetition_deltas": result.repetition_deltas,
        "rsi_launch_eligible": False,
        "source_tokens": _source_token_summary(items),
        "total_reader_calls": result.total_reader_calls,
        "worst_case_paired_delta": result.worst_case_paired_delta,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.diagnostic_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
