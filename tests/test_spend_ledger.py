from __future__ import annotations

import pytest

from rsicontext.experiment.ledger import SpendCapError, SpendCaps, SpendLedger


def test_spend_ledger_authorizes_before_dispatch_and_enforces_caps() -> None:
    ledger = SpendLedger(
        SpendCaps(
            max_reader_calls=2,
            max_reader_input_tokens=100,
            max_cost_usd=1.0,
            max_gpu_seconds=10.0,
            max_wall_seconds=10.0,
            max_retries=0,
        )
    )
    ledger.authorize_reader(input_tokens=40, output_tokens=2, gpu_seconds=1.0, wall_seconds=1.0)
    with pytest.raises(SpendCapError, match="reader_input_tokens"):
        ledger.authorize_reader(input_tokens=70)
    ledger.authorize_researcher(cost_usd=0.25, wall_seconds=0.5)
    snapshot = ledger.snapshot()
    assert snapshot.reader_calls == 1
    assert snapshot.researcher_cost_usd == 0.25
    assert snapshot.to_ledger_pairs()[0][0] == "gpu_seconds"


def test_spend_caps_allow_zero_dollar_local_only_runs() -> None:
    ledger = SpendLedger(
        SpendCaps(
            max_reader_calls=1,
            max_reader_input_tokens=8,
            max_cost_usd=0.0,
            max_gpu_seconds=1.0,
            max_wall_seconds=1.0,
            max_retries=0,
        )
    )
    ledger.authorize_reader(input_tokens=4, gpu_seconds=0.1, wall_seconds=0.1)
    with pytest.raises(SpendCapError, match="cost_usd"):
        ledger.authorize_researcher(cost_usd=0.01)
