from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import cast

import pytest

import rsicontext.experiment.paired_diagnostic as paired_module
from rsicontext.eval import EvaluationItem, extractive_span_match
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment import OperationalReplayExecutionError, load_api_profiles
from rsicontext.experiment.paired_diagnostic import (
    PairedPolicyDiagnosticContract,
    build_paired_policy_diagnostic_contract,
    paired_call_schedule,
    run_paired_policy_diagnostic,
)
from rsicontext.policy import Artifact, Budget, DocumentChunk, LexicalPolicy, TruncationPolicy

ROOT = Path(__file__).parents[1]


def _head_policy() -> TruncationPolicy:
    return TruncationPolicy("head")


def _item(index: int) -> EvaluationItem:
    answer = f"answer-{index}"
    head_text = f"HEAD_CONTEXT_{index} is unrelated."
    lexical_text = f"querytoken-{index} LEXICAL_CONTEXT_{index} supports {answer}."
    chunks = (
        DocumentChunk(f"head-{index}", "doc", 0, len(head_text), head_text, 8),
        DocumentChunk(
            f"lexical-{index}",
            "doc",
            len(head_text),
            len(head_text) + len(lexical_text),
            lexical_text,
            8,
        ),
    )
    return EvaluationItem(
        f"item-{index}",
        f"What is querytoken-{index}?",
        answer,
        Artifact("doc", chunks),
    )


def _contract(
    items: tuple[EvaluationItem, ...],
    *,
    prior_upper: float = 0.2,
    minimum_mean_delta: float = 0.5,
    maximum_exact_p_value: float = 1.0,
) -> PairedPolicyDiagnosticContract:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    return build_paired_policy_diagnostic_contract(
        task_id="paired-test",
        dataset_fingerprint="a" * 64,
        items=items,
        profile=profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        reference_policy_id="lexical",
        reference_policy_factory=LexicalPolicy,
        comparator_policy_id="head",
        comparator_policy_factory=_head_policy,
        scorer=extractive_span_match,
        budget=Budget(8),
        token_axis_id="test-axis",
        source_id="test-source",
        source_revision="b" * 40,
        source_sha256="c" * 64,
        preregistration_sha256="d" * 64,
        prior_result_sha256="e" * 64,
        prior_contract_sha256="f" * 64,
        prior_item_flip_rate=0.05,
        prior_item_flip_upper_95=prior_upper,
        repetitions=3,
        canary_repetitions=2,
        schedule_seed=1729,
        bootstrap_seed=20260831,
        bootstrap_samples=1000,
        minimum_mean_delta=minimum_mean_delta,
        maximum_policy_instability=0.1,
        maximum_exact_p_value=maximum_exact_p_value,
        test_transport_allowed=True,
    )


def _stream(answer: str, *, response_id: str, prompt_tokens: int) -> bytes:
    event = {
        "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
        "id": response_id,
        "model": "hy3-ioa",
        "usage": {"completion_tokens": 2, "prompt_tokens": prompt_tokens},
    }
    return f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()


def test_paired_schedule_is_deterministic_balanced_and_interleaved() -> None:
    schedule = paired_call_schedule(item_count=5, repetitions=3, seed=1729)

    assert schedule == paired_call_schedule(item_count=5, repetitions=3, seed=1729)
    assert schedule != paired_call_schedule(item_count=5, repetitions=3, seed=1730)
    assert len(schedule) == 30
    assert {(call.repetition, call.item_index, call.policy_id) for call in schedule} == {
        (repeat, item, policy) for repeat in range(3) for item in range(5) for policy in (0, 1)
    }
    for offset in range(0, len(schedule), 2):
        pair = schedule[offset : offset + 2]
        assert pair[0].repetition == pair[1].repetition
        assert pair[0].item_index == pair[1].item_index
        assert {pair[0].policy_id, pair[1].policy_id} == {0, 1}


