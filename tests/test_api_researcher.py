"""Tests for the DeepSeek API researcher arm (participant/api_researcher.py).

Unit tests use an injected fake transport (monkeypatched urllib) so no real
endpoint is called; one marked-live smoke requires SIFLOW_API_KEY and
SIFLOW_BASE_URL in the environment.
"""

from __future__ import annotations

import json
import urllib.error
from dataclasses import dataclass
from pathlib import Path

import pytest

from rsicontext.participant.api_researcher import (
    APIResearcherConfig,
    APIResearcherEmptyError,
    APIResearcherError,
    APIResearcherImprover,
    APIResearcherRetryableError,
    APIResearcherTransportError,
    APIResearcherTruncatedError,
    RetryPolicy,
)
from rsicontext.participant.registration import ImprovementRoundInput, ParticipantError

_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"


def _config() -> APIResearcherConfig:
    return APIResearcherConfig(endpoint=_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash")


def _agent_tree(tmp_path: Path) -> Path:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "policy.py").write_text("POLICY = 'h0'\n")
    (agent_dir / "notes.md").write_text("# notes\n")
    (agent_dir / "binary.bin").write_bytes(b"\x00\x01")  # excluded from prompt
    return agent_dir


def _round_input(agent_dir: Path) -> ImprovementRoundInput:
    return ImprovementRoundInput(
        round_index=0,
        task_text="improve the strategy",
        restricted_feedback_bytes=json.dumps({"previous": 0.5}).encode(),
        current_agent_dir=agent_dir,
        state_path=None,
        remaining_slots=5,
        task_order_seed=7,
    )


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _fake_server(monkeypatch: pytest.MonkeyPatch, reply_content: str) -> dict[str, object]:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        body = request.data if isinstance(request.data, bytes) else None
        captured["body"] = json.loads(body.decode() if body else "{}")
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        payload = {
            "choices": [{"message": {"content": reply_content, "role": "assistant"}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 120},
            "model": "deepseek-ai/deepseek-v4.1-flash",
        }
        return _FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


def test_config_requires_chat_completions_suffix() -> None:
    with pytest.raises(ParticipantError):
        APIResearcherConfig(endpoint="https://api.siflow.cn/model-api", model="m")


def test_improve_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    reply = json.dumps({"changes": {"policy.py": "POLICY = 'improved'\n"}})
    captured = _fake_server(monkeypatch, reply)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")

    improver = APIResearcherImprover(config=_config())
    output = improver.improve(_round_input(agent_dir))

    assert output.agent_files_changed == {"policy.py": "POLICY = 'improved'\n"}
    assert output.usage.input_tokens == 500
    assert output.usage.output_tokens == 120
    assert output.usage.wall_seconds >= 0
    # Prompt carried the agent files (binary excluded) and the feedback.
    body = captured["body"]
    assert isinstance(body, dict)
    user_text = body["messages"][1]["content"]
    assert "policy.py" in user_text
    assert "binary.bin" not in user_text
    assert "previous" in user_text
    # Credentials never live on the improver object.
    assert "sk-test" not in repr(improver)


def test_missing_credential_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    improver = APIResearcherImprover(config=_config())
    with pytest.raises(Exception, match="credential"):
        improver.improve(_round_input(_agent_tree(tmp_path)))


@pytest.mark.parametrize(
    "reply",
    [
        "no json here",
        '{"not_changes": {}}',
        '{"changes": {"../../evil.py": "x"}}',
        '{"changes": {"no_ext": "x"}}',
        '{"changes": {"ok.py": 42}}',
    ],
)
def test_unsafe_or_malformed_replies_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reply: str
) -> None:
    agent_dir = _agent_tree(tmp_path)
    _fake_server(monkeypatch, reply)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    improver = APIResearcherImprover(config=_config())
    with pytest.raises(APIResearcherError):
        improver.improve(_round_input(agent_dir))


