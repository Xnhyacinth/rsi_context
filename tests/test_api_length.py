from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.experiment import load_api_profiles
from rsicontext.experiment.api_length import (
    run_api_length_canary,
    write_api_length_canary,
)

ROOT = Path(__file__).parents[1]


def _stream(answer: str, *, prompt_tokens: int = 200) -> bytes:
    chunk = {
        "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
        "id": "length-response",
        "model": "hy3-ioa",
        "usage": {"completion_tokens": 4, "prompt_tokens": prompt_tokens},
    }
    return f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()


def test_length_canary_records_cells_usage_and_replay(tmp_path: Path) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    payloads: list[dict[str, object]] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        assert request.data is not None
        payloads.append(json.loads(cast(bytes, request.data)))
        return _stream("AURORA-7319")

    tick = [0.0]

    def timer() -> float:
        value = tick[0]
        tick[0] += 0.1
        return value

    result = run_api_length_canary(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        target_lengths=(256, 512),
        positions=("front", "tail"),
        repetitions=2,
        transport=transport,
        timer=timer,
        started_at="2026-08-14T00:00:00Z",
    )

    assert len(result.observations) == 8
    assert len(result.summaries) == 4
    assert all(summary.accuracy == 1.0 for summary in result.summaries)
    assert all(summary.score_standard_deviation == 0.0 for summary in result.summaries)
    assert all(summary.answer_stable for summary in result.summaries)
    assert all(observation.observed_model == "hy3-ioa" for observation in result.observations)
    assert all(payload["stream"] is True for payload in payloads)
    assert "secret-value" not in json.dumps(result.to_dict())

    path = tmp_path / "length.json"
    write_api_length_canary(result, path)
    assert json.loads(path.read_text(encoding="utf-8"))["canary_id"] == "single-needle-noise-v3"
    with pytest.raises(FileExistsError):
        write_api_length_canary(result, path)


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_lengths": (0,)},
        {"target_lengths": (131_072,)},
        {"positions": ("unknown",)},
        {"repetitions": False},
    ],
)
def test_length_canary_rejects_invalid_matrix(overrides: dict[str, object]) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    values = {
        "profile": profile,
        "endpoint": "https://copilot.tencent.com/v2/chat/completions",
        "api_key": "key",
        "target_lengths": (256,),
        "positions": ("front",),
        "repetitions": 1,
        **overrides,
    }

    with pytest.raises((TypeError, ValueError)):
        run_api_length_canary(**values)  # type: ignore[arg-type]
