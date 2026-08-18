from __future__ import annotations

import json
from pathlib import Path

from rsicontext.artifacts import ArtifactStore, load_manifest
from rsicontext.campaign.toy import run_toy_campaign


def test_toy_campaign_exercises_discovery_regression_and_selection(tmp_path: Path) -> None:
    result = run_toy_campaign(tmp_path)

    assert [round_.score for round_ in result.rounds] == [0.0, 1.0, 0.0]
    assert result.metrics.discovery_gain == 1.0
    assert result.metrics.post_peak_regression is True
    assert result.selected_round == 1
    assert result.last_round == 2
    assert result.replay.standard_deviation == 0.0

    store = ArtifactStore(tmp_path / "store")
    lineage = store.lineage(result.rounds[-1].artifact_id)
    assert [record.artifact_id for record in lineage] == [
        round_.artifact_id for round_ in result.rounds
    ]


def test_toy_campaign_writes_replayable_summary_and_manifests(tmp_path: Path) -> None:
    first = run_toy_campaign(tmp_path)
    second = run_toy_campaign(tmp_path)

    assert first.to_dict() == second.to_dict()
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["selected_round"] == 1
    for round_ in first.rounds:
        manifest = load_manifest(tmp_path / f"round-{round_.round_index:02d}-manifest.json")
        assert manifest.candidate_name == round_.policy_name
        assert manifest.cost.evaluation_input_tokens == round_.reader_input_tokens
        assert manifest.cost.evaluation_output_tokens == round_.reader_output_tokens
