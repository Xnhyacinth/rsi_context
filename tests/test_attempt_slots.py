from __future__ import annotations

import pytest

from rsicontext.experiment.attempts import AttemptBudgetError, consume_attempt_slot


def test_invalid_submissions_still_consume_attempt_slots() -> None:
    records = consume_attempt_slot((), max_slots=2, status="invalid", reason="audit failed")
    records = consume_attempt_slot(records, max_slots=2, status="valid")

    assert [record.status for record in records] == ["invalid", "valid"]
    assert records[0].slot_index == 0
    with pytest.raises(AttemptBudgetError, match="no attempt slots remain"):
        consume_attempt_slot(records, max_slots=2, status="valid")