def test_paired_diagnostic_runs_matched_calls_and_aggregate_statistics(tmp_path: Path) -> None:
    items = (_item(0), _item(1))
    contract = _contract(items)
    task_context_order: list[str] = []
    event_order: list[str] = []
    calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        payload = json.loads(cast(bytes, request.data))
        content = str(payload["messages"][-1]["content"])
        calls[0] += 1
        if "canary code" in content:
            event_order.append("canary")
            return _stream("amber", response_id=f"canary-{calls[0]}", prompt_tokens=67)
        event_order.append("task")
        task_context_order.append(content)
        for index in range(2):
            if f"LEXICAL_CONTEXT_{index}" in content:
                return _stream(f"answer-{index}", response_id=f"task-{calls[0]}", prompt_tokens=80)
            if f"HEAD_CONTEXT_{index}" in content:
                return _stream("wrong", response_id=f"task-{calls[0]}", prompt_tokens=80)
        raise AssertionError("unexpected task context")

    tick = [0.0]

    def timer() -> float:
        tick[0] += 0.1
        return tick[0]

    result = run_paired_policy_diagnostic(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        reference_policy_factory=LexicalPolicy,
        comparator_policy_factory=_head_policy,
        scorer=extractive_span_match,
        budget=Budget(8),
        transport=transport,
        timer=timer,
        private_ledger_path=tmp_path / "private-ledger.json",
    )

    assert calls[0] == contract.max_reader_calls == 18
    assert len(task_context_order) == 12
    assert (
        event_order
        == ["canary"] * 2 + ["task"] * 6 + ["canary"] * 2 + ["task"] * 6 + ["canary"] * 2
    )
    assert result.reference.repetition_scores == (1.0, 1.0, 1.0)
    assert result.comparator.repetition_scores == (0.0, 0.0, 0.0)
    assert result.paired_mean_delta == 1.0
    assert result.bootstrap_lower_95 == 1.0
    assert result.bootstrap_upper_95 == 1.0
    assert result.reference.unstable_item_count == 0
    assert result.reference.unstable_item_rate == 0.0
    assert result.comparator.unstable_item_count == 0
    assert result.worst_case_paired_delta == 1.0
    assert result.reference_better_count == 2
    assert result.comparator_better_count == 0
    assert result.exact_p_value == 0.5
    assert result.task_reader_calls == 12
    assert result.total_reader_calls == 18
    assert result.diagnostic_passed is True
    assert result.rsi_launch_eligible is False
    assert len(result.private_ledger_sha256) == 64
    assert (tmp_path / "private-ledger.json").is_file()
    private_payload = json.loads((tmp_path / "private-ledger.json").read_text(encoding="utf-8"))
    assert private_payload["anchor_calls"]["pre"]["endpoint_sha256"]
    assert "endpoint" not in private_payload["anchor_calls"]["pre"]
    assert (tmp_path / "private-ledger.json").stat().st_mode & 0o777 == 0o600
    public_payload = json.dumps(result.to_dict())
    for forbidden in ("item_ids", "item_outcomes", "predictions", "schedule"):
        assert forbidden not in public_payload


def test_comparator_instability_invalidates_the_diagnostic(tmp_path: Path) -> None:
    items = (_item(0), _item(1))
    contract = _contract(items)
    head_calls = [0]

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        payload = json.loads(cast(bytes, request.data))
        content = str(payload["messages"][-1]["content"])
        if "canary code" in content:
            return _stream("amber", response_id="canary", prompt_tokens=67)
        if "LEXICAL_CONTEXT" in content:
            index = 0 if "LEXICAL_CONTEXT_0" in content else 1
            return _stream(f"answer-{index}", response_id="lexical", prompt_tokens=80)
        index = 0 if "HEAD_CONTEXT_0" in content else 1
        head_calls[0] += 1
        answer = f"answer-{index}" if head_calls[0] == 1 else "wrong"
        return _stream(answer, response_id="head", prompt_tokens=80)

    result = run_paired_policy_diagnostic(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        reference_policy_factory=LexicalPolicy,
        comparator_policy_factory=_head_policy,
        scorer=extractive_span_match,
        budget=Budget(8),
        transport=transport,
        private_ledger_path=tmp_path / "private-ledger.json",
    )

    assert result.comparator.unstable_item_count == 1
    assert result.comparator.unstable_item_rate == 0.5
    assert result.worst_case_paired_delta == 0.0
    assert "comparator unstable-item rate exceeds the preregistered maximum" in result.failures
    assert "worst-case policy delta does not exceed the replay sensitivity bound" in result.failures
    assert result.diagnostic_passed is False


def test_effect_point_estimate_cannot_substitute_for_margin_lower_bound(
    tmp_path: Path,
) -> None:
    items = tuple(_item(index) for index in range(40))
    contract = _contract(
        items,
        prior_upper=0.1650387736914096,
        minimum_mean_delta=0.2,
        maximum_exact_p_value=0.05,
    )

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        assert request.data is not None
        payload = json.loads(cast(bytes, request.data))
        content = str(payload["messages"][-1]["content"])
        if "canary code" in content:
            return _stream("amber", response_id="canary", prompt_tokens=67)
        match = re.search(r"(?:LEXICAL|HEAD)_CONTEXT_(\d+)", content)
        assert match is not None
        index = int(match.group(1))
        answer = f"answer-{index}" if "LEXICAL_CONTEXT" in content and index < 8 else "wrong"
        return _stream(answer, response_id="task", prompt_tokens=80)

    result = run_paired_policy_diagnostic(
        contract,
        items=items,
        profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
            "tencent-copilot-hy3-ioa"
        ),
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        reference_policy_factory=LexicalPolicy,
        comparator_policy_factory=_head_policy,
        scorer=extractive_span_match,
        budget=Budget(8),
        transport=transport,
        private_ledger_path=tmp_path / "private-ledger.json",
    )

    assert result.paired_mean_delta == 0.2
    assert result.exact_p_value == pytest.approx(0.0078125)
    assert result.bootstrap_lower_95 < contract.prior_item_flip_upper_95
    assert (
        "paired bootstrap lower bound does not exceed the replay sensitivity bound"
        in result.failures
    )
    assert result.diagnostic_passed is False


