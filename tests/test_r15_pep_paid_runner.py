"""Guarded PEP launch tests use only local fake SSE transports."""

from __future__ import annotations

import json
import os
import stat
import sys
import urllib.request
from pathlib import Path
from typing import cast

import pytest

import rsicontext.analysis.pep_fixed_reader_r15 as pep_screen

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r15_pep_paid_runner as runner  # noqa: E402

from rsicontext.eval.openai_compatible import Transport  # noqa: E402
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint  # noqa: E402

_SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_PEP_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/python-pep-process",
    )
)
_TOKENIZER = Path("/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b")
_SECRET = "secret-never-persist-r15-pep"


class _AnswerTokenizer:
    def __call__(
        self, text: str, *, add_special_tokens: bool, return_offsets_mapping: bool
    ) -> dict[str, list[int]]:
        return {"input_ids": [1] if text else []}


def _unverified_test_screen(
    cases: tuple[pep_screen.PepCase, ...],
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    geometry_report: dict[str, object],
    transport: Transport,
    geometry_path: Path,
    source_root: Path,
    tokenizer_path: Path,
) -> dict[str, object]:
    del geometry_path, source_root, tokenizer_path
    return pep_screen._run_pep_screen_unverified(
        cases,
        profile=profile,
        endpoint=endpoint,
        geometry_report=geometry_report,
        transport=transport,
    )


def _launch() -> dict[str, object]:
    return {
        "geometry_sha256": "registered-test-artifact",
        "canary_registration_sha256": canary.registration_sha256(),
        "canary_script_sha256": "registered-test-code",
        "runner_script_sha256": "registered-test-code",
        "endpoint_sha256": runner._sha(canary.ENDPOINT.encode()),
        "profile_sha256": canary.PROFILE_SHA256,
        "task_call_cap": 12,
        "task_local_plus_requested_ceiling": 42747,
        "canary_call_cap": 2,
        "canary_local_input_tokens": 62,
        "canary_requested_output_tokens": 2048,
        "global_call_cap": 14,
        "global_local_plus_requested_ceiling": 46967,
        "auxiliary_call_cap": 0,
    }


def _stream(
    answer: str, model: str, input_tokens: int, sequence: int, completion_tokens: int = 1
) -> bytes:
    identity = {"id": f"fake-r15-{sequence}", "model": model}
    first = {**identity, "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}]}
    usage = {
        **identity,
        "choices": [],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": completion_tokens},
    }
    return (
        "data: " + json.dumps(first) + "\n\ndata: " + json.dumps(usage) + "\n\ndata: [DONE]\n\n"
    ).encode()


def _fake_transport(
    geometry: dict[str, object], calls: list[str], *, failure: str | None = None
) -> Transport:
    registered = cast(dict[str, dict[str, object]], geometry["registered_requests"])
    assert isinstance(registered, dict)

    def fake(request: urllib.request.Request, timeout: float) -> bytes:
        assert _SECRET not in str(request.header_items())
        assert isinstance(request.data, bytes)
        body = json.loads(request.data)
        prompt = body["messages"][1]["content"]
        calls.append(prompt)
        if failure == "transport-secret" and len(calls) == 2:
            raise RuntimeError(f"Authorization: Bearer {_SECRET}")
        if prompt == canary.PROMPT:
            answer, tokens = "amber", 62
        else:
            digest = runner._sha(prompt.encode())
            entry = registered[digest]
            local = cast(dict[str, int], entry["local_template_geometry"])
            tokens = local["rendered_input_tokens"]
            if prompt.startswith("Historical source URL: "):
                if "/peps/pep-0621.rst" in prompt:
                    answer = "form=license-table"
                elif "/peps/pep-0639.rst" in prompt:
                    answer = "form=license-string"
                else:
                    answer = "form=unknown"
            else:
                answer = (
                    "plan=license-string"
                    if "form=license-string" in prompt
                    else "plan=license-table"
                )
                if failure == "full-task-wrong-plan" and len(calls) == 3:
                    answer = "plan=license-string"
        model = "bad-model" if failure == "pre-canary-model" and len(calls) == 1 else body["model"]
        return _stream(
            answer, model, tokens, len(calls),
            completion_tokens=2 if prompt == canary.PROMPT else 1,
        )

    return fake


@pytest.fixture
def prepared(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    if not _SOURCE.is_dir():
        pytest.skip("pinned PEP source checkout is unavailable")
    geometry = cast(dict[str, object], json.loads(runner._GEOMETRY_PATH.read_text()))
    monkeypatch.setenv("SIFLOW_API_KEY", _SECRET)
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("injected transport read the real credential"),
    )
    monkeypatch.setattr(runner, "_read_launch_manifest", lambda: (_launch(), "test-launch-sha"))
    monkeypatch.setattr(runner, "_validate_registration", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pep_screen, "_validate_registration", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(canary, "_tokenizer", lambda _path: _AnswerTokenizer())
    monkeypatch.setattr(
        canary,
        "_geometry",
        lambda _tokenizer, _profile: {
            "stage": "source-free-profile-canary",
            "prompt_sha256": canary.PROMPT_SHA256,
            "request_sha256": canary.REQUEST_SHA256,
            "local_template_geometry": {"rendered_input_tokens": 62},
        },
    )
    return geometry


def test_fake_full_screen_persists_separate_usage_and_private_files(
    prepared: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "run_pep_screen", _unverified_test_screen)
    calls: list[str] = []
    run_dir = tmp_path / "pep-run"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake_transport(prepared, calls),
    )
    assert result["status"] == "completed-synthetic-screen"
    assert result["qualified_parent"] is False
    assert result["provider_block_valid"] is False
    assert result["attempted_http_calls"] == len(calls) == 14
    assert result["task_http_calls"] == 12
    assert result["canary_http_calls"] == 2
    assert result["task_provider_usage_total"] is None
    assert result["pre_canary_provider_usage"] is None
    assert result["post_canary_provider_usage"] is None
    assert cast(dict[str, int], result["synthetic_usage"])["unknown_usage_attempts"] == 0
    assert set(path.name for path in run_dir.iterdir()) == {
        "identity.json",
        "reservation.json",
        "attempts.jsonl",
        "pre_canary.json",
        "task.json",
        "post_canary.json",
        "final.json",
    }
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    joined = "".join(path.read_text() for path in run_dir.iterdir())
    assert _SECRET not in joined
    assert "Authorization" not in joined
    assert "synthetic-test-key" not in joined


@pytest.mark.parametrize(
    "failure,expected_status,expected_task_calls",
    (("pre-canary-model", "pre-canary-failed", 0), ("transport-secret", "task-worker-failed", 1)),
)
def test_failure_persists_safe_attempt_and_stops_later_dispatch(
    prepared: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_status: str,
    expected_task_calls: int,
) -> None:
    monkeypatch.setattr(runner, "run_pep_screen", _unverified_test_screen)
    calls: list[str] = []
    run_dir = tmp_path / failure
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake_transport(prepared, calls, failure=failure),
    )
    assert result["status"] == expected_status
    assert result["task_http_calls"] == expected_task_calls
    assert not (run_dir / "post_canary.json").exists()
    assert (run_dir / "final.json").exists()
    journal = (run_dir / "attempts.jsonl").read_text()
    assert "dispatched" in journal
    assert _SECRET not in journal
    assert "Authorization" not in journal
    if failure == "transport-secret":
        assert "transport-failed" in journal
        assert cast(dict[str, int], result["synthetic_usage"])["unknown_usage_attempts"] == 1


