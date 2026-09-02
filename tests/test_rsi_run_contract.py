from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.eval import exact_match
from rsicontext.experiment.rsi_run import (
    BoundedRSIRunContract,
    build_bounded_rsi_run_contract,
    contract_file_sha256,
    policy_tree_sha256,
    validate_contract_file_unchanged,
)
from rsicontext.policy import Budget
from rsicontext.researcher import ProcessLimits


def _policy(tmp_path: Path) -> Path:
    root = tmp_path / "policy"
    root.mkdir()
    (root / "seed.py").write_text("VALUE = 1\n", encoding="utf-8")
    return root


def test_run_contract_binds_every_allocation_before_execution(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    limits = ProcessLimits(timeout_seconds=1800.0)

    contract = build_bounded_rsi_run_contract(
        dataset_fingerprint="a" * 64,
        visible_items_sha256="d" * 64,
        visible_item_ids=("item-1", "item-2"),
        initial_policy_directory=policy,
        scorer=exact_match,
        token_axis_identity={"label": "unit-token-axis"},
        reader_identity={
            "api_key_env": "RSICONTEXT_TEST_API_KEY",
            "model": "reader-model",
            "profile_hash": "b" * 64,
        },
        researcher_identity={"kind": "codex", "profile_hash": "c" * 64},
        researcher_environment_allowlist=("RSICONTEXT_TEST_API_KEY",),
        max_budget_usd=2.5,
        rounds=5,
        budget=Budget(max_tokens=8192, max_chunks=37, max_free_text_tokens=256),
        max_prompt_bytes=2_000_000,
        process_limits=limits,
    )

    assert contract.rounds == 5
    assert contract.visible_item_count == 2
    assert contract.visible_items_sha256 == "d" * 64
    assert contract.max_reader_calls == 12
    assert contract.max_researcher_turns == 5
    assert contract.researcher_wall_seconds_ceiling == 9000.0
    assert contract.budget == Budget(
        max_tokens=8192,
        max_chunks=37,
        max_free_text_tokens=256,
    )
    assert contract.researcher_environment_allowlist == ("RSICONTEXT_TEST_API_KEY",)
    assert contract.max_budget_usd == 2.5
    assert contract.researcher_budget_usd_ceiling == 12.5
    assert contract.formal_process_isolation is False
    assert contract.initial_policy_sha256 == policy_tree_sha256(policy)
    assert len(contract.scorer_module_sha256) == 64
    assert contract.invalid_submission_reader_calls == 0
    assert contract.valid_candidate_reader_calls_per_item == 1
    assert contract.lineage_rule == "next-from-last-valid-attempt"
    assert contract.search_mode == "normal"
    assert contract.selection_rule == "visible-strict-historical-best"
    assert contract.matched_primary_estimand is False
    serialized = contract.to_dict()
    assert serialized["token_axis_identity_preimage"] == {"label": "unit-token-axis"}
    assert serialized["reader_identity_preimage"] == {
        "api_key_env": "RSICONTEXT_TEST_API_KEY",
        "model": "reader-model",
        "profile_hash": "b" * 64,
    }
    assert serialized["researcher_identity_preimage"] == {
        "kind": "codex",
        "profile_hash": "c" * 64,
    }
    assert serialized["budget"] == {
        "max_chunks": 37,
        "max_free_text_tokens": 256,
        "max_tokens": 8192,
    }
    assert serialized["schema_version"] == 2
    assert len(contract.contract_sha256) == 64
    contract.validate_observed(round_slots=5, valid_candidate_rounds=3, reader_calls=8)

    with pytest.raises(RuntimeError, match="valid candidate rounds"):
        contract.validate_observed(round_slots=5, valid_candidate_rounds=3, reader_calls=10)


def test_run_contract_rejects_post_hoc_budget_or_identity_gaps(tmp_path: Path) -> None:
    policy = _policy(tmp_path)

    with pytest.raises(ValueError, match="dataset_fingerprint"):
        build_bounded_rsi_run_contract(
            dataset_fingerprint="main",
            visible_items_sha256="d" * 64,
            visible_item_ids=("item-1",),
            initial_policy_directory=policy,
            scorer=exact_match,
            token_axis_identity={"label": "unit-token-axis"},
            reader_identity={"profile_hash": "b" * 64},
            researcher_identity={"profile_hash": "c" * 64},
            researcher_environment_allowlist=(),
            max_budget_usd=None,
            rounds=5,
            budget=Budget(max_tokens=8192),
            max_prompt_bytes=2_000_000,
            process_limits=ProcessLimits(),
        )
    with pytest.raises(ValueError, match="reader_identity"):
        build_bounded_rsi_run_contract(
            dataset_fingerprint="a" * 64,
            visible_items_sha256="d" * 64,
            visible_item_ids=("item-1",),
            initial_policy_directory=policy,
            scorer=exact_match,
            token_axis_identity={"label": "unit-token-axis"},
            reader_identity=None,
            researcher_identity={"profile_hash": "c" * 64},
            researcher_environment_allowlist=(),
            max_budget_usd=None,
            rounds=5,
            budget=Budget(max_tokens=8192),
            max_prompt_bytes=2_000_000,
            process_limits=ProcessLimits(),
        )
    with pytest.raises(ValueError, match="max_prompt_bytes"):
        build_bounded_rsi_run_contract(
            dataset_fingerprint="a" * 64,
            visible_items_sha256="d" * 64,
            visible_item_ids=("item-1",),
            initial_policy_directory=policy,
            scorer=exact_match,
            token_axis_identity={"label": "unit-token-axis"},
            reader_identity={"profile_hash": "b" * 64},
            researcher_identity={"profile_hash": "c" * 64},
            researcher_environment_allowlist=(),
            max_budget_usd=None,
            rounds=5,
            budget=Budget(max_tokens=8192),
            max_prompt_bytes=0,
            process_limits=ProcessLimits(),
        )


def test_run_contract_rejects_secret_identity_values_and_nonqualification() -> None:
    with pytest.raises(ValueError, match=r"reader_identity.*secret-bearing key"):
        build_bounded_rsi_run_contract(
            dataset_fingerprint="a" * 64,
            visible_items_sha256="d" * 64,
            visible_item_ids=("item-1",),
            initial_policy_directory=Path(__file__).parent.parent / "policy",
            scorer=exact_match,
            token_axis_identity={"label": "unit-token-axis"},
            reader_identity={"api_key": "must-not-be-stored"},
            researcher_identity={"profile_hash": "c" * 64},
            researcher_environment_allowlist=(),
            max_budget_usd=None,
            rounds=1,
            budget=Budget(max_tokens=8192),
            max_prompt_bytes=2_000_000,
            process_limits=ProcessLimits(),
        )

    policy_contract = build_bounded_rsi_run_contract(
        dataset_fingerprint="a" * 64,
        visible_items_sha256="d" * 64,
        visible_item_ids=("item-1",),
        initial_policy_directory=Path(__file__).parent.parent / "policy",
        scorer=exact_match,
        token_axis_identity={"label": "unit-token-axis"},
        reader_identity={"profile_hash": "b" * 64},
        researcher_identity={"profile_hash": "c" * 64},
        researcher_environment_allowlist=(),
        max_budget_usd=None,
        rounds=1,
        budget=Budget(max_tokens=8192),
        max_prompt_bytes=2_000_000,
        process_limits=ProcessLimits(),
    )
    with pytest.raises(ValueError, match="visible qualification"):
        replace(policy_contract, qualification_only=False)
    with pytest.raises(ValueError, match="visible qualification"):
        replace(policy_contract, formal_process_isolation=True)


def test_contract_hash_binds_every_budget_dimension(tmp_path: Path) -> None:
    policy = _policy(tmp_path)

    def build(budget: Budget) -> BoundedRSIRunContract:
        return build_bounded_rsi_run_contract(
            dataset_fingerprint="a" * 64,
            visible_items_sha256="d" * 64,
            visible_item_ids=("item-1",),
            initial_policy_directory=policy,
            scorer=exact_match,
            token_axis_identity={"label": "unit-token-axis"},
            reader_identity={"profile_hash": "b" * 64},
            researcher_identity={"profile_hash": "c" * 64},
            researcher_environment_allowlist=(),
            max_budget_usd=None,
            rounds=1,
            budget=budget,
            max_prompt_bytes=2_000_000,
            process_limits=ProcessLimits(),
        )

    base = build(Budget(max_tokens=8192, max_chunks=8, max_free_text_tokens=64))

    for budget in (
        Budget(max_tokens=8191, max_chunks=8, max_free_text_tokens=64),
        Budget(max_tokens=8192, max_chunks=7, max_free_text_tokens=64),
        Budget(max_tokens=8192, max_chunks=8, max_free_text_tokens=63),
    ):
        changed = build(budget)
        assert changed.contract_sha256 != base.contract_sha256


def test_contract_file_content_must_remain_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "run_contract.json"
    path.write_text(json.dumps({"schema_version": 2}) + "\n", encoding="utf-8")
    expected = contract_file_sha256(path)

    validate_contract_file_unchanged(path, expected)
    path.write_text(json.dumps({"schema_version": 2}, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="content changed"):
        validate_contract_file_unchanged(path, expected)


def test_policy_tree_identity_changes_with_source_bytes(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    before = policy_tree_sha256(policy)

    (policy / "seed.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert policy_tree_sha256(policy) != before
