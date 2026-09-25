"""Offline, fake-worker causal screen for the PostgreSQL source pair.

Every intervention runs the same policy through the real sequence runner.
The responder models a deterministic text extraction interface only; these
results are not a fixed-reader score or provider token accounting.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from typing import Any

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.postgresql_model_fixed import postgresql_model_fixed_policy_text
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

_TERMS = re.compile(r"<term><literal>([a-z_]+)</literal> \(<type>")
_FAILOVER_SPAN = re.compile(
    r'\s*<varlistentry id="sql-createsubscription-params-with-failover">.*?</varlistentry>',
    re.DOTALL,
)


class FakeCatalogWorker:
    """Test double that responds to prompt content, never revision metadata."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.replies: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("Read the complete upstream CREATE SUBSCRIPTION SGML below."):
            names = list(dict.fromkeys(_TERMS.findall(prompt)))
            answer = "parameters=" + ",".join(names)
        elif prompt.startswith("Use ONLY the retained upstream parameter catalog"):
            retained = prompt.split("Retained catalog:\n", 1)[1].split("\n\nProject request:\n", 1)[
                0
            ]
            request = prompt.split("\n\nProject request:\n", 1)[1]
            catalog_names = set(retained.removeprefix("parameters=").split(","))
            answer = (
                "plan=configure-native"
                if "failover" in catalog_names and "WITH (failover = true)" in request
                else "plan=defer-native"
            )
        else:
            raise ValueError("unexpected worker prompt")
        self.replies.append(answer)
        return answer


class _RereadRegistry(DocumentRegistry):
    def __init__(self, *, allow_source: bool) -> None:
        super().__init__()
        self.allow_source = allow_source

    def get(self, doc_id: str) -> DocumentRef | None:
        if doc_id == "upstream-create-subscription" and not self.allow_source:
            return None
        return super().get(doc_id)


@dataclass
class ScreenCase:
    name: str
    record: SequenceRecord
    env: ProjectState
    worker: FakeCatalogWorker
    material_sha256: str
    notice_sha256: str

    def summary(self) -> dict[str, object]:
        transcript = [
            entry for session in self.record.sessions for entry in session.model_transcript
        ]
        if len(transcript) != len(self.worker.prompts):
            raise RuntimeError("worker dispatch/transcript length mismatch")
        prompt_hashes = [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in self.worker.prompts
        ]
        if not all(
            entry["prompt_sha256"] == full_hash[:12]
            for entry, full_hash in zip(transcript, prompt_hashes, strict=True)
        ):
            raise RuntimeError("worker prompt hash/transcript mismatch")
        return {
            "case": self.name,
            "material_sha256": self.material_sha256,
            "notice_sha256": self.notice_sha256,
            "sessions_passed": [session.passed for session in self.record.sessions],
            "failures": [session.failures for session in self.record.sessions],
            "policy_errors": [session.policy_errors for session in self.record.sessions],
            "persist_ok": [session.persist_ok for session in self.record.sessions],
            "carry_bytes": [session.carry_bytes for session in self.record.sessions],
            "worker_dispatches": sum(session.model_calls for session in self.record.sessions),
            "worker_dispatches_by_session": [
                session.model_calls for session in self.record.sessions
            ],
            "worker_stage_ids": [entry["stage_id"] for entry in transcript],
            "worker_prompt_sha256": prompt_hashes,
            "worker_reply_sha256": [
                hashlib.sha256(text.encode("utf-8")).hexdigest() for text in self.worker.replies
            ],
            "worker_prompt_utf8_bytes": [len(text.encode("utf-8")) for text in self.worker.prompts],
            "local_whitespace_estimates_only": self.record.cost(),
            "final_plan": self.env.records.get("native_capability_decision", {}).get("plan"),
            "action_kinds": [action.kind for action in self.env.transcript],
            "receipts": {
                key: {
                    "check": self.env.records[key].get("check"),
                    "subject": self.env.records[key].get("subject"),
                    "verdict": self.env.records[key].get("verdict"),
                }
                for key in ("source-review-receipt", "decision-review-receipt")
                if key in self.env.records
            },
        }


def _change_source(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    source_text: str | None,
    notice_text: str | None,
) -> tuple[LifecycleInstance, LifecycleInstance]:
    first, second = sessions
    survey = first.stages[0]
    doc = (
        replace(survey.documents[0], text=source_text)
        if source_text is not None
        else survey.documents[0]
    )
    notice = (
        replace(survey.documents[1], text=notice_text)
        if notice_text is not None
        else survey.documents[1]
    )
    changed = replace(first, stages=(replace(survey, documents=(doc, notice)), *first.stages[1:]))
    return changed, second


def without_decisive_span(text: str) -> str:
    """A separately hashed constructed ablation of the 17.0 SGML."""

    changed, count = _FAILOVER_SPAN.subn("", text, count=1)
    if count != 1:
        raise ValueError("expected exactly one decisive failover parameter span")
    return changed