@pytest.mark.live
def test_live_siflow_deepseek_round_trip(tmp_path: Path) -> None:
    """Live smoke: one real round on the researcher endpoint (needs env vars)."""

    import os

    if not os.environ.get("SIFLOW_API_KEY") or not os.environ.get("SIFLOW_BASE_URL"):
        pytest.skip("live smoke requires SIFLOW_API_KEY and SIFLOW_BASE_URL")
    config = APIResearcherConfig(
        endpoint=f"{os.environ['SIFLOW_BASE_URL']}/chat/completions"
        if not os.environ["SIFLOW_BASE_URL"].endswith("/chat/completions")
        else os.environ["SIFLOW_BASE_URL"],
        model="deepseek-ai/deepseek-v4.1-flash",
    )
    improver = APIResearcherImprover(config=config)
    output = improver.improve(_round_input(_agent_tree(tmp_path)))
    assert isinstance(output.agent_files_changed, dict)
    assert output.usage.input_tokens > 0


# --- retry / reliability gates (the 1/4 arm record) -------------------------


@dataclass(frozen=True, slots=True)
class _Reply:
    """One scripted researcher reply: content, finish reason, tokens, or transport error."""

    content: str = '{"changes": {}}'
    finish_reason: str | None = None
    input_tokens: int = 500
    output_tokens: int = 120
    transport_error: bool = False


class _ScriptedServer:
    """Fake urllib transport replaying scripted replies in order."""

    def __init__(self, replies: list[_Reply]) -> None:
        self._replies = list(replies)
        self.request_count = 0

    def urlopen(self, request: object, timeout: float) -> _FakeResponse:
        self.request_count += 1
        reply = self._replies.pop(0) if self._replies else _Reply()
        if reply.transport_error:
            raise urllib.error.URLError("connection reset by peer")
        payload = {
            "choices": [
                {
                    "message": {"content": reply.content, "role": "assistant"},
                    "finish_reason": reply.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": reply.input_tokens,
                "completion_tokens": reply.output_tokens,
            },
            "model": "deepseek-ai/deepseek-v4.1-flash",
        }
        return _FakeResponse(json.dumps(payload).encode())


def _scripted_server(monkeypatch: pytest.MonkeyPatch, replies: list[_Reply]) -> _ScriptedServer:
    server = _ScriptedServer(replies)
    monkeypatch.setattr("urllib.request.urlopen", server.urlopen)
    return server


def _improver(retry: RetryPolicy | None = None) -> APIResearcherImprover:
    config = (
        APIResearcherConfig(endpoint=_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash")
        if retry is None
        else APIResearcherConfig(
            endpoint=_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash", retry=retry
        )
    )
    return APIResearcherImprover(config=config, sleep=lambda seconds: None)


def test_retry_succeeds_after_empty_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(
        monkeypatch,
        [
            _Reply(content="", input_tokens=400, output_tokens=50),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 1\n"}})),
        ],
    )

    improver = _improver()
    output = improver.improve(_round_input(agent_dir))

    assert server.request_count == 2
    assert output.agent_files_changed == {"policy.py": "P = 1\n"}
    # The failed attempt's tokens are charged to the round too.
    assert output.usage.input_tokens == 900
    assert output.usage.output_tokens == 170
    assert [record["outcome"] for record in improver.attempts()] == ["empty_content", "ok"]
    assert [record["attempt"] for record in improver.attempts()] == [1, 2]
    assert improver.attempts()[0]["input_tokens"] == 400
    assert improver.attempts()[1]["output_tokens"] == 120


def test_truncation_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(
        monkeypatch,
        [
            _Reply(
                content='{"changes": {"policy.py": "P = 1"',
                finish_reason="length",
                input_tokens=300,
                output_tokens=2000,
            ),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 2\n"}})),
        ],
    )

    improver = _improver()
    output = improver.improve(_round_input(agent_dir))

    assert server.request_count == 2
    assert output.agent_files_changed == {"policy.py": "P = 2\n"}
    assert output.usage.output_tokens == 2120
    assert [record["outcome"] for record in improver.attempts()] == ["truncated", "ok"]


def test_transport_error_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(
        monkeypatch,
        [
            _Reply(transport_error=True),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 3\n"}})),
        ],
    )

    improver = _improver()
    output = improver.improve(_round_input(agent_dir))

    assert server.request_count == 2
    assert output.agent_files_changed == {"policy.py": "P = 3\n"}
    # A transport failure reported no usage; only the success is charged.
    assert output.usage.input_tokens == 500
    assert [record["outcome"] for record in improver.attempts()] == ["transport_error", "ok"]
    assert improver.attempts()[0]["input_tokens"] == 0


@pytest.mark.parametrize(
    ("failure_reply", "error_class"),
    [
        (_Reply(content="", input_tokens=100, output_tokens=10), APIResearcherEmptyError),
        (
            _Reply(
                content='{"changes"', finish_reason="length", input_tokens=100, output_tokens=10
            ),
            APIResearcherTruncatedError,
        ),
        (_Reply(transport_error=True), APIResearcherTransportError),
    ],
)
def test_transient_failures_exhaust_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_reply: _Reply,
    error_class: type[APIResearcherRetryableError],
) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(monkeypatch, [failure_reply, failure_reply, failure_reply])

    improver = _improver(retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0))
    with pytest.raises(error_class):
        improver.improve(_round_input(agent_dir))

    assert server.request_count == 3
    assert [record["outcome"] for record in improver.attempts()] == [
        error_class.outcome,
        error_class.outcome,
        error_class.outcome,
    ]


