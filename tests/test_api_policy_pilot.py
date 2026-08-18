from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.campaign.api_policy_pilot import (
    run_api_policy_pilot,
    write_api_policy_pilot,
)
from rsicontext.eval import ReaderOutput
from rsicontext.experiment import load_api_profiles
from rsicontext.policy import ContextPack

ROOT = Path(__file__).parents[1]


class EvidenceReader:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        self.calls += 1
        answer = "AURORA-7319" if "AURORA-7319" in " ".join(context.ordered_text()) else ""
        return ReaderOutput(answer, context.token_count + 60, 7 if answer else 0)


def test_api_policy_pilot_has_known_dynamic_trajectory_and_replay(tmp_path: Path) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    reader = EvidenceReader()
    tick = [0.0]

    def timer() -> float:
        value = tick[0]
        tick[0] += 0.1
        return value

    result = run_api_policy_pilot(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        reader=reader,
        timer=timer,
        started_at="2026-08-14T00:00:00Z",
    )

    scores = {observation.policy_name: observation.score for observation in result.policies}
    assert scores == {
        "head-8k": pytest.approx(1 / 3),
        "lexical-8k": 1.0,
        "tail-8k": pytest.approx(1 / 3),
        "head-tail-8k": pytest.approx(2 / 3),
        "full-32k": 1.0,
    }
    assert result.trajectory.discovery_gain == pytest.approx(2 / 3)
    assert result.trajectory.post_peak_regression is True
    assert result.replay.standard_deviation == 0.0
    assert result.replay_reader_calls == 9
    assert result.replay_reader_input_tokens > 0
    assert result.replay_wall_seconds == pytest.approx(0.1)
    assert result.qualification_only is True
    assert reader.calls == 24
    assert "secret-value" not in json.dumps(result.to_dict())

    path = tmp_path / "pilot.json"
    write_api_policy_pilot(result, path)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2
    with pytest.raises(FileExistsError):
        write_api_policy_pilot(result, path)
