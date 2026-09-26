"""Offline admission tests; never execute model-authored policy code."""

from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from rsicontext.experiment.brokered_researcher_pretest import (
    AdmissionPlan,
    ResearcherDraw,
    preflight_runtime,
    stage_audited_snapshot,
)
from rsicontext.experiment.brokered_researcher_pretest import (
    run_offline_admission as _run_offline_admission,
)
from rsicontext.security.policy_jail import JailSetupError, StagedPolicyJail

_BASELINE = b"def on_turn(turn):\n    return {'pack_text': '', 'actions': ()}\n"
_CHANGED = b"def on_turn(turn):\n    return {'pack_text': 'changed', 'actions': ()}\n"


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plan(draws: int = 2, cap: int = 1_000_000) -> AdmissionPlan:
    return AdmissionPlan(
        planned_draws=draws,
        baseline_sha256=_hash(_BASELINE),
        source_sha256=_hash(b"source"),
        feedback_sha256=_hash(b"feedback"),
        researcher_model="declared-researcher",
        worker_model="declared-worker",
        max_candidate_bytes=cap,
    )


def _host() -> dict[str, str]:
    return {
        "manifest_sha256": "a" * 64,
        "probe_policy_sha256": "b" * 64,
        "python_sha256": "c" * 64,
    }


def _complete(policy: bytes = _CHANGED) -> ResearcherDraw:
    return ResearcherDraw(
        policy_bytes=policy,
        model_echo="declared-researcher",
        finish_reason="stop",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        usage_source="provider",
    )


def run_offline_admission(
    plan: AdmissionPlan,
    *,
    output: Path,
    preflight: Callable[[], dict[str, str]],
    draw: Callable[[int], ResearcherDraw],
) -> dict[str, object]:
    return _run_offline_admission(
        plan,
        baseline_policy_bytes=_BASELINE,
        source_bytes=b"source",
        visible_feedback_bytes=b"feedback",
        output=output,
        preflight=preflight,
        draw=draw,
    )


def test_host_failure_precedes_output_draw_and_policy_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_load(_source: str) -> None:
        raise AssertionError("candidate reached host load_policy")

    monkeypatch.setattr("rsicontext.lifecycle.policy.load_policy", forbidden_load)
    called = False

    def draw(_index: int) -> ResearcherDraw:
        nonlocal called
        called = True
        return _complete()

    def fail_host() -> dict[str, str]:
        raise JailSetupError("non-root-owned path ancestor: /usr/bin")

    with pytest.raises(JailSetupError, match="/usr/bin"):
        run_offline_admission(_plan(), output=tmp_path / "result", preflight=fail_host, draw=draw)
    assert not called
    assert not (tmp_path / "result").exists()


def test_planned_denominator_is_persisted_before_first_draw_and_failures_count(
    tmp_path: Path,
) -> None:
    output = tmp_path / "admission"

    def draw(index: int) -> ResearcherDraw:
        current = json.loads((output / "result.json").read_text())
        assert current["valid_submitted"]["denominator"] == 3
        assert len(current["draws"]) == 3
        if index == 0:
            raise TimeoutError("provider timed out")
        if index == 1:
            return _complete(b"import os\ndef on_turn(turn):\n    return {}\n")
        return _complete()

    result = run_offline_admission(_plan(3), output=output, preflight=_host, draw=draw)
    rows = cast(list[dict[str, object]], result["draws"])
    assert [row["status"] for row in rows] == [
        "draw-failed",
        "audit-rejected",
        "valid-submitted-awaiting-jailed-exercise",
    ]
    assert result["valid_submitted"] == {"numerator": 1, "denominator": 3}
    assert result["audited_and_exercised"] == {"numerator": 0, "denominator": 3}
    assert result["live_ready"] is False
    assert (output / "draw-02/policy/seed.py").read_bytes() == _CHANGED
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "draw-02").stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "draw-02/policy").stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "draw-02/policy/seed.py").stat().st_mode) == 0o600
    assert stat.S_IMODE((output / "result.json").stat().st_mode) == 0o600
    assert list((output / "draw-02").rglob("*")) == [
        output / "draw-02/policy",
        output / "draw-02/policy/seed.py",
    ]


