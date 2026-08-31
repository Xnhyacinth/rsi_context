from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from rsicontext.eval import EvaluationItem
from rsicontext.experiment import OperationalReplayExecutionError, OperationalReplayResult
from rsicontext.policy import Artifact, DocumentChunk

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "hy3_popqa_replay.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hy3_popqa_replay_script_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hy3 PopQA replay script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


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


def _patch_main_compilation(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(SCRIPT, "producer_attestation", lambda *args, **kwargs: attestation)
    monkeypatch.setattr(SCRIPT, "require_clean_producer", lambda value: None)
    monkeypatch.setattr(SCRIPT, "require_stable_attestation", lambda before, after: None)
    monkeypatch.setattr(
        SCRIPT,
        "resolve_api_endpoint",
        lambda profile: SimpleNamespace(
            endpoint="https://copilot.tencent.com/v2/chat/completions", api_key="key"
        ),
    )
    monkeypatch.setattr(SCRIPT, "file_sha256", lambda path: SCRIPT._SOURCE_SHA256)
    monkeypatch.setattr(SCRIPT, "verify_tokenizer_snapshot", lambda path, files: "f" * 64)
    monkeypatch.setattr(SCRIPT, "_load_tokenizer", lambda path: object())
    monkeypatch.setattr(SCRIPT, "load_helmet_kilt_items", lambda *args, **kwargs: _items())
    monkeypatch.setattr(SCRIPT, "public_visible_items_fingerprint", lambda **kwargs: "a" * 64)


def test_cli_refuses_to_overwrite_an_existing_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    monkeypatch.setattr("sys.argv", ["hy3_popqa_replay.py", "--output-dir", str(output)])

    with pytest.raises(FileExistsError, match="already exists"):
        SCRIPT.main()


def test_policy_factories_are_named_and_fresh() -> None:
    assert set(SCRIPT._POLICIES) == {"head", "lexical", "middle", "tail"}
    for factory in SCRIPT._POLICIES.values():
        assert factory() is not factory()


def test_public_cli_locks_replay_minimums_and_thresholds() -> None:
    parser = SCRIPT._parser()
    args = parser.parse_args(["--output-dir", "unused"])

    assert args.max_items == 40
    assert args.repetitions == 5
    assert args.canary_repetitions == 3
    assert not hasattr(args, "max_score_standard_deviation")
    assert not hasattr(args, "max_item_flip_rate")


def test_producer_attestation_covers_all_loaded_package_sources() -> None:
    package_sources = {
        path.relative_to(SCRIPT._REPO_ROOT)
        for path in (SCRIPT._REPO_ROOT / "src" / "rsicontext").rglob("*.py")
    }

    assert package_sources <= set(SCRIPT._PRODUCER_FILES)
    assert Path("scripts/hy3_popqa_replay.py") in SCRIPT._PRODUCER_FILES


def test_main_wires_persisted_attestations_and_writes_aggregate_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_main_compilation(monkeypatch)
    output = tmp_path / "success"

    def run(contract: object, **kwargs: object) -> OperationalReplayResult:
        del contract
        assert kwargs["persisted_contract_path"] == output / "run_contract.json"
        assert kwargs["persisted_producer_attestation_path"] == (
            output / "producer_attestation.json"
        )
        assert isinstance(kwargs["persisted_contract_sha256"], str)
        return OperationalReplayResult(
            contract_sha256="b" * 64,
            reader_calls=209,
            aggregate_scores=(0.5,) * 5,
            score_standard_deviation=0.0,
            item_count=40,
            item_flip_count=0,
            item_flip_rate=0.0,
            item_flip_rate_upper_95=0.08762160119728664,
            semantic_canary_passed=True,
            raw_canary_answer_stable=True,
            input_usage_stable=True,
            output_usage_stable=True,
            observed_model_stable=True,
            anchor_summaries=(),
            item_replays=(),
            failures=(),
            operational_block_passed=True,
        )

    monkeypatch.setattr(SCRIPT, "run_operational_api_replay", run)
    monkeypatch.setattr("sys.argv", ["hy3_popqa_replay.py", "--output-dir", str(output)])

    assert SCRIPT.main() == 0
    payload = json.loads((output / "replay_result.json").read_text(encoding="utf-8"))
    assert payload["operational_block_passed"] is True
    assert payload["rsi_launch_eligible"] is False
    assert "item_replays" not in payload
    assert (output / "producer_attestation.json").is_file()
    assert (output / "run_contract.json").is_file()


def test_main_failure_preserves_endpoint_call_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_main_compilation(monkeypatch)
    output = tmp_path / "failure"

    def fail(contract: object, **kwargs: object) -> OperationalReplayResult:
        del contract, kwargs
        raise OperationalReplayExecutionError(7, 6, "task-replay-0", TimeoutError("secret"))

    monkeypatch.setattr(SCRIPT, "run_operational_api_replay", fail)
    monkeypatch.setattr("sys.argv", ["hy3_popqa_replay.py", "--output-dir", str(output)])

    with pytest.raises(OperationalReplayExecutionError):
        SCRIPT.main()

    payload = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert payload["attempted_reader_calls"] == 7
    assert payload["completed_transport_calls"] == 6
    assert payload["error_phase"] == "task-replay-0"
    assert payload["error_type"] == "TimeoutError"
    assert "secret" not in json.dumps(payload)


@pytest.mark.parametrize("drift", ["source", "tokenizer"])
def test_main_rejects_compilation_input_drift_before_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    drift: str,
) -> None:
    _patch_main_compilation(monkeypatch)
    output = tmp_path / drift
    if drift == "source":
        source_hashes = iter((SCRIPT._SOURCE_SHA256, "0" * 64))
        monkeypatch.setattr(SCRIPT, "file_sha256", lambda path: next(source_hashes))
    else:
        tokenizer_hashes = iter(("f" * 64, "e" * 64))
        monkeypatch.setattr(
            SCRIPT,
            "verify_tokenizer_snapshot",
            lambda path, files: next(tokenizer_hashes),
        )
    monkeypatch.setattr(
        SCRIPT,
        "run_operational_api_replay",
        lambda *args, **kwargs: pytest.fail("endpoint replay must not start after input drift"),
    )
    monkeypatch.setattr("sys.argv", ["hy3_popqa_replay.py", "--output-dir", str(output)])

    with pytest.raises(RuntimeError, match="during item compilation"):
        SCRIPT.main()

    assert output.exists() is False
