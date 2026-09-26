"""R20 Iceberg S2 probe tests use injected SSE and never contact Siflow."""

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
from rsicontext.analysis.iceberg_short_private_r20 import ORACLE_SHA256, verified_oracle
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r20_iceberg_short_offline as short  # noqa: E402
import r20_iceberg_short_paid_runner as runner  # noqa: E402

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
SECRET = "never-persist-r20-secret"


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not SOURCE.is_dir() or not TOKENIZER.is_dir():
        pytest.skip("pinned Iceberg source or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned tokenizer runtime unavailable")


def _stream(answer: str, model: str, input_tokens: int, sequence: int) -> bytes:
    identity = {"id": f"r20-fake-{sequence}", "model": model}
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
    answers: tuple[str, str, str, str] = (
        "plan=suppress-row", "plan=emit-row", "plan=emit-row", "plan=emit-row"
    ),
    missing_usage: bool = False,
) -> Transport:
    canary_fake = canary._fake_transport(profile, tokenizer)
    registered = cast(dict[str, object], json.loads(short.REGISTRATION.read_bytes()))
    requests = cast(list[dict[str, object]], registered["requests"])
    by_hash = {
        str(item["request_sha256"]): (
            str(item["case"]),
            cast(dict[str, object], item["local_template_geometry"])["rendered_input_tokens"],
        )
        for item in requests
    }

    def fake(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        assert SECRET not in str(request.header_items())
        body = cast(dict[str, object], json.loads(request.data))
        messages = cast(list[dict[str, str]], body["messages"])
        prompt = messages[1]["content"]
        if prompt == canary.PROMPT:
            calls.append("canary")
            return canary_fake(request, timeout)
        case, input_tokens = by_hash[runner._sha(request.data)]
        assert case in short.CASE_ORDER
        assert len(prompt.encode()) < 3000
        assert "Selected reference body:" not in prompt
        assert "private_correct_reply" not in request.data.decode()
        assert "private_oracle" not in request.data.decode()
        calls.append(case)
        answer = answers[short.CASE_ORDER.index(case)]
        raw = _stream(answer, profile.model, cast(int, input_tokens), len(calls))
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


def test_registration_and_private_truth_table(tokenizer: ChatTokenizer) -> None:
    profile = canary._profile()
    frozen = json.loads(short.REGISTRATION.read_bytes())
    assert frozen == short.build_registration(
        SOURCE, TOKENIZER, profile=profile, tokenizer=tokenizer
    )
    assert frozen["case_order"] == list(short.CASE_ORDER)
    assert frozen["local_input_tokens"] == 784
    assert frozen["local_input_plus_requested_ceiling"] == 8976
    assert verified_oracle() == {
        "data-counter-match": "plan=suppress-row",
        "file-counter-match": "plan=emit-row",
        "data-counter-mismatch": "plan=emit-row",
    }
    registration_text = short.REGISTRATION.read_text()
    assert "plan=suppress-row" not in registration_text
    assert "plan=emit-row" not in registration_text
    a, b, c, d = (short.decision_user(case) for case in short.CASE_ORDER)
    assert all("same partition spec 2, region=A" in prompt for prompt in (a, b, c, d))
    assert a.replace("counter=data", "counter=<counter>") == b.replace(
        "counter=file", "counter=<counter>"
    )
    assert a.replace("delete value 42", "delete value <value>") == c.replace(
        "delete value 99", "delete value <value>"
    )
    assert a.replace(short.RULES["data-counter-match"], "<rule>") == d.replace(
        short.RULES["unknown-diagnostic"], "<rule>"
    )
    for item, prompt in zip(frozen["requests"], (a, b, c, d), strict=True):
        assert item["prompt_sha256"] == runner._sha(prompt.encode())
        assert item["request_sha256"] == runner._sha(
            short._canonical(short._request_payload(profile, prompt))
        )


def test_complete_synthetic_panel_has_six_calls_and_private_ledger(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    run_dir = tmp_path / "complete"
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=run_dir,
        transport_override=_route(canary._profile(), tokenizer, calls),
    )
    assert result["status"] == "completed-synthetic-screen"
    assert result["scope"] == "r20-iceberg-short-paid-feasibility-v2"
    assert result["task_feasible"] is True
    assert result["provider_block_valid"] is False
    assert result["qualified_parent"] is False
    assert result["attempted_http_calls"] == 6
    assert result["task_http_calls"] == 4
    assert result["canary_http_calls"] == 2
    assert result["local_plus_requested_tokens"] == 13196
    assert calls == ["canary", *short.CASE_ORDER, "canary"]
    task = json.loads((run_dir / "task.json").read_bytes())
    assert [row["correct"] for row in task["cases"]] == [True, True, True, None]
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


def test_wrong_format_valid_first_plan_keeps_controls(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    answers = ("plan=emit-row", "plan=emit-row", "plan=emit-row", "plan=suppress-row")
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=tmp_path / "wrong-first",
        transport_override=_route(canary._profile(), tokenizer, calls, answers=answers),
    )
    assert calls == ["canary", *short.CASE_ORDER, "canary"]
    assert result["status"] == "completed-synthetic-screen"
    assert result["task_feasible"] is False
    task = json.loads((tmp_path / "wrong-first/task.json").read_bytes())
    assert task["status"] == "completed-panel"
    assert [row["correct"] for row in task["cases"]] == [False, True, True, None]


@pytest.mark.parametrize(
    "failure, expected_status",
    [("missing-usage", "usage-unverified"), ("invalid-format", "task-failed")],
)
def test_protocol_failures_stop_before_second_target(
    tokenizer: ChatTokenizer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_status: str,
) -> None:
    _prepared(monkeypatch)
    calls: list[str] = []
    answers = (
        ("invalid", "plan=emit-row", "plan=emit-row", "plan=emit-row")
        if failure == "invalid-format"
        else ("plan=suppress-row", "plan=emit-row", "plan=emit-row", "plan=emit-row")
    )
    result = runner.run_guarded(
        source_root=SOURCE,
        tokenizer_path=TOKENIZER,
        run_dir=tmp_path / failure,
        transport_override=_route(
            canary._profile(), tokenizer, calls, answers=answers,
            missing_usage=failure == "missing-usage",
        ),
    )
    assert result["status"] == expected_status
    assert calls == ["canary", short.CASE_ORDER[0]]
    assert result["task_http_calls"] == 1 and result["canary_http_calls"] == 1
    assert not (tmp_path / failure / "post_canary.json").exists()


@pytest.mark.usefixtures("tokenizer")
def test_live_v2_checks_credentials_before_any_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared(monkeypatch)

    def refuse_credential(*_args: object, **_kwargs: object) -> None:
        raise ValueError("test credential refusal")

    monkeypatch.setattr(
        runner, "resolve_api_endpoint",
        refuse_credential,
    )
    monkeypatch.setattr(
        runner, "_urlopen_transport",
        lambda *_args, **_kwargs: pytest.fail("credential refusal reached HTTP"),
    )
    result = runner.run_guarded(
        source_root=SOURCE, tokenizer_path=TOKENIZER, run_dir=tmp_path / "no-credential"
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["scope"] == "r20-iceberg-short-paid-feasibility-v2"
    assert result["failure_type"] == "ValueError"
    assert "attempted_http_calls" not in result


def test_forged_launch_refuses_before_credential_resolution_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed_launch = runner._LAUNCH.read_bytes()
    forged = tmp_path / "forged.json"
    forged.write_text(runner._LAUNCH.read_text().replace("13196", "13197"))
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


def test_cli_rejects_protocol_complete_but_wrong_panel(
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
    assert runner._LAUNCH_REL == "configs/r20_iceberg_short_paid_launch_v2.json"
    assert launch["schema_version"] == 2
    assert launch["global_call_cap"] == 6
    assert launch["live_enabled"] is True
    assert launch["registration_sha256"] == runner._sha(short.REGISTRATION.read_bytes())
    assert launch["private_oracle_sha256"] == ORACLE_SHA256
    assert digest == runner._sha(runner._LAUNCH.read_bytes())
    v1_raw = (ROOT / "configs/r20_iceberg_short_paid_launch_v1.json").read_bytes()
    assert runner._sha(v1_raw) == (
        "3bd1b78f5bf02fd7eb3a1d6e7d42d380e4a3fa82c9c4c6a4425a0e859418fb78"
    )
    v1 = json.loads(v1_raw)
    for field in set(v1) - {"schema_version", "scope", "live_enabled", "bound_file_sha256"}:
        assert launch[field] == v1[field]
    producer = "scripts/r20_iceberg_short_paid_runner.py"
    bound = cast(dict[str, str], launch["bound_file_sha256"])
    assert {name: digest for name, digest in bound.items() if name != producer} == {
        name: digest for name, digest in v1["bound_file_sha256"].items()
        if name != producer
    }
