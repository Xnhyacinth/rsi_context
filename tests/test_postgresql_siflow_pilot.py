"""The live PG development runner must stop and account for every worker call."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest

from rsicontext.analysis.postgresql_model_screen import FakeCatalogWorker
from rsicontext.analysis.postgresql_siflow_pilot import run_development_pilot
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint
from rsicontext.lifecycle.material_postgresql_source_contrast import (
    build_postgresql_source_contrast_sessions,
)
from rsicontext.lifecycle.spec import LifecycleInstance

_PROFILE = APIProfile(
    id="siflow-qwen3.6-27b-r11-pg-dev-2048",
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
    system_prompt="You are the project worker. Follow the requested output format exactly.",
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
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        "local_template_geometry": {"rendered_input_tokens": 10},
        "stage": "source-survey"
        if prompt.startswith("Read the complete")
        else "project-request-stage",
    }


def _stream(answer: str, *, prompt_tokens: int = 10, finish: str = "stop") -> bytes:
    payload = {
        "id": "fake-1",
        "model": _PROFILE.model,
        "choices": [{"delta": {"content": answer}, "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 2},
    }
    return ("data: " + json.dumps(payload) + "\n\ndata: [DONE]\n\n").encode()


def _pair(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    variable = (
        "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT"
        if revision == "16"
        else "RSICONTEXT_POSTGRESQL_SOURCE_ROOT"
    )
    configured = os.environ.get(variable)
    if not configured:
        pytest.skip(f"set {variable} to pinned detached checkout")
    root = Path(configured)
    return build_postgresql_source_contrast_sessions(root, revision=revision)


def test_provider_prompt_mismatch_stops_after_one_counted_attempt() -> None:
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("parameters=copy_data", prompt_tokens=11)

    result = run_development_pilot(
        _pair("16"),
        _pair("17"),
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        preflight=_preflight,
        transport=transport,
    )
    assert calls == 1
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_count"] == 1
    assert cast(dict[str, Any], result["provider_usage_total"])["unknown_usage_attempts"] == 1


def test_non_stop_finish_reason_is_counted_and_stops() -> None:
    calls = 0

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return _stream("parameters=copy_data", finish="length")

    result = run_development_pilot(
        _pair("16"),
        _pair("17"),
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        preflight=_preflight,
        transport=transport,
    )
    assert calls == 1
    assert result["worker_attempt_count"] == 1
    assert result["status"] == "stopped-on-worker-failure"


def test_all_eight_fake_provider_trajectories_respect_global_cap() -> None:
    fake = FakeCatalogWorker()

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        if not isinstance(request.data, bytes):
            raise ValueError("missing request body")
        body = json.loads(request.data)
        return _stream(fake(body["messages"][1]["content"]))

    result = run_development_pilot(
        _pair("16"),
        _pair("17"),
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        preflight=_preflight,
        transport=transport,
    )
    assert result["status"] == "completed-development-screen"
    assert result["worker_attempt_count"] == len(fake.prompts) == 11
    assert result["worker_attempt_count"] <= cast(int, result["worker_attempt_cap"])
    assert cast(dict[str, Any], result["provider_usage_total"]) == {
        "input_tokens": 110,
        "output_tokens": 22,
        "unknown_usage_attempts": 0,
    }
    cases = cast(list[dict[str, Any]], result["cases"])
    assert len(cases) == 8
    assert [case["session_passed"] for case in cases[:2]] == [[True, True], [True, True]]