def run_case(
    name: str,
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    source_text: str | None = None,
    notice_text: str | None = None,
    withhold_upstream: bool = False,
    clear_carry: bool = False,
    allow_reread: bool = True,
    prior_receipt_fails: bool = False,
    decision_receipt_fails: bool = False,
) -> ScreenCase:
    """Run one intervention without changing the policy or legal answer."""

    if withhold_upstream:
        source_text = "[[doc:upstream-create-subscription]] withheld"
        notice_text = "[[doc:upstream-notice]] withheld"
    if source_text is not None or notice_text is not None:
        sessions = _change_source(sessions, source_text, notice_text)
    first, second = sessions
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
                        "decision-reviewed": {"configure-native": False, "defer-native": False}
                    },
                ),
                *second.stages[3:],
            ),
        )
    sessions = first, second
    worker = FakeCatalogWorker()
    env = ProjectState()
    budget = ToolBudget(max_calls=16)
    registry = _RereadRegistry(allow_source=allow_reread)
    policy = postgresql_model_fixed_policy_text()
    factory_calls = 0

    def factory(state: dict[str, object]) -> PolicyHook:
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls == 2 and clear_carry:
            state["carry"] = {}
        return PolicyHook(state, policy, tool_budget=budget, registry=registry, responder=worker)

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
        decision_rules=lambda result, _sessions: result.decisions.update(
            prior=result.sessions[0].passed, later=result.sessions[1].passed
        ),
    )
    material = first.stages[0].documents[0].text
    notice = first.stages[0].documents[1].text
    return ScreenCase(
        name,
        record,
        env,
        worker,
        hashlib.sha256(material.encode("utf-8")).hexdigest(),
        hashlib.sha256(notice.encode("utf-8")).hexdigest(),
    )


def run_screen(
    older: tuple[LifecycleInstance, LifecycleInstance],
    newer: tuple[LifecycleInstance, LifecycleInstance],
) -> dict[str, object]:
    """Stop on the first violated structural expectation; return evidence."""

    older_source = older[0].stages[0].documents[0].text
    newer_source = newer[0].stages[0].documents[0].text
    older_notice = older[0].stages[0].documents[1].text
    newer_notice = newer[0].stages[0].documents[1].text
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
        ("full-16", older, {}, [True, True], "defer-native", 2),
        ("full-17", newer, {}, [True, True], "configure-native", 2),
        ("withheld-16", older, {"withhold_upstream": True}, [True, False], None, 0),
        ("withheld-17", newer, {"withhold_upstream": True}, [True, False], None, 0),
        (
            "swapped-16",
            older,
            {"source_text": newer_source, "notice_text": newer_notice},
            [True, False],
            "configure-native",
            2,
        ),
        (
            "swapped-17",
            newer,
            {"source_text": older_source, "notice_text": older_notice},
            [True, False],
            "defer-native",
            2,
        ),
        (
            "decisive-span-removed-17",
            newer,
            {"source_text": without_decisive_span(newer_source)},
            [True, False],
            "defer-native",
            2,
        ),
        (
            "empty-carry-no-reread-17",
            newer,
            {"clear_carry": True, "allow_reread": False},
            [True, False],
            None,
            1,
        ),
        (
            "empty-carry-reread-17",
            newer,
            {"clear_carry": True},
            [True, True],
            "configure-native",
            3,
        ),
        (
            "prior-receipt-fails-17",
            newer,
            {"prior_receipt_fails": True},
            [False, False],
            "configure-native",
            2,
        ),
        (
            "decision-receipt-fails-17",
            newer,
            {"decision_receipt_fails": True},
            [True, False],
            None,
            2,
        ),
    )
    cases = []
    for name, sessions, kwargs, expected, expected_plan, expected_calls in specs:
        case = run_case(name, sessions, **kwargs)
        observed = [session.passed for session in case.record.sessions]
        plan = case.env.records.get("native_capability_decision", {}).get("plan")
        calls = sum(session.model_calls for session in case.record.sessions)
        if observed != expected or plan != expected_plan or calls != expected_calls:
            raise RuntimeError(
                f"{name}: expected {(expected, expected_plan, expected_calls)}, "
                f"got {(observed, plan, calls)}; failures={case.record.failure_detail}"
            )
        if not all(session.persist_ok for session in case.record.sessions):
            raise RuntimeError(f"{name}: carry flush failed")
        if name in ("full-16", "full-17", "empty-carry-reread-17") and any(
            session.policy_errors for session in case.record.sessions
        ):
            raise RuntimeError(f"{name}: unexpected policy errors")
        if name in ("full-16", "full-17"):
            source = sessions[0].stages[0].documents[0].text
            if (
                source not in case.worker.prompts[0]
                or "project-request" in case.worker.prompts[0]
                or "project-request" not in case.worker.prompts[1]
                or case.record.sessions[0].final_carry
                != {"parameter_catalog": case.worker.replies[0]}
            ):
                raise RuntimeError(f"{name}: survey/request boundary not established")
        cases.append(case.summary())
    policy = postgresql_model_fixed_policy_text()
    return {
        "status": "offline-structural-screen-passed",
        "worker": "deterministic-fake-catalog-v1",
        "provider_usage": None,
        "fixed_reader_difficulty": None,
        "policy_sha256": hashlib.sha256(policy.encode("utf-8")).hexdigest(),
        "screen_case_count": len(cases),
        "cases": cases,
    }


__all__ = ["FakeCatalogWorker", "ScreenCase", "run_case", "run_screen", "without_decisive_span"]
