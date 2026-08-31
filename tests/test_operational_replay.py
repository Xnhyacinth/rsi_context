from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.eval import EvaluationItem, extractive_span_match
from rsicontext.experiment import load_api_profiles
from rsicontext.experiment.operational_replay import (
    OperationalReplayContract,
    OperationalReplayExecutionError,
    build_operational_replay_contract,
    operational_record_sha256,
    run_operational_api_replay,
    write_operational_record,
    write_operational_replay_contract,
    write_operational_replay_result,
)
from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk, LexicalPolicy

ROOT = Path(__file__).parents[1]


class _AbstainingPolicy:
    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        del artifact, query, budget
        return ContextPack(abstain=True)


def _item(item_id: str, query: str, answer: str) -> EvaluationItem:
    text = f"The supported answer is {answer}."
    chunk = DocumentChunk(f"chunk-{item_id}", item_id, 0, len(text), text, 7)
    return EvaluationItem(item_id, query, answer, Artifact(item_id, (chunk,)))


def _stream(answer: str, *, response_id: str, prompt_tokens: int) -> bytes:
    event = {
        "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
        "id": response_id,
        "model": "hy3-ioa",
        "usage": {
            "completion_tokens": 3 if answer.endswith(".") else 2,
            "prompt_tokens": prompt_tokens,
        },
    }
    return f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()


def _contract(items: tuple[EvaluationItem, ...]) -> OperationalReplayContract:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    return build_operational_replay_contract(
        task_id="popqa-replay-test",
        dataset_fingerprint="a" * 64,
        items=items,
        profile=profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        token_axis_id="test-token-axis-v1",
        source_id="test-source",
        source_revision="b" * 40,
        source_sha256="c" * 64,
        repetitions=3,
        canary_repetitions=2,
        max_score_standard_deviation=0.0,
        max_item_flip_rate=0.0,
        test_transport_allowed=True,
    )


def test_operational_replay_uses_scorer_stability_not_raw_punctuation() -> None:
    items = (
        _item("one", "What is the supported answer?", "Ottawa"),
        _item("two", "What is the other supported answer?", "Paris"),
    )
    contract = _contract(items)
    calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        payload = json.loads(cast(bytes, request.data))
        query = str(payload["messages"][-1]["content"])
        calls[0] += 1
        if "canary code" in query:
            answer = "amber." if calls[0] % 2 else "amber"
            return _stream(answer, response_id=f"canary-{calls[0]}", prompt_tokens=67)
        if "other supported" in query:
            return _stream("Paris.", response_id=f"task-{calls[0]}", prompt_tokens=90)
        return _stream("Ottawa", response_id=f"task-{calls[0]}", prompt_tokens=80)

    tick = [0.0]

    def timer() -> float:
        tick[0] += 0.1
        return tick[0]

    result = run_operational_api_replay(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        transport=transport,
        timer=timer,
    )

    assert calls[0] == 12
    assert result.reader_calls == contract.max_reader_calls == 12
    assert result.aggregate_scores == (1.0, 1.0, 1.0)
    assert result.score_standard_deviation == 0.0
    assert result.item_flip_rate == 0.0
    assert result.semantic_canary_passed is True
    assert result.raw_canary_answer_stable is False
    assert result.input_usage_stable is True
    assert result.output_usage_stable is False
    assert result.observed_model_stable is True
    assert result.operational_block_passed is True
    assert "secret-value" not in json.dumps(result.to_dict())
    assert "item_replays" not in result.to_dict()
    assert tuple(anchor.phase for anchor in result.anchor_summaries) == ("pre", "mid", "post")
    assert result.item_flip_count == 0
    assert result.item_flip_rate_upper_95 > 0.0
    assert result.rsi_launch_eligible is False


def test_operational_replay_fails_on_task_level_score_flip() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)
    task_calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        payload = json.loads(cast(bytes, request.data))
        query = str(payload["messages"][-1]["content"])
        if "canary code" in query:
            return _stream("amber.", response_id="canary", prompt_tokens=67)
        task_calls[0] += 1
        answer = "wrong" if task_calls[0] == 2 else "Ottawa"
        return _stream(answer, response_id=f"task-{task_calls[0]}", prompt_tokens=80)

    result = run_operational_api_replay(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        transport=transport,
    )

    assert result.aggregate_scores == (1.0, 0.0, 1.0)
    assert result.item_flip_rate == 1.0
    assert result.operational_block_passed is False
    assert "task score standard deviation exceeds contract" in result.failures
    assert "item score flip rate exceeds contract" in result.failures


