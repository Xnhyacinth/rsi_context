"""Offline R15 KEP reader controls; every model response is synthetic SSE."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.analysis.k8s_fixed_reader_r15 import (
    CASE_ORDER,
    MAX_WORKER_ATTEMPTS,
    PROFILE_ID,
    SyntheticTransport,
    enumerate_allowed_prompt_geometry,
    make_synthetic_transport,
    neutralize_both_order_rules,
    run_offline_screen,
)
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, load_api_profiles
from rsicontext.lifecycle.material_k8s_r14 import build_k8s_resource_order_sessions

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
_TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)


@pytest.fixture(scope="module")
def source_root() -> Path:
    if not _SOURCE.is_dir():
        pytest.skip("pinned KEP checkout is unavailable")
    return _SOURCE


@pytest.fixture(scope="module")
def profile() -> APIProfile:
    return load_api_profiles(_ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json").get(
        PROFILE_ID
    )


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not _TOKENIZER.is_dir():
        pytest.skip("pinned Qwen tokenizer snapshot is unavailable")
    try:
        module = importlib.import_module("transformers")
    except ImportError:
        pytest.skip("install pinned optional tokenizer runtime for R15 geometry tests")
    return cast(
        ChatTokenizer, module.AutoTokenizer.from_pretrained(str(_TOKENIZER), local_files_only=True)
    )


@pytest.fixture(scope="module")
def registry(
    source_root: Path, profile: APIProfile, tokenizer: ChatTokenizer
) -> list[dict[str, object]]:
    return enumerate_allowed_prompt_geometry(source_root, profile=profile, tokenizer=tokenizer)


def _endpoint() -> ResolvedAPIEndpoint:
    return ResolvedAPIEndpoint(
        endpoint="https://api.siflow.cn/model-api/chat/completions",
        api_key="offline-synthetic-key",
    )


def test_rule_intervention_controls_both_restatements_and_only_registered_spans(
    source_root: Path,
) -> None:
    source = build_k8s_resource_order_sessions(source_root)[0].stages[0].documents[0].text
    changed, ledger = neutralize_both_order_rules(source)
    assert ledger["untouched_bytes_exact"] is True
    spans = cast(list[dict[str, object]], ledger["spans"])
    assert [span["start_line"] for span in spans] == [780, 835]
    assert [span["end_line"] for span in spans] == [794, 848]
    assert changed.count("[Ordered-prefix calculation withheld") == 2
    assert "sidecar containers with index < i" not in changed
    assert "before the first sidecar containers" not in changed
    assert "Max(nonSidecarInitContainers)" in changed
    with pytest.raises(ValueError, match="complete pinned KEP README"):
        neutralize_both_order_rules(source + "drift")


def test_exact_final_chat_enumerates_every_dynamic_prompt(
    registry: list[dict[str, object]], profile: APIProfile
) -> None:
    assert len(registry) == 12
    assert len({item["prompt_sha256"] for item in registry}) == 12
    assert {item["stage"] for item in registry} == {
        "source-survey",
        "resource-request-stage",
        "resource-order-change",
    }
    assert len([item for item in registry if item["stage"] == "source-survey"]) == 3
    assert len([item for item in registry if item["stage"] == "resource-request-stage"]) == 3
    assert len([item for item in registry if item["stage"] == "resource-order-change"]) == 6
    for item in registry:
        assert item["profile_sha256"] == profile.profile_hash
        geometry = item["local_template_geometry"]
        assert isinstance(geometry, dict)
        assert geometry["rendered_input_tokens"] + profile.max_output_tokens <= (
            profile.evaluation_max_model_len
        )


def test_fake_sse_screen_counts_all_calls_and_source_controls(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
) -> None:
    result = run_offline_screen(
        source_root,
        profile=profile,
        endpoint=_endpoint(),
        tokenizer=tokenizer,
        transport=make_synthetic_transport(tokenizer, profile),
        geometry_registry=registry,
    )
    assert result["status"] == "completed-offline-screen"
    assert result["live_ready"] is False
    assert result["usage_provenance"] == "synthetic_sse_transport_only"
    assert result["worker_attempt_count"] == MAX_WORKER_ATTEMPTS == 9
    cases = result["cases"]
    assert isinstance(cases, list)
    assert [item["case"] for item in cases] == list(CASE_ORDER)
    assert [item["session_passed"] for item in cases] == [
        [True, True],
        [True, False],
        [True, False],
    ]
    assert [item["model_calls"] for item in cases] == [[2, 1], [2, 1], [2, 1]]
    attempts = cast(list[dict[str, object]], result["attempts"])
    assert all(item["status"] == "ok" and item["finish_reason"] == "stop" for item in attempts)
    assert result["provider_usage_total"] is None
    usage = result["synthetic_usage_total"]
    assert isinstance(usage, dict)
    assert usage["unknown_usage_attempts"] == 0
    assert usage["input_tokens"] == 44108
    assert usage["output_tokens"] == 71


@pytest.mark.parametrize("drift", ("request", "case", "profile"))
def test_geometry_or_profile_drift_refuses_before_transport(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
    drift: str,
) -> None:
    calls = 0
    fake = make_synthetic_transport(tokenizer, profile)

    def counted(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return fake(request, timeout)

    if drift == "profile":
        with pytest.raises(ValueError, match="shared profile hash"):
            run_offline_screen(
                source_root,
                profile=replace(profile, system_prompt="changed"),
                endpoint=_endpoint(),
                tokenizer=tokenizer,
                transport=SyntheticTransport(counted),
                geometry_registry=registry,
            )
    else:
        altered = [dict(item) for item in registry]
        first = next(
            item
            for item in altered
            if item["stage"] == "source-survey"
            and isinstance(item["cases"], list)
            and "full-source" in item["cases"]
        )
        if drift == "request":
            first["request_sha256"] = "0" * 64
        else:
            first["cases"] = ["source-free"]
        result = run_offline_screen(
            source_root,
            profile=profile,
            endpoint=_endpoint(),
            tokenizer=tokenizer,
            transport=SyntheticTransport(counted),
            geometry_registry=altered,
        )
        assert result["status"] == "stopped-on-worker-failure"
        assert result["preflight_failures"]
    assert calls == 0


def test_attempt_cap_refuses_before_tenth_transport(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rsicontext.analysis.k8s_fixed_reader_r15.MAX_WORKER_ATTEMPTS", 2)
    calls = 0
    fake = make_synthetic_transport(tokenizer, profile)

    def counted(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return fake(request, timeout)

    result = run_offline_screen(
        source_root,
        profile=profile,
        endpoint=_endpoint(),
        tokenizer=tokenizer,
        transport=SyntheticTransport(counted),
        geometry_registry=registry,
    )
    assert result["status"] == "stopped-on-attempt-cap"
    assert result["worker_attempt_count"] == calls == 2
    refusals = result["attempt_cap_refusals"]
    assert isinstance(refusals, int) and refusals >= 1


def test_private_world_hash_drift_refuses_before_transport(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rsicontext.analysis.k8s_fixed_reader_r15.WORLD_SHA256", ("0" * 64, "1" * 64)
    )
    calls = 0

    def forbidden(_request: urllib.request.Request, _timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        raise AssertionError("private-world drift reached transport")

    with pytest.raises(ValueError, match="canonical evaluator world"):
        run_offline_screen(
            source_root,
            profile=profile,
            endpoint=_endpoint(),
            tokenizer=tokenizer,
            transport=SyntheticTransport(forbidden),
            geometry_registry=registry,
        )
    assert calls == 0


def test_plain_transport_cannot_enter_offline_runner(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
) -> None:
    def forbidden(_request: urllib.request.Request, _timeout: float) -> bytes:
        raise AssertionError("plain transport reached dispatch")

    with pytest.raises(TypeError, match="explicit synthetic transport"):
        run_offline_screen(
            source_root,
            profile=profile,
            endpoint=_endpoint(),
            tokenizer=tokenizer,
            transport=cast(SyntheticTransport, forbidden),
            geometry_registry=registry,
        )


@pytest.mark.parametrize("failure", ("wrong-model", "non-stop", "missing-usage"))
def test_synthetic_sse_failure_stops_without_later_calls(
    source_root: Path,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registry: list[dict[str, object]],
    failure: str,
) -> None:
    calls = 0
    fake = make_synthetic_transport(tokenizer, profile)

    def broken(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        raw = fake(request, timeout)
        if failure == "wrong-model":
            return raw.replace(profile.model.encode(), b"Unregistered/Model")
        if failure == "non-stop":
            return raw.replace(b'"finish_reason": "stop"', b'"finish_reason": "length"')
        return b"\n".join(line for line in raw.split(b"\n") if b'"usage"' not in line)

    result = run_offline_screen(
        source_root,
        profile=profile,
        endpoint=_endpoint(),
        tokenizer=tokenizer,
        transport=SyntheticTransport(broken),
        geometry_registry=registry,
    )
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_count"] == calls == 1
    attempts = cast(list[dict[str, object]], result["attempts"])
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["response_provenance"] == "synthetic_sse"


def test_paid_cli_refuses_before_credentials_or_output(tmp_path: Path) -> None:
    output = tmp_path / "no-paid-result.json"
    process = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "scripts/r15_k8s_reader_screen.py"),
            "--execute",
            "--output",
            str(output),
        ],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
    response = json.loads(process.stderr)
    assert response["live_ready"] is False
    assert response["status"] == "refused"
    assert not output.exists()