def test_full_source_failure_stops_before_paid_post_canary(
    prepared: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "run_pep_screen", _unverified_test_screen)
    calls: list[str] = []
    run_dir = tmp_path / "full-source-failure"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake_transport(prepared, calls, failure="full-task-wrong-plan"),
    )
    assert result["status"] == "stopped-on-full-task-failure"
    assert result["task_http_calls"] == 2
    assert result["canary_http_calls"] == 1
    assert len(calls) == 3
    assert not (run_dir / "post_canary.json").exists()
    assert (run_dir / "task.json").exists()
    assert (run_dir / "final.json").exists()


def test_endpoint_drift_refuses_before_canary_with_safe_result(
    prepared: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_BASE_URL", "https://other.example/model-api/chat/completions")
    calls: list[str] = []
    run_dir = tmp_path / "endpoint-drift"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake_transport(prepared, calls),
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert calls == []
    assert (run_dir / "final.json").exists()
    assert not (run_dir / "pre_canary.json").exists()
    assert _SECRET not in (run_dir / "final.json").read_text()


def test_journal_enforces_task_and_global_call_caps_before_transport(
    prepared: dict[str, object], tmp_path: Path
) -> None:
    manifest = _launch()
    request = _canary_request()
    assert isinstance(request.data, bytes)
    digest = runner._sha(request.data)
    assert digest == canary.REQUEST_SHA256
    # Reuse a registered body as a test-only task request to drive cap checks.
    geometry: dict[str, object] = {
        "registered_requests": {
            "test": {
                "request_sha256": digest,
                "local_template_geometry": {"rendered_input_tokens": 62},
            }
        }
    }
    journal = runner._JournalTransport(
        base=lambda _request, _timeout: _stream("amber", canary._profile().model, 62, 1),
        journal_path=tmp_path / "attempts.jsonl",
        geometry=geometry,
        manifest=manifest,
    )
    journal(request, 1.0)
    journal.phase = "task"
    for _ in range(12):
        journal(request, 1.0)
    assert journal.attempts == 13
    with pytest.raises(RuntimeError, match="task provider attempt cap"):
        journal(request, 1.0)
    journal.phase = "post-canary"
    journal(request, 1.0)
    assert journal.attempts == 14
    with pytest.raises(RuntimeError):
        journal(request, 1.0)
    assert journal.attempts == 14


def _canary_request() -> urllib.request.Request:
    body = {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": canary._profile().system_prompt},
            {"role": "user", "content": canary.PROMPT},
        ],
        "model": "Qwen/Qwen3.6-27B",
        "seed": 42,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
    }
    request = urllib.request.Request(
        canary.ENDPOINT,
        data=json.dumps(body, separators=(",", ":"), sort_keys=True).encode(),
        method="POST",
    )
    return request


