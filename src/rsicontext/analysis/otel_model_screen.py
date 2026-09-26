"""Offline fake-worker controls for the OTel source-contrast reader policy.

This tests the sequence wiring and interventions, not model difficulty.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.otel_model_fixed import otel_model_fixed_policy_text
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

_CANDIDATES = ("db.statement", "db.query.text")


class FakeAttributeWorker:
    """Deterministic source-content test double, without revision metadata."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.replies: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("Read the complete upstream database client span convention"):
            rows = [line for line in prompt.splitlines() if line.startswith("|")]
            found = [
                field
                for field in _CANDIDATES
                if any(
                    f"`{field}`" in row
                    and "Recommended" in row
                    and ("database statement" in row or "database query" in row)
                    for row in rows
                )
            ]
            answer = "attribute=" + found[0] if len(found) == 1 else "invalid"
        elif prompt.startswith("Use only the retained upstream attribute"):
            retained = prompt.split("Retained attribute:\n", 1)[1].split(
                "\n\nProject request:\n", 1
            )[0]
            answer = "plan=" + retained.removeprefix("attribute=")
        else:
            raise ValueError("unexpected worker prompt")
        self.replies.append(answer)
        return answer


class _RereadRegistry(DocumentRegistry):
    def __init__(self, *, allow_source: bool) -> None:
        super().__init__()
        self.allow_source = allow_source

    def get(self, doc_id: str) -> DocumentRef | None:
        if doc_id == "upstream-db" and not self.allow_source:
            return None
        return super().get(doc_id)


@dataclass
class ScreenCase:
    name: str
    record: SequenceRecord
    env: ProjectState
    worker: FakeAttributeWorker
    source_sha256: str
    license_sha256: str

    def summary(self) -> dict[str, object]:
        transcript = [
            entry for session in self.record.sessions for entry in session.model_transcript
        ]
        prompts = self.worker.prompts
        if len(transcript) != len(prompts):
            raise RuntimeError("worker dispatch/transcript length mismatch")
        prompt_hashes = [hashlib.sha256(text.encode()).hexdigest() for text in prompts]
        if not all(
            entry["prompt_sha256"] == digest[:12]
            for entry, digest in zip(transcript, prompt_hashes, strict=True)
        ):
            raise RuntimeError("worker prompt hash/transcript mismatch")
        return {
            "case": self.name,
            "source_sha256": self.source_sha256,
            "license_sha256": self.license_sha256,
            "sessions_passed": [session.passed for session in self.record.sessions],
            "failures": [session.failures for session in self.record.sessions],
            "policy_errors": [session.policy_errors for session in self.record.sessions],
            "persist_ok": [session.persist_ok for session in self.record.sessions],
            "carry_bytes": [session.carry_bytes for session in self.record.sessions],
            "worker_dispatches": sum(session.model_calls for session in self.record.sessions),
            "worker_prompt_sha256": prompt_hashes,
            "worker_reply_sha256": [
                hashlib.sha256(text.encode()).hexdigest() for text in self.worker.replies
            ],
            "worker_prompt_utf8_bytes": [len(text.encode()) for text in prompts],
            "provider_usage": None,
            "final_plan": self.env.records.get("query_attribute_plan", {}).get("plan"),
            "action_kinds": [action.kind for action in self.env.transcript],
            "receipts": {
                key: {
                    "check": self.env.records[key].get("check"),
                    "subject": self.env.records[key].get("subject"),
                    "verdict": self.env.records[key].get("verdict"),
                }
                for key in ("review-receipt", "decision-receipt")
                if key in self.env.records
            },
        }


