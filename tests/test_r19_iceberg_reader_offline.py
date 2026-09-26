"""Synthetic-only admission chain and named R19 failure behavior."""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest

from rsicontext.analysis.iceberg_fixed_reader_r19 import RULE_BUNDLES

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import r19_iceberg_reader_offline as reader  # noqa: E402

_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake")
_TOKENIZER = Path("/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b")


@pytest.fixture(scope="module", autouse=True)
def optional_runtime() -> None:
    if not _SOURCE.is_dir() or not _TOKENIZER.is_dir():
        pytest.skip("pinned Iceberg source or tokenizer unavailable")
    if importlib.util.find_spec("transformers") is None:
        pytest.skip("run with pinned optional tokenizer-only runtime for R19 synthetic chain")


def _run(tmp_path: Path, fault: str | None = None) -> tuple[dict[str, object], Path]:
    run_dir = tmp_path / "private-run"
    return (
        reader.run_offline_screen(
            source_root=_SOURCE,
            tokenizer_root=_TOKENIZER,
            run_dir=run_dir,
            fault=fault,
        ),
        run_dir,
    )


def _journal(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_full_synthetic_chain_is_private_and_preserves_control_shortcuts(tmp_path: Path) -> None:
    result, run_dir = _run(tmp_path)
    assert result["status"] == "completed-synthetic-screen"
    assert result["provider_usage_total"] is None
    assert result["qualified_parent"] is False
    assert result["live_ready"] is False
    assert result["attempted_http_calls"] == result["synthetic_transport_calls"] == 10
    assert result["task_http_calls"] == 8
    assert result["canary_http_calls"] == 2
    assert result["auxiliary_calls"] == 0
    usage = result["synthetic_usage"]
    assert isinstance(usage, dict) and usage["unknown_usage_attempts"] == 0
    task = json.loads((run_dir / "task.json").read_text())
    assert [item["case"] for item in task["cases"]] == list(reader.CASE_ORDER)
    assert task["executed_arms"] == list(reader.CASE_ORDER)
    assert [item["session_passed"] for item in task["cases"]] == [
        [True, True],
        [True, True],
        [True, True],
        [True, True],
    ]
    assert [item["source_rule_extraction_matches_oracle"] for item in task["cases"]] == [
        True,
        True,
        None,
        None,
    ]
    assert [item["control_prior_rule_match"] for item in task["cases"]] == [
        None,
        None,
        False,
        False,
    ]
    assert [item["control_shortcut_completion"] for item in task["cases"]] == [
        None,
        None,
        True,
        True,
    ]
    assert all(item["s2_plan_correct"] is True for item in task["cases"])
    assert [item["observed_s1_carry"] for item in task["cases"]] == [
        {"rule": RULE_BUNDLES[0]},
        {"rule": RULE_BUNDLES[1]},
        {"rule": RULE_BUNDLES[2]},
        {"rule": RULE_BUNDLES[2]},
    ]
    attempts = task["attempts"]
    assert len(attempts) == 8
    assert all(isinstance(item.get("reply"), str) for item in attempts)
    assert all(item.get("provider_usage") is not None for item in attempts)
    assert all(item.get("response_model") == "Qwen/Qwen3.6-27B" for item in attempts)
    assert all(item.get("finish_reason") == "stop" for item in attempts)
    events = _journal(run_dir / "attempts.jsonl")
    assert len(events) == 20
    assert [event["event"] for event in events] == [
        value for _ in range(10) for value in ("dispatched", "response-received")
    ]
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    contents = "".join(path.read_text() for path in run_dir.iterdir())
    assert "synthetic-only-key" not in contents
    assert "Authorization" not in contents
    assert "Bearer " not in contents


def test_mixed_s1_stops_before_s2_and_controls(tmp_path: Path) -> None:
    result, run_dir = _run(tmp_path, "mixed-first")
    assert result["status"] == "task-failed"
    assert result["task_http_calls"] == 1
    assert result["canary_http_calls"] == 1
    assert not (run_dir / "post_canary.json").exists()
    task = json.loads((run_dir / "task.json").read_text())
    assert [case["case"] for case in task["cases"]] == ["authentic-pack"]
    assert task["executed_arms"] == ["authentic-pack"]
    assert task["cases"][0]["failure_type"] == "InvalidReaderReply"
    assert task["cases"][0]["source_rule_extraction_matches_oracle"] is None
    assert len(task["attempts"]) == 1


def test_missing_usage_remains_unknown_and_stops(tmp_path: Path) -> None:
    result, run_dir = _run(tmp_path, "missing-usage-first")
    assert result["status"] == "usage-unverified"
    assert result["task_http_calls"] == 1
    assert result["provider_usage_total"] is None
    usage = result["synthetic_usage"]
    assert isinstance(usage, dict) and usage["unknown_usage_attempts"] == 1
    assert not (run_dir / "post_canary.json").exists()
    events = _journal(run_dir / "attempts.jsonl")
    assert events[-1]["event"] == "response-received"
    assert events[-1]["provider_usage"] is None


def test_wrong_coherent_s1_is_scored_without_censoring_controls(tmp_path: Path) -> None:
    result, run_dir = _run(tmp_path, "authentic-wrong")
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_http_calls"] == 8
    task = json.loads((run_dir / "task.json").read_text())
    assert [case["case"] for case in task["cases"]] == list(reader.CASE_ORDER)
    first = task["cases"][0]
    assert first["session_passed"] == [True, False]
    assert first["source_rule_extraction_matches_oracle"] is False
    assert first["s2_plan_correct"] is False
    assert first["observed_s1_carry"] == {"rule": RULE_BUNDLES[1]}
    assert len(task["attempts"]) == 8
