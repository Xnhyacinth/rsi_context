from __future__ import annotations

import pytest

from rsicontext.campaign.hard_baseline_gate import HARD_POLICY_TOKENS
from rsicontext.datasets import NOMINAL_HARD_CONTEXT_TOKENS
from rsicontext.experiment import (
    CONTROL_CELL,
    CONTROL_PACK_TOKENS,
    CONTROL_SOURCE_TOKENS,
    ENVELOPE_MAX_PACK_TOKENS,
    EVOLVE,
    FROZEN,
    LAYERS,
    RSI_MAIN,
    TRANSFER,
    launch_a2_pilot,
    pack_within_envelope,
    researcher_path_allowed,
)
from rsicontext.experiment.a2 import build_a2_pilot_plan
from rsicontext.experiment.a2_controller import A2LaunchError, A2LaunchRequest
from rsicontext.experiment.ledger import SpendCaps


def test_control_cell_matches_hard_panel_source_and_pack() -> None:
    assert CONTROL_SOURCE_TOKENS == NOMINAL_HARD_CONTEXT_TOKENS
    assert CONTROL_PACK_TOKENS == HARD_POLICY_TOKENS == ENVELOPE_MAX_PACK_TOKENS
    assert CONTROL_CELL.matched_grammar is True
    assert RSI_MAIN.matched_grammar is False
    assert TRANSFER.official is True
    assert LAYERS == ("control_cell", "rsi_main", "transfer")


def test_frozen_and_evolve_surfaces_are_disjoint_and_complete_enough() -> None:
    assert not set(FROZEN) & set(EVOLVE)
    assert "official_scorer" in FROZEN
    assert "reader_weights" in FROZEN
    assert "policy_python" in EVOLVE
    assert "visible_diagnostics" in EVOLVE
    assert pack_within_envelope(CONTROL_PACK_TOKENS) is True
    assert pack_within_envelope(CONTROL_PACK_TOKENS + 1) is False
    assert pack_within_envelope(0) is True


def test_researcher_may_edit_only_policy_paths() -> None:
    assert researcher_path_allowed("policy/policy.py") is True
    assert researcher_path_allowed("policy") is True
    assert researcher_path_allowed("src/rsicontext/eval/core.py") is False
    assert researcher_path_allowed("configs/serving_profiles.json") is False


def test_a2_stays_refused_under_the_rsi_contract() -> None:
    plan = build_a2_pilot_plan(
        researchers=("codex-gpt-5.6-sol", "claude-opus"),
        task_profiles=("compositional_multihop", "dense_global_comparison"),
        seeds=(17, 29),
    )
    with pytest.raises(A2LaunchError):
        launch_a2_pilot(
            A2LaunchRequest(
                plan=plan,
                caps=SpendCaps(
                    max_reader_calls=10_720,
                    max_reader_input_tokens=200_000_000,
                    max_cost_usd=50.0,
                    max_gpu_seconds=200_000.0,
                    max_wall_seconds=300_000.0,
                    max_retries=20,
                ),
                landscape_passed=True,
                isolation_formal=True,
                difficulty_profiles_passed=plan.task_profiles,
            )
        )
