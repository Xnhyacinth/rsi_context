"""Improvement-loop usage accounting: the C_improve column source.

C_deploy (per-task service cost) is accounted by the deployment ledger, not
here; this module only accumulates what the improvement process itself spent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _nonnegative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _nonnegative_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return number


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Tokens, wall time, and dollars spent by one improvement round."""

    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0.0
    dollar_estimate: float | None = None

    def __post_init__(self) -> None:
        _nonnegative_int(self.input_tokens, "input_tokens")
        _nonnegative_int(self.output_tokens, "output_tokens")
        _nonnegative_number(self.wall_seconds, "wall_seconds")
        if self.dollar_estimate is not None:
            _nonnegative_number(self.dollar_estimate, "dollar_estimate")

    def total(self) -> int:
        """Total accounted tokens for this round."""

        return self.input_tokens + self.output_tokens


@dataclass(slots=True)
class UsageLedger:
    """Accumulate per-round ``UsageReport`` records into per-arm C_improve totals.

    The ledger key is the arm label the caller records under (an ``ArmKind``
    value or any explicit per-participant label); it never pools arms itself.
    """

    _rounds: dict[str, list[UsageReport]] = field(default_factory=dict, init=False)

    def record(self, arm: str, report: UsageReport) -> None:
        """Append one round's improvement-loop usage under an arm label."""

        if not isinstance(arm, str) or not arm.strip():
            raise ValueError("arm label must be a non-empty string")
        if not isinstance(report, UsageReport):
            raise TypeError("report must be a UsageReport")
        self._rounds.setdefault(arm, []).append(report)

    def rounds(self, arm: str) -> tuple[UsageReport, ...]:
        """Every recorded report for an arm, in recorded order."""

        return tuple(self._rounds[arm])

    def arms(self) -> tuple[str, ...]:
        """Recorded arm labels in deterministic sorted order."""

        return tuple(sorted(self._rounds))

    def arm_total(self, arm: str) -> UsageReport:
        """Sum tokens, wall time, and dollars over all rounds of one arm."""

        reports = self._rounds[arm]
        dollars = [report.dollar_estimate for report in reports]
        dollar: float | None = None
        if reports and None not in dollars:
            dollar = sum(value for value in dollars if value is not None)
        return UsageReport(
            input_tokens=sum(report.input_tokens for report in reports),
            output_tokens=sum(report.output_tokens for report in reports),
            wall_seconds=sum(report.wall_seconds for report in reports),
            dollar_estimate=dollar,
        )
