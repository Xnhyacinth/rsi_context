"""The live candidate entry remains closed until OS and broker isolation exist."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import r3_researcher_pilot as pilot
from r2a_compare import _offline_responder, _run_arm

from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.security.isolated_policy import (
    PolicyIsolationUnavailable,
    require_isolated_policy_executor,
)


def test_isolation_gate_has_no_attestation_or_bypass_parameter() -> None:
    with pytest.raises(PolicyIsolationUnavailable, match="jailed candidate process"):
        require_isolated_policy_executor()


def test_live_pilot_refuses_before_provider_or_candidate_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A malicious candidate need not pass static audit to prove that the live
    # entry never reaches the point where it could execute.
    calls: list[str] = []
    monkeypatch.setenv("SIFLOW_API_KEY", "test-only")
    monkeypatch.setattr(pilot, "_available_models", lambda: calls.append("provider"))
    monkeypatch.setattr(
        pilot,
        "_researcher_unassisted_round",
        lambda *args, **kwargs: calls.append("researcher"),
    )
    monkeypatch.setattr(pilot, "_run_arm", lambda *args, **kwargs: calls.append("worker"))
    output = tmp_path / "pilot.json"
    with pytest.raises(PolicyIsolationUnavailable):
        pilot.run(output)
    assert calls == []
    assert not output.exists()
    assert not output.with_suffix("").exists()


def test_pinned_baseline_offline_path_still_runs() -> None:
    run = _run_arm(
        strong_model_fixed_policy_text(), build_research_v4_dossier(), _offline_responder
    )
    assert run["instance_id"] == build_research_v4_dossier().instance_id
    assert run["model_calls"] > 0
    assert run["policy_errors"] == []
