"""The live candidate entry remains closed until OS and broker isolation exist."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import arm_comparison_v2
import r2a_compare
import r2b_compare
import r3_compare
import r3_researcher_pilot as pilot
import trajectory_v3
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


def test_shared_live_researcher_round_refuses_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_http(*args: object, **kwargs: object) -> None:
        raise AssertionError("live researcher reached HTTP")

    monkeypatch.setattr("urllib.request.urlopen", fail_http)
    with pytest.raises(PolicyIsolationUnavailable):
        r2a_compare._researcher_unassisted_round("baseline", {}, live=True)


def test_r2a_r2b_r3_live_entries_refuse_before_worker_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "test-only")

    def fail_worker(*args: object, **kwargs: object) -> None:
        raise AssertionError("live reader responder constructed")

    for module, main in (
        (r2a_compare, r2a_compare.main),
        (r2b_compare, r2b_compare.main),
        (r3_compare, r3_compare.main),
    ):
        monkeypatch.setattr(module, "_live_responder_factory", fail_worker)
        output = tmp_path / f"{module.__name__}.json"
        monkeypatch.setattr(sys, "argv", [module.__name__, "--output", str(output)])
        assert main() == 2
        assert not output.exists()


def test_legacy_live_entries_refuse_before_researcher_or_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIFLOW_API_KEY", "test-only")

    def fail_start(*args: object, **kwargs: object) -> None:
        raise AssertionError("legacy live run started")

    monkeypatch.setattr(arm_comparison_v2, "load_worlds_v2", fail_start)
    arm_output = tmp_path / "arm.json"
    monkeypatch.setattr(sys, "argv", ["arm_comparison_v2", "--output", str(arm_output)])
    assert arm_comparison_v2.main() == 2
    assert not arm_output.exists()

    monkeypatch.setattr(trajectory_v3, "run_dev_session", fail_start)
    trajectory_output = tmp_path / "trajectory.json"
    monkeypatch.setattr(
        sys, "argv", ["trajectory_v3", "--researcher", "--output", str(trajectory_output)]
    )
    assert trajectory_v3.main() == 2
    assert not trajectory_output.exists()
    monkeypatch.setattr(sys, "argv", ["trajectory_v3", "--output", str(trajectory_output)])
    assert trajectory_v3.main() == 2
    assert not trajectory_output.exists()
    with pytest.raises(PolicyIsolationUnavailable):
        trajectory_v3._researcher_round(tmp_path / "strategy.py", b"visible", 0)


def test_legacy_strategy_file_never_executes_in_host(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    strategy = tmp_path / "strategy.py"
    strategy.write_text(f"open({str(marker)!r}, 'w').write('unsafe')\n", encoding="utf-8")
    with pytest.raises(PolicyIsolationUnavailable):
        arm_comparison_v2.normalize_answer("reply", strategy)
    assert not marker.exists()

    hook = trajectory_v3.TrajectoryHook({}, strategy_text=strategy.read_text())
    with pytest.raises(PolicyIsolationUnavailable):
        hook._strategy_namespace()
    assert not marker.exists()