def test_public_paired_contract_locks_panel_repeats_and_thresholds() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    items = tuple(_item(index) for index in range(40))

    with pytest.raises(ValueError, match="exactly three repetitions"):
        build_paired_policy_diagnostic_contract(
            task_id="public-invalid",
            dataset_fingerprint="a" * 64,
            items=items,
            profile=profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            reference_policy_id="lexical",
            reference_policy_factory=LexicalPolicy,
            comparator_policy_id="head",
            comparator_policy_factory=_head_policy,
            scorer=extractive_span_match,
            budget=Budget(8),
            token_axis_id="test-axis",
            source_id="test-source",
            source_revision="b" * 40,
            source_sha256="c" * 64,
            preregistration_sha256="d" * 64,
            prior_result_sha256="e" * 64,
            prior_contract_sha256="f" * 64,
            prior_item_flip_rate=0.05,
            prior_item_flip_upper_95=0.1650387736914096,
            repetitions=2,
            canary_repetitions=3,
            schedule_seed=1729,
            bootstrap_seed=20260831,
            bootstrap_samples=10_000,
            minimum_mean_delta=0.2,
            maximum_policy_instability=0.1,
            maximum_exact_p_value=0.05,
            producer_git_revision="1" * 40,
            producer_attestation_sha256="2" * 64,
        )


def test_public_contract_rejects_a_self_consistent_but_unregistered_panel() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    with pytest.raises(ValueError, match="experiment identity is locked"):
        build_paired_policy_diagnostic_contract(
            task_id="arbitrary-public-task",
            dataset_fingerprint="a" * 64,
            items=tuple(_item(index) for index in range(40)),
            profile=profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            reference_policy_id="lexical",
            reference_policy_factory=LexicalPolicy,
            comparator_policy_id="head",
            comparator_policy_factory=_head_policy,
            scorer=extractive_span_match,
            budget=Budget(8),
            token_axis_id="arbitrary-axis",
            source_id="arbitrary-source",
            source_revision="b" * 40,
            source_sha256="c" * 64,
            preregistration_sha256="d" * 64,
            prior_result_sha256=(
                "23cb05483f4023be803765ab966875d8c5c91b496767b034c3c85e6bc35271e7"
            ),
            prior_contract_sha256=(
                "a3eb98fd0a97ff4f0860ec39bb73944ee211d95c63b3ae1990d7a5d8d2c960c2"
            ),
            prior_item_flip_rate=0.05,
            prior_item_flip_upper_95=0.1650387736914096,
            repetitions=3,
            canary_repetitions=3,
            schedule_seed=1729,
            bootstrap_seed=20260831,
            bootstrap_samples=10_000,
            minimum_mean_delta=0.2,
            maximum_policy_instability=0.1,
            maximum_exact_p_value=0.05,
            reader_max_output_tokens=64,
            producer_git_revision="1" * 40,
            producer_attestation_sha256="2" * 64,
        )


def test_reader_call_cap_is_checked_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = (_item(0), _item(1))
    contract = _contract(items)

    def overrun_canary(*args: object, **kwargs: object) -> None:
        del args
        transport = cast(Transport, kwargs["transport"])
        request = urllib.request.Request("https://copilot.tencent.com/v2/chat/completions")
        for _ in range(contract.max_reader_calls + 1):
            transport(request, 30.0)

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        del request, timeout
        return b""

    monkeypatch.setattr(paired_module, "run_api_canary", overrun_canary)
    with pytest.raises(OperationalReplayExecutionError) as raised:
        run_paired_policy_diagnostic(
            contract,
            items=items,
            profile=load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
                "tencent-copilot-hy3-ioa"
            ),
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reference_policy_factory=LexicalPolicy,
            comparator_policy_factory=_head_policy,
            scorer=extractive_span_match,
            budget=Budget(8),
            transport=transport,
            private_ledger_path=tmp_path / "private-ledger.json",
        )

    assert raised.value.attempted_reader_calls == contract.max_reader_calls
    assert raised.value.completed_transport_calls == contract.max_reader_calls
    assert raised.value.cause_type == "RuntimeError"
