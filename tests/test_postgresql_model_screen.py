"""Behavioral checks for the model-driven PostgreSQL B development control."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.postgresql_model_screen import run_case, run_screen
from rsicontext.lifecycle.material_postgresql_source_contrast import (
    build_postgresql_source_contrast_sessions,
)
from rsicontext.lifecycle.postgresql_model_fixed import postgresql_model_fixed_policy_text
from rsicontext.lifecycle.spec import LifecycleInstance


def _sessions(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    variable = (
        "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT"
        if revision == "16"
        else "RSICONTEXT_POSTGRESQL_SOURCE_ROOT"
    )
    configured = os.environ.get(variable)
    if not configured:
        pytest.skip(f"set {variable} to the detached pinned checkout")
    return build_postgresql_source_contrast_sessions(Path(configured), revision=revision)


def test_same_policy_runs_complete_stop_early_matrix() -> None:
    assert "failover" not in postgresql_model_fixed_policy_text()
    evidence = run_screen(_sessions("16"), _sessions("17"))
    assert evidence["status"] == "offline-structural-screen-passed"
    assert evidence["screen_case_count"] == 11
    assert evidence["provider_usage"] is None
    assert evidence["fixed_reader_difficulty"] is None
    assert (
        evidence["policy_sha256"]
        == hashlib.sha256(postgresql_model_fixed_policy_text().encode("utf-8")).hexdigest()
    )
    cases = {str(case["case"]): case for case in cast(list[dict[str, object]], evidence["cases"])}
    assert cases["full-16"]["final_plan"] == "defer-native"
    assert cases["full-17"]["final_plan"] == "configure-native"
    assert cases["full-16"]["worker_prompt_sha256"] != cases["full-17"]["worker_prompt_sha256"]
    assert cases["empty-carry-reread-17"]["worker_dispatches"] == 3
    assert cases["empty-carry-no-reread-17"]["worker_dispatches"] == 1


@pytest.mark.parametrize("revision", ["16", "17"])
def test_survey_is_request_blind_and_receipt_path_is_real(revision: str) -> None:
    case = run_case("full", _sessions(revision))
    assert [session.passed for session in case.record.sessions] == [True, True]
    assert all(not session.policy_errors for session in case.record.sessions)
    assert len(case.worker.prompts) == 2
    assert "<refentry" in case.worker.prompts[0]
    assert "project-request" not in case.worker.prompts[0]
    assert "failover = true" not in case.worker.prompts[0]
    assert "project-request" in case.worker.prompts[1]
    assert case.record.sessions[0].final_carry is not None
    assert "parameter_catalog" in case.record.sessions[0].final_carry
    assert case.record.sessions[0].carry_bytes < 4096
    assert [action.kind for action in case.env.transcript] == [
        "request_verification",
        "create_record",
        "finalize",
        "request_verification",
        "create_record",
        "finalize",
    ]
    assert case.env.records["source_review"]["provenance"] == ["source-review-receipt"]
    assert case.env.records["native_capability_decision"]["provenance"] == [
        "decision-review-receipt"
    ]


def test_prior_and_current_receipt_failures_are_separate() -> None:
    sessions = _sessions("17")
    prior = run_case("prior", sessions, prior_receipt_fails=True)
    current = run_case("current", sessions, decision_receipt_fails=True)
    assert [session.passed for session in prior.record.sessions] == [False, False]
    assert "source_review" not in prior.env.records
    assert prior.env.records["source-review-receipt"]["verdict"] == "fail"
    assert "native_capability_decision" in prior.env.records
    assert [session.passed for session in current.record.sessions] == [True, False]
    assert current.env.records["source_review"]["status"] == "final"
    assert current.env.records["decision-review-receipt"]["verdict"] == "fail"
    assert "native_capability_decision" not in current.env.records


def test_cli_preserves_an_existing_evidence_file(tmp_path: Path) -> None:
    output = tmp_path / "screen.json"
    output.write_bytes(b"existing evidence\n")
    script = Path(__file__).resolve().parent.parent / "scripts/r10_pg_model_screen.py"

    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "output already exists" in result.stderr
    assert output.read_bytes() == b"existing evidence\n"
