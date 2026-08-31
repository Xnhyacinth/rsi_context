from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from rsicontext.eval import EvaluationItem
from rsicontext.experiment import (
    PairedPolicyDiagnosticContract,
    PairedPolicyDiagnosticResult,
    PairedPolicySummary,
)
from rsicontext.policy import Artifact, DocumentChunk

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "hy3_paired_signal_diagnostic.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hy3_paired_signal_script_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hy3 paired diagnostic script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _items() -> tuple[EvaluationItem, ...]:
    rows = []
    for index in range(40):
        text = f"The supported answer is answer-{index}."
        chunk = DocumentChunk(f"chunk-{index}", "document", 0, len(text), text, 9)
        rows.append(
            EvaluationItem(
                f"item-{index}",
                f"What is answer {index}?",
                f"answer-{index}",
                Artifact("document", (chunk,)),
            )
        )
    return tuple(rows)


@pytest.fixture
def script() -> ModuleType:
    return _load_script()


def _patch_compilation(script: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    attestation = {
        "git_revision": "d" * 40,
        "package_versions": {"rsibench-context": "0.1.0", "transformers": "test"},
        "producer_file_sha256": {},
        "producer_files_match_head": True,
        "producer_head_blob_sha256": {},
        "python_version": "3.12.3",
        "repository_root_matches": True,
        "worktree_dirty": False,
    }
    monkeypatch.setattr(script, "producer_attestation", lambda *args, **kwargs: attestation)
    monkeypatch.setattr(script, "require_clean_producer", lambda value: None)
    monkeypatch.setattr(script, "require_stable_attestation", lambda before, after: None)
    monkeypatch.setattr(
        script,
        "resolve_api_endpoint",
        lambda profile: SimpleNamespace(
            endpoint="https://copilot.tencent.com/v2/chat/completions", api_key="key"
        ),
    )

    def digest(path: Path) -> str:
        if path == script._DEFAULT_SOURCE:
            return cast(str, script._SOURCE_SHA256)
        if path == script._DEFAULT_PRIOR_RESULT:
            return cast(str, script._PRIOR_RESULT_SHA256)
        if path == script._PREREGISTRATION:
            return "f" * 64
        raise AssertionError(f"unexpected digest path: {path}")

    monkeypatch.setattr(script, "file_sha256", digest)
    monkeypatch.setattr(script, "verify_tokenizer_snapshot", lambda path, files: "e" * 64)
    monkeypatch.setattr(script, "_load_tokenizer", lambda path: object())
    monkeypatch.setattr(script, "load_helmet_kilt_items", lambda *args, **kwargs: _items())
    monkeypatch.setattr(script, "public_visible_items_fingerprint", lambda **kwargs: "a" * 64)
    monkeypatch.setattr(
        script,
        "_load_prior_replay",
        lambda path: {
            "contract_sha256": script._PRIOR_CONTRACT_SHA256,
            "item_flip_rate": 0.05,
            "item_flip_rate_upper_95": 0.1650387736914096,
        },
    )


def _passing_result(contract_sha256: str) -> PairedPolicyDiagnosticResult:
    policy = PairedPolicySummary(
        policy_id="lexical",
        repetition_scores=(0.8, 0.8, 0.8),
        pairwise_disagreement=0.0,
        unstable_item_count=0,
        unstable_item_rate=0.0,
        unstable_item_rate_upper_95=0.08762160119728664,
        input_tokens_total=100,
        output_tokens_total=10,
        policy_pack_tokens_total=100,
        latency_seconds_total=5.0,
        latency_seconds_mean=1.0,
    )
    comparator = replace(policy, policy_id="head", repetition_scores=(0.2, 0.2, 0.2))
    return PairedPolicyDiagnosticResult(
        contract_sha256=contract_sha256,
        reference=policy,
        comparator=comparator,
        repetition_deltas=(0.6, 0.6, 0.6),
        paired_mean_delta=0.6,
        bootstrap_lower_95=0.3,
        bootstrap_upper_95=0.8,
        worst_case_paired_delta=0.6,
        reference_better_count=24,
        comparator_better_count=0,
        tied_count=16,
        exact_p_value=0.0,
        prior_item_flip_upper_95=0.1650387736914096,
        task_reader_calls=240,
        total_reader_calls=249,
        semantic_canary_passed=True,
        input_usage_stable=True,
        output_usage_stable=True,
        observed_model_stable=True,
        anchor_summaries=(),
        private_ledger_sha256="9" * 64,
        failures=(),
        diagnostic_passed=True,
    )


def test_cli_locks_the_public_schedule(script: ModuleType) -> None:
    args = script._parser().parse_args(
        ["--output-dir", "unused", "--private-evaluator-dir", "/tmp/private-unused"]
    )

    assert args.output_dir == Path("unused")
    for forbidden in (
        "max_items",
        "repetitions",
        "pack_tokens",
        "minimum_mean_delta",
        "maximum_policy_instability",
    ):
        assert not hasattr(args, forbidden)


def test_producer_attestation_covers_script_sources_and_preregistration(
    script: ModuleType,
) -> None:
    package_sources = {
        path.relative_to(script._REPO_ROOT)
        for path in (script._REPO_ROOT / "src" / "rsicontext").rglob("*.py")
    }

    assert package_sources <= set(script._PRODUCER_FILES)
    assert Path("scripts/hy3_paired_signal_diagnostic.py") in script._PRODUCER_FILES
    assert script._PREREGISTRATION in script._PRODUCER_FILES


def test_main_wires_private_ledger_and_publishes_only_aggregate_result(
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_compilation(script, monkeypatch)
    output = tmp_path / "paired"
    private = tmp_path / "private-paired"
    monkeypatch.setattr(script, "_PUBLIC_RESULTS_ROOT", tmp_path)
    real_builder = script.build_paired_policy_diagnostic_contract

    def build(**kwargs: object) -> PairedPolicyDiagnosticContract:
        assert kwargs["task_id"] == "helmet-rag-popqa-k1000-to-8192-token-pack/lexical-vs-head"
        assert kwargs["reader_max_output_tokens"] == 64
        kwargs["producer_git_revision"] = None
        kwargs["producer_attestation_sha256"] = None
        kwargs["test_transport_allowed"] = True
        return cast(PairedPolicyDiagnosticContract, real_builder(**kwargs))

    def run(
        contract: PairedPolicyDiagnosticContract, **kwargs: object
    ) -> PairedPolicyDiagnosticResult:
        assert kwargs["private_ledger_path"] == private / "private_evaluator_ledger.json"
        assert kwargs["persisted_contract_path"] == output / "run_contract.json"
        assert kwargs["persisted_producer_attestation_path"] == (
            output / "producer_attestation.json"
        )
        return _passing_result(contract.contract_sha256)

    monkeypatch.setattr(script, "build_paired_policy_diagnostic_contract", build)
    monkeypatch.setattr(script, "run_paired_policy_diagnostic", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            SCRIPT_PATH.name,
            "--output-dir",
            str(output),
            "--private-evaluator-dir",
            str(private),
        ],
    )

    assert script.main() == 0
    payload = json.loads((output / "diagnostic_result.json").read_text(encoding="utf-8"))
    assert payload["diagnostic_passed"] is True
    assert payload["rsi_launch_eligible"] is False
    assert "item_outcomes" not in payload
    assert (output / "run_contract.json").is_file()
    assert (output / "producer_attestation.json").is_file()


def test_main_refuses_to_overwrite_existing_output(
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    monkeypatch.setattr(script, "_PUBLIC_RESULTS_ROOT", tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            SCRIPT_PATH.name,
            "--output-dir",
            str(output),
            "--private-evaluator-dir",
            str(tmp_path / "private"),
        ],
    )

    with pytest.raises(FileExistsError, match="already exists"):
        script.main()


def test_run_directories_reject_symlink_and_repository_private_paths(
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(script, "_PUBLIC_RESULTS_ROOT", tmp_path)
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(RuntimeError, match="non-symlink"):
        script._prepare_run_directories(
            linked_parent / "public",
            tmp_path / "private",
        )
    with pytest.raises(RuntimeError, match="outside the repository"):
        script._prepare_run_directories(
            tmp_path / "public",
            script._REPO_ROOT / "private-evaluator-test",
        )
