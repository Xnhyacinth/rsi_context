"""Source identity and causal action checks for PostgreSQL intake cards."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import fields, replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_postgresql_task_cards import (
    TaskCardId,
    build_postgresql_task_card_sessions,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageView, _build_stage_view
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

SOURCE_ENV = {
    "16": "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT",
    "17": "RSICONTEXT_POSTGRESQL_SOURCE_ROOT",
}
CARDS: tuple[TaskCardId, ...] = ("connect-offline", "binary-initial-copy")
EXPECTED_REQUEST_IDENTITY = {
    "connect-offline": (
        819,
        "6eef2d6283b3b721d462ea83ea2a4b02fea8dff53097108b49a8b64d5c73267c",
    ),
    "binary-initial-copy": (
        733,
        "883fa202221f692630f87cd1431a3aaa146c15a86a7d24a9abb2fa0d27335cd6",
    ),
}
EXPECTED_SPAN_SHA256 = {
    "16": {
        "connect": "1266ee9c19eda3fb0da9cebfbc41095a14db7c316a51f7c57dcfb8f9157d55a0",
        "binary": "6a60456fd5f78d2506a49256a2bf5563624d6526b62ec4a9edd2bd4368d1f236",
        "origin": "4854db46bb1a8c00a10ef78141a8d8cc8eabe6143884188e8606379c658c7765",
        "origin_note": "d8e6e0d77f2334b3633efc93f33d8fc8afcf1fe0007575beafe6668b752a1f10",
    },
    "17": {
        "connect": "9bb8279eddf8bd9c819ad6dd07886a2ec72de3b6e4e6172d42abe87d14f0b8f1",
        "binary": "4d1c2f8e221d50fe9f244345c35b8725440e3f3cbe06d788b69c787868cb7ebf",
        "origin": "68b549734f013a5d591f5eddf582f665e05b224b0386f5500f16cdeedf6caa3a",
        "origin_note": "d8e6e0d77f2334b3633efc93f33d8fc8afcf1fe0007575beafe6668b752a1f10",
    },
}


def _source_root(revision: str) -> Path:
    configured = os.environ.get(SOURCE_ENV[revision])
    if not configured:
        pytest.skip(f"set {SOURCE_ENV[revision]} to the detached pinned checkout")
    return Path(configured)


def _sessions(revision: str, card_id: TaskCardId) -> tuple[LifecycleInstance, LifecycleInstance]:
    return build_postgresql_task_card_sessions(
        _source_root(revision), revision=revision, card_id=card_id
    )


def _visible_without_source_text(view: StageView) -> dict[str, object]:
    projection = {field.name: getattr(view, field.name) for field in fields(StageView)}
    projection["documents"] = tuple(
        replace(doc, text="<pinned source bytes>") if doc.doc_id.startswith("upstream-") else doc
        for doc in view.documents
    )
    return projection


@pytest.mark.parametrize("card_id", CARDS)
def test_revisions_have_identical_non_source_stage_views(card_id: TaskCardId) -> None:
    older, newer = _sessions("16", card_id), _sessions("17", card_id)
    for left, right in zip(older, newer, strict=True):
        assert left.instance_id == right.instance_id
        for index, (left_stage, right_stage) in enumerate(
            zip(left.stages, right.stages, strict=True)
        ):
            left_view = _build_stage_view(left_stage, left.axes, remaining=len(left.stages) - index)
            right_view = _build_stage_view(
                right_stage, right.axes, remaining=len(right.stages) - index
            )
            assert _visible_without_source_text(left_view) == _visible_without_source_text(
                right_view
            )
    assert older[1].stages[2].commit_precondition == newer[1].stages[2].commit_precondition
    assert older[1].stages[2].verification_oracle == newer[1].stages[2].verification_oracle


@pytest.mark.parametrize("card_id", CARDS)
def test_constructed_request_identity_is_pinned_for_both_revisions(card_id: TaskCardId) -> None:
    expected_size, expected_hash = EXPECTED_REQUEST_IDENTITY[card_id]
    for revision in ("16", "17"):
        request = _sessions(revision, card_id)[1].stages[1].documents[0].text.encode("utf-8")
        assert len(request) == expected_size
        assert hashlib.sha256(request).hexdigest() == expected_hash


@pytest.mark.parametrize("revision", ("16", "17"))
def test_decisive_sgml_spans_match_reviewed_hashes(revision: str) -> None:
    raw = (_source_root(revision) / "doc/src/sgml/ref/create_subscription.sgml").read_bytes()
    for label, expected in EXPECTED_SPAN_SHA256[revision].items():
        if label == "origin_note":
            pattern = rb"<para>\s+When using a subscription parameter combination of.*?</para>"
        else:
            pattern = (
                rb'<varlistentry id="sql-createsubscription-(?:params-)?with-'
                + label.encode()
                + rb'">.*?</varlistentry>'
            )
        match = re.search(pattern, raw, re.DOTALL)
        assert match is not None
        assert hashlib.sha256(match.group()).hexdigest() == expected


_POLICY = r"""
import re

