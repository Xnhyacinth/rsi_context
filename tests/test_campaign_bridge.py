"""Tests for the campaign↔participant bridge (WS-7).

Verifies the bridge adapts ImprovementRoundInput into a callback-compatible
request, seeds the workspace from the participant agent tree, derives the
changed-file map by tree diff, and composes the three first arms into a
no-reader end-to-end smoke over a tiny fake agent tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.participant.arms import (
    ExperienceAccumulationImprover,
    FixedStrategyImprover,
)
from rsicontext.participant.campaign_bridge import (
    CampaignBridgeError,
    _CampaignRequestShape,
    build_open_s_arm,
    make_campaign_run_round,
)
from rsicontext.participant.registration import ImprovementRoundInput


def _agent_tree(tmp_path: Path) -> Path:
    agent_dir = tmp_path / "agent"
    (agent_dir / "sub").mkdir(parents=True)
    (agent_dir / "policy.py").write_text("POLICY = 'h0'\n")
    (agent_dir / "sub" / "retrieval.py").write_text("def retrieve():\n    return []\n")
    return agent_dir


def _round_input(
    agent_dir: Path,
    index: int = 0,
    state_path: Path | None = None,
) -> ImprovementRoundInput:
    feedback = json.dumps({"previous": 0.5, "incumbent": 0.6}).encode("utf-8")
    return ImprovementRoundInput(
        round_index=index,
        task_text="improve the strategy",
        restricted_feedback_bytes=feedback,
        current_agent_dir=agent_dir,
        state_path=state_path,
        remaining_slots=5,
        task_order_seed=7,
    )


def _scores(feedback: bytes) -> tuple[float | None, float | None]:
    parsed = json.loads(feedback)
    return float(parsed["previous"]), float(parsed["incumbent"])


def test_bridge_seeds_workspace_and_detects_changes(tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    workspace_root = tmp_path / "workspaces"
    seen: dict[str, object] = {}

    def callback(request: object) -> None:
        assert isinstance(request, _CampaignRequestShape)
        seen["round_index"] = request.round_index
        seen["previous_score"] = request.previous_score
        seen["incumbent_score"] = request.incumbent_score
        seen["prediction_item_ids"] = request.prediction_item_ids
        # The researcher "edit": rewrite policy.py in the seeded workspace.
        policy_dir = Path(request.policy_directory)
        (policy_dir / "policy.py").write_text("POLICY = 'improved'\n")

    run_round = make_campaign_run_round(
        callback,
        workspace_root,
        prediction_item_ids=("item-1",),
        feedback_bytes_to_scores=_scores,
    )
    changed = run_round(_round_input(agent_dir))

    assert changed == {"policy.py": "POLICY = 'improved'\n"}
    # The bridged request carries the campaign-visible fields.
    assert seen["round_index"] == 0
    assert seen["previous_score"] == 0.5
    assert seen["incumbent_score"] == 0.6
    assert seen["prediction_item_ids"] == ("item-1",)
    # Untouched files survive in the workspace but are not reported changed.
    assert (workspace_root / "round-00" / "policy" / "sub" / "retrieval.py").exists()


def test_bridge_requires_existing_agent_dir(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspaces"

    def callback(request: object) -> None:
        return None

    run_round = make_campaign_run_round(
        callback,
        workspace_root,
        prediction_item_ids=("item-1",),
        feedback_bytes_to_scores=_scores,
    )
    with pytest.raises(CampaignBridgeError):
        run_round(_round_input(tmp_path / "missing"))


def test_open_s_arm_over_bridge(tmp_path: Path) -> None:
    agent_dir = _agent_tree(tmp_path)
    workspace_root = tmp_path / "workspaces"

    def callback(request: object) -> None:
        assert isinstance(request, _CampaignRequestShape)
        policy_dir = Path(request.policy_directory)
        (policy_dir / "policy.py").write_text("POLICY = 'round-edit'\n")

    arm = build_open_s_arm(
        callback,
        workspace_root,
        prediction_item_ids=("item-1",),
        feedback_bytes_to_scores=_scores,
    )
    output = arm.improve(_round_input(agent_dir))
    assert output.agent_files_changed == {"policy.py": "POLICY = 'round-edit'\n"}
    assert output.state_update is None


def test_three_arm_no_reader_smoke(tmp_path: Path) -> None:
    """Contract: the three first arms run over identical round inputs.

    The fixed arm changes nothing; the experience arm freezes the agent
    tree and grows state only; the open-S arm edits the agent tree via the
    bridge. Byte-identity of the inputs each arm received is the fairness
    contract (group 4a); here the end-to-end composition is the point.
    """

    fixed_dir = _agent_tree(tmp_path / "fixed-agent")
    experience_dir = _agent_tree(tmp_path / "experience-agent")
    open_s_dir = _agent_tree(tmp_path / "open-s-agent")

    fixed = FixedStrategyImprover()
    experience = ExperienceAccumulationImprover(byte_cap=4096)

    def edit_policy(request: object) -> None:
        assert isinstance(request, _CampaignRequestShape)
        Path(request.policy_directory, "policy.py").write_text("POLICY = 'smoke'\n")

    open_s = build_open_s_arm(
        edit_policy,
        tmp_path / "workspaces",
        prediction_item_ids=("item-1", "item-2"),
        feedback_bytes_to_scores=_scores,
    )

    state_path = tmp_path / "state.json"
    outputs = [
        fixed.improve(_round_input(fixed_dir)),
        experience.improve(_round_input(experience_dir, state_path=state_path)),
        open_s.improve(_round_input(open_s_dir)),
    ]

    assert outputs[0].agent_files_changed == {}
    assert outputs[0].state_update is None
    assert outputs[1].agent_files_changed == {}
    assert outputs[1].state_update is not None
    assert outputs[2].agent_files_changed == {"policy.py": "POLICY = 'smoke'\n"}
    # The original agent trees of the fixed and experience arms are
    # untouched (byte-frozen); the open-S edit happened in the bridged
    # workspace copy, so the source tree also remains intact.
    assert (fixed_dir / "policy.py").read_text() == "POLICY = 'h0'\n"
    assert (experience_dir / "policy.py").read_text() == "POLICY = 'h0'\n"
    assert (open_s_dir / "policy.py").read_text() == "POLICY = 'h0'\n"
