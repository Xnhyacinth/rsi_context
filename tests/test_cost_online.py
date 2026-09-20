from __future__ import annotations

import pytest

from rsicontext.experiment.cost import (
    CostRecord,
    OnlineCostRecord,
    TotalCost,
    amortized_online_total,
    amortized_total,
)


def _initial(
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    wall: float = 0.0,
    dollars: float | None = None,
) -> CostRecord:
    return CostRecord(
        improve_tokens_in=tokens_in,
        improve_tokens_out=tokens_out,
        improve_wall_seconds=wall,
        improve_dollar_estimate=dollars,
        deploy_tokens_in=0,
        deploy_tokens_out=0,
        deploy_wall_seconds=0.0,
        deploy_dollar_estimate=None,
        memory_ops={},
        horizon_tasks=0,
    )


def _task(
    task_index: int,
    *,
    serve_in: int = 0,
    serve_out: int = 0,
    update_in: int = 0,
    update_out: int = 0,
    maintain_in: int = 0,
    maintain_out: int = 0,
    serve_wall: float = 0.0,
    update_wall: float = 0.0,
    maintain_wall: float = 0.0,
    serve_dollars: float | None = None,
    update_dollars: float | None = None,
    maintain_dollars: float | None = None,
) -> OnlineCostRecord:
    return OnlineCostRecord(
        task_index=task_index,
        serve_tokens_in=serve_in,
        serve_tokens_out=serve_out,
        update_tokens_in=update_in,
        update_tokens_out=update_out,
        maintain_tokens_in=maintain_in,
        maintain_tokens_out=maintain_out,
        serve_wall_seconds=serve_wall,
        update_wall_seconds=update_wall,
        maintain_wall_seconds=maintain_wall,
        serve_dollar_estimate=serve_dollars,
        update_dollar_estimate=update_dollars,
        maintain_dollar_estimate=maintain_dollars,
    )


# --- contract-tests group 6b: online (continuously-updating) cost ---


def test_online_formula_exact_against_hand_computed_case() -> None:
    records = [
        _task(
            0,
            serve_in=100,
            serve_out=20,
            update_in=30,
            update_out=6,
            maintain_in=10,
            maintain_out=2,
            serve_wall=1.0,
            update_wall=0.2,
            maintain_wall=0.1,
            serve_dollars=0.10,
            update_dollars=0.03,
            maintain_dollars=0.01,
        ),
        _task(
            1,
            serve_in=150,
            serve_out=25,
            update_in=40,
            update_out=8,
            maintain_in=15,
            maintain_out=3,
            serve_wall=1.5,
            update_wall=0.3,
            maintain_wall=0.15,
            serve_dollars=0.15,
            update_dollars=0.04,
            maintain_dollars=0.02,
        ),
        _task(
            2,
            serve_in=200,
            serve_out=30,
            update_in=50,
            update_out=10,
            maintain_in=20,
            maintain_out=4,
            serve_wall=2.0,
            update_wall=0.4,
            maintain_wall=0.2,
            serve_dollars=0.20,
            update_dollars=0.05,
            maintain_dollars=0.02,
        ),
    ]
    total = amortized_online_total(
        records, _initial(tokens_in=1000, tokens_out=200, wall=50.0, dollars=2.0)
    )
    assert isinstance(total, TotalCost)
    # Per-task sums: 140+205+270 in, 28+36+44 out, 1.3+1.95+2.6 wall, 0.14+0.21+0.27 dollars.
    assert total.deploy_tokens_in == 615
    assert total.deploy_tokens_out == 108
    assert total.deploy_wall_seconds == pytest.approx(5.85)
    assert total.deploy_dollar_estimate == pytest.approx(0.62)
    # C_total(3) = C_initial_improve + Σ_t (serve+update+maintain), per component.
    assert total.tokens_in == 1000 + 615
    assert total.tokens_out == 200 + 108
    assert total.wall_seconds == pytest.approx(50.0 + 5.85)
    assert total.dollar_estimate == pytest.approx(2.0 + 0.62)


def test_zero_update_system_reduces_to_offline_formula() -> None:
    # Fixed-strategy reference: every task's serve cost equals the offline
    # per-unit C_deploy, no update/maintain stream.
    offline = CostRecord(
        improve_tokens_in=400,
        improve_tokens_out=80,
        improve_wall_seconds=20.0,
        improve_dollar_estimate=1.2,
        deploy_tokens_in=60,
        deploy_tokens_out=12,
        deploy_wall_seconds=0.7,
        deploy_dollar_estimate=0.05,
        memory_ops={},
        horizon_tasks=3,
    )
    served = [
        _task(t, serve_in=60, serve_out=12, serve_wall=0.7, serve_dollars=0.05) for t in range(3)
    ]
    online = amortized_online_total(served, offline)
    reference = amortized_total(offline, 3)
    # The online total over N identical serve-only tasks equals
    # C_improve + N·C_deploy on every aggregate component.
    assert online.tokens_in == reference.tokens_in == 400 + 3 * 60
    assert online.tokens_out == reference.tokens_out == 80 + 3 * 12
    assert (
        online.wall_seconds
        == pytest.approx(reference.wall_seconds)
        == pytest.approx(20.0 + 3 * 0.7)
    )
    assert online.dollar_estimate == pytest.approx(reference.dollar_estimate)
    assert online.dollar_estimate == pytest.approx(1.2 + 3 * 0.05)