def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        source = turn.view.documents[0].text
        normalized = re.sub(r"\s+", " ", source)
        state["carry"] = {
            "connect_forces_false": (
                "Setting this to <literal>false</literal> will force the values of"
                in normalized
                and "<literal>copy_data</literal> to <literal>false</literal>"
                in normalized
            ),
            "binary_requires_receiver": (
                "initial synchronization requires all data types to have binary"
                in normalized
                and "subscriber lacks a binary receive function" in normalized
            ),
        }
        return {"pack_text": "[[doc:upstream-create-subscription]] reviewed source"}
    if stage == "review-source":
        phase = state.get("review_phase", 0)
        state["review_phase"] = phase + 1
        if phase == 0:
            return {"pack_text": "request review", "actions": (
                turn.actions.request_verification("review-receipt", "review-complete", "reviewed"),
            )}
        return {"pack_text": "commit review", "actions": (
            turn.actions.create_record("source_review", {"plan": "reviewed"}),
            turn.actions.finalize("source_review", {"plan": "reviewed", "status": "final"},
                                  ("review-receipt",)),
        )}
    if stage == "project-request-stage":
        request = turn.view.documents[0].text
        carry = state.get("carry", {})
        target = re.search(r"project-state record ([a-z][a-z_]+) with the selected plan", request)
        if target is None:
            return {"pack_text": "missing record target", "errors": ["missing record target"]}
        if "connect=false" in request:
            supported = carry.get("connect_forces_false", False)
            plan = "stage-disconnected" if supported else "launch-with-copy"
        elif "binary receive function" in request:
            supported = carry.get("binary_requires_receiver", False)
            plan = "use-text-copy" if supported else "use-binary-copy"
        else:
            return {"pack_text": "unknown request", "errors": ["unknown request"]}
        state["chosen_plan"] = plan
        state["decision_record"] = target.group(1)
        return {"pack_text": "request resolved from carry"}
    if stage == "decide-task":
        plan = state.get("chosen_plan")
        record_id = state.get("decision_record")
        phase = state.get("decision_phase", 0)
        state["decision_phase"] = phase + 1
        if phase == 0:
            return {"pack_text": "request decision review", "actions": (
                turn.actions.request_verification("decision-receipt", "decision-reviewed", plan),
            )}
        return {"pack_text": "commit decision", "actions": (
            turn.actions.create_record(record_id, {"plan": plan}),
            turn.actions.finalize(record_id, {"plan": plan, "status": "final"},
                                  ("decision-receipt",)),
        )}
    return {"pack_text": "observed"}
"""


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
) -> tuple[SequenceRecord, ProjectState]:
    env = ProjectState()
    budget = ToolBudget(max_calls=20)
    registry = DocumentRegistry()

    def factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(state, _POLICY, tool_budget=budget, registry=registry)

    def decisions(record: SequenceRecord, _instances: list[LifecycleInstance]) -> None:
        record.decisions["prior"] = record.sessions[0].passed
        record.decisions["later"] = record.sessions[1].passed

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
        decision_rules=decisions,
    )
    return record, env


@pytest.mark.parametrize(
    "card_id,expected",
    (("connect-offline", "stage-disconnected"), ("binary-initial-copy", "use-text-copy")),
)
def test_constructed_source_aware_action_and_receipt_chain(
    card_id: TaskCardId, expected: str
) -> None:
    for revision in ("16", "17"):
        record, env = _run(_sessions(revision, card_id))
        assert record.decisions == {"prior": True, "later": True}
        assert env.records["task_decision"]["plan"] == expected
        assert env.records["decision-receipt"]["verdict"] == "pass"
        assert "decision-receipt" in env.verification_record_ids


@pytest.mark.parametrize("card_id", CARDS)
def test_decision_record_target_comes_from_visible_request(card_id: TaskCardId) -> None:
    first, second = _sessions("16", card_id)
    request_stage = second.stages[1]
    request = request_stage.documents[0]
    assert "project-state record task_decision with the selected plan" in request.text
    renamed = "reviewed_project_plan"
    request_stage = replace(
        request_stage,
        documents=(replace(request, text=request.text.replace("task_decision", renamed)),),
    )
    decision_stage = second.stages[2]
    precondition = dict(decision_stage.commit_precondition or {})
    precondition["record_id"] = renamed
    decision_stage = replace(
        decision_stage,
        expected_state_delta={renamed: {"status": "final"}},
        commit_precondition=precondition,
    )
    second = replace(
        second,
        stages=(second.stages[0], request_stage, decision_stage, second.stages[3]),
        sandbox_spec={
            "records": ["source_review", renamed],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    record, env = _run((first, second))
    assert record.decisions == {"prior": True, "later": True}
    assert renamed in env.finalized_record_ids
    assert "task_decision" not in env.records


def test_binary_card_excludes_pre_16_publisher_initial_copy_exception() -> None:
    request = _sessions("16", "binary-initial-copy")[1].stages[1].documents[0].text
    assert "publisher is PostgreSQL 16 or newer" in request


@pytest.mark.parametrize("card_id", CARDS)
def test_withheld_source_breaks_constructed_decision(card_id: TaskCardId) -> None:
    for revision in ("16", "17"):
        first, second = _sessions(revision, card_id)
        survey = first.stages[0]
        withheld = tuple(
            replace(doc, text=f"[[doc:{doc.doc_id}]] withheld") for doc in survey.documents
        )
        first = replace(first, stages=(replace(survey, documents=withheld), *first.stages[1:]))
        record, env = _run((first, second))
        assert record.decisions == {"prior": True, "later": False}
        assert env.records["decision-receipt"]["verdict"] == "pass"
        assert env.records["task_decision"]["plan"] not in (
            "stage-disconnected",
            "use-text-copy",
        )


def test_unknown_card_and_revision_fail_closed() -> None:
    with pytest.raises(ValueError, match="unsupported PostgreSQL task card"):
        build_postgresql_task_card_sessions(_source_root("16"), revision="16", card_id="bogus")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported PostgreSQL source revision"):
        build_postgresql_task_card_sessions(_source_root("16"), revision="18", card_id=CARDS[0])
