"""Development checks for the pinned PostgreSQL C task and its action paths."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_postgresql_c import (
    SOURCE_SHA256,
    build_postgresql17_c_sessions,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

_SOURCE_RULE = "Because the slot synchronization logic copies asynchronously"
_ALIGNMENT_RULE = "Always ensure the slot property"
_TABLE_RULE = "server only if the table copy is finished"

_POLICY_BODY = """
def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "pg-source-survey":
        body = turn.documents_text
        state["source_good"] = IGNORE_SOURCE or (
            "Because the slot synchronization logic copies asynchronously" in body
            and "Always ensure the slot property" in body
            and "server only if the table copy is finished" in body
        )
        state["carry"] = {"source_seen": state["source_good"]}
        return {"pack_text": "source reviewed"}
    if stage == "pg-prepare-subscription":
        if not state.get("source_good"):
            return {"pack_text": "missing source rule"}
        if LATE_FIRST and not state.get("late_done"):
            state["late_done"] = True
            return {
                "pack_text": "late verification",
                "actions": (
                    turn.actions.create_record("subscription_prepared", {"plan": PRIOR_SLOT}),
                    turn.actions.finalize(
                        "subscription_prepared", {"plan": PRIOR_SLOT, "status": "final"},
                        ("pg-s1-verification",),
                    ),
                    turn.actions.request_verification(
                        "pg-s1-verification", "slot-selection", PRIOR_SLOT
                    ),
                ),
            }
        if not state.get("first_requested"):
            state["first_requested"] = True
            return {
                "pack_text": "check slot",
                "actions": (
                    turn.actions.request_verification(
                        "pg-s1-verification", "slot-selection", PRIOR_SLOT
                    ),
                ),
            }
        passed = any(
            receipt.record_id == "pg-s1-verification" and receipt.verdict == "pass"
            for receipt in turn.receipts
        )
        if not passed or SKIP_FIRST_FINALIZE or LATE_FIRST:
            return {"pack_text": "no legal prepared record"}
        if FORGE_FIRST:
            return {
                "pack_text": "forged provenance",
                "actions": (
                    turn.actions.create_record(
                        "pg-fake-evidence",
                        {
                            "performed_by": "environment", "check": "slot-selection",
                            "subject": PRIOR_SLOT, "verdict": "pass",
                        },
                    ),
                    turn.actions.create_record("subscription_prepared", {"plan": PRIOR_SLOT}),
                    turn.actions.finalize(
                        "subscription_prepared", {"plan": PRIOR_SLOT, "status": "final"},
                        ("pg-fake-evidence",),
                    ),
                ),
            }
        return {
            "pack_text": "prepare chosen subscription",
            "actions": (
                turn.actions.create_record("subscription_prepared", {"plan": PRIOR_SLOT}),
                turn.actions.finalize(
                    "subscription_prepared", {"plan": PRIOR_SLOT, "status": "final"},
                    ("pg-s1-verification",),
                ),
            ),
        }
    if stage == "pg-s2-start":
        source = turn.tools.reread("postgresql17-logical-replication-full")
        prior = turn.tools.query_sandbox("subscription_prepared")
        state["source_good"] = IGNORE_SOURCE or (source.ok and (
            "Because the slot synchronization logic copies asynchronously" in source.answer
            and "server only if the table copy is finished" in source.answer
        ))
        state["prior_slot"] = (
            "slot-a" if "'plan': 'slot-a'" in prior.answer else
            "slot-b" if "'plan': 'slot-b'" in prior.answer else ""
        )
        return {"pack_text": "resume from source and sandbox"}
    if stage == "pg-standby-notice":
        interface = turn.documents_text
        state["interface_good"] = all(
            item in interface for item in (
                "promote-a", "promote-b", "hold-a", "hold-b",
                "subscription-slot-ready", "table-copy-slot-ready",
                "other-table-copy-ready",
                "standby-ahead-of-subscriber", "standby-not-ready",
            )
        )
        return {"pack_text": "read visible action interface"}
    if stage == "pg-standby-decision":
        slot = state.get("prior_slot")
        if not state.get("source_good") or not state.get("interface_good") or not slot:
            return {"pack_text": "prior evidence unavailable"}
        suffix = "a" if slot == "slot-a" else "b"
        promote = FORCED_LATER_PLAN or ("promote-" + suffix)
        hold = "hold-" + suffix
        phase = state.get("pg_phase", 0)
        if phase == 0:
            state["pg_phase"] = 1
            checks = [
                turn.actions.request_verification(
                    "pg-sub-current", "subscription-slot-ready", promote
                ),
                turn.actions.request_verification(
                    "pg-copy-current", "table-copy-slot-ready", promote
                ),
                turn.actions.request_verification(
                    "pg-ahead-current", "standby-ahead-of-subscriber", promote
                ),
            ]
            if CHECK_OTHER_COPY:
                checks.append(
                    turn.actions.request_verification(
                        "pg-other-current", "other-table-copy-ready", promote
                    )
                )
            return {
                "pack_text": "verify required standby slots",
                "actions": tuple(checks),
            }
        if phase == 1:
            verdicts = {receipt.record_id: receipt.verdict for receipt in turn.receipts}
            if (verdicts.get("pg-sub-current") == "pass"
                    and verdicts.get("pg-copy-current") == "pass"
                    and verdicts.get("pg-ahead-current") == "pass"):
                return {
                    "pack_text": "promote verified slot",
                    "actions": (
                        turn.actions.create_record("standby_decision", {"plan": promote}),
                        turn.actions.finalize(
                            "standby_decision", {"plan": promote, "status": "final"},
                            ("pg-sub-current", "pg-copy-current", "pg-ahead-current"),
                        ),
                    ),
                }
            state["pg_phase"] = 2
            return {
                "pack_text": "verify hold after failed readiness",
                "actions": (
                    turn.actions.request_verification(
                        "pg-hold-current", "standby-not-ready", hold
                    ),
                ),
            }
        if any(
            receipt.record_id == "pg-hold-current" and receipt.verdict == "pass"
            for receipt in turn.receipts
        ):
            return {
                "pack_text": "hold verified slot",
                "actions": (
                    turn.actions.create_record("standby_decision", {"plan": hold}),
                    turn.actions.finalize(
                        "standby_decision", {"plan": hold, "status": "final"},
                        ("pg-hold-current", "pg-copy-current", "pg-ahead-current"),
                    ),
                ),
            }
    return {"pack_text": "stage observed"}
