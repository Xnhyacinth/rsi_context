"""The OTel development pilot accounts for every bounded worker request."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest

from rsicontext.analysis.otel_model_screen import FakeAttributeWorker
from rsicontext.analysis.otel_siflow_pilot import _case_specs, run_development_pilot
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint
from rsicontext.lifecycle.material_otel_source_contrast import (
    build_otel_source_contrast_sessions,
)
from rsicontext.lifecycle.spec import LifecycleInstance

_PROFILE = APIProfile(
    id="siflow-qwen3.6-27b-r12-otel-dev-2048",
    provider="Siflow",
    endpoint_env="SIFLOW_BASE_URL",
    api_key_env="SIFLOW_API_KEY",
    allowed_host="api.siflow.cn",
    model="Qwen/Qwen3.6-27B",
    protocol="chat-completions-sse",
    evaluation_max_model_len=262144,
    max_output_tokens=2048,
    seed=42,
    temperature=0.0,
    provider_revision=None,
    chat_template_enable_thinking=False,
    system_prompt=(
        "You are the project worker. Follow the requested output format exactly. "
        "For questions, return only the answer phrase."
    ),
)
_ENDPOINT = ResolvedAPIEndpoint("https://api.siflow.cn/model-api/chat/completions", "test-key")


def _preflight(prompt: str) -> dict[str, object]:
    payload = {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": _PROFILE.max_output_tokens,
        "messages": [
            {"content": _PROFILE.system_prompt, "role": "system"},
            {"content": prompt, "role": "user"},
        ],
        "model": _PROFILE.model,
        "seed": _PROFILE.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
    }
    return {
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest(),
        "local_template_geometry": {"rendered_input_tokens": 10},
        "stage": "source-survey"
        if prompt.startswith("Read the complete")
        else "project-request-stage",
    }


def _stream(
    answer: str, *, prompt_tokens: int = 10, finish: str = "stop", model: str = _PROFILE.model
) -> bytes:
    payload = {
        "id": "fake-1",
        "model": model,
        "choices": [{"delta": {"content": answer}, "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 2},
    }
    return ("data: " + json.dumps(payload) + "\n\ndata: [DONE]\n\n").encode()


def _pair(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    variable = (
        "RSICONTEXT_OTEL124_SOURCE_ROOT"
        if revision == "1.24"
        else "RSICONTEXT_OTEL_SOURCE_ROOT"
    )
    configured = os.environ.get(variable)
    if not configured:
        pytest.skip(f"set {variable} to pinned detached checkout")
    return build_otel_source_contrast_sessions(Path(configured), revision=revision)


def _run(
    transport: Any,
    *,
    preflight: Any = _preflight,
    profile: APIProfile = _PROFILE,
) -> dict[str, object]:
    return run_development_pilot(
        _pair("1.24"),
        _pair("1.43"),
        profile=profile,
        endpoint=_ENDPOINT,
        preflight=preflight,
        transport=transport,
    )


def test_all_eight_fake_provider_trajectories_respect_cap() -> None:
    fake = FakeAttributeWorker()

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        if not isinstance(request.data, bytes):
            raise ValueError("missing request body")
        body = json.loads(request.data)
        return _stream(fake(body["messages"][1]["content"]))

    result = _run(transport)
    assert result["status"] == "completed-development-screen"
    assert result["worker_attempt_count"] == len(fake.prompts) <= 16
    assert result["worker_attempt_count"] <= cast(int, result["worker_attempt_cap"])
    cases = cast(list[dict[str, Any]], result["cases"])
    assert [case["case"] for case in cases] == [
        "full-124",
        "full-143",
        "withheld-124",
        "withheld-143",
        "swapped-124",
        "swapped-143",
        "recommended-row-removed-143",
        "empty-carry-no-reread-143",
    ]
    assert [case["session_passed"] for case in cases[:2]] == [[True, True], [True, True]]
    assert [case["session_passed"] for case in cases[2:4]] == [[True, False], [True, False]]
    assert cases[4]["final_plan"] == "db.query.text"
    assert cases[5]["final_plan"] == "db.statement"
    assert cases[6]["material_sha256"] == (
        "80fab68f70ce6d1542c5cfeb45b95b1e6cf6dbbfe4d67aadbb59f87dd9ccd97c"
    )
    deletion_attempts = cast(list[int], cases[6]["worker_attempt_indexes"])
    assert len(deletion_attempts) == 2
    attempts = cast(list[dict[str, object]], result["attempts"])
    assert [attempts[index]["stage"] for index in deletion_attempts] == [
        "source-survey",
        "source-survey",
    ]
    assert cases[7]["worker_attempt_indexes"] == [len(fake.prompts) - 1]
    usage = cast(dict[str, Any], result["provider_usage_total"])
    assert usage["input_tokens"] == len(fake.prompts) * 10
    assert usage["output_tokens"] == len(fake.prompts) * 2
    assert usage["unknown_usage_attempts"] == 0


def test_source_interventions_keep_later_request_and_private_oracle() -> None:
    older, newer = _pair("1.24"), _pair("1.43")
    cases = {name: sessions for name, sessions, _, _ in _case_specs(older, newer)}
    for name, reference in (
        ("swapped-124", older),
        ("swapped-143", newer),
        ("recommended-row-removed-143", newer),
    ):
        altered_first, altered_second = cases[name]
        assert altered_second is reference[1]
        assert altered_first.stages[1:] == reference[0].stages[1:]
        assert altered_first.axes == reference[0].axes
        assert altered_first.sandbox_spec == reference[0].sandbox_spec
        altered_source = altered_first.stages[0].documents[0]
        original_source = reference[0].stages[0].documents[0]
        assert altered_source.doc_id == original_source.doc_id
        assert altered_source.source_url == original_source.source_url
        assert altered_source.text != original_source.text
    deleted_source = cases["recommended-row-removed-143"][0].stages[0].documents[0].text
    assert "| [`db.query.text`]" not in deleted_source
    assert hashlib.sha256(deleted_source.encode()).hexdigest() == (
        "80fab68f70ce6d1542c5cfeb45b95b1e6cf6dbbfe4d67aadbb59f87dd9ccd97c"
    )


def test_full_case_failure_stops_before_other_cases() -> None:
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("attribute=db.query.text")

    result = _run(transport)
    assert result["status"] == "stopped-on-full-task-failure"
    assert len(cast(list[object], result["cases"])) == 1
    assert result["worker_attempt_count"] == calls == 2


def test_provider_prompt_mismatch_stops_and_keeps_usage() -> None:
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("attribute=db.statement", prompt_tokens=11)

    result = _run(transport)
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_count"] == calls == 1
    assert result["provider_usage_total"] == {
        "input_tokens": 11,
        "output_tokens": 2,
        "unknown_usage_attempts": 0,
    }


def test_non_stop_and_model_mismatch_keep_valid_usage() -> None:
    for response in (
        _stream("attribute=db.statement", finish="length"),
        _stream("attribute=db.statement", model="other-model"),
    ):
        result = _run(lambda request, timeout, raw=response: raw)
        assert result["status"] == "stopped-on-worker-failure"
        assert result["worker_attempt_count"] == 1
        assert result["provider_usage_total"] == {
            "input_tokens": 10,
            "output_tokens": 2,
            "unknown_usage_attempts": 0,
        }
        attempt = cast(list[dict[str, object]], result["attempts"])[0]
        assert attempt["response_model_observed"] == (
            "other-model" if b"other-model" in response else _PROFILE.model
        )


def test_malformed_response_counts_attempt_without_invented_usage() -> None:
    result = _run(lambda request, timeout: b"data: {bad-json}\n\ndata: [DONE]\n\n")
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_count"] == 1
    assert result["provider_usage_total"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "unknown_usage_attempts": 1,
    }


def test_preflight_failure_and_hash_mismatch_never_reach_network() -> None:
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("attribute=db.statement")

    def bad_hash(prompt: str) -> dict[str, object]:
        return {**_preflight(prompt), "prompt_sha256": "bad"}

    for preflight in (bad_hash, lambda prompt: 1 / 0):
        result = _run(transport, preflight=preflight)
        assert result["status"] == "stopped-on-worker-failure"
        assert result["worker_attempt_count"] == 0
        assert len(cast(list[object], result["preflight_failures"])) == 1
    assert calls == 0


def test_global_cap_counts_failed_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rsicontext.analysis.otel_siflow_pilot.MAX_WORKER_ATTEMPTS", 1)
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("attribute=db.statement")

    result = _run(transport)
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_cap"] == 1
    assert result["worker_attempt_count"] == calls == 1


def test_profile_must_be_explicit_non_thinking() -> None:
    from dataclasses import replace

    with pytest.raises(ValueError, match="non-thinking"):
        _run(
            lambda request, timeout: b"",
            profile=replace(_PROFILE, chat_template_enable_thinking=None),
        )