def test_operational_replay_uses_canonical_canary_not_permissive_task_scorer() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        if b"canary code" in cast(bytes, request.data):
            return _stream("a", response_id="canary", prompt_tokens=67)
        return _stream("Ottawa", response_id="task", prompt_tokens=80)

    result = run_operational_api_replay(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        transport=transport,
    )

    assert result.semantic_canary_passed is False
    assert all(anchor.task_scorer_correct_count == 2 for anchor in result.anchor_summaries)
    assert all(anchor.canonical_correct_count == 0 for anchor in result.anchor_summaries)
    assert "canonical semantic canary failed" in result.failures


def test_operational_replay_rejects_contract_drift_before_api_call() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)
    calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del request, timeout
        calls[0] += 1
        return _stream("amber", response_id="unexpected", prompt_tokens=67)

    with pytest.raises(RuntimeError, match="dataset or item payload"):
        run_operational_api_replay(
            contract,
            items=(_item("changed", "Changed?", "Paris"),),
            profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
                "tencent-copilot-hy3-ioa"
            ),
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            transport=transport,
        )

    assert calls[0] == 0


def test_operational_replay_counts_failed_transport_attempt() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)
    calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del request, timeout
        calls[0] += 1
        if calls[0] == 2:
            raise TimeoutError("simulated timeout")
        return _stream("amber", response_id=f"response-{calls[0]}", prompt_tokens=67)

    with pytest.raises(OperationalReplayExecutionError) as error:
        run_operational_api_replay(
            contract,
            items=items,
            profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
                "tencent-copilot-hy3-ioa"
            ),
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            transport=transport,
        )

    assert calls[0] == 2
    assert error.value.attempted_reader_calls == 2
    assert error.value.completed_transport_calls == 1
    assert error.value.phase == "pre-canary"


def test_operational_replay_preserves_call_counts_on_postprocessing_failure() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = build_operational_replay_contract(
        task_id="abstain-ledger-test",
        dataset_fingerprint="a" * 64,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        policy_factory=_AbstainingPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        token_axis_id="test-token-axis-v1",
        source_id="test-source",
        source_revision="b" * 40,
        source_sha256="c" * 64,
        repetitions=3,
        canary_repetitions=2,
        max_score_standard_deviation=0.0,
        max_item_flip_rate=0.0,
        test_transport_allowed=True,
    )

    with pytest.raises(OperationalReplayExecutionError) as error:
        run_operational_api_replay(
            contract,
            items=items,
            profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
                "tencent-copilot-hy3-ioa"
            ),
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=_AbstainingPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            transport=lambda request, timeout: _stream(
                "amber", response_id="canary", prompt_tokens=67
            ),
        )

    assert error.value.attempted_reader_calls == 6
    assert error.value.completed_transport_calls == 6
    assert error.value.phase == "result-reconciliation"


def test_operational_replay_guard_runs_around_every_transport() -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)
    guard_calls = [0]

    def guard() -> None:
        guard_calls[0] += 1
        if guard_calls[0] == 3:
            raise RuntimeError("contract changed")

    with pytest.raises(OperationalReplayExecutionError) as error:
        run_operational_api_replay(
            contract,
            items=items,
            profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
                "tencent-copilot-hy3-ioa"
            ),
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            transport=lambda request, timeout: _stream(
                "amber", response_id="response", prompt_tokens=67
            ),
            test_contract_guard=guard,
        )

    assert error.value.attempted_reader_calls == 1
    assert error.value.completed_transport_calls == 1
    assert error.value.phase == "pre-canary"


