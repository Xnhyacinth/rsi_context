"""R18 calibration paid runner is exercised with injected SSE only."""

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
import r17_kep_diagnostic_offline as fake_sse  # noqa: E402
import r18_kep_calibration_paid_runner as runner  # noqa: E402

SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
R16_TASK = Path(
    os.environ.get(
        "RSICONTEXT_R16_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json",
    )
)
R17_TASK = Path(
    os.environ.get(
        "RSICONTEXT_R17_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/"
        "kep-arithmetic-diagnostic-v1/task.json",
    )
)
TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)
SECRET = "never-write-r18-test-secret"


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not all(path.exists() for path in (SOURCE, R16_TASK, R17_TASK, TOKENIZER)):
        pytest.skip("pinned source, paid observations or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned tokenizer runtime unavailable")


def fake_route(
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    calls: list[str],
    *,
    bad_final: bool = False,
    missing_usage: bool = False,
) -> Transport:
    canary_fake = canary._fake_transport(profile, tokenizer)
    registration = json.loads(runner._REGISTRATION_PATH.read_text())
    expected = {item["prompt_sha256"]: item["case"] for item in registration["requests"]}
    answers = {
        "coarse-membership": "a_sidecar_m=300\nb_sidecar_m=0",
        "coarse-numeric": "effective_cpu_m=1200\nplan=hold-at-1000m",
        "explicit-membership": "a_sidecar_m=0\nb_sidecar_m=300",
        "explicit-numeric": "invalid" if bad_final else "effective_cpu_m=800\nplan=admit-at-1000m",
    }

    def route(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        assert SECRET not in str(request.header_items())
        prompt = json.loads(request.data)["messages"][1]["content"]
        calls.append("canary" if prompt == canary.PROMPT else "task")
        if prompt == canary.PROMPT:
            return canary_fake(request, timeout)
        raw = fake_sse._fake_sse(
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


def guarded_run(run_dir: Path, transport: Transport) -> dict[str, object]:
    return runner.run_guarded(
        source_root=SOURCE,
        r16_task=R16_TASK,
        r17_task=R17_TASK,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=transport,
    )


def test_full_fake_chain_counts_six_calls_and_keeps_private_synthetic_evidence(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", SECRET)
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("synthetic run resolved credentials"),
    )
    calls: list[str] = []
    run_dir = tmp_path / "full"
    result = guarded_run(run_dir, fake_route(canary._profile(), tokenizer, calls))
    assert result["status"] == "completed-synthetic-calibration"
    assert result["provider_block_valid"] is False
    assert result["qualified_parent"] is False
    assert result["attempted_http_calls"] == 6
    assert result["task_http_calls"] == 4 and result["canary_http_calls"] == 2
    assert result["local_plus_requested_tokens"] == 13822
    assert result["task_provider_usage_total"] is None
    assert calls == ["canary", "task", "task", "task", "task", "canary"]
    task = json.loads((run_dir / "task.json").read_text())
    assert task["status"] == "completed-calibration"
    assert task["provider_usage_total"] is None
    assert task["synthetic_usage_total"]["input_tokens"] == 1410
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    contents = "".join(path.read_text() for path in run_dir.iterdir())
    assert SECRET not in contents and "Authorization" not in contents
    events = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events].count("dispatched") == 6
    assert [event["event"] for event in events].count("response-received") == 6
    with pytest.raises(FileExistsError, match="overwrite"):
        guarded_run(run_dir, fake_route(canary._profile(), tokenizer, []))


def test_invalid_final_reply_stops_before_post_canary(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    calls: list[str] = []
    run_dir = tmp_path / "invalid-final"
    result = guarded_run(run_dir, fake_route(canary._profile(), tokenizer, calls, bad_final=True))
    assert result["status"] == "task-worker-or-format-failed"
    assert result["provider_block_valid"] is False
    assert calls == ["canary", "task", "task", "task", "task"]
    assert not (run_dir / "post_canary.json").exists()
    task = json.loads((run_dir / "task.json").read_text())
    assert task["failure_type"] == "InvalidReplyFormat"


def test_missing_usage_stops_without_retry(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    calls: list[str] = []
    run_dir = tmp_path / "missing-usage"
    result = guarded_run(
        run_dir, fake_route(canary._profile(), tokenizer, calls, missing_usage=True)
    )
    assert result["status"] == "usage-unverified"
    assert calls == ["canary", "task"]
    assert result["task_http_calls"] == 1 and result["canary_http_calls"] == 1
    assert not (run_dir / "post_canary.json").exists()


def test_forged_launch_refuses_before_credentials_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forged = tmp_path / "forged-launch.json"
    forged.write_text(runner._LAUNCH_PATH.read_text().replace("13822", "13823"))
    monkeypatch.setattr(runner, "_LAUNCH_PATH", forged)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("forged launch resolved credentials"),
    )
    calls: list[str] = []

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    result = guarded_run(tmp_path / "forged", fake)
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert calls == []
