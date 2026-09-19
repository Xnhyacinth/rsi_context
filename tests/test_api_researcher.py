"""Tests for the DeepSeek API researcher arm (participant/api_researcher.py).

Unit tests use an injected fake transport (monkeypatched urllib) so no real
endpoint is called; one marked-live smoke requires SIFLOW_API_KEY and
SIFLOW_BASE_URL in the environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.participant.api_researcher import (
    APIResearcherConfig,
    APIResearcherError,
    APIResearcherImprover,
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

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        captured["body"] = json.loads(request.data.decode() if request.data else "{}")
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