def test_public_operational_replay_rejects_custom_transport_before_call() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    items = tuple(_item(f"item-{index}", f"Question {index}?", "Ottawa") for index in range(40))
    contract = build_operational_replay_contract(
        task_id="public-custom-transport-test",
        dataset_fingerprint="a" * 64,
        items=items,
        profile=profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        token_axis_id="test-token-axis-v1",
        source_id="test-source",
        source_revision="b" * 40,
        source_sha256="c" * 64,
        repetitions=5,
        canary_repetitions=3,
        max_score_standard_deviation=0.0,
        max_item_flip_rate=0.0,
        producer_git_revision="d" * 40,
        producer_attestation_sha256="e" * 64,
    )
    calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del request, timeout
        calls[0] += 1
        return _stream("amber", response_id="response", prompt_tokens=67)

    with pytest.raises(RuntimeError, match="custom transport"):
        run_operational_api_replay(
            contract,
            items=items,
            profile=profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            transport=transport,
        )

    assert calls[0] == 0


def test_public_operational_replay_contract_enforces_qualification_minimums() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    items = tuple(_item(f"item-{index}", f"Question {index}?", "Ottawa") for index in range(40))

    with pytest.raises(ValueError, match="at least five task replays"):
        build_operational_replay_contract(
            task_id="public-minimum-test",
            dataset_fingerprint="a" * 64,
            items=items,
            profile=profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
            token_axis_id="test-token-axis-v1",
            source_id="test-source",
            source_revision="b" * 40,
            source_sha256="c" * 64,
            repetitions=3,
            canary_repetitions=3,
            max_score_standard_deviation=0.0,
            max_item_flip_rate=0.0,
        )


def test_public_operational_replay_requires_internal_file_attestation() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    items = tuple(_item(f"item-{index}", f"Question {index}?", "Ottawa") for index in range(40))
    contract = build_operational_replay_contract(
        task_id="public-attestation-test",
        dataset_fingerprint="a" * 64,
        items=items,
        profile=profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        token_axis_id="test-token-axis-v1",
        source_id="test-source",
        source_revision="b" * 40,
        source_sha256="c" * 64,
        repetitions=5,
        canary_repetitions=3,
        max_score_standard_deviation=0.0,
        max_item_flip_rate=0.0,
        producer_git_revision="d" * 40,
        producer_attestation_sha256="e" * 64,
    )

    with pytest.raises(RuntimeError, match="persisted contract attestation"):
        run_operational_api_replay(
            contract,
            items=items,
            profile=profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            policy_factory=LexicalPolicy,
            scorer=extractive_span_match,
            budget=Budget(64),
        )


def test_operational_replay_contract_and_result_writes_are_exclusive(tmp_path: Path) -> None:
    items = (_item("one", "What is the supported answer?", "Ottawa"),)
    contract = _contract(items)
    contract_path = tmp_path / "contract.json"

    write_operational_replay_contract(contract, contract_path)

    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    assert payload["evidence_tier"] == "non-public-test-transport-v1"
    assert payload["qualification_only"] is True
    assert payload["token_axis_id"] == "test-token-axis-v1"
    assert payload["max_reader_calls"] == 9
    with pytest.raises(FileExistsError):
        write_operational_replay_contract(contract, contract_path)

    result = run_operational_api_replay(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        policy_factory=LexicalPolicy,
        scorer=extractive_span_match,
        budget=Budget(64),
        transport=lambda request, timeout: _stream(
            "amber" if b"canary" in cast(bytes, request.data) else "Ottawa",
            response_id="response",
            prompt_tokens=67,
        ),
    )
    result_path = tmp_path / "result.json"
    write_operational_replay_result(result, result_path)
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["operational_block_passed"] is True
    assert "item_replays" not in result_payload
    with pytest.raises(FileExistsError):
        write_operational_replay_result(result, result_path)


def test_operational_record_write_is_atomic_before_serialization(tmp_path: Path) -> None:
    path = tmp_path / "record.json"

    with pytest.raises(TypeError):
        write_operational_record({"not_json": object()}, path)

    assert path.exists() is False
    payload = {"stable": True}
    write_operational_record(payload, path)
    assert operational_record_sha256(payload) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_operational_record_rolls_back_after_directory_sync_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "record.json"
    real_fsync = os.fsync
    calls = [0]

    def fail_directory_sync(descriptor: int) -> None:
        calls[0] += 1
        if calls[0] == 2:
            raise OSError("simulated directory sync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_directory_sync)

    with pytest.raises(OSError, match="directory sync"):
        write_operational_record({"stable": True}, path)

    assert path.exists() is False
    assert tuple(tmp_path.iterdir()) == ()