def test_serve_update_maintain_streams_attributed_separately() -> None:
    # Each stream flows into the total independently: a serve-only task, an
    # update-only task, and a maintain-only task contribute their own tokens,
    # and no stream's tokens land in another stream's accounting.
    serve_only = _task(0, serve_in=100, serve_out=10, serve_wall=1.0, serve_dollars=0.1)
    update_only = _task(1, update_in=200, update_out=20, update_wall=2.0, update_dollars=0.2)
    maintain_only = _task(
        2, maintain_in=50, maintain_out=5, maintain_wall=0.5, maintain_dollars=0.05
    )
    total = amortized_online_total([serve_only, update_only, maintain_only])
    assert total.deploy_tokens_in == 100 + 200 + 50
    assert total.deploy_tokens_out == 10 + 20 + 5
    assert total.deploy_wall_seconds == pytest.approx(3.5)
    assert total.deploy_dollar_estimate == pytest.approx(0.35)
    # The per-task record keeps the three streams distinct in its payload.
    payload = serve_only.to_dict()
    assert payload["serve_tokens_in"] == 100
    assert payload["update_tokens_in"] == 0
    assert payload["maintain_tokens_in"] == 0
    # Moving budget between streams changes only that stream's contribution.
    with_more_update = _task(0, serve_in=100, update_in=250, maintain_in=50)
    grown = amortized_online_total([with_more_update])
    assert grown.deploy_tokens_in == 400
    assert grown.tokens_in == 400  # no initial improve pass


def test_online_dollar_absent_when_a_running_stream_lacks_one() -> None:
    # Task 1's update stream ran tokens but carries no price: unknown, so the
    # deploy dollars (and the total) are None rather than a partial sum.
    records = [
        _task(0, serve_dollars=0.10, update_dollars=0.03, maintain_dollars=0.01),
        _task(1, serve_dollars=0.15, update_in=200, update_dollars=None, maintain_dollars=0.02),
    ]
    total = amortized_online_total(records, _initial(tokens_in=10, dollars=1.0))
    assert total.deploy_dollar_estimate is None
    assert total.dollar_estimate is None  # one unpriced running stream poisons the total
    # The same records without an initial improve pass stay unpriced too.
    no_initial = amortized_online_total(records)
    assert no_initial.dollar_estimate is None


def test_online_dollar_idle_stream_needs_no_price() -> None:
    # A fixed-strategy task: update and maintain never ran, so their missing
    # prices are free, not unknown — only the serve stream's price is needed.
    serve_only = _task(0, serve_in=100, serve_dollars=0.12)
    total = amortized_online_total([serve_only], _initial(tokens_in=5, dollars=1.0))
    assert total.deploy_dollar_estimate == pytest.approx(0.12)
    assert total.dollar_estimate == pytest.approx(1.12)


def test_online_dollar_present_with_initial_when_all_streams_priced() -> None:
    records = [_task(0, serve_dollars=0.10, update_dollars=0.03, maintain_dollars=0.01)]
    total = amortized_online_total(records, _initial(tokens_in=5, dollars=1.0))
    assert total.dollar_estimate == pytest.approx(1.0 + 0.14)


def test_empty_sequence_is_all_zero_cost() -> None:
    total = amortized_online_total([])
    assert total.horizon == 1
    assert total.tokens_in == 0
    assert total.tokens_out == 0
    assert total.wall_seconds == pytest.approx(0.0)
    assert total.dollar_estimate == pytest.approx(0.0)
    # An initial improve pass alone still lands in the improve column.
    only_initial = amortized_online_total(
        [], _initial(tokens_in=7, tokens_out=3, wall=2.5, dollars=0.4)
    )
    assert only_initial.tokens_in == 7
    assert only_initial.tokens_out == 3
    assert only_initial.wall_seconds == pytest.approx(2.5)
    assert only_initial.dollar_estimate == pytest.approx(0.4)


def test_online_record_rejects_negative_tokens_and_bad_shapes() -> None:
    with pytest.raises(ValueError, match="serve_tokens_in"):
        _task(0, serve_in=-1)
    with pytest.raises(ValueError, match="update_tokens_out"):
        _task(0, update_out=-5)
    with pytest.raises(ValueError, match="maintain_tokens_in"):
        _task(0, maintain_in=-2)
    with pytest.raises(ValueError, match="task_index"):
        _task(-1)
    with pytest.raises(ValueError, match="serve_dollar_estimate"):
        _task(0, serve_dollars=-0.01)
    with pytest.raises(ValueError, match="update_wall_seconds"):
        _task(0, update_wall=-1.0)


def test_amortized_online_total_rejects_non_online_records() -> None:
    with pytest.raises(TypeError, match="OnlineCostRecord"):
        amortized_online_total([_initial(tokens_in=1)])  # type: ignore[list-item]