def test_existing_run_directory_is_never_overwritten(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep"
    sentinel.write_text("unchanged")
    with pytest.raises(FileExistsError):
        runner.run_guarded(source_root=_SOURCE, tokenizer_path=_TOKENIZER, run_dir=existing)
    assert sentinel.read_text() == "unchanged"


def test_repository_run_directory_is_rejected_before_creation() -> None:
    run_dir = runner.ROOT / "r15-paid-test-must-not-exist"
    assert not run_dir.exists()
    with pytest.raises(ValueError, match="outside the repository"):
        runner.run_guarded(source_root=_SOURCE, tokenizer_path=_TOKENIZER, run_dir=run_dir)
    assert not run_dir.exists()


def test_forged_launch_manifest_refuses_without_credential_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forged = tmp_path / "forged-launch.json"
    forged.write_text(runner._LAUNCH_PATH.read_text().replace("42747", "42748"))
    monkeypatch.setattr(runner, "_LAUNCH_PATH", forged)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("credential must not be resolved"),
    )
    calls: list[str] = []
    run_dir = tmp_path / "forged-run"

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=fake,
    )
    assert result["status"] == "refused-or-interrupted"
    assert "attempted_http_calls" not in result
    assert calls == []
    assert (run_dir / "reservation.json").exists()
    assert (run_dir / "attempts.jsonl").exists()
    assert (run_dir / "final.json").exists()


@pytest.mark.parametrize(
    "usage,expected_event",
    (
        (None, "response-received"),
        ({"input_tokens": 61, "output_tokens": 1}, "usage-out-of-contract"),
        ({"input_tokens": 62, "output_tokens": 2049}, "usage-out-of-contract"),
    ),
)
def test_journal_stops_on_missing_or_invalid_provider_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    usage: dict[str, int] | None,
    expected_event: str,
) -> None:
    request = _canary_request()
    raw = _stream("amber", canary._profile().model, 62, 1)
    journal = runner._JournalTransport(
        base=lambda _request, _timeout: raw,
        journal_path=tmp_path / "attempts.jsonl",
        geometry={"registered_requests": {}},
        manifest=_launch(),
    )
    monkeypatch.setattr(runner, "_validated_usage", lambda _raw: usage)
    with pytest.raises(RuntimeError, match="usage"):
        journal(request, 1.0)
    assert journal.attempts == 1
    events = [json.loads(line) for line in journal.journal_path.read_text().splitlines()]
    assert events[0]["event"] == "dispatched"
    assert any(event["event"] == expected_event for event in events)
    assert any(event.get("response_sha256") == runner._sha(raw) for event in events)


def test_usage_parser_exception_retains_response_hash_and_unknown_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _stream("amber", canary._profile().model, 62, 1)
    journal = runner._JournalTransport(
        base=lambda _request, _timeout: raw,
        journal_path=tmp_path / "attempts.jsonl",
        geometry={"registered_requests": {}},
        manifest=_launch(),
    )

    def broken(_raw: bytes) -> dict[str, int]:
        raise ValueError(f"secret {_SECRET}")

    monkeypatch.setattr(runner, "_validated_usage", broken)
    with pytest.raises(RuntimeError, match="usage parsing failed"):
        journal(_canary_request(), 1.0)
    evidence = journal.journal_path.read_text()
    assert "usage-parse-failed" in evidence
    assert runner._sha(raw) in evidence
    assert _SECRET not in evidence
    assert journal.unknown_usage_attempts == 1


def test_journal_rejects_endpoint_drift_before_transport(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    source = _canary_request()
    request = urllib.request.Request(
        "https://wrong.example/model-api/chat/completions",
        data=source.data,
        method="POST",
    )
    journal = runner._JournalTransport(
        base=fake,
        journal_path=tmp_path / "attempts.jsonl",
        geometry={"registered_requests": {}},
        manifest=_launch(),
    )
    with pytest.raises(RuntimeError, match="endpoint differs"):
        journal(request, 1.0)
    assert calls == []
    assert journal.attempts == 0


def test_cli_requires_explicit_execute_flag() -> None:
    with pytest.raises(SystemExit):
        runner.main(
            [
                "--source-root",
                str(_SOURCE),
                "--tokenizer-path",
                str(_TOKENIZER),
                "--run-dir",
                "/tmp/never-created-r15-pep",
            ]
        )