def run_case(
    name: str,
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    source_text: str | None = None,
    license_text: str | None = None,
    withhold_upstream: bool = False,
    clear_carry: bool = False,
    allow_reread: bool = True,
    prior_receipt_fails: bool = False,
    decision_receipt_fails: bool = False,
) -> ScreenCase:
    """Change one visible input or oracle while retaining the legal answer."""
    first, second = sessions
    survey = first.stages[0]
    if withhold_upstream:
        source_text = "[[doc:upstream-db]] withheld"
        license_text = "[[doc:upstream-license]] withheld"
    source = (
        replace(survey.documents[0], text=source_text)
        if source_text is not None
        else survey.documents[0]
    )
    license_doc = (
        replace(survey.documents[1], text=license_text)
        if license_text is not None
        else survey.documents[1]
    )
    first = replace(
        first, stages=(replace(survey, documents=(source, license_doc)), *first.stages[1:])
    )
    if prior_receipt_fails:
        stage = first.stages[1]
        first = replace(
            first,
            stages=(
                first.stages[0],
                replace(stage, verification_oracle={"review-complete": {"reviewed": False}}),
                *first.stages[2:],
            ),
        )
    if decision_receipt_fails:
        stage = second.stages[2]
        second = replace(
            second,
            stages=(
                *second.stages[:2],
                replace(
                    stage,
                    verification_oracle={
                        "plan-reviewed": {"db.statement": False, "db.query.text": False}
                    },
                ),
                *second.stages[3:],
            ),
        )
    worker = FakeAttributeWorker()
    env = ProjectState()
    budget = ToolBudget(max_calls=16)
    registry = _RereadRegistry(allow_source=allow_reread)
    factory_calls = 0
    policy = otel_model_fixed_policy_text()

    def factory(state: dict[str, object]) -> PolicyHook:
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls == 2 and clear_carry:
            state["carry"] = {}
        return PolicyHook(state, policy, tool_budget=budget, registry=registry, responder=worker)

    record = run_session_sequence(
        [first, second],
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    return ScreenCase(
        name,
        record,
        env,
        worker,
        hashlib.sha256(source.text.encode()).hexdigest(),
        hashlib.sha256(license_doc.text.encode()).hexdigest(),
    )


def run_screen(
    older: tuple[LifecycleInstance, LifecycleInstance],
    newer: tuple[LifecycleInstance, LifecycleInstance],
) -> dict[str, object]:
    """Run matched source, carry, and receipt interventions."""
    older_source, older_license = (doc.text for doc in older[0].stages[0].documents)
    newer_source, newer_license = (doc.text for doc in newer[0].stages[0].documents)
    specs: tuple[
        tuple[
            str,
            tuple[LifecycleInstance, LifecycleInstance],
            dict[str, Any],
            list[bool],
            str | None,
            int,
        ],
        ...,
    ] = (
        ("full-124", older, {}, [True, True], "db.statement", 2),
        ("full-143", newer, {}, [True, True], "db.query.text", 2),
        ("withheld-124", older, {"withhold_upstream": True}, [True, False], None, 0),
        ("withheld-143", newer, {"withhold_upstream": True}, [True, False], None, 0),
        (
            "swapped-124",
            older,
            {"source_text": newer_source, "license_text": newer_license},
            [True, False],
            "db.query.text",
            2,
        ),
        (
            "swapped-143",
            newer,
            {"source_text": older_source, "license_text": older_license},
            [True, False],
            "db.statement",
            2,
        ),
        (
            "empty-carry-no-reread-143",
            newer,
            {"clear_carry": True, "allow_reread": False},
            [True, False],
            None,
            1,
        ),
        ("empty-carry-reread-143", newer, {"clear_carry": True}, [True, True], "db.query.text", 3),
        (
            "prior-receipt-fails-143",
            newer,
            {"prior_receipt_fails": True},
            [False, False],
            "db.query.text",
            2,
        ),
        (
            "decision-receipt-fails-143",
            newer,
            {"decision_receipt_fails": True},
            [True, False],
            None,
            2,
        ),
    )
    cases = []
    for name, sessions, intervention, expected, expected_plan, expected_calls in specs:
        case = run_case(name, sessions, **intervention)
        observed = [session.passed for session in case.record.sessions]
        plan = case.env.records.get("query_attribute_plan", {}).get("plan")
        calls = sum(session.model_calls for session in case.record.sessions)
        if (observed, plan, calls) != (expected, expected_plan, expected_calls):
            raise RuntimeError(
                f"{name}: expected {(expected, expected_plan, expected_calls)}, "
                f"got {(observed, plan, calls)}; failures={case.record.failure_detail}"
            )
        if not all(session.persist_ok for session in case.record.sessions):
            raise RuntimeError(f"{name}: carry flush failed")
        if name in ("full-124", "full-143") and (
            sessions[0].stages[0].documents[0].text not in case.worker.prompts[0]
            or "project-request" in case.worker.prompts[0]
            or "project-request" not in case.worker.prompts[1]
            or case.record.sessions[0].final_carry != {"attribute": case.worker.replies[0]}
        ):
            raise RuntimeError(f"{name}: survey/request boundary not established")
        cases.append(case.summary())
    return {
        "status": "offline-structural-screen-passed",
        "worker": "deterministic-fake-attribute-v1",
        "provider_usage": None,
        "fixed_reader_difficulty": None,
        "policy_sha256": hashlib.sha256(otel_model_fixed_policy_text().encode()).hexdigest(),
        "screen_case_count": len(cases),
        "cases": cases,
    }


__all__ = ["FakeAttributeWorker", "ScreenCase", "run_case", "run_screen"]
