"""Offline source and action controls for the OTel DBMS system card."""

from __future__ import annotations

import os
from dataclasses import fields, replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_otel_task_cards import (
    SYSTEM_KEYS,
    SYSTEM_ROW,
    build_otel_dbms_system_card_sessions,
    system_row_sha256,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageView, _build_stage_view
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

_SOURCE_ENV = {
    "1.24": "RSICONTEXT_OTEL124_SOURCE_ROOT",
    "1.43": "RSICONTEXT_OTEL_SOURCE_ROOT",
}

_POLICY = """
import re


def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        source = turn.view.documents[0].text
        rows = [row for row in source.splitlines() if row.startswith("|")]
        matches = []
        for row in rows:
            match = re.search(r"\\[`(db[.]system(?:[.]name)?)`\\]", row)
            if match and "Required" in row:
                matches.append(match.group(1))
        chosen = matches[0] if len(matches) == 1 else None
        state["carry"] = {"chosen": chosen} if KEEP_CARRY else {}
        return {"pack_text": "[[doc:upstream-db]] source inspected"}
    if stage == "review-source":
        phase = state.get("review_phase", 0)
        if phase == 0:
            state["review_phase"] = 1
            return {"pack_text": "request review", "actions": (
                turn.actions.request_verification("review-receipt", "review-complete", "reviewed"),
            )}
        if phase == 1 and not SKIP_FIRST:
            state["review_phase"] = 2
            return {"pack_text": "commit review", "actions": (
                turn.actions.create_record("convention_review", {"plan": "reviewed"}),
                turn.actions.finalize("convention_review", {"plan": "reviewed", "status": "final"},
                                      ("review-receipt",)),
            )}
    if stage == "decide-attribute":
        plan = state.get("carry", {}).get("chosen") if SOURCE_AWARE else FIXED_PLAN
        if plan is None:
            return {"pack_text": "no source key"}
        phase = state.get("decision_phase", 0)
        if phase == 0:
            state["decision_phase"] = 1
            return {"pack_text": "request plan review", "actions": (
                turn.actions.request_verification("decision-receipt", "plan-reviewed", plan),
            )}
        if phase == 1:
            state["decision_phase"] = 2
            return {"pack_text": "commit plan", "actions": (
                turn.actions.create_record("dbms_system_plan", {"plan": plan}),
                turn.actions.finalize("dbms_system_plan", {"plan": plan, "status": "final"},
                                      ("decision-receipt",)),
            )}
    return {"pack_text": "observed"}
"""


def _root(revision: str) -> Path:
    configured = os.environ.get(_SOURCE_ENV[revision])
    if not configured:
        pytest.skip(f"set {_SOURCE_ENV[revision]} to the pinned detached checkout")
    return Path(configured)


def _sessions(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    return build_otel_dbms_system_card_sessions(_root(revision), revision=revision)


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    source_aware: bool = True,
    fixed_plan: str = "db.system.name",
    keep_carry: bool = True,
    skip_first: bool = False,
) -> tuple[list[bool], ProjectState]:
    env = ProjectState()
    budget = ToolBudget(max_calls=20)
    registry = DocumentRegistry()
    policy = (
        f"SOURCE_AWARE = {source_aware!r}\n"
        f"FIXED_PLAN = {fixed_plan!r}\n"
        f"KEEP_CARRY = {keep_carry!r}\n"
        f"SKIP_FIRST = {skip_first!r}\n" + _POLICY
    )

    def factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(state, policy, tool_budget=budget, registry=registry)

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    assert not any(session.policy_errors for session in record.sessions)
    return [session.passed for session in record.sessions], env


def _without_source(view: StageView) -> dict[str, object]:
    projection = {field.name: getattr(view, field.name) for field in fields(StageView)}
    projection["documents"] = tuple(
        replace(doc, text="<pinned source bytes>") if doc.doc_id.startswith("upstream-") else doc
        for doc in view.documents
    )
    return projection


def test_matched_views_hide_legal_key_and_preserve_source_row_identity() -> None:
    older, newer = _sessions("1.24"), _sessions("1.43")
    for revision in ("1.24", "1.43"):
        assert system_row_sha256(_root(revision), revision=revision) == SYSTEM_ROW[revision][1]
    for old_session, new_session in zip(older, newer, strict=True):
        for index, (old_stage, new_stage) in enumerate(
            zip(old_session.stages, new_session.stages, strict=True)
        ):
            old_view = _build_stage_view(
                old_stage, old_session.axes, remaining=len(old_session.stages) - index
            )
            new_view = _build_stage_view(
                new_stage, new_session.axes, remaining=len(new_session.stages) - index
            )
            assert _without_source(old_view) == _without_source(new_view)
    request = older[1].stages[1].documents[0].text
    assert all(key not in request for key in SYSTEM_KEYS.values())
    assert older[1].stages[2].commit_precondition != newer[1].stages[2].commit_precondition
    assert older[1].stages[2].verification_oracle == newer[1].stages[2].verification_oracle


def test_source_aware_offline_policy_completes_both_with_opposite_keys() -> None:
    outcomes = []
    for revision in ("1.24", "1.43"):
        passed, env = _run(_sessions(revision))
        outcomes.append((passed, env.records["dbms_system_plan"]["plan"]))
    assert outcomes == [([True, True], "db.system"), ([True, True], "db.system.name")]


@pytest.mark.parametrize("fixed", ["db.system", "db.system.name"])
def test_source_free_fixed_key_fails_one_revision(fixed: str) -> None:
    outcomes = [
        _run(_sessions(revision), source_aware=False, fixed_plan=fixed)[0][1]
        for revision in ("1.24", "1.43")
    ]
    assert outcomes == [fixed == SYSTEM_KEYS["1.24"], fixed == SYSTEM_KEYS["1.43"]]


def test_source_swap_changes_action_but_fails_original_oracle() -> None:
    for original, substitute in (("1.24", "1.43"), ("1.43", "1.24")):
        first, second = _sessions(original)
        substitute_first, _ = _sessions(substitute)
        survey = first.stages[0]
        swapped = replace(survey.documents[0], text=substitute_first.stages[0].documents[0].text)
        first = replace(
            first,
            stages=(replace(survey, documents=(swapped, survey.documents[1])), *first.stages[1:]),
        )
        passed, env = _run((first, second))
        assert passed == [True, False]
        assert env.records["dbms_system_plan"]["plan"] == SYSTEM_KEYS[substitute]


def test_withheld_source_missing_carry_or_prior_commit_breaks_sequence() -> None:
    first, second = _sessions("1.43")
    survey = first.stages[0]
    withheld = tuple(
        replace(doc, text=f"[[doc:{doc.doc_id}]] withheld") for doc in survey.documents
    )
    first = replace(first, stages=(replace(survey, documents=withheld), *first.stages[1:]))
    assert _run((first, second))[0] == [True, False]
    assert _run(_sessions("1.43"), keep_carry=False)[0] == [True, False]
    assert _run(_sessions("1.43"), skip_first=True)[0] == [False, False]


def test_rejects_unknown_revision_and_changed_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported OpenTelemetry source revision"):
        build_otel_dbms_system_card_sessions(_root("1.24"), revision="unknown")
    with pytest.raises(ValueError, match="unsupported OpenTelemetry source revision"):
        system_row_sha256(_root("1.24"), revision="unknown")
    source = _root("1.24")
    for relative in ("docs/database/database-spans.md", "LICENSE"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((source / relative).read_bytes())
    target = tmp_path / "docs/database/database-spans.md"
    lines = target.read_bytes().splitlines(keepends=True)
    lines[67] = lines[67].replace(b"Required |", b"Optional |")
    target.write_bytes(b"".join(lines))
    with pytest.raises(ValueError, match="pinned OpenTelemetry DBMS row mismatch"):
        system_row_sha256(tmp_path, revision="1.24")
    with pytest.raises(ValueError, match="pinned OpenTelemetry source mismatch"):
        build_otel_dbms_system_card_sessions(tmp_path, revision="1.24")