@pytest.mark.parametrize(
    "draw",
    [
        ResearcherDraw(policy_bytes=_CHANGED, model_echo="other", finish_reason="stop"),
        ResearcherDraw(
            policy_bytes=_CHANGED, model_echo="declared-researcher", finish_reason="length"
        ),
        ResearcherDraw(
            policy_bytes=_CHANGED,
            model_echo="declared-researcher",
            finish_reason="stop",
            input_tokens=1,
            output_tokens=2,
            usage_source="unknown",
        ),
        ResearcherDraw(
            policy_bytes=_CHANGED,
            model_echo="declared-researcher",
            finish_reason="stop",
            input_tokens=True,
            output_tokens=2,
            total_tokens=3,
            usage_source="provider",
        ),
    ],
)
def test_incomplete_or_unverified_provider_result_is_not_valid(
    tmp_path: Path, draw: ResearcherDraw
) -> None:
    result = run_offline_admission(
        _plan(1), output=tmp_path / "admission", preflight=_host, draw=lambda _: draw
    )
    rows = cast(list[dict[str, object]], result["draws"])
    assert rows[0]["status"] == "researcher-response-unverified"
    assert result["valid_submitted"] == {"numerator": 0, "denominator": 1}


def test_candidate_cap_and_unchanged_do_not_enter_numerator(tmp_path: Path) -> None:
    result = run_offline_admission(
        _plan(2, len(_BASELINE)),
        output=tmp_path / "admission",
        preflight=_host,
        draw=lambda index: _complete(_BASELINE if index == 0 else b"x" * (len(_BASELINE) + 1)),
    )
    rows = cast(list[dict[str, object]], result["draws"])
    assert [row["status"] for row in rows] == ["unchanged", "candidate-too-large"]
    assert result["valid_submitted"] == {"numerator": 0, "denominator": 2}
    assert not (tmp_path / "admission/draw-01").exists()


def test_policy_boundary_refusal_counts_and_next_draw_continues(tmp_path: Path) -> None:
    # The AST auditor accepts this harmless string, but scan_policy's
    # conservative text scanner rejects it with PolicyBoundaryError.
    rejected = (
        b"def on_turn(turn):\n    note = 'os.'\n    return {'pack_text': note, 'actions': ()}\n"
    )
    result = run_offline_admission(
        _plan(2),
        output=tmp_path / "admission",
        preflight=_host,
        draw=lambda index: _complete(rejected if index == 0 else _CHANGED),
    )
    rows = cast(list[dict[str, object]], result["draws"])
    assert [row["status"] for row in rows] == [
        "policy-contract-rejected",
        "valid-submitted-awaiting-jailed-exercise",
    ]
    assert rows[0]["error_type"] == "PolicyBoundaryError"
    assert result["valid_submitted"] == {"numerator": 1, "denominator": 2}
    assert result["audited_and_exercised"] == {"numerator": 0, "denominator": 2}


def test_real_preflight_stage_failure_cleans_temp_and_never_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "host-probe"
    parent.mkdir()
    launched = False

    def fail_stage(*_args: object, **_kwargs: object) -> None:
        raise JailSetupError("non-root-owned path ancestor: /usr/lib")

    def forbidden_launch(*_args: object, **_kwargs: object) -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(
        "rsicontext.experiment.brokered_researcher_pretest.tempfile.mkdtemp",
        lambda **_kwargs: str(parent),
    )
    monkeypatch.setattr(
        "rsicontext.experiment.brokered_researcher_pretest.stage_policy_jail", fail_stage
    )
    monkeypatch.setattr(
        "rsicontext.experiment.brokered_researcher_pretest.launch_policy_jail", forbidden_launch
    )
    with pytest.raises(JailSetupError, match="/usr/lib"):
        preflight_runtime(
            python_executable=Path("/trusted/python"), expected_python_sha256="a" * 64
        )
    assert not launched
    assert not parent.exists()


