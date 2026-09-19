from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from rsicontext.experiment.cost import (
    CostLedger,
    CostRecord,
    TotalCost,
    amortized_total,
    compose_from_ledger,
)
from rsicontext.reader_tiers import (
    GateEvidence,
    ReaderTier,
    TierDecision,
    check_rejection_ceiling,
    evaluate_tier,
    profile_tier,
)


def _record(
    *,
    improve_in: int = 100,
    improve_out: int = 20,
    improve_wall: float = 30.0,
    improve_dollars: float | None = 1.5,
    deploy_in: int = 10,
    deploy_out: int = 2,
    deploy_wall: float = 0.5,
    deploy_dollars: float | None = 0.01,
) -> CostRecord:
    return CostRecord(
        improve_tokens_in=improve_in,
        improve_tokens_out=improve_out,
        improve_wall_seconds=improve_wall,
        improve_dollar_estimate=improve_dollars,
        deploy_tokens_in=deploy_in,
        deploy_tokens_out=deploy_out,
        deploy_wall_seconds=deploy_wall,
        deploy_dollar_estimate=deploy_dollars,
        memory_ops={"writes": 3, "reads": 7, "bytes": 4096, "ops": 10},
        horizon_tasks=4,
    )


# --- contract-tests group 6: cost ledger ---


def test_cost_record_carries_both_columns_and_memory_ops() -> None:
    record = _record()
    payload = record.to_dict()
    for key in (
        "improve_tokens_in",
        "improve_tokens_out",
        "improve_wall_seconds",
        "improve_dollar_estimate",
        "deploy_tokens_in",
        "deploy_tokens_out",
        "deploy_wall_seconds",
        "deploy_dollar_estimate",
    ):
        assert key in payload
    assert payload["memory_ops"] == {"bytes": 4096, "ops": 10, "reads": 7, "writes": 3}
    assert record.horizon_tasks == 4


def test_amortized_total_two_column_formula_exact() -> None:
    record = _record()
    total = amortized_total(record, 2)
    assert isinstance(total, TotalCost)
    assert total.improve_tokens_in == 100
    assert total.deploy_tokens_in == 10
    # C_total(2) = C_improve + 2 * C_deploy, per component.
    assert total.tokens_in == 100 + 2 * 10
    assert total.tokens_out == 20 + 2 * 2
    assert total.wall_seconds == pytest.approx(30.0 + 2 * 0.5)
    assert total.dollar_estimate == pytest.approx(1.5 + 2 * 0.01)


def test_amortized_total_optional_dollar_absent_when_any_column_lacks_it() -> None:
    no_dollars = amortized_total(_record(improve_dollars=None, deploy_dollars=0.01), 3)
    assert no_dollars.improve_dollar_estimate is None
    assert no_dollars.dollar_estimate is None


def test_cost_ledger_accumulates_every_appended_record() -> None:
    ledger = CostLedger()
    first = _record()
    second = _record(improve_in=50, deploy_in=5, improve_dollars=None, deploy_dollars=None)
    ledger.append(first)
    ledger.append(second)
    assert len(ledger.records) == 2
    totals = ledger.totals()
    assert totals.improve_tokens_in == 150
    assert totals.deploy_tokens_in == 15
    assert totals.improve_dollar_estimate is None  # second record lacks one
    assert ledger.memory_ops() == {"bytes": 8192, "ops": 20, "reads": 14, "writes": 6}


def test_cost_ledger_summary_reports_each_requested_horizon() -> None:
    ledger = CostLedger([_record()])
    table = ledger.summary((1, 2, 5))
    assert sorted(table) == [1, 2, 5]
    assert table[1].tokens_in == 110
    assert table[2].tokens_in == 120
    assert table[5].tokens_in == 150
    assert table[5].dollar_estimate == pytest.approx(1.5 + 5 * 0.01)


def test_cost_record_rejects_negative_tokens() -> None:
    with pytest.raises(ValueError, match="improve_tokens_in"):
        CostRecord(
            improve_tokens_in=-1,
            improve_tokens_out=0,
            improve_wall_seconds=0.0,
            improve_dollar_estimate=None,
            deploy_tokens_in=0,
            deploy_tokens_out=0,
            deploy_wall_seconds=0.0,
            deploy_dollar_estimate=None,
            memory_ops={},
            horizon_tasks=0,
        )


def test_cost_record_memory_ops_copied_on_construction() -> None:
    ops = {"writes": 1}
    fresh = CostRecord(
        improve_tokens_in=0,
        improve_tokens_out=0,
        improve_wall_seconds=0.0,
        improve_dollar_estimate=None,
        deploy_tokens_in=0,
        deploy_tokens_out=0,
        deploy_wall_seconds=0.0,
        deploy_dollar_estimate=None,
        memory_ops=ops,
        horizon_tasks=0,
    )
    ops["writes"] = 99
    assert fresh.memory_ops["writes"] == 1  # mapping is copied, not aliased


def test_compose_from_ledger_maps_spend_fields_to_columns() -> None:
    record = compose_from_ledger(
        reader_input_tokens=40,
        reader_output_tokens=8,
        reader_wall_seconds=1.25,
        researcher_input_tokens=500,
        researcher_output_tokens=80,
        researcher_wall_seconds=12.0,
        researcher_cost_usd=0.75,
        memory_ops={"writes": 2, "reads": 5},
        horizon_tasks=3,
    )
    assert record.deploy_tokens_in == 40
    assert record.deploy_tokens_out == 8
    assert record.deploy_wall_seconds == pytest.approx(1.25)
    assert record.improve_tokens_in == 500
    assert record.improve_tokens_out == 80
    assert record.improve_wall_seconds == pytest.approx(12.0)
    assert record.improve_dollar_estimate == pytest.approx(0.75)
    assert record.deploy_dollar_estimate is None  # reader dollars not tracked by SpendLedger
    assert record.horizon_tasks == 3


