"""Guarded R17 KEP diagnostic uses injected SSE only; never a paid endpoint."""

from __future__ import annotations

import json
import os
import stat
import sys
import urllib.request
from pathlib import Path

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r17_kep_diagnostic_offline as offline  # noqa: E402
import r17_kep_diagnostic_paid_runner as runner  # noqa: E402

SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
TASK = Path(
    os.environ.get(
        "RSICONTEXT_R16_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json",
    )
)
TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)
SECRET = "never-write-r17-test-secret"


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not SOURCE.is_dir() or not TASK.is_file() or not TOKENIZER.is_dir():
        pytest.skip("pinned KEP source, R16 task or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned optional tokenizer runtime unavailable")


def fake_route(
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    calls: list[str],
    *,
    bad_membership: bool = False,
    missing_usage: bool = False,
) -> Transport:
    canary_fake = canary._fake_transport(profile, tokenizer)
    registration = json.loads(runner._REGISTRATION_PATH.read_text())
    expected = {item["prompt_sha256"]: item["case"] for item in registration["requests"]}
    answers = {
        "legacy-with-prior": "plan=hold-at-1000m",
        "rule-membership": "invalid" if bad_membership else "a_sidecar_m=0\nb_sidecar_m=300",
        "numeric-with-prior": "effective_cpu_m=1100\nplan=hold-at-1000m",
        "numeric-without-prior": "effective_cpu_m=800\nplan=admit-at-1000m",
    }

    def route(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        assert SECRET not in str(request.header_items())
        prompt = json.loads(request.data)["messages"][1]["content"]
        calls.append("canary" if prompt == canary.PROMPT else "task")
        if prompt == canary.PROMPT:
            return canary_fake(request, timeout)
        raw = offline._fake_sse(
            request,
            timeout,
            tokenizer=tokenizer,
            profile=profile,
            answers=answers,
            expected=expected,
        )
        if missing_usage:
            return b"\n".join(line for line in raw.split(b"\n") if b'"usage"' not in line)
        return raw

    return route


def test_synthetic_full_chain_private_complete_and_no_credential_lookup(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", SECRET)
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("injected transport looked up credentials"),
    )
    calls: list[str] = []
    run_dir = tmp_path / "full"
    result = runner.run_guarded(
        source_root=SOURCE,
        r16_task=TASK,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=fake_route(canary._profile(), tokenizer, calls),
    )
    assert result["status"] == "completed-synthetic-diagnostic"
    assert result["provider_block_valid"] is False
    assert result["qualified_parent"] is False
    assert result["task_provider_usage_total"] is None
    assert result["task_http_calls"] == 4
    assert result["canary_http_calls"] == 2
    assert result["attempted_http_calls"] == 6
    assert result["local_plus_requested_tokens"] == 13618
    assert calls == ["canary", "task", "task", "task", "task", "canary"]
    task = json.loads((run_dir / "task.json").read_text())
    assert task["status"] == "completed-diagnostic"
    assert task["worker_attempt_count"] == 4
    assert task["provider_usage_total"] is None
    assert task["synthetic_usage_total"]["input_tokens"] == 1206
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    contents = "".join(path.read_text() for path in run_dir.iterdir())
    assert SECRET not in contents
    assert "Authorization" not in contents
    events = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events].count("dispatched") == 6
    assert [event["event"] for event in events].count("response-received") == 6
    with pytest.raises(FileExistsError, match="overwrite"):
        runner.run_guarded(
            source_root=SOURCE,
            r16_task=TASK,
            tokenizer_path=TOKENIZER,
            run_dir=run_dir,
            transport_override=fake_route(canary._profile(), tokenizer, []),
        )


def test_invalid_task_reply_stops_before_remaining_calls_and_post_canary(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    calls: list[str] = []
    run_dir = tmp_path / "bad-format"
    result = runner.run_guarded(
        source_root=SOURCE,
        r16_task=TASK,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=fake_route(canary._profile(), tokenizer, calls, bad_membership=True),
    )
    assert result["status"] == "task-worker-or-format-failed"
    assert calls == ["canary", "task", "task"]
    assert result["task_http_calls"] == 2
    assert not (run_dir / "post_canary.json").exists()


def test_missing_provider_usage_stops_without_retry_or_post_canary(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    calls: list[str] = []
    run_dir = tmp_path / "missing-usage"
    result = runner.run_guarded(
        source_root=SOURCE,
        r16_task=TASK,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=fake_route(canary._profile(), tokenizer, calls, missing_usage=True),
    )
    assert result["status"] == "usage-unverified"
    assert calls == ["canary", "task"]
    assert result["task_http_calls"] == 1
    assert result["canary_http_calls"] == 1
    assert not (run_dir / "post_canary.json").exists()
    events = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
    assert any(event["event"] == "response-received" and event["provider_usage"] is None
               for event in events)


def test_forged_launch_refuses_before_credential_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forged = tmp_path / "forged-launch.json"
    forged.write_text(runner._LAUNCH_PATH.read_text().replace("13618", "13619"))
    monkeypatch.setattr(runner, "_LAUNCH_PATH", forged)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("forged launch looked up credentials"),
    )
    calls: list[str] = []

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    result = runner.run_guarded(
        source_root=SOURCE,
        r16_task=TASK,
        tokenizer_path=TOKENIZER,
        run_dir=tmp_path / "forged",
        transport_override=fake,
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert calls == []
    assert (tmp_path / "forged/final.json").exists()
