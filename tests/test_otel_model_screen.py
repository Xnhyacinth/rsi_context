"""Behavioral checks for the OTel model-driven development screen."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest

from rsicontext.analysis.otel_model_screen import FakeAttributeWorker, run_case, run_screen
from rsicontext.lifecycle.material_otel_source_contrast import build_otel_source_contrast_sessions
from rsicontext.lifecycle.spec import LifecycleInstance


def _sessions(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    variable = (
        "RSICONTEXT_OTEL124_SOURCE_ROOT" if revision == "1.24" else "RSICONTEXT_OTEL_SOURCE_ROOT"
    )
    configured = os.environ.get(variable)
    if not configured:
        pytest.skip(f"set {variable} to pinned detached checkout")
    return build_otel_source_contrast_sessions(Path(configured), revision=revision)


def test_offline_screen_separates_source_carry_and_receipts() -> None:
    result = run_screen(_sessions("1.24"), _sessions("1.43"))
    cases = {case["case"]: case for case in cast(list[dict[str, Any]], result["cases"])}
    assert result["screen_case_count"] == 10
    assert result["provider_usage"] is None
    assert cases["full-124"]["final_plan"] == "db.statement"
    assert cases["full-143"]["final_plan"] == "db.query.text"
    assert cases["swapped-124"]["sessions_passed"] == [True, False]
    assert cases["swapped-143"]["sessions_passed"] == [True, False]
    assert cases["empty-carry-no-reread-143"]["worker_dispatches"] == 1
    assert cases["empty-carry-reread-143"]["worker_dispatches"] == 3
    assert cases["prior-receipt-fails-143"]["sessions_passed"] == [False, False]
    assert cases["decision-receipt-fails-143"]["sessions_passed"] == [True, False]


def test_fake_worker_uses_recommended_query_text_row_only() -> None:
    worker = FakeAttributeWorker()
    source = (
        "Read the complete upstream database client span convention below.\n"
        "| `db.statement` | string | Database statement | Optional |\n"
        "| `db.query.text` | string | The database query being executed. | `Recommended` |\n"
    )
    assert worker(source) == "attribute=db.query.text"
    assert worker(source.replace("`Recommended`", "Optional")) == "invalid"


def test_withheld_source_never_dispatches_worker() -> None:
    case = run_case("withheld", _sessions("1.43"), withhold_upstream=True)
    assert case.worker.prompts == []
    assert [session.passed for session in case.record.sessions] == [True, False]