def test_retry_disabled_for_outcome_class(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(monkeypatch, [_Reply(content=""), _Reply(content="ok")])

    improver = _improver(retry=RetryPolicy(retry_on=("truncated",)))
    with pytest.raises(APIResearcherEmptyError):
        improver.improve(_round_input(agent_dir))

    assert server.request_count == 1


def test_malformed_json_not_retried(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    # The HTTP reply parses as JSON but carries no usable content channel.
    server = _scripted_server(monkeypatch, [_Reply(content="no json here"), _Reply()])

    improver = _improver()
    with pytest.raises(APIResearcherError) as excinfo:
        improver.improve(_round_input(agent_dir))

    assert not isinstance(excinfo.value, APIResearcherRetryableError)
    assert server.request_count == 1


def test_empty_changes_is_valid_outcome_not_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    server = _scripted_server(monkeypatch, [_Reply(content='{"changes": {}}'), _Reply()])

    improver = _improver()
    output = improver.improve(_round_input(agent_dir))

    assert server.request_count == 1
    assert output.agent_files_changed == {}
    assert [record["outcome"] for record in improver.attempts()] == ["ok"]


def test_backoff_sleeps_between_attempts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    _scripted_server(
        monkeypatch,
        [
            _Reply(content=""),
            _Reply(content=""),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 4\n"}})),
        ],
    )

    sleeps: list[float] = []
    improver = APIResearcherImprover(
        config=APIResearcherConfig(
            endpoint=_ENDPOINT,
            model="deepseek-ai/deepseek-v4.1-flash",
            retry=RetryPolicy(max_attempts=3, backoff_seconds=1.5),
        ),
        sleep=sleeps.append,
    )
    output = improver.improve(_round_input(agent_dir))

    assert output.agent_files_changed == {"policy.py": "P = 4\n"}
    assert sleeps == [1.5, 1.5]


def test_attempt_log_persists_across_rounds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent_dir = _agent_tree(tmp_path)
    monkeypatch.setenv("SIFLOW_API_KEY", "sk-test")
    _scripted_server(
        monkeypatch,
        [
            _Reply(content=""),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 5\n"}})),
            _Reply(content=json.dumps({"changes": {"policy.py": "P = 6\n"}})),
        ],
    )

    improver = _improver()
    first = improver.improve(_round_input(agent_dir))
    second = improver.improve(_round_input(agent_dir))

    assert first.usage.input_tokens == 1000  # 500 (failed) + 500 (ok)
    assert second.usage.input_tokens == 500
    assert len(improver.usage_reports()) == 2
    # The attempt log spans both rounds; the second round restarts at 1.
    assert [record["attempt"] for record in improver.attempts()] == [1, 2, 1]
    assert [record["outcome"] for record in improver.attempts()] == [
        "empty_content",
        "ok",
        "ok",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": True},
        {"backoff_seconds": -1.0},
        {"backoff_seconds": float("nan")},
        {"retry_on": ("not_a_failure_class",)},
        {"retry_on": "truncated"},
    ],
)
def test_retry_policy_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ParticipantError):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]


def test_config_rejects_non_retry_policy_retry() -> None:
    with pytest.raises(ParticipantError):
        APIResearcherConfig(
            endpoint=_ENDPOINT,
            model="deepseek-ai/deepseek-v4.1-flash",
            retry="always",  # type: ignore[arg-type]
        )
