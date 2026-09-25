"""Versioned OTel B witness for the opt-in prior verification gate."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_otel_long_b import build_otel_long_b_sessions
from rsicontext.lifecycle.material_otel_long_b_v2 import build_otel_long_b_v2_sessions
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance


@pytest.fixture(scope="module")
def source_root() -> Path:
    configured = os.environ.get("RSICONTEXT_OTEL_SOURCE_ROOT")
    if configured is None:
        pytest.skip("set RSICONTEXT_OTEL_SOURCE_ROOT to the pinned detached checkout")
    return Path(configured)


class _Witness:
    """Read source once, retain only the bounded carry, then use receipts."""

    def __init__(self, state: dict[str, object], *, force_prior: bool) -> None:
        self.state = state
        self.force_prior = force_prior
        self.requested: set[str] = set()
        self.dual_constraint = False
        self.query_proposal = False
        self.views: list[StageView] = []

    @property
    def carry(self) -> dict[str, object]:
        raw = self.state["carry"]
        assert isinstance(raw, dict)
        return raw

    def on_stage(self, stage: StageView) -> StageResponse:
        self.views.append(stage)
        if stage.stage_id == "otel-long-source-review":
            text = "\n".join(doc.text for doc in stage.documents)
            self.carry["mode"] = "`database/dup` - emit both" in text
            self.carry["privacy"] = (
                "Non-parameterized query text SHOULD NOT be collected by default" in text
                and "Parameterized query text SHOULD be collected by default" in text
            )
        elif stage.stage_id == "otel-dual-collector-constraint":
            self.dual_constraint = any(
                "legacy collector must still receive" in doc.text for doc in stage.documents
            )
        elif stage.stage_id == "otel-migration-award":
            if not (self.carry.get("mode") and self.dual_constraint):
                return StageResponse("No supported mode")
            if "dual-v" not in self.requested:
                self.requested.add("dual-v")
                return StageResponse(
                    "Verify dual emission",
                    (
                        Action(
                            "request_verification",
                            "dual-v",
                            {"check": "dual-emission", "subject": "database/dup"},
                        ),
                    ),
                )
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if self.force_prior or ("dual-v" in receipts and receipts["dual-v"].verdict == "pass"):
                self.carry["migrated"] = True
                return StageResponse(
                    "Finalize primary migration",
                    (
                        Action("create_record", "migration_commit", {"plan": "database/dup"}),
                        Action("finalize", "migration_commit", {"status": "final"}, ("dual-v",)),
                    ),
                )
        elif stage.stage_id == "otel-query-text-proposal":
            self.query_proposal = any(
                "raw non-parameterized SQL query text" in doc.text for doc in stage.documents
            )
        elif stage.stage_id == "otel-query-text-rollout":
            if not (
                self.carry.get("migrated") and self.carry.get("privacy") and self.query_proposal
            ):
                return StageResponse("Missing earlier project evidence")
            if "privacy-v" not in self.requested:
                self.requested.add("privacy-v")
                return StageResponse(
                    "Verify query-text safety",
                    (
                        Action(
                            "request_verification",
                            "privacy-v",
                            {
                                "check": "query-text-safety",
                                "subject": "hold-raw-enable-parameterized",
                            },
                        ),
                    ),
                )
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if "privacy-v" in receipts and receipts["privacy-v"].verdict == "pass":
                return StageResponse(
                    "Finalize query-text rollout",
                    (
                        Action(
                            "create_record",
                            "query_text_rollout",
                            {
                                "plan": "hold-raw-enable-parameterized",
                                "raw_nonparameterized": "hold",
                                "parameterized_without_values": "allow",
                            },
                        ),
                        Action(
                            "finalize", "query_text_rollout", {"status": "final"}, ("privacy-v",)
                        ),
                    ),
                )
        return StageResponse("No action")


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance], *, force_prior: bool = False
) -> tuple[SequenceRecord, ProjectState, list[_Witness]]:
    env = ProjectState()
    witnesses: list[_Witness] = []

    def factory(state: dict[str, object]) -> _Witness:
        witness = _Witness(state, force_prior=force_prior)
        witnesses.append(witness)
        return witness

    result = run_session_sequence(list(sessions), factory, envs=[env, env], max_turns_per_stage=3)
    return result, env, witnesses


def test_v2_source_reference_passes_both_sessions(source_root: Path) -> None:
    sessions = build_otel_long_b_v2_sessions(source_root)
    result, env, witnesses = _run(sessions)
    assert [session.passed for session in result.sessions] == [True, True], result.to_dict()
    assert witnesses[0] is not witnesses[1]
    assert witnesses[1].carry["mode"] is True
    assert env.records["dual-v"]["verdict"] == "pass"
    assert env.records["privacy-v"]["verdict"] == "pass"
    assert all(
        not hasattr(view, "commit_precondition") for witness in witnesses for view in witness.views
    )


def test_v2_failed_prior_receipt_blocks_second_session_even_after_forced_finalize(
    source_root: Path,
) -> None:
    first, second = build_otel_long_b_v2_sessions(source_root)
    award = first.stages[2]
    failing_award = replace(award, verification_oracle={"dual-emission": {"database/dup": False}})
    first = replace(first, stages=(*first.stages[:2], failing_award, *first.stages[3:]))
    result, env, _witnesses = _run((first, second), force_prior=True)
    assert "migration_commit" in env.finalized_record_ids
    assert env.records["dual-v"]["verdict"] == "fail"
    assert "query_text_rollout" in env.finalized_record_ids
    assert [session.passed for session in result.sessions] == [False, False]
    assert any("environment-issued PASS" in failure for failure in result.sessions[1].failures), (
        result.sessions[1].failures
    )


def test_v2_is_an_opt_in_material_revision(source_root: Path) -> None:
    old_first, old_second = build_otel_long_b_sessions(source_root)
    first, second = build_otel_long_b_v2_sessions(source_root)
    assert first.instance_id != old_first.instance_id
    assert second.instance_id != old_second.instance_id
    assert first.stages[0].documents == old_first.stages[0].documents
    assert "prior_verification" not in (old_second.stages[2].commit_precondition or {})
    gate = second.stages[2].commit_precondition
    assert gate is not None
    assert gate["prior_verification"] == {
        "check": "dual-emission",
        "plan_field": "plan",
        "allowed_later_plans": {"database/dup": ["hold-raw-enable-parameterized"]},
    }
    serialized = json.dumps(
        [session.to_dict() for session in (first, second)],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assert hashlib.sha256(serialized).hexdigest() == (
        "b6c165629868d89295e16ece0e3f4e635fd90d4937c3d7c6e0b647b38a1b0bbd"
    )
