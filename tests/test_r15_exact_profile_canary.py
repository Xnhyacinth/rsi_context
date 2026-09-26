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
from rsicontext.experiment.api import ResolvedAPIEndpoint

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


def _allow_test_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "secret-never-persist-r15")
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    attestation = {
        "worktree_dirty": False,
        "repository_root_matches": True,
        "producer_files_match_head": True,
    }
    monkeypatch.setattr(canary, "producer_attestation", lambda *_args, **_kwargs: attestation)


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


def test_artifact_collision_refuses_without_overwriting_or_resolving_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "collision.json"
    output.write_text("sentinel")
    monkeypatch.setattr(canary, "resolve_api_endpoint", lambda *_args, **_kwargs: pytest.fail())
    with pytest.raises(SystemExit):
        canary.main(_args("--execute", output, registration=canary.registration_sha256()))
    assert output.read_text() == "sentinel"


def test_unwritable_artifact_location_refuses_before_resolving_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "regular-file"
    parent.write_text("not a directory")
    output = parent / "canary.json"
    monkeypatch.setattr(canary, "resolve_api_endpoint", lambda *_args, **_kwargs: pytest.fail())
    with pytest.raises(SystemExit):
        canary.main(_args("--execute", output, registration=canary.registration_sha256()))
    assert parent.read_text() == "not a directory"


def test_live_execute_requires_external_output_path_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer_root = tmp_path / "producer"
    producer_root.mkdir()
    monkeypatch.setattr(canary, "ROOT", producer_root)
    output = producer_root / "canary.json"
    with pytest.raises(SystemExit):
        canary.main(_args("--execute", output, registration=canary.registration_sha256()))
    assert not output.exists()


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


def test_direct_fake_transport_uses_only_a_dummy_key(tokenizer: ChatTokenizer) -> None:
    profile = canary._profile()
    observed: list[str | None] = []
    fake = canary._fake_transport(profile, tokenizer)

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        observed.append(request.get_header("Authorization"))
        return fake(request, timeout)

    result = canary.run_canary(
        profile=profile,
        endpoint=ResolvedAPIEndpoint(canary.ENDPOINT, "offline-synthetic-key"),
        tokenizer=tokenizer,
        transport=transport,
        synthetic=True,
    )
    assert result["status"] == "passed"
    assert observed == ["Bearer offline-synthetic-key"]
    assert result["provider_usage_total"] is None
    assert result["synthetic_usage_total"] == {"input_tokens": 62, "output_tokens": 1}


def test_live_attempt_ledger_is_flushed_before_fake_billed_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tokenizer: ChatTokenizer
) -> None:
    _allow_test_execute(monkeypatch)
    output = tmp_path / "billed.json"
    fake = canary._fake_transport(canary._profile(), tokenizer)

    def billed(request: urllib.request.Request, timeout: float) -> bytes:
        before = json.loads(output.read_text())
        assert before["status"] == "dispatch-started"
        assert before["live_model_called"] is True
        assert before["call_count"] == 1
        assert before["attempt"]["request_sha256"] == canary.REQUEST_SHA256
        assert before["provider_usage_total"] is None
        assert "secret-never-persist-r15" not in output.read_text()
        return fake(request, timeout)

    monkeypatch.setattr(canary, "_urlopen_transport", billed)
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 0
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "passed"
    assert artifact["live_model_called"] is True
    assert artifact["provider_usage_total"] == {"input_tokens": 62, "output_tokens": 1}
    assert artifact["attempt"]["usage_provenance"] == "provider-reported"
    assert output.stat().st_mode & 0o777 == 0o600


def test_postprocessing_failure_retains_billed_attempt_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tokenizer: ChatTokenizer
) -> None:
    _allow_test_execute(monkeypatch)
    output = tmp_path / "postprocessing.json"
    fake = canary._fake_transport(canary._profile(), tokenizer)
    monkeypatch.setattr(canary, "_urlopen_transport", fake)

    def failed_postprocessing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Bearer secret-never-persist-r15")

    monkeypatch.setattr(canary, "_safe_attempt", failed_postprocessing)
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 2
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "refused"
    assert artifact["live_model_called"] is True
    assert artifact["call_count"] == 1
    assert artifact["provider_usage_total"] == {"input_tokens": 62, "output_tokens": 1}
    assert artifact["attempt"]["status"] == "response-received"
    assert "secret-never-persist-r15" not in output.read_text()


def test_attempt_ledger_write_failure_blocks_fake_network_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_execute(monkeypatch)
    output = tmp_path / "write-failure.json"
    original = canary._update_artifact

    def fail_attempt_write(path: Path, result: dict[str, object]) -> None:
        if result.get("status") == "dispatch-started":
            raise OSError("simulated disk failure")
        original(path, result)

    def forbidden_transport(request: urllib.request.Request, timeout: float) -> bytes:
        pytest.fail("network dispatch must wait for durable attempt ledger")

    monkeypatch.setattr(canary, "_update_artifact", fail_attempt_write)
    monkeypatch.setattr(canary, "_urlopen_transport", forbidden_transport)
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 2
    artifact = json.loads(output.read_text())
    assert artifact["live_model_called"] is False
    assert artifact["provider_usage_total"] is None


@pytest.mark.parametrize(
    "failure",
    (
        "wrong-model",
        "non-stop",
        "wrong-input-usage",
        "wrong-output-usage",
        "transport-secret",
        "malformed-response-id",
    ),
)
def test_execute_failure_is_named_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tokenizer: ChatTokenizer, failure: str
) -> None:
    _allow_test_execute(monkeypatch)
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
        if failure == "malformed-response-id":
            return raw.replace(b"offline-r15-profile-canary", b"\\ud800")
        return raw.replace(b'"completion_tokens": 1', b'"completion_tokens": 2')

    monkeypatch.setattr(canary, "_urlopen_transport", broken)
    output = tmp_path / f"{failure}.json"
    assert canary.main(_args("--execute", output, registration=canary.registration_sha256())) == 2
    artifact = json.loads(output.read_text())
    assert artifact["status"] == "failed"
    assert artifact["mode"] == "execute"
    assert artifact["transport_kind"] == "live-siflow"
    assert artifact["live_model_called"] is True
    assert artifact["call_count"] == 1
    assert artifact["failure_type"] in {
        "OutputUsageMismatch",
        "ResponseIdentityInvalid",
        "ReaderProtocolError",
        "ValueError",
        "RuntimeError",
        "_AbortAfterFailure",
    }
    if failure == "wrong-output-usage":
        assert artifact["failure_type"] == "OutputUsageMismatch"
        assert artifact["answer_exact"] is True
    if failure == "malformed-response-id":
        assert artifact["failure_type"] == "ResponseIdentityInvalid"
        assert artifact["attempt"]["response_id_sha256"] is not None
        assert artifact["attempt"]["response_id_valid"] is False
        assert artifact["provider_usage_total"] == {"input_tokens": 62, "output_tokens": 1}
    assert "secret-never-persist-r15" not in output.read_text()
    assert "Bearer" not in output.read_text()