def test_reject_invalid_plan_before_any_draw() -> None:
    with pytest.raises(ValueError, match="planned_draws"):
        _plan(0)
    with pytest.raises(ValueError, match="max_candidate_bytes"):
        _plan(cap=1_000_001)


def test_public_parent_refuses_before_preflight_or_draw(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    called = False

    def preflight() -> dict[str, str]:
        nonlocal called
        called = True
        return _host()

    with pytest.raises(PermissionError, match="private"):
        run_offline_admission(
            _plan(1), output=public / "admission", preflight=preflight, draw=lambda _: _complete()
        )
    assert not called
    assert not (public / "admission").exists()


def test_candidate_staging_rechecks_exact_snapshot_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "admission"
    run_offline_admission(_plan(1), output=output, preflight=_host, draw=lambda _: _complete())
    snapshot = output / "draw-00"
    staged_bytes: list[bytes] = []

    def fake_stage(root: Path, policy_bytes: bytes, **_kwargs: object) -> StagedPolicyJail:
        staged_bytes.append(policy_bytes)
        return StagedPolicyJail(root, _hash(policy_bytes), "d" * 64)

    monkeypatch.setattr(
        "rsicontext.experiment.brokered_researcher_pretest.stage_policy_jail", fake_stage
    )
    artifact = stage_audited_snapshot(
        snapshot,
        expected_policy_sha256=_hash(_CHANGED),
        jail_root=tmp_path / "trusted-jail",
        python_executable=Path("/trusted/python"),
        expected_python_sha256="e" * 64,
    )
    assert staged_bytes == [_CHANGED]
    assert artifact.policy_sha256 == _hash(_CHANGED)
    with pytest.raises(ValueError, match="declared SHA256"):
        stage_audited_snapshot(
            snapshot,
            expected_policy_sha256="f" * 64,
            jail_root=tmp_path / "bad-jail",
            python_executable=Path("/trusted/python"),
            expected_python_sha256="e" * 64,
        )
    assert staged_bytes == [_CHANGED]


def test_preflight_identity_records_only_expected_hashes(tmp_path: Path) -> None:
    def host_with_secret() -> dict[str, str]:
        return {**_host(), "accidental_secret": "must-not-persist"}

    output = tmp_path / "admission"
    result = run_offline_admission(
        _plan(1), output=output, preflight=host_with_secret, draw=lambda _: _complete()
    )
    assert result["host_preflight"] == _host()
    assert "must-not-persist" not in (output / "result.json").read_text()


@pytest.mark.parametrize(
    ("material_name", "replacement"),
    [
        ("baseline_policy_bytes", b"other baseline"),
        ("source_bytes", b"other source"),
        ("visible_feedback_bytes", b"other visible feedback"),
    ],
)
def test_declared_material_hash_mismatch_refuses_before_preflight_and_draw(
    tmp_path: Path, material_name: str, replacement: bytes
) -> None:
    called: list[str] = []

    def host() -> dict[str, str]:
        called.append("host")
        return _host()

    def draw(_index: int) -> ResearcherDraw:
        called.append("draw")
        return _complete()

    materials = {
        "baseline_policy_bytes": _BASELINE,
        "source_bytes": b"source",
        "visible_feedback_bytes": b"feedback",
    }
    materials[material_name] = replacement
    with pytest.raises(ValueError, match=f"{material_name} differs"):
        _run_offline_admission(
            _plan(1),
            output=tmp_path / "admission",
            preflight=host,
            draw=draw,
            **materials,
        )
    assert called == []
    assert not (tmp_path / "admission").exists()


def test_false_baseline_digest_cannot_turn_unchanged_policy_into_valid_update(
    tmp_path: Path,
) -> None:
    false_plan = replace(_plan(1), baseline_sha256="0" * 64)
    with pytest.raises(ValueError, match="baseline_policy_bytes differs"):
        _run_offline_admission(
            false_plan,
            baseline_policy_bytes=_BASELINE,
            source_bytes=b"source",
            visible_feedback_bytes=b"feedback",
            output=tmp_path / "admission",
            preflight=_host,
            draw=lambda _: _complete(_BASELINE),
        )
    assert not (tmp_path / "admission").exists()