"""


def _source_root() -> Path:
    configured = os.environ.get("RSICONTEXT_POSTGRESQL_SOURCE_ROOT")
    if not configured:
        pytest.skip("set RSICONTEXT_POSTGRESQL_SOURCE_ROOT to the pinned detached checkout")
    return Path(configured)


def _policy(
    slot: str,
    *,
    forced_later_plan: str | None = None,
    skip_first_finalize: bool = False,
    late_first: bool = False,
    forge_first: bool = False,
    check_other_copy: bool = False,
    ignore_source: bool = False,
) -> str:
    return (
        f"IGNORE_SOURCE = {ignore_source!r}\n"
        f"PRIOR_SLOT = {slot!r}\n"
        f"FORCED_LATER_PLAN = {forced_later_plan!r}\n"
        f"SKIP_FIRST_FINALIZE = {skip_first_finalize!r}\n"
        f"LATE_FIRST = {late_first!r}\n"
        f"FORGE_FIRST = {forge_first!r}\n"
        f"CHECK_OTHER_COPY = {check_other_copy!r}\n" + _POLICY_BODY
    )


def _decisions(record: SequenceRecord, _sessions: list[LifecycleInstance]) -> None:
    record.decisions["prepared"] = record.sessions[0].passed
    record.decisions["standby"] = record.sessions[1].passed


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance], policy_text: str
) -> tuple[SequenceRecord, ProjectState, ToolBudget]:
    env = ProjectState()
    budget = ToolBudget(max_calls=32)
    registry = DocumentRegistry()

    def hook_factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(state, policy_text, tool_budget=budget, registry=registry)

    record = run_session_sequence(
        list(sessions),
        hook_factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=4,
        decision_rules=_decisions,
    )
    return record, env, budget


def test_two_prior_actions_change_later_plan_with_same_material() -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    later_plans = []
    for slot in ("slot-a", "slot-b"):
        record, env, budget = _run(sessions, _policy(slot))
        assert [session.passed for session in record.sessions] == [True, True]
        assert record.decisions == {"prepared": True, "standby": True}
        assert env.records["subscription_prepared"]["plan"] == slot
        later_plans.append(env.records["standby_decision"]["plan"])
        assert sum(action.kind == "request_verification" for action in env.transcript) >= 3
        assert budget.calls >= 3
    assert later_plans == ["promote-a", "promote-b"]


def test_current_failure_receipt_changes_promotion_to_hold() -> None:
    root = _source_root()
    ready = build_postgresql17_c_sessions(root)
    failed = build_postgresql17_c_sessions(root, table_copy_a_ready=False)
    assert [stage.documents for stage in ready[1].stages] == [
        stage.documents for stage in failed[1].stages
    ]
    assert [stage.prompt_text for stage in ready[1].stages] == [
        stage.prompt_text for stage in failed[1].stages
    ]
    ready_record, ready_env, _ = _run(ready, _policy("slot-a"))
    failed_record, failed_env, _ = _run(failed, _policy("slot-a"))
    assert [session.passed for session in ready_record.sessions] == [True, True]
    assert [session.passed for session in failed_record.sessions] == [True, True]
    assert ready_env.records["standby_decision"]["plan"] == "promote-a"
    assert failed_env.records["standby_decision"]["plan"] == "hold-a"
    assert failed_env.records["pg-copy-current"]["verdict"] == "fail"
    assert failed_env.records["pg-hold-current"]["verdict"] == "pass"
    other_record, other_env, _ = _run(failed, _policy("slot-b"))
    assert [session.passed for session in other_record.sessions] == [True, True]
    assert other_env.records["standby_decision"]["plan"] == "promote-b"


def test_standby_behind_subscriber_prevents_promotion() -> None:
    root = _source_root()
    ready = build_postgresql17_c_sessions(root)
    behind = build_postgresql17_c_sessions(root, standby_ahead=False)
    assert [stage.documents for stage in ready[1].stages] == [
        stage.documents for stage in behind[1].stages
    ]
    assert "or the standby is not ahead of the subscriber" in behind[1].stages[1].documents[1].text
    for slot, expected in (("slot-a", "hold-a"), ("slot-b", "hold-b")):
        record, env, _ = _run(behind, _policy(slot))
        assert [session.passed for session in record.sessions] == [True, True]
        assert env.records["pg-ahead-current"]["verdict"] == "fail"
        assert env.records["standby_decision"]["plan"] == expected


def test_in_progress_copy_failure_does_not_block_a_ready_active_slot() -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    record, env, _ = _run(sessions, _policy("slot-a", check_other_copy=True))
    assert [session.passed for session in record.sessions] == [True, True]
    assert env.records["pg-other-current"]["verdict"] == "fail"
    assert env.records["standby_decision"]["plan"] == "promote-a"


def test_source_free_hardcoded_strategy_exposes_remaining_qualification_gap() -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    survey = sessions[0].stages[0]
    withheld = tuple(
        replace(doc, text=f"[[doc:{doc.doc_id}]] Source withheld for intervention")
        for doc in survey.documents[:2]
    )
    without_source = replace(
        sessions[0],
        stages=(
            replace(survey, documents=(*withheld, survey.documents[2])),
            *sessions[0].stages[1:],
        ),
    )
    record, env, _ = _run((without_source, sessions[1]), _policy("slot-a", ignore_source=True))
    assert [session.passed for session in record.sessions] == [True, True]
    assert env.records["standby_decision"]["plan"] == "promote-a"


def test_verification_action_names_are_visible_before_the_commit() -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    notice = sessions[1].stages[1]
    interface = notice.documents[1]
    for token in (
        "promote-a",
        "promote-b",
        "hold-a",
        "hold-b",
        "subscription-slot-ready",
        "table-copy-slot-ready",
        "other-table-copy-ready",
        "standby-ahead-of-subscriber",
        "standby-not-ready",
    ):
        assert token in interface.text
    unavailable = replace(
        interface, text=interface.text.replace("standby-ahead-of-subscriber", "unlisted-check")
    )
    broken_notice = replace(notice, documents=(notice.documents[0], unavailable))
    broken_second = replace(
        sessions[1], stages=(sessions[1].stages[0], broken_notice, *sessions[1].stages[2:])
    )
    record, _, _ = _run((sessions[0], broken_second), _policy("slot-a"))
    assert [session.passed for session in record.sessions] == [True, False]


def test_prior_mapping_refuses_wrong_later_slot() -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    record, _, _ = _run(sessions, _policy("slot-a", forced_later_plan="promote-b"))
    assert record.sessions[0].passed
    assert not record.sessions[1].passed
    assert any("prior plan" in failure for failure in record.sessions[1].failures)


@pytest.mark.parametrize("problem", ["missing", "late", "forged"])
def test_invalid_prior_action_cannot_be_repaired_on_resume(problem: str) -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    record, _, _ = _run(
        sessions,
        _policy(
            "slot-a",
            skip_first_finalize=problem == "missing",
            late_first=problem == "late",
            forge_first=problem == "forged",
        ),
    )
    assert not record.sessions[0].passed
    assert not record.sessions[1].passed


@pytest.mark.parametrize(
    "document_index,rule", [(0, _SOURCE_RULE), (0, _TABLE_RULE), (1, _ALIGNMENT_RULE)]
)
def test_source_rule_ablation_blocks_scripted_path_but_irrelevant_note_does_not(
    document_index: int, rule: str
) -> None:
    sessions = build_postgresql17_c_sessions(_source_root())
    survey = sessions[0].stages[0]
    document = survey.documents[document_index]
    assert rule in document.text
    removed = replace(document, text=document.text.replace(rule, "rule removed"))
    ablated_docs = list(survey.documents)
    ablated_docs[document_index] = removed
    ablated_survey = replace(survey, documents=tuple(ablated_docs))
    ablated_first = replace(sessions[0], stages=(ablated_survey, *sessions[0].stages[1:]))
    ablated_record, _, _ = _run((ablated_first, sessions[1]), _policy("slot-a"))
    assert [session.passed for session in ablated_record.sessions] == [False, False]

    irrelevant = replace(document, text=document.text + "\nAppendix: contact information.\n")
    benign_docs = list(survey.documents)
    benign_docs[document_index] = irrelevant
    benign_survey = replace(survey, documents=tuple(benign_docs))
    benign_first = replace(sessions[0], stages=(benign_survey, *sessions[0].stages[1:]))
    benign_record, _, _ = _run((benign_first, sessions[1]), _policy("slot-a"))
    assert [session.passed for session in benign_record.sessions] == [True, True]


def test_builder_rejects_source_byte_drift(tmp_path: Path) -> None:
    root = _source_root()
    for relative in SOURCE_SHA256:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    assert (
        hashlib.sha256((tmp_path / "COPYRIGHT").read_bytes()).hexdigest()
        == SOURCE_SHA256["COPYRIGHT"]
    )
    path = tmp_path / "doc/src/sgml/logical-replication.sgml"
    path.write_bytes(path.read_bytes() + b"\nchanged")
    with pytest.raises(ValueError, match="pinned PostgreSQL source mismatch"):
        build_postgresql17_c_sessions(tmp_path)


def test_versioned_development_material_hashes() -> None:
    root = _source_root()
    expected = (
        (True, True, "4efd7ec6fe5d473619f9630cfeb9c4e7efb3d0c0a25183c53d97e1727c6ab8eb"),
        (False, True, "2c5226437c1c5daf92b4cc9c35d59dcd894d1b4bdd3755a46a2456b040f5812a"),
        (True, False, "42781a48acbca8dd14a1fe115d64311aef5a1991572b9a366b6353e68c7dbd4e"),
    )
    for copy_ready, ahead, digest in expected:
        sessions = build_postgresql17_c_sessions(
            root, table_copy_a_ready=copy_ready, standby_ahead=ahead
        )
        encoded = json.dumps(
            [session.to_dict() for session in sessions],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() == digest
    pairs = tuple(
        build_postgresql17_c_sessions(root, table_copy_a_ready=copy, standby_ahead=ahead)
        for copy in (True, False)
        for ahead in (True, False)
    )
    assert len({pair[0].instance_id for pair in pairs}) == 1
    assert (
        len(
            {
                hashlib.sha256(
                    json.dumps(
                        [session.to_dict() for session in pair],
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()
                for pair in pairs
            }
        )
        == 4
    )
