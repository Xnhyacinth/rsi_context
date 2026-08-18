from __future__ import annotations

import pytest

from rsicontext.analysis.metrics import (
    ALWAYS_UNCHANGED_COMPARATOR,
    UNIFORM_COMPARATOR,
    Outcome,
    leave_one_trajectory_out_base_rate,
)


def test_leave_one_trajectory_out_uses_the_remaining_empirical_rate() -> None:
    rates = leave_one_trajectory_out_base_rate(
        {
            "t0": (Outcome.IMPROVE, Outcome.IMPROVE),
            "t1": (Outcome.UNCHANGED, Outcome.REGRESS),
        },
        "t0",
    )

    assert rates == pytest.approx((0.0, 0.5, 0.5))
    assert pytest.approx((1 / 3, 1 / 3, 1 / 3)) == UNIFORM_COMPARATOR
    assert ALWAYS_UNCHANGED_COMPARATOR == (0.0, 1.0, 0.0)
