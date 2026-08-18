"""Attempt-slot accounting: invalid submissions still consume the budgeted slot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AttemptStatus = Literal["valid", "invalid"]


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    slot_index: int
    status: AttemptStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.slot_index, int) or isinstance(self.slot_index, bool):
            raise TypeError("slot_index must be an integer")
        if self.slot_index < 0:
            raise ValueError("slot_index must be non-negative")
        if self.status not in {"valid", "invalid"}:
            raise ValueError("status must be valid or invalid")
        if self.status == "invalid":
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("invalid attempts require a non-empty reason")
        elif self.reason is not None:
            raise ValueError("valid attempts cannot carry a rejection reason")


class AttemptBudgetError(RuntimeError):
    """Raised when no attempt slots remain."""


def consume_attempt_slot(
    records: tuple[AttemptRecord, ...],
    *,
    max_slots: int,
    status: AttemptStatus,
    reason: str | None = None,
) -> tuple[AttemptRecord, ...]:
    """Append one consumed slot. Invalid submissions still occupy the index."""

    if not isinstance(max_slots, int) or isinstance(max_slots, bool) or max_slots <= 0:
        raise ValueError("max_slots must be a positive integer")
    if len(records) >= max_slots:
        raise AttemptBudgetError("no attempt slots remain")
    record = AttemptRecord(slot_index=len(records), status=status, reason=reason)
    return (*records, record)
