"""Exact-profile canary tests with only injected local SSE transports."""

from __future__ import annotations

import importlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402

_TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not _TOKENIZER.is_dir():
        pytest.skip("pinned Qwen tokenizer is unavailable")
    try:
        module = importlib.import_module("transformers")
    except ImportError:
        pytest.skip("install pinned optional tokenizer runtime")
    return cast(
        ChatTokenizer, module.AutoTokenizer.from_pretrained(str(_TOKENIZER), local_files_only=True)
    )


def _args(mode: str, output: Path, *, registration: str | None = None) -> list[str]:
    args = [mode, "--tokenizer-path", str(_TOKENIZER), "--output", str(output)]
    if registration is not None:
        args.extend(("--registration-sha256", registration))
    return args


def test_exact_registration_and_final_chat_geometry(tokenizer: ChatTokenizer) -> None:
    profile = canary._profile()
    geometry = canary._geometry(tokenizer, profile)
    local = geometry["local_template_geometry"]
    assert isinstance(local, dict)
    assert local["rendered_input_tokens"] == 62
    assert local["evidence_span_tokens"] == [30, 37]
    assert local["query_span_tokens"] == [40, 47]
    assert local["span_status"] == "unique_later_query"
    assert geometry["request_sha256"] == canary.REQUEST_SHA256
    assert geometry["prompt_sha256"] == canary.PROMPT_SHA256
    assert canary.registration()["max_output_tokens"] == 2048


def test_offline_dry_run_writes_synthetic_usage_without_env_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    output = tmp_path / "dry-run.json"
    assert canary.main(_args("--dry-run", output)) == 0
    artifact = json.loads(output.read_text())
    captured = capsys.readouterr()
    assert artifact["status"] == "passed"
    assert artifact["live_model_called"] is False
    assert artifact["provider_usage_total"] is None
    assert artifact["synthetic_usage_total"] == {"input_tokens": 62, "output_tokens": 1}
    assert artifact["attempt"]["model_echo_exact"] is True
    assert artifact["attempt"]["finish_stop"] is True
    assert artifact["attempt"]["request_sha256"] == canary.REQUEST_SHA256
    assert "secret-never-persist-r15" not in output.read_text() + captured.out + captured.err


def test_execute_registration_refusal_writes_artifact_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.setenv("SIFLOW_BASE_URL", canary.ENDPOINT)
    output = tmp_path / "refused.json"
    assert canary.main(_args("--execute", output, registration="0" * 64)) == 2
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "refused"
    assert artifact["failure_code"] == "registration-mismatch"
    assert artifact["live_model_called"] is False
    assert "secret-never-persist-r15" not in output.read_text()


def test_execute_missing_key_refuses_with_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    monkeypatch.setenv("SIFLOW_BASE_URL", canary.ENDPOINT)
    output = tmp_path / "missing-key.json"
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 2
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "refused"
    assert artifact["live_model_called"] is False
    assert artifact["provider_usage_total"] is None


def test_live_execute_refuses_dirty_producer_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        canary,
        "producer_attestation",
        lambda *_args, **_kwargs: {"worktree_dirty": True},
    )
    output = tmp_path / "dirty.json"
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 2
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "refused"
    assert artifact["live_model_called"] is False
    assert artifact["code_identity"]["producer_attestation"]["worktree_dirty"] is True


def test_fixed_endpoint_needs_only_key_in_execute_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    tokenizer = canary._tokenizer(_TOKENIZER)
    output = tmp_path / "fixed-endpoint.json"
    assert (
        canary.main(
            _args("--execute", output, registration=canary.registration_sha256()),
            transport_override=canary._fake_transport(canary._profile(), tokenizer),
        )
        == 0
    )
    assert json.loads(output.read_text())["status"] == "passed"


def test_guarded_execute_with_injected_fake_stays_synthetic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.setenv("SIFLOW_BASE_URL", canary.ENDPOINT)
    tokenizer = canary._tokenizer(_TOKENIZER)
    fake = canary._fake_transport(canary._profile(), tokenizer)
    output = tmp_path / "guarded-fake.json"
    assert (
        canary.main(
            _args("--execute", output, registration=canary.registration_sha256()),
            transport_override=fake,
        )
        == 0
    )
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "passed"
    assert artifact["mode"] == "execute-test"
    assert artifact["transport_kind"] == "injected-test"
    assert artifact["live_model_called"] is False
    assert artifact["provider_usage_total"] is None
    assert artifact["synthetic_usage_total"] == {"input_tokens": 62, "output_tokens": 1}
    assert "secret-never-persist-r15" not in output.read_text()


@pytest.mark.parametrize(
    "failure",
    ("wrong-model", "non-stop", "wrong-input-usage", "wrong-output-usage", "transport-secret"),
)
def test_execute_failure_is_named_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.setenv("SIFLOW_BASE_URL", canary.ENDPOINT)
    tokenizer = canary._tokenizer(_TOKENIZER)
    fake = canary._fake_transport(canary._profile(), tokenizer)

    def broken(request: urllib.request.Request, timeout: float) -> bytes:
        if failure == "transport-secret":
            raise RuntimeError("Bearer secret-never-persist-r15")
        raw = fake(request, timeout)
        if failure == "wrong-model":
            return raw.replace(b"Qwen/Qwen3.6-27B", b"Wrong/Model")
        if failure == "non-stop":
            return raw.replace(b'"finish_reason": "stop"', b'"finish_reason": "length"')
        if failure == "wrong-input-usage":
            return raw.replace(b'"prompt_tokens": 62', b'"prompt_tokens": 61')
        return raw.replace(b'"completion_tokens": 1', b'"completion_tokens": 2')

    output = tmp_path / f"{failure}.json"
    assert (
        canary.main(
            _args("--execute", output, registration=canary.registration_sha256()),
            transport_override=broken,
        )
        == 2
    )
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "failed"
    assert artifact["live_model_called"] is False
    assert artifact["failure_type"] in {
        "AnswerMismatch",
        "ReaderProtocolError",
        "ValueError",
        "RuntimeError",
    }
    assert "secret-never-persist-r15" not in output.read_text()
    assert "Bearer" not in output.read_text()