# --- contract-tests group 7: reader tiers ---


def _evidence(
    *,
    answer: bool = True,
    usage: bool = True,
    echo: bool = True,
    variance: float | None = 0.02,
    repeats: int = 5,
    version: str | None = "2026-09-01-hy3",
    window: tuple[str, str] | None = ("2026-09-01", "2026-09-30"),
    echo_recorded: bool = True,
    local_anchor: bool = False,
) -> GateEvidence:
    return GateEvidence(
        canary_answer_form_ok=answer,
        canary_usage_ok=usage,
        canary_model_echo_ok=echo,
        canary_timestamp="2026-09-01T00:00:00Z",
        variance_floor_value=variance,
        variance_repeats=repeats,
        version_string=version,
        access_window=window,
        model_echo_recorded=echo_recorded,
        local_anchor=local_anchor,
    )


def test_t2_requires_all_gates() -> None:
    decision = evaluate_tier(_evidence())
    assert decision.tier is ReaderTier.T2_VERSIONED_API
    assert decision.eligible_for_efficiency is True
    assert decision.batch_invalidating is False


def test_t2_missing_variance_floor_drops_to_t3() -> None:
    decision = evaluate_tier(_evidence(variance=None))
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert decision.eligible_for_efficiency is False
    assert any("variance floor not measured" in reason for reason in decision.reasons)


def test_t2_missing_echo_record_drops_to_t3() -> None:
    decision = evaluate_tier(_evidence(echo_recorded=False))
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert any("model echo not recorded" in reason for reason in decision.reasons)


def test_t2_insufficient_variance_repeats_drops_to_t3() -> None:
    decision = evaluate_tier(_evidence(repeats=4))
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert any("repeats" in reason for reason in decision.reasons)


def test_canary_drift_invalidates_batch_with_reasons() -> None:
    decision = evaluate_tier(_evidence(usage=False))
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert decision.batch_invalidating is True
    assert any("canary drift: usage" in reason for reason in decision.reasons)


def test_t3_excluded_from_efficiency() -> None:
    decision = evaluate_tier(_evidence(version=None, window=None))
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert decision.eligible_for_efficiency is False


def test_t1_requires_local_anchor_attestation() -> None:
    decision = evaluate_tier(_evidence(local_anchor=True))
    assert decision.tier is ReaderTier.T1_ANCHOR
    assert decision.eligible_for_efficiency is True


def test_tier_decision_immutable_new_decision_per_evaluation() -> None:
    first = evaluate_tier(_evidence(version="v1"))
    with pytest.raises(FrozenInstanceError):
        first.tier = ReaderTier.T3_COMPATIBILITY_ONLY  # type: ignore[misc]
    second = evaluate_tier(_evidence(version="v2"))
    assert first is not second
    assert first.tier is second.tier is ReaderTier.T2_VERSIONED_API
    assert dataclasses.replace(first, tier=ReaderTier.T3_COMPATIBILITY_ONLY).tier is (
        ReaderTier.T3_COMPATIBILITY_ONLY
    )


def test_rejection_ceiling_above_ceiling_rejects_for_block() -> None:
    decision = check_rejection_ceiling(0.5, 0.2, _evidence())
    assert decision.tier is ReaderTier.T3_COMPATIBILITY_ONLY
    assert decision.eligible_for_efficiency is False
    assert any("exceeds" in reason for reason in decision.reasons)


def test_rejection_ceiling_at_or_below_ceiling_falls_through_to_gates() -> None:
    at_ceiling = check_rejection_ceiling(0.2, 0.2, _evidence())
    assert at_ceiling.tier is ReaderTier.T2_VERSIONED_API
    below = check_rejection_ceiling(0.1, 0.2, _evidence())
    assert below.tier is ReaderTier.T2_VERSIONED_API


def test_profile_tier_null_revision_maps_to_t3() -> None:
    profile = {
        "id": "tencent-copilot-hy3-ioa",
        "provider": "Tencent Copilot",
        "model": "hy3-ioa",
        "provider_revision": None,
    }
    assert profile_tier(profile) is ReaderTier.T3_COMPATIBILITY_ONLY


def test_profile_tier_pinned_revision_is_t2_pending_gates() -> None:
    profile = {
        "id": "local-qwen3.6-27b-128k-bf16-h200x8",
        "provider": "vllm-0.25.1",
        "provider_revision": "1b559cf7215ebe67ff10758e14f6293ba883223b",
    }
    # Profile JSON alone cannot express T2 eligibility: gates must pass first.
    # A pinned revision is the evidence floor; the gate verdict comes from
    # evaluate_tier on runtime evidence.
    assert profile_tier(profile) is ReaderTier.T2_VERSIONED_API
    gate = evaluate_tier(
        _evidence(
            variance=None,
            repeats=0,
            version=None,
            window=None,
            echo_recorded=False,
        )
    )
    assert gate.tier is ReaderTier.T3_COMPATIBILITY_ONLY


def test_tier_decision_rejects_bad_shapes() -> None:
    with pytest.raises(TypeError):
        TierDecision(tier="t2", eligible_for_efficiency=True, reasons=())  # type: ignore[arg-type]
