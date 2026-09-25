"""Construction and boundary checks for the unqualified long OTel B parent."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_otel_long_b import (
    SOURCE_REVISION,
    SOURCE_SHA256,
    build_otel_long_b_sessions,
)
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance

_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0")


def _verify(record_id: str, check: str, subject: str) -> Action:
    return Action(
        kind="request_verification",
        record_id=record_id,
        fields={"check": check, "subject": subject},
    )


def _finalize(record_id: str, fields: dict[str, str], receipt_id: str) -> tuple[Action, Action]:
    return (
        Action(kind="create_record", record_id=record_id, fields=fields),
        Action(
            kind="finalize",
            record_id=record_id,
            fields={"status": "final"},
            provenance=(receipt_id,),
        ),
    )


class _Reference:
    """A deterministic witness using only views, receipts, and bounded carry."""

    def __init__(self, state: dict[str, object]) -> None:
        self.state = state
        carried = state.get("carry")
        self.initial_carry = dict(carried) if isinstance(carried, dict) else {}
        self.seen: list[StageView] = []
        self.dual_constraint = False
        self.query_proposal = False

    @property
    def carry(self) -> dict[str, object]:
        raw = self.state["carry"]
        assert isinstance(raw, dict)
        return raw

    def on_stage(self, stage: StageView) -> StageResponse:
        self.seen.append(stage)
        if stage.stage_id == "otel-long-source-review":
            text = "\n".join(document.text for document in stage.documents)
            self.carry["dual_mode_source"] = "`database/dup` - emit both" in text
            self.carry["privacy_source"] = (
                "Non-parameterized query text SHOULD NOT be collected by default" in text
                and "unless there is sanitization" in text
                and "Parameterized query text SHOULD be collected by default" in text
            )
        elif stage.stage_id == "otel-dual-collector-constraint":
            self.dual_constraint = any(
                "legacy collector must still receive" in document.text
                and "new collector receives the stable" in document.text
                for document in stage.documents
            )
        elif stage.stage_id == "otel-migration-award":
            if not (self.carry.get("dual_mode_source") and self.dual_constraint):
                return StageResponse("No source-supported dual-emission choice")
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if "dual-check" not in receipts and not self.carry.get("dual_requested"):
                self.carry["dual_requested"] = True
                return StageResponse(
                    "Request dual-emission validation",
                    (_verify("dual-check", "dual-emission", "database/dup"),),
                )
            if receipts.get("dual-check") and receipts["dual-check"].verdict == "pass":
                self.carry["migration_validated"] = True
                return StageResponse(
                    "Finalize the validated dual-mode migration",
                    _finalize("migration_commit", {"plan": "database/dup"}, "dual-check"),
                )
        elif stage.stage_id == "otel-query-text-proposal":
            self.query_proposal = any(
                "raw non-parameterized SQL query text" in document.text
                and "no sanitizer" in document.text
                and "without parameter values" in document.text
                for document in stage.documents
            )
        elif stage.stage_id == "otel-query-text-rollout":
            if not (
                self.carry.get("migration_validated")
                and self.carry.get("privacy_source")
                and self.query_proposal
            ):
                return StageResponse("Prior migration or privacy evidence is missing")
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if "privacy-check" not in receipts and not self.carry.get("privacy_requested"):
                self.carry["privacy_requested"] = True
                return StageResponse(
                    "Request query-text-safety validation",
                    (
                        _verify(
                            "privacy-check", "query-text-safety", "hold-raw-enable-parameterized"
                        ),
                    ),
                )
            if receipts.get("privacy-check") and receipts["privacy-check"].verdict == "pass":
                return StageResponse(
                    "Hold raw text; allow parameterized query text without values",
                    _finalize(
                        "query_text_rollout",
                        {
                            "plan": "hold-raw-enable-parameterized",
                            "raw_nonparameterized": "hold",
                            "parameterized_without_values": "allow",
                        },
                        "privacy-check",
                    ),
                )
        return StageResponse("No action")


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
) -> tuple[SequenceRecord, ProjectState, list[_Reference]]:
    env = ProjectState()
    hooks: list[_Reference] = []

    def factory(state: dict[str, object]) -> _Reference:
        hook = _Reference(state)
        hooks.append(hook)
        return hook

    record = run_session_sequence(list(sessions), factory, envs=[env, env], max_turns_per_stage=3)
    return record, env, hooks


def _replace_survey(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    change: Callable[[DocumentRef], DocumentRef | None],
) -> tuple[LifecycleInstance, LifecycleInstance]:
    first, second = sessions
    survey = first.stages[0]
    documents = tuple(changed for doc in survey.documents if (changed := change(doc)) is not None)
    changed_survey = replace(
        survey,
        documents=documents,
        gold_evidence_ids=tuple(doc.doc_id for doc in documents),
    )
    return replace(first, stages=(changed_survey, *first.stages[1:])), second


def test_full_pinned_source_and_reference_survive_real_reset() -> None:
    sessions = build_otel_long_b_sessions(_SOURCE)
    source_documents = sessions[0].stages[0].documents
    assert len(source_documents) == 2
    for document, relative in zip(source_documents, SOURCE_SHA256, strict=True):
        raw = (_SOURCE / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256[relative]
        assert document.text.split("\n", 1)[1].encode("utf-8") == raw
    record, env, hooks = _run(sessions)
    assert [session.passed for session in record.sessions] == [True, True], record.to_dict()
    assert record.sessions[0].persist_ok and record.sessions[1].persist_ok
    assert hooks[0] is not hooks[1]
    assert hooks[1].initial_carry == record.sessions[0].final_carry
    assert all(
        not any(doc.doc_id.startswith("otel-") for doc in view.documents) for view in hooks[1].seen
    )
    assert env.records["migration_commit"]["plan"] == "database/dup"
    assert env.records["query_text_rollout"]["raw_nonparameterized"] == "hold"
    assert env.records["query_text_rollout"]["parameterized_without_values"] == "allow"
    assert env.records["dual-check"]["verdict"] == "pass"
    assert env.records["privacy-check"]["verdict"] == "pass"


def test_selected_files_match_the_existing_portable_source_manifest() -> None:
    manifest = json.loads(
        (
            Path(__file__).resolve().parent.parent / "configs/r4_parent_source_manifest_v1.json"
        ).read_text(encoding="utf-8")
    )
    entry = next(source for source in manifest["sources"] if source["id"] == "otel-semconv-v1.43.0")
    assert entry["revision"] == SOURCE_REVISION
    for relative, expected in SOURCE_SHA256.items():
        assert entry["selected_files"][relative]["sha256"] == expected


@pytest.mark.parametrize("removed", ["mode", "privacy"])
def test_deleting_decisive_source_breaks_the_corresponding_decision(removed: str) -> None:
    sessions = build_otel_long_b_sessions(_SOURCE)

    def change(doc: DocumentRef) -> DocumentRef:
        if removed == "mode" and doc.doc_id == "otel-database-spans-full":
            return replace(doc, text=doc.text.replace("`database/dup` - emit both", "[removed]"))
        if removed == "privacy":
            return replace(
                doc,
                text=doc.text.replace(
                    "Non-parameterized query text SHOULD NOT be collected by default", "[removed]"
                ).replace("Parameterized query text SHOULD be collected by default", "[removed]"),
            )
        return doc

    record, _env, _hooks = _run(_replace_survey(sessions, change))
    if removed == "mode":
        assert [session.passed for session in record.sessions] == [False, False]
    else:
        assert [session.passed for session in record.sessions] == [True, False]


@pytest.mark.parametrize("flipped_check", ["dual-emission", "query-text-safety"])
def test_flipped_environment_receipt_blocks_the_reference_transition(
    flipped_check: str,
) -> None:
    first, second = build_otel_long_b_sessions(_SOURCE)
    if flipped_check == "dual-emission":
        award = first.stages[2]
        flipped = replace(award, verification_oracle={"dual-emission": {"database/dup": False}})
        first = replace(first, stages=(*first.stages[:2], flipped, *first.stages[3:]))
    else:
        award = second.stages[2]
        flipped = replace(
            award,
            verification_oracle={"query-text-safety": {"hold-raw-enable-parameterized": False}},
        )
        second = replace(second, stages=(*second.stages[:2], flipped, *second.stages[3:]))
    record, env, _hooks = _run((first, second))
    assert [session.passed for session in record.sessions] == (
        [False, False] if flipped_check == "dual-emission" else [True, False]
    )
    receipt_id = "dual-check" if flipped_check == "dual-emission" else "privacy-check"
    assert env.records[receipt_id]["verdict"] == "fail"
    if flipped_check == "dual-emission":
        assert "migration_commit" not in env.finalized_record_ids


def test_later_legal_write_requires_an_award_from_before_resume() -> None:
    _first, second = build_otel_long_b_sessions(_SOURCE)

    class ForceLater:
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.stage_id == "otel-s2-start":
                return StageResponse(
                    "Try to backfill the missing migration",
                    _finalize("migration_commit", {"plan": "database/dup"}, "backfill-note"),
                )
            if stage.stage_id == "otel-query-text-rollout":
                return StageResponse(
                    "Attempt an otherwise legal query-text rollout",
                    (
                        _verify(
                            "privacy-check", "query-text-safety", "hold-raw-enable-parameterized"
                        ),
                        *_finalize(
                            "query_text_rollout",
                            {
                                "plan": "hold-raw-enable-parameterized",
                                "raw_nonparameterized": "hold",
                                "parameterized_without_values": "allow",
                            },
                            "privacy-check",
                        ),
                    ),
                )
            return StageResponse("No action")

    env = ProjectState()
    result = run_lifecycle(second, ForceLater(), env)
    assert "migration_commit" in env.finalized_record_ids
    assert "query_text_rollout" in env.finalized_record_ids
    assert not result.final_check.passed
    assert any(
        "prior finalized record 'migration_commit' was absent at session start" in failure
        for failure in result.final_check.failures
    ), result.final_check.failures


def test_prior_finalization_alone_does_not_certify_a_passing_prior_receipt() -> None:
    """Characterize a remaining qualification gap without changing the grader."""

    first, second = build_otel_long_b_sessions(_SOURCE)
    award = first.stages[2]
    award = replace(award, verification_oracle={"dual-emission": {"database/dup": False}})
    first = replace(first, stages=(*first.stages[:2], award, *first.stages[3:]))

    class ForceFirst:
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.stage_id == "otel-migration-award":
                return StageResponse(
                    "Force an invalid award despite the failed receipt",
                    (
                        _verify("dual-check", "dual-emission", "database/dup"),
                        *_finalize("migration_commit", {"plan": "database/dup"}, "dual-check"),
                    ),
                )
            return StageResponse("No action")

    class ForceSecond:
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.stage_id == "otel-query-text-rollout":
                return StageResponse(
                    "Force the otherwise legal later rollout",
                    (
                        _verify(
                            "privacy-check", "query-text-safety", "hold-raw-enable-parameterized"
                        ),
                        *_finalize(
                            "query_text_rollout",
                            {
                                "plan": "hold-raw-enable-parameterized",
                                "raw_nonparameterized": "hold",
                                "parameterized_without_values": "allow",
                            },
                            "privacy-check",
                        ),
                    ),
                )
            return StageResponse("No action")

    env = ProjectState()
    first_result = run_lifecycle(first, ForceFirst(), env)
    second_result = run_lifecycle(second, ForceSecond(), env)
    assert not first_result.final_check.passed
    assert any("lacks an environment-issued" in f for f in first_result.final_check.failures)
    assert second_result.final_check.passed
    # The full two-session project still fails. The isolated second-stage
    # gate only proves earlier finalization, not earlier verification success.


def test_irrelevant_local_note_does_not_change_reference_decisions() -> None:
    sessions = build_otel_long_b_sessions(_SOURCE)
    note = DocumentRef(
        doc_id="local-office-note",
        title="Office note",
        text="[[doc:local-office-note]] The office printer is unavailable on Sunday.",
        source_url="benchmark:constructed/irrelevant-note",
        retrieved_date="2026-09-25",
    )
    first, second = sessions
    survey = first.stages[0]
    changed = replace(survey, documents=(*survey.documents, note))
    record, _env, _hooks = _run((replace(first, stages=(changed, *first.stages[1:])), second))
    assert [session.passed for session in record.sessions] == [True, True]


def test_source_byte_drift_is_rejected_before_world_construction(tmp_path: Path) -> None:
    for relative in SOURCE_SHA256:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((_SOURCE / relative).read_bytes())
    sql = tmp_path / "docs/db/sql.md"
    sql.write_bytes(sql.read_bytes() + b"\nmodified")
    with pytest.raises(ValueError, match="pinned OTel source mismatch"):
        build_otel_long_b_sessions(tmp_path)
