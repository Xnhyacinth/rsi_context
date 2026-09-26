"""R19 Iceberg S2 probe tests use injected SSE and never contact Siflow."""

from __future__ import annotations

import json
import os
import stat
import sys
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.analysis.iceberg_short_private_r19 import ORACLE_SHA256
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile
from rsicontext.lifecycle.material_iceberg_row_scan import build_iceberg_row_scan_sessions

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_r18_iceberg_geometry as geometry_source  # noqa: E402
import r15_exact_profile_canary as canary  # noqa: E402
import r19_iceberg_short_offline as short  # noqa: E402
import r19_iceberg_short_paid_runner as runner  # noqa: E402

SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_ICEBERG_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake",
    )
)
TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)
SECRET = "never-persist-r19-secret"


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not SOURCE.is_dir() or not TOKENIZER.is_dir():
        pytest.skip("pinned Iceberg source or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned tokenizer runtime unavailable")


def _stream(answer: str, model: str, input_tokens: int, sequence: int) -> bytes:
    identity = {"id": f"r19-fake-{sequence}", "model": model}
    first = {**identity, "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}]}
    usage = {
        **identity,
        "choices": [],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": 5},
    }
    return (
        "data: " + json.dumps(first) + "\n\ndata: " + json.dumps(usage) + "\n\ndata: [DONE]\n\n"
    ).encode()


def _route(
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    calls: list[str],
    *,
    first_answer: str = "plan=suppress-row",
    second_answer: str = "plan=emit-row",
    missing_usage: bool = False,
) -> Transport:
    canary_fake = canary._fake_transport(profile, tokenizer)
    registered = cast(dict[str, object], json.loads(short.REGISTRATION.read_bytes()))
    requests = cast(list[dict[str, object]], registered["requests"])
    by_hash = {str(item["request_sha256"]): str(item["case"]) for item in requests}

    def fake(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        assert SECRET not in str(request.header_items())
        body = cast(dict[str, object], json.loads(request.data))
        messages = cast(list[dict[str, str]], body["messages"])
        prompt = messages[1]["content"]
        if prompt == canary.PROMPT:
            calls.append("canary")
            return canary_fake(request, timeout)
        case = by_hash[runner._sha(request.data)]
        assert case in short.CASE_ORDER
        assert len(prompt.encode()) < 3000
        assert "Selected reference body:" not in prompt
        assert "private_correct_reply" not in request.data.decode()
        assert "private_oracle" not in request.data.decode()
        calls.append(case)
        answer = first_answer if case == "data-counter" else second_answer
        raw = _stream(answer, profile.model, 321, len(calls))
        if missing_usage:
            return b"\n".join(line for line in raw.split(b"\n") if b'"usage"' not in line)
        return raw

    return fake


def _prepared(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise transport and ledger while a development tree is uncommitted."""

    monkeypatch.setenv("SIFLOW_API_KEY", SECRET)
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("injected run resolved a credential"),
    )
    monkeypatch.setattr(
        runner,
        "_read_launch",
        lambda: (json.loads(runner._LAUNCH.read_bytes()), "synthetic-launch-sha"),
    )
    monkeypatch.setattr(
        runner,
        "producer_attestation",
        lambda *_args, **_kwargs: {"worktree_dirty": False, "producer_files_match_head": True},
    )
    monkeypatch.setattr(runner, "require_clean_producer", lambda _attestation: None)
    monkeypatch.setattr(
        runner, "require_stable_attestation", lambda _before, _after: None
    )


def test_registration_is_exact_two_prompt_counter_only_contrast(tokenizer: ChatTokenizer) -> None:
    profile = canary._profile()
    generated = short.build_registration(SOURCE, TOKENIZER, profile=profile, tokenizer=tokenizer)
    frozen = json.loads(short.REGISTRATION.read_bytes())
    assert frozen == generated
    assert frozen["case_order"] == ["data-counter", "file-counter"]
    assert frozen["local_input_tokens"] == 642
    assert frozen["local_input_plus_requested_ceiling"] == 4738
    assert "private_correct_reply" not in short.REGISTRATION.read_text()
    assert "plan=suppress-row" not in short.REGISTRATION.read_text()
    assert "plan=emit-row" not in short.REGISTRATION.read_text()
    request = build_iceberg_row_scan_sessions(SOURCE, case="authentic-pack")[1]
    request_text = request.stages[1].documents[0].text
    data = geometry_source.decision_user(request_text, short.RULES["data-counter"])
    file = geometry_source.decision_user(request_text, short.RULES["file-counter"])
    assert data.replace("counter=data", "counter=<counter>") == file.replace(
        "counter=file", "counter=<counter>"
    )
    for item, prompt in zip(frozen["requests"], (data, file), strict=True):
        assert item["prompt_sha256"] == runner._sha(prompt.encode())
        assert item["request_sha256"] == runner._sha(
            short._canonical(short._request_payload(profile, prompt))
        )
        assert item["local_template_geometry"]["rendered_input_tokens"] == 321


def test_correct_pair_has_four_calls_private_ledger_and_no_long_source(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    run_dir = tmp_path / "correct"
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=_route(canary._profile(), tokenizer, calls),
    )
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_feasible"] is True
    assert result["provider_block_valid"] is False
    assert result["qualified_parent"] is False
    assert result["attempted_http_calls"] == 4
    assert result["task_http_calls"] == 2
    assert result["canary_http_calls"] == 2
    assert result["local_plus_requested_tokens"] == 8958
    assert calls == ["canary", "data-counter", "file-counter", "canary"]
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    joined = "".join(path.read_text() for path in run_dir.iterdir())
    assert SECRET not in joined and "Authorization" not in joined
    with pytest.raises(FileExistsError, match="overwrite"):
        runner.run_guarded(
            source_root=SOURCE,
            tokenizer_path=TOKENIZER,
            run_dir=run_dir,
            transport_override=_route(canary._profile(), tokenizer, []),
        )


def test_wrong_first_plan_still_tests_second_and_post_canary(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=tmp_path / "wrong-first",
        transport_override=_route(
            canary._profile(), tokenizer, calls, first_answer="plan=emit-row"
        ),
    )
    assert calls == ["canary", "data-counter", "file-counter", "canary"]
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_feasible"] is False
    task = json.loads((tmp_path / "wrong-first/task.json").read_bytes())
    assert task["status"] == "completed-pair"
    assert [row["correct"] for row in task["cases"]] == [False, True]


def test_fixed_suppress_shortcut_is_observed_in_both_arms(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    run_dir = tmp_path / "fixed-suppress"
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=_route(
            canary._profile(), tokenizer, calls, second_answer="plan=suppress-row"
        ),
    )
    assert calls == ["canary", "data-counter", "file-counter", "canary"]
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_feasible"] is False
    task = json.loads((run_dir / "task.json").read_bytes())
    assert [row["correct"] for row in task["cases"]] == [True, False]


def test_terminal_newline_is_valid_outer_whitespace(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=tmp_path / "newline",
        transport_override=_route(
            canary._profile(), tokenizer, calls, first_answer="plan=suppress-row\n"
        ),
    )
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_feasible"] is True


@pytest.mark.parametrize(
    "failure, expected_status",
    [("missing-usage", "usage-unverified"), ("invalid-format", "task-failed")],
)
def test_failures_stop_without_second_target_or_post_canary(
    tokenizer: ChatTokenizer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_status: str,
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    transport = _route(
        canary._profile(),
        tokenizer,
        calls,
        first_answer="invalid" if failure == "invalid-format" else "plan=suppress-row",
        missing_usage=failure == "missing-usage",
    )
    run_dir = tmp_path / failure
    result = runner.run_guarded(
        source_root=SOURCE, tokenizer_path=TOKENIZER, run_dir=run_dir,
        transport_override=transport,
    )
    assert result["status"] == expected_status
    assert calls == ["canary", "data-counter"]
    assert result["task_http_calls"] == 1 and result["canary_http_calls"] == 1
    assert not (run_dir / "post_canary.json").exists()
    assert (run_dir / "final.json").exists()


def test_forged_launch_refuses_before_credential_resolution_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed_launch = runner._LAUNCH.read_bytes()
    forged = tmp_path / "forged.json"
    forged.write_text(runner._LAUNCH.read_text().replace("8958", "8959"))
    monkeypatch.setattr(runner, "_LAUNCH", forged)
    monkeypatch.setattr(
        runner,
        "_committed_bytes",
        lambda relative: committed_launch if relative == runner._LAUNCH_REL else b"",
    )
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("forged launch resolved credentials"),
    )
    result = runner.run_guarded(
        source_root=SOURCE, tokenizer_path=TOKENIZER, run_dir=tmp_path / "forged-run"
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert "attempted_http_calls" not in result


def test_cli_rejects_protocol_complete_but_wrong_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        runner,
        "run_guarded",
        lambda **_kwargs: {
            "status": "completed-paid-screen",
            "provider_block_valid": True,
            "task_feasible": False,
        },
    )
    exit_code = runner.main(
        [
            "--execute", "--source-root", str(SOURCE), "--tokenizer-path", str(TOKENIZER),
            "--run-dir", str(tmp_path / "unused"),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert printed["provider_block_valid"] is True
    assert printed["task_feasible"] is False


def test_committed_launch_and_bound_code_match_head() -> None:
    launch, digest = runner._read_launch()
    assert launch["global_call_cap"] == 4
    assert launch["private_oracle_sha256"] == ORACLE_SHA256
    assert digest == runner._sha(runner._LAUNCH.read_bytes())
