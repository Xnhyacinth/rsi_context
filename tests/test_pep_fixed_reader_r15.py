"""Fake-transport behavior for the R15 PEP fixed-reader development screen."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

import rsicontext.analysis.pep_fixed_reader_r15 as pep_screen_module
from rsicontext.analysis.pep_fixed_reader_r15 import (
    CASE_ORDER,
    MAX_WORKER_ATTEMPTS,
    PepCase,
    _run_pep_screen_unverified,
    build_geometry_report,
    build_pep_cases,
    run_pep_screen,
)
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, load_api_profiles
from rsicontext.lifecycle.material_pep_r14 import SOURCE_FILES, SOURCE_REVISION

_ROOT = Path(__file__).resolve().parent.parent
_PROFILE = load_api_profiles(_ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json").get(
    "siflow-qwen3.6-27b-r15-bc-dev-2048"
)
_ENDPOINT = ResolvedAPIEndpoint("https://api.siflow.cn/model-api/chat/completions", "test-key")


class _CharacterTokenizer:
    """Deterministic geometry double; the CLI separately uses pinned Qwen."""

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        **kwargs: Any,
    ) -> str | list[int] | Mapping[str, Sequence[int]]:
        assert kwargs == {"enable_thinking": False}
        assert add_generation_prompt
        rendered = (
            "<system>" + messages[0]["content"] + "</system>"
            "<user>" + messages[1]["content"] + "</user><assistant>"
        )
        return [ord(character) for character in rendered] if tokenize else rendered

    def __call__(
        self, text: str, *, add_special_tokens: bool, return_offsets_mapping: bool
    ) -> Mapping[str, Sequence[Any]]:
        assert not add_special_tokens and return_offsets_mapping
        return {
            "input_ids": [ord(character) for character in text],
            "offset_mapping": [(index, index + 1) for index in range(len(text))],
        }


def _cases() -> tuple[PepCase, ...]:
    configured = os.environ.get("RSICONTEXT_PEP_SOURCE_ROOT")
    if configured is None:
        pytest.skip("set RSICONTEXT_PEP_SOURCE_ROOT to the pinned detached checkout")
    return build_pep_cases(Path(configured))


def _report(cases: tuple[PepCase, ...]) -> dict[str, object]:
    return build_geometry_report(_CharacterTokenizer(), _PROFILE, cases)


def _stream(
    answer: str, *, prompt_tokens: int, model: str = _PROFILE.model, finish: str = "stop"
) -> bytes:
    payload = {
        "id": "fake-pep-1",
        "model": model,
        "choices": [{"delta": {"content": answer}, "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 2},
    }
    return ("data: " + json.dumps(payload) + "\n\ndata: [DONE]\n\n").encode()


def _fake_transport(
    report: dict[str, object], calls: list[str], *, usage_delta: int = 0
) -> Any:
    registered = cast(dict[str, dict[str, Any]], report["registered_requests"])

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        body = json.loads(request.data)
        assert body["model"] == _PROFILE.model
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        prompt = body["messages"][1]["content"]
        calls.append(prompt)
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        geometry = registered[digest]["local_template_geometry"]
        count = cast(int, geometry["rendered_input_tokens"])
        if prompt.startswith("Historical source URL: "):
            if "/peps/pep-0621.rst" in prompt:
                answer = "form=license-table"
            elif "/peps/pep-0639.rst" in prompt:
                answer = "form=license-string"
            else:
                answer = "form=unknown"
        elif "form=license-string" in prompt:
            answer = "plan=license-string"
        else:
            answer = "plan=license-table"
        return _stream(answer, prompt_tokens=count + usage_delta)

    return transport


def test_material_controls_keep_matched_request_and_private_oracles() -> None:
    cases = _cases()
    assert tuple(case.name for case in cases) == CASE_ORDER
    for index in (0, 1):
        full, identity, free = cases[index], cases[index + 2], cases[index + 4]
        assert full.request == identity.request == free.request
        assert full.sessions[1] == identity.sessions[1] == free.sessions[1]
        assert full.sessions[0].axes == identity.sessions[0].axes == free.sessions[0].axes
        assert identity.source_url == full.source_url
        assert "PEP: " in identity.source
        assert "- Format: Table" not in identity.source
        assert "Add string value to" not in identity.source
        assert free.source_url == "benchmark:withheld"
    assert cases[4].source == cases[5].source
    assert cases[4].source_url == cases[5].source_url


def test_dry_run_enumerates_every_valid_later_prompt() -> None:
    report = _report(_cases())
    case_reports = cast(list[dict[str, Any]], report["cases"])
    assert len(case_reports) == 6
    assert report["worker_attempt_cap"] == 12
    assert report["profile_max_total_output_tokens"] == 12 * 2048
    assert report["local_worst_case_total_input_tokens"] == sum(
        case["local_worst_case_input_tokens"] for case in case_reports
    )
    for case in case_reports:
        branches = case["branches"]
        assert [branch["source_finding"] for branch in branches] == [
            "form=license-table",
            "form=license-string",
            "form=unknown",
        ]
        assert all(len(branch["calls"]) == 2 for branch in branches)
        later_hashes = {branch["calls"][1]["prompt_sha256"] for branch in branches}
        assert len(later_hashes) == 3
        for branch in branches:
            for call in branch["calls"]:
                assert call["local_template_geometry"]["span_status"] == "unique_later_query"
                assert call["request_sha256"]


def test_all_six_arms_invoke_fake_provider_and_account_usage() -> None:
    cases = _cases()
    report = _report(cases)
    calls: list[str] = []
    result = _run_pep_screen_unverified(
        cases,
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        geometry_report=report,
        transport=_fake_transport(report, calls),
    )
    assert result["status"] == "completed-development-screen"
    assert result["worker_attempt_count"] == len(calls) == MAX_WORKER_ATTEMPTS
    outcomes = cast(list[dict[str, Any]], result["cases"])
    assert [case["case"] for case in outcomes] == list(CASE_ORDER)
    assert [case["session_passed"] for case in outcomes[:4]] == [[True, True]] * 4
    assert outcomes[4]["session_passed"] == [True, True]
    assert outcomes[5]["session_passed"] == [True, False]
    assert all(case["model_calls"] == [1, 1] for case in outcomes)
    usage = cast(dict[str, int], result["provider_usage_total"])
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] == 2 * MAX_WORKER_ATTEMPTS
    assert usage["unknown_usage_attempts"] == 0
    assert all(len(case["worker_attempt_indexes"]) == 2 for case in outcomes)


def test_provider_usage_mismatch_stops_after_one_billed_attempt() -> None:
    cases = _cases()
    report = _report(cases)
    calls: list[str] = []
    result = _run_pep_screen_unverified(
        cases,
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        geometry_report=report,
        transport=_fake_transport(report, calls, usage_delta=1),
    )
    assert result["status"] == "stopped-on-worker-failure"
    assert result["worker_attempt_count"] == len(calls) == 1
    assert cast(dict[str, int], result["provider_usage_total"])["unknown_usage_attempts"] == 0
    assert len(cast(list[object], result["cases"])) == 1


def test_unregistered_request_refuses_before_transport() -> None:
    cases = _cases()
    report = _report(cases)
    report["registered_requests"] = {}
    calls: list[str] = []
    result = _run_pep_screen_unverified(
        cases,
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        geometry_report=report,
        transport=_fake_transport(report, calls),
    )
    assert result["status"] == "stopped-on-worker-failure"
    assert calls == []
    assert result["worker_attempt_count"] == 0
    assert cast(list[dict[str, str]], result["preflight_failures"])


def test_cross_case_registered_request_refuses_before_transport() -> None:
    cases = _cases()
    report = _report(cases)
    case_reports = copy.deepcopy(cast(list[dict[str, Any]], report["cases"]))
    report["cases"] = case_reports
    other_prompt = case_reports[1]["branches"][0]["calls"][0]["prompt_sha256"]
    for branch in case_reports[0]["branches"]:
        branch["calls"][0]["prompt_sha256"] = other_prompt
    calls: list[str] = []
    result = _run_pep_screen_unverified(
        cases,
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        geometry_report=report,
        transport=_fake_transport(report, calls),
    )
    assert result["status"] == "stopped-on-worker-failure"
    assert calls == []
    assert result["worker_attempt_count"] == 0
    failures = cast(list[dict[str, str]], result["preflight_failures"])
    assert failures[0]["error_code"] == "preflight_rejected"
    assert failures[0]["error_type"] == "ValueError"


def test_cumulative_local_input_ceiling_refuses_before_transport() -> None:
    cases = _cases()
    report = _report(cases)
    report["local_worst_case_total_input_tokens"] = 1
    calls: list[str] = []
    result = _run_pep_screen_unverified(
        cases,
        profile=_PROFILE,
        endpoint=_ENDPOINT,
        geometry_report=report,
        transport=_fake_transport(report, calls),
    )
    assert result["status"] == "stopped-on-worker-failure"
    assert calls == []
    assert result["worker_attempt_count"] == 0
    failures = cast(list[dict[str, str]], result["preflight_failures"])
    assert failures[0]["error_code"] == "preflight_rejected"
    assert failures[0]["error_type"] == "ValueError"


@pytest.mark.parametrize(
    "forged_field,expected_error",
    (
        ("source", "source identity differs from frozen artifact"),
        ("tokenizer", "tokenizer differs from frozen artifact"),
        ("producer", "producer bytes or runtime differ from frozen artifact"),
    ),
)
def test_public_screen_rejects_forged_identity_before_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forged_field: str,
    expected_error: str,
) -> None:
    cases = _cases()
    report = _report(cases)
    source_root = Path(os.environ["RSICONTEXT_PEP_SOURCE_ROOT"])
    tokenizer_path = Path("/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b")
    tokenizer_manifest = "8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290"
    report["source_identity"] = {
        "revision": SOURCE_REVISION,
        "selected_file_sha256": {relative: digest for relative, digest in SOURCE_FILES.values()},
    }
    report["tokenizer"] = {"manifest_sha256": tokenizer_manifest}
    report["profile_file_sha256"] = hashlib.sha256(
        (_ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json").read_bytes()
    ).hexdigest()
    current_producer = {
        "worktree_dirty": False,
        "repository_root_matches": True,
        "producer_files_match_head": True,
        "producer_file_sha256": {"producer": "pinned"},
        "python_version": "3.12",
        "package_versions": {"transformers": "5.15.0"},
    }
    report["producer_attestation"] = current_producer.copy()
    if forged_field == "source":
        report["source_identity"] = {"revision": "forged"}
    elif forged_field == "tokenizer":
        report["tokenizer"] = {"manifest_sha256": "forged"}
    else:
        report["producer_attestation"] = {
            **current_producer,
            "producer_file_sha256": {"producer": "forged"},
        }
    geometry_path = tmp_path / "forged-geometry.json"
    geometry_bytes = json.dumps(report).encode()
    geometry_path.write_bytes(geometry_bytes)
    registration = {
        "schema_version": 1,
        "scope": "r15-pep-reader",
        "geometry_artifact_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
        "profile_sha256": _PROFILE.profile_hash,
        "tokenizer_manifest_sha256": tokenizer_manifest,
        "source_revision": SOURCE_REVISION,
        "total_provider_token_ceiling": (
            cast(int, report["local_worst_case_total_input_tokens"])
            + cast(int, report["profile_max_total_output_tokens"])
        ),
    }
    registration_bytes = json.dumps(registration).encode()
    manifest_path = tmp_path / "registration.json"
    manifest_path.write_bytes(registration_bytes)
    monkeypatch.setattr(pep_screen_module, "_REGISTRATION_PATH", manifest_path)
    original_run = subprocess.run

    def tracked_registration(command: list[str], **kwargs: Any) -> Any:
        if command[-2:] == ["show", "HEAD:configs/r15_pep_fixed_reader_registration_v1.json"]:
            return subprocess.CompletedProcess(command, 0, stdout=registration_bytes)
        return original_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", tracked_registration)
    monkeypatch.setattr(
        pep_screen_module, "producer_attestation", lambda *_args, **_kwargs: current_producer
    )
    calls: list[str] = []
    with pytest.raises(ValueError, match=expected_error):
        run_pep_screen(
            cases,
            profile=_PROFILE,
            endpoint=_ENDPOINT,
            geometry_report=report,
            geometry_path=geometry_path,
            source_root=source_root,
            tokenizer_path=tokenizer_path,
            transport=_fake_transport(report, calls),
        )
    assert calls == []


def test_cli_execute_refuses_without_credentials_or_network() -> None:
    result = subprocess.run(  # nosec B603
        [sys.executable, str(_ROOT / "scripts/r15_pep_reader_screen.py"), "--execute"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "paid execution is closed" in result.stderr


def test_profile_is_shared_r15_fixed_qwen() -> None:
    assert isinstance(_PROFILE, APIProfile)
    assert _PROFILE.model == "Qwen/Qwen3.6-27B"
    assert _PROFILE.chat_template_enable_thinking is False
    assert _PROFILE.max_output_tokens == 2048
