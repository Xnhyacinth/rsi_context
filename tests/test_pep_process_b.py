"""PEP 1 B development world: two legal status paths and causal probes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_pep_process_b import (
    SOURCE_RELATIVE,
    SOURCE_REVISION,
    SOURCE_SHA256,
    build_pep_process_b_sessions,
)
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget, ToolSurface

Status = Literal["accepted", "provisional"]
_NEXT = {
    "accepted": "complete-reference-implementation",
    "provisional": "collect-interface-feedback",
}
_RULE_ACCEPTED = "Once a PEP has been accepted, the reference implementation must be completed."
_RULE_ACCEPTED_REPEAT = (
    'The reference implementation must be completed before any PEP is given status "Final"'
)
_RULE_PROVISIONAL = "additional user feedback is needed"
_RULE_PROVISIONAL_INTRO = "To allow gathering of additional design and interface feedback"
_RULE_PROVISIONAL_REPEAT = (
    "If changes based on implementation experience and user feedback are made to "
    "Standards track PEPs while in the Provisional"
)


@pytest.fixture(scope="module")
def source_root() -> Path:
    configured = os.environ.get("RSICONTEXT_PEP_SOURCE_ROOT")
    if configured is None:
        pytest.skip("set RSICONTEXT_PEP_SOURCE_ROOT to the pinned detached checkout")
    root = Path(configured)
    if not root.is_dir():
        pytest.fail(f"configured PEP checkout is missing: {root}")
    return root


def _rules(text: str) -> dict[str, bool]:
    flat = " ".join(text.split())
    return {
        "accepted": _RULE_ACCEPTED in flat or _RULE_ACCEPTED_REPEAT in flat,
        "provisional": any(
            phrase in flat
            for phrase in (_RULE_PROVISIONAL, _RULE_PROVISIONAL_INTRO, _RULE_PROVISIONAL_REPEAT)
        ),
    }


class _Reference:
    """A view-only witness with fresh per-session state and optional metered reread."""

    def __init__(
        self,
        state: dict[str, object],
        *,
        choice: Status | None,
        env: ProjectState,
        budget: ToolBudget,
        registry: DocumentRegistry,
        keep_carry: bool,
        reread_on_resume: bool,
        force_first: bool,
        wrong_next: bool,
    ) -> None:
        self.state = state
        self.choice = choice
        self.env = env
        self.budget = budget
        self.registry = registry
        self.keep_carry = keep_carry
        self.reread_on_resume = reread_on_resume
        self.force_first = force_first
        self.wrong_next = wrong_next
        self.requested: set[str] = set()
        self.views: list[StageView] = []
        self.initial_state = json.loads(json.dumps(state))

    def _tool_surface(self, stage: StageView) -> ToolSurface:
        return ToolSurface(
            documents=stage.documents,
            env=self.env,
            budget=self.budget,
            registry=self.registry,
        )

    def on_stage(self, stage: StageView) -> StageResponse:
        self.views.append(stage)
        state = self.state
        if stage.stage_id == "pep-process-review":
            text = "\n".join(doc.text for doc in stage.documents)
            state["working_rules"] = _rules(text)
        elif stage.stage_id == "mock-status-charter":
            state["charter"] = any(
                "permits either of two simulated status paths" in doc.text
                for doc in stage.documents
            )
        elif stage.stage_id == "pep-status-decision":
            if not state.get("charter") or self.choice is None:
                return StageResponse("No authorized status")
            if "status-v" not in self.requested:
                self.requested.add("status-v")
                return StageResponse(
                    "Request mock status clearance",
                    (
                        Action(
                            "request_verification",
                            "status-v",
                            {"check": "status-clearance", "subject": self.choice},
                        ),
                    ),
                )
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if self.force_first or (
                "status-v" in receipts and receipts["status-v"].verdict == "pass"
            ):
                state["chosen_status"] = self.choice
                return StageResponse(
                    "Finalize simulated status",
                    (
                        Action("create_record", "status_decision", {"plan": self.choice}),
                        Action("finalize", "status_decision", {"status": "final"}, ("status-v",)),
                    ),
                )
        elif stage.stage_id == "pep-s1-end":
            if self.keep_carry:
                state["carry"] = {
                    "chosen_status": state.get("chosen_status"),
                    "rules": state.get("working_rules"),
                }
            else:
                state["carry"] = {}
        elif stage.stage_id == "pep-s2-start" and self.reread_on_resume:
            surface = self._tool_surface(stage)
            source = surface.reread("pep1-process-full")
            prior = surface.query_sandbox("status_decision")
            if source.ok and prior.ok:
                state["recovered_rules"] = _rules(source.answer)
                for candidate_status in ("accepted", "provisional"):
                    if f"'plan': '{candidate_status}'" in prior.answer:
                        state["recovered_status"] = candidate_status
        elif stage.stage_id == "pep-next-step-request":
            state["request_seen"] = any(
                "complete-reference-implementation" in doc.text
                and "collect-interface-feedback" in doc.text
                for doc in stage.documents
            )
        elif stage.stage_id == "pep-next-step-decision":
            carry = state.get("carry")
            carried = carry if isinstance(carry, dict) else {}
            status = carried.get("chosen_status") or state.get("recovered_status")
            rules = carried.get("rules") or state.get("recovered_rules")
            if (
                not state.get("request_seen")
                or not isinstance(status, str)
                or status not in _NEXT
                or not isinstance(rules, dict)
                or rules.get(status) is not True
            ):
                return StageResponse("No source-grounded next action")
            plan = _NEXT[status]
            if self.wrong_next:
                plan = _NEXT["provisional" if status == "accepted" else "accepted"]
            if "next-v" not in self.requested:
                self.requested.add("next-v")
                return StageResponse(
                    "Request mock next-step clearance",
                    (
                        Action(
                            "request_verification",
                            "next-v",
                            {"check": "next-step-clearance", "subject": plan},
                        ),
                    ),
                )
            receipts = {receipt.record_id: receipt for receipt in stage.receipts}
            if "next-v" in receipts and receipts["next-v"].verdict == "pass":
                return StageResponse(
                    "Finalize status-specific next action",
                    (
                        Action("create_record", "next_step_plan", {"plan": plan}),
                        Action("finalize", "next_step_plan", {"status": "final"}, ("next-v",)),
                    ),
                )
        return StageResponse("No action")


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    choice: Status,
    keep_carry: bool = True,
    reread_on_resume: bool = False,
    force_first: bool = False,
    wrong_next: bool = False,
) -> tuple[SequenceRecord, ProjectState, ToolBudget, list[_Reference]]:
    env = ProjectState()
    budget = ToolBudget(max_calls=8)
    registry = DocumentRegistry()
    witnesses: list[_Reference] = []

    def factory(state: dict[str, object]) -> _Reference:
        witness = _Reference(
            state,
            choice=choice if not witnesses else None,
            env=env,
            budget=budget,
            registry=registry,
            keep_carry=keep_carry,
            reread_on_resume=reread_on_resume,
            force_first=force_first,
            wrong_next=wrong_next,
        )
        witnesses.append(witness)
        return witness

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    return record, env, budget, witnesses


@pytest.mark.parametrize("choice", ["accepted", "provisional"])
def test_two_legal_prior_statuses_induce_different_later_actions(
    source_root: Path, choice: Status
) -> None:
    sessions = build_pep_process_b_sessions(source_root)
    record, env, _budget, witnesses = _run(sessions, choice=choice)
    assert [session.passed for session in record.sessions] == [True, True], record.to_dict()
    assert env.records["status_decision"]["plan"] == choice
    assert env.records["next_step_plan"]["plan"] == _NEXT[choice]
    assert env.records["status-v"]["verdict"] == "pass"
    assert env.records["next-v"]["verdict"] == "pass"
    actions = list(env.transcript)
    assert next(i for i, action in enumerate(actions) if action.record_id == "status-v") < next(
        i
        for i, action in enumerate(actions)
        if action.kind == "finalize" and action.record_id == "status_decision"
    )
    assert witnesses[0] is not witnesses[1]
    assert witnesses[1].choice is None
    assert witnesses[1].initial_state == {
        "carry": {"chosen_status": choice, "rules": {"accepted": True, "provisional": True}}
    }
    assert not witnesses[1].views[0].documents
    assert all(
        not hasattr(view, "commit_precondition") for witness in witnesses for view in witness.views
    )


@pytest.mark.parametrize("choice", ["accepted", "provisional"])
def test_prior_action_changes_later_legal_answer(source_root: Path, choice: Status) -> None:
    sessions = build_pep_process_b_sessions(source_root)
    record, env, _budget, _witnesses = _run(sessions, choice=choice, wrong_next=True)
    assert [session.passed for session in record.sessions] == [True, False]
    assert env.records["next-v"]["verdict"] == "pass"
    assert env.records["next_step_plan"]["plan"] != _NEXT[choice]
    assert any("prior plan" in failure for failure in record.sessions[1].failures)


@pytest.mark.parametrize("choice", ["accepted", "provisional"])
def test_failed_prior_receipt_blocks_later_action_even_if_forced(
    source_root: Path, choice: Status
) -> None:
    first, second = build_pep_process_b_sessions(source_root)
    award = first.stages[2]
    changed = replace(award, verification_oracle={"status-clearance": {choice: False}})
    first = replace(first, stages=(*first.stages[:2], changed, *first.stages[3:]))
    record, env, _budget, _witnesses = _run((first, second), choice=choice, force_first=True)
    assert [session.passed for session in record.sessions] == [False, False]
    assert env.records["status-v"]["verdict"] == "fail"
    assert "status_decision" in env.finalized_record_ids
    assert any("environment-issued PASS" in failure for failure in record.sessions[1].failures)


@pytest.mark.parametrize("choice", ["accepted", "provisional"])
def test_deleting_only_the_relevant_source_rule_breaks_that_route(
    source_root: Path, choice: Status
) -> None:
    first, second = build_pep_process_b_sessions(source_root)
    survey = first.stages[0]
    source = survey.documents[0]
    # Remove all supporting occurrences for the chosen route. The frozen
    # evaluator gate is not edited to follow the policy's failed reading.
    changed_text = source.text
    if choice == "accepted":
        for target in (_RULE_ACCEPTED, _RULE_ACCEPTED_REPEAT):
            pattern = r"\s+".join(re.escape(word) for word in target.split())
            changed_text, removed_count = re.subn(pattern, "[removed]", changed_text)
            assert removed_count == 1
    else:
        # PEP 1 has a status paragraph and a later maintenance paragraph
        # that both mention feedback while Provisional.
        for start, end in (
            (_RULE_PROVISIONAL_INTRO, "included in a Python release*."),
            (
                "If changes based on implementation experience and user feedback are made to",
                "at the point where it is marked Final.",
            ),
        ):
            pattern = re.escape(start) + r".*?" + re.escape(end)
            changed_text, removed_count = re.subn(
                pattern, "[removed]", changed_text, count=1, flags=re.DOTALL
            )
            assert removed_count == 1
    changed_survey = replace(survey, documents=(replace(source, text=changed_text),))
    first = replace(first, stages=(changed_survey, *first.stages[1:]))
    record, _env, _budget, _witnesses = _run((first, second), choice=choice)
    assert [session.passed for session in record.sessions] == [True, False]
    other: Status = "provisional" if choice == "accepted" else "accepted"
    control, _env, _budget, _witnesses = _run((first, second), choice=other)
    assert [session.passed for session in control.sessions] == [True, True]


def test_one_of_two_accepted_source_spans_is_not_a_decisive_deletion(
    source_root: Path,
) -> None:
    first, second = build_pep_process_b_sessions(source_root)
    survey = first.stages[0]
    source = survey.documents[0]
    pattern = r"\s+".join(re.escape(word) for word in _RULE_ACCEPTED.split())
    changed_text, removed_count = re.subn(pattern, "[removed]", source.text)
    assert removed_count == 1
    changed = replace(survey, documents=(replace(source, text=changed_text),))
    first = replace(first, stages=(changed, *first.stages[1:]))
    record, _env, _budget, _witnesses = _run((first, second), choice="accepted")
    assert [session.passed for session in record.sessions] == [True, True]


def test_no_carry_requires_metered_reread_and_sandbox_query(source_root: Path) -> None:
    sessions = build_pep_process_b_sessions(source_root)
    missing, _env, missing_budget, _ = _run(sessions, choice="accepted", keep_carry=False)
    assert [session.passed for session in missing.sessions] == [True, False]
    recovered, env, budget, witnesses = _run(
        sessions, choice="accepted", keep_carry=False, reread_on_resume=True
    )
    assert [session.passed for session in recovered.sessions] == [True, True]
    assert env.records["next_step_plan"]["plan"] == _NEXT["accepted"]
    assert witnesses[1].initial_state == {"carry": {}}
    assert budget.calls == missing_budget.calls + 2
    assert [
        receipt.tool for receipt in budget.receipts if receipt.tool in ("reread", "query_sandbox")
    ] == ["reread", "query_sandbox"]


def test_irrelevant_material_leaves_both_legal_vectors(source_root: Path) -> None:
    first, second = build_pep_process_b_sessions(source_root)
    survey = first.stages[0]
    note = DocumentRef(
        "office-note",
        "Office note",
        "[[doc:office-note]] The meeting-room projector is unavailable.",
        source_url="benchmark:constructed/irrelevant-note",
        retrieved_date="2026-09-26",
    )
    first = replace(
        first, stages=(replace(survey, documents=(*survey.documents, note)), *first.stages[1:])
    )
    for choice in ("accepted", "provisional"):
        record, env, _budget, _ = _run((first, second), choice=choice)
        assert [session.passed for session in record.sessions] == [True, True]
        assert env.records["next_step_plan"]["plan"] == _NEXT[choice]


def test_pinned_source_and_manifest_match(source_root: Path) -> None:
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256
    sessions = build_pep_process_b_sessions(source_root)
    source = sessions[0].stages[0].documents[0]
    assert source.text.split("\n", 1)[1].encode("utf-8") == raw
    assert SOURCE_REVISION in source.source_url
    manifest = json.loads(
        (
            Path(__file__).resolve().parent.parent / "configs/r7_pep_source_manifest_v1.json"
        ).read_text()
    )
    assert manifest["source_revision"] == SOURCE_REVISION
    assert manifest["selected_files"][SOURCE_RELATIVE]["sha256"] == SOURCE_SHA256


def test_source_byte_drift_rejected_before_world_construction(tmp_path: Path) -> None:
    target = tmp_path / SOURCE_RELATIVE
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not the pinned PEP 1")
    with pytest.raises(ValueError, match="pinned PEP 1 source mismatch"):
        build_pep_process_b_sessions(tmp_path)


def test_world_pair_has_frozen_serialization(source_root: Path) -> None:
    sessions = build_pep_process_b_sessions(source_root)
    raw = json.dumps(
        [session.to_dict() for session in sessions],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assert hashlib.sha256(raw).hexdigest() == (
        "a8fbe631ad500db24930ceac99812b4a97406a1f8e5b42575eaaeee432bdd6f9"
    )
