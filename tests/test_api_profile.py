from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.experiment.api import (
    load_api_profiles,
    run_api_canary,
    write_api_canary,
)
from rsicontext.registry.schema import RegistryError

ROOT = Path(__file__).parents[1]


def _stream(answer: str, *, model: str = "hy3-ioa") -> bytes:
    chunks = (
        {
            "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
            "id": "response-1",
            "model": model,
            "usage": {"completion_tokens": 2, "prompt_tokens": 20},
        },
    )
    events = [f"data: {json.dumps(chunk)}" for chunk in chunks]
    return ("\n\n".join((*events, "data: [DONE]")) + "\n\n").encode()


def test_api_profile_is_strict_and_marks_unversioned_provider() -> None:
    profiles = load_api_profiles(ROOT / "configs" / "api_profiles.json")
    profile = profiles.get("tencent-copilot-hy3-ioa")

    assert profile.model == "hy3-ioa"
    assert profile.protocol == "chat-completions-sse"
    assert profile.provider_revision is None
    assert profile.chat_template_enable_thinking is None
    assert (
        profile.profile_hash == "4b6628b16beedd447cb58c551178d9bea8263257736577b8a14f673103ec7082"
    )
    assert profile.version_pinned is False
    assert len(profile.profile_hash) == 64


def test_api_profile_rejects_unknown_fields(tmp_path: Path) -> None:
    raw = json.loads((ROOT / "configs" / "api_profiles.json").read_text(encoding="utf-8"))
    raw["profiles"][0]["reasoning_effort"] = "high"
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match="unexpected"):
        load_api_profiles(path)


def test_api_canary_records_replay_and_never_records_key() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    payloads: list[dict[str, object]] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        assert request.data is not None
        payloads.append(json.loads(cast(bytes, request.data)))
        return _stream("amber")

    ticks = iter((0.0, 0.2, 1.0, 1.3, 2.0, 2.4))
    result = run_api_canary(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        repetitions=3,
        transport=transport,
        timer=lambda: next(ticks),
        started_at="2026-08-14T00:00:00Z",
    )

    assert result.answers == ("amber", "amber", "amber")
    assert result.answer_stable is True
    assert result.observed_models == ("hy3-ioa", "hy3-ioa", "hy3-ioa")
    assert result.input_tokens == (20, 20, 20)
    assert result.latency_seconds == pytest.approx((0.2, 0.3, 0.4))
    assert result.version_pinned is False
    assert result.answer_correct is True
    assert result.usage_stable is True
    assert "secret-value" not in json.dumps(result.to_dict())
    assert all(payload["temperature"] == 0.0 for payload in payloads)
    assert all(payload["stream"] is True for payload in payloads)


def test_api_canary_record_is_exclusive(tmp_path: Path) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    result = run_api_canary(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        repetitions=1,
        transport=lambda request, timeout: _stream("amber"),
        timer=iter((0.0, 0.1)).__next__,
        started_at="2026-08-14T00:00:00Z",
    )
    path = tmp_path / "nested" / "canary.json"

    write_api_canary(result, path)

    assert json.loads(path.read_text(encoding="utf-8"))["answers"] == ["amber"]
    with pytest.raises(FileExistsError):
        write_api_canary(result, path)


def test_api_canary_distinguishes_stable_from_correct() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    result = run_api_canary(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="key",
        repetitions=2,
        transport=lambda request, timeout: _stream("blue"),
        timer=iter((0.0, 0.1, 1.0, 1.2)).__next__,
        started_at="2026-08-14T00:00:00Z",
    )

    assert result.answer_stable is True
    assert result.answer_correct is False


def test_api_canary_rejects_invalid_repetition_budget() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    with pytest.raises(ValueError, match="repetitions"):
        run_api_canary(
            profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            repetitions=0,
        )
