"""Development intake for two matched PostgreSQL source-decision cards.

The upstream SGML and COPYRIGHT are pinned bytes. Requests, actions, and
receipts are constructed sandbox state, not PostgreSQL execution evidence.
Both revisions support the same legal action for each card; these cards do
not provide a version-flip or a qualified difficulty result.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

from rsicontext.lifecycle.material_postgresql_source_contrast import (
    build_postgresql_source_contrast_sessions,
)
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance

TaskCardId = Literal["connect-offline", "binary-initial-copy"]

_REQUESTS: dict[TaskCardId, str] = {
    "connect-offline": (
        "BENCHMARK SANDBOX ONLY. The publisher cannot be contacted during today's "
        "subscription setup; all other setup prerequisites are satisfied. "
        "An operator proposes CREATE SUBSCRIPTION with "
        "connect=false, create_slot=true, enabled=true, copy_data=true and expects "
        "an immediate initial copy. Choose plan=launch-with-copy if that command "
        "can initialize and copy now; otherwise choose plan=stage-disconnected, "
        "which creates a disconnected subscription and defers slot creation, "
        "enablement, and refresh until the publisher is available and the "
        "operator can complete those steps. Create and finalize the project-state "
        "record task_decision with the selected plan after requesting a "
        "decision-reviewed receipt. "
        "The receipt confirms local review, not database execution."
    ),
    "binary-initial-copy": (
        "BENCHMARK SANDBOX ONLY. Initial table synchronization is required. "
        "The publisher is PostgreSQL 16 or newer. "
        "The publisher has a binary send function for one published data type, "
        "but the subscriber lacks its binary receive function. Text input "
        "and output for that type are compatible on both sides, and all "
        "other replication prerequisites are satisfied. Choose "
        "plan=use-binary-copy if binary=true can complete this initial copy; "
        "otherwise choose plan=use-text-copy with binary=false. Create and "
        "finalize the project-state record task_decision with the selected plan "
        "after requesting a decision-reviewed receipt. "
        "The receipt confirms local review, not database execution."
    ),
}
_PLANS: dict[TaskCardId, tuple[str, str]] = {
    "connect-offline": ("stage-disconnected", "launch-with-copy"),
    "binary-initial-copy": ("use-text-copy", "use-binary-copy"),
}
_DECISION = "task_decision"


def build_postgresql_task_card_sessions(
    source_root: Path, *, revision: str, card_id: TaskCardId
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one source-identical-visible pair; the legal plan stays private."""

    if card_id not in _REQUESTS:
        raise ValueError(f"unsupported PostgreSQL task card: {card_id}")
    first, second = build_postgresql_source_contrast_sessions(source_root, revision=revision)
    legal, alternative = _PLANS[card_id]
    request = DocumentRef(
        doc_id="project-request",
        title="Constructed PostgreSQL project decision",
        text="[[doc:project-request]] Constructed PostgreSQL project decision\n"
        + _REQUESTS[card_id],
        source_url=f"benchmark:constructed/postgresql-{card_id}-v1",
        retrieved_date="2026-09-26",
    )
    request_stage = replace(
        second.stages[1],
        prompt_text="Apply the constructed project request to the supplied upstream source.",
        documents=(request,),
    )
    decision_stage = replace(
        second.stages[2],
        stage_id="decide-task",
        prompt_text="Commit the source-grounded project decision with current review evidence.",
        expected_state_delta={_DECISION: {"status": "final"}},
        commit_precondition={
            "record_id": _DECISION,
            "prior_finalized_record": "source_review",
            "prior_verification": {
                "check": "review-complete",
                "plan_field": "plan",
                "allowed_later_plans": {"reviewed": [legal, alternative]},
            },
            "plan_field": "plan",
            "legal_plans": [legal],
            "plan_requirements": {
                legal: {"requires_check": "decision-reviewed"},
                alternative: {"requires_check": "decision-reviewed"},
            },
        },
        verification_oracle={"decision-reviewed": {legal: True, alternative: True}},
    )
    first = replace(
        first,
        instance_id=f"research-v5-pg-{card_id}-s1-dev-0001",
        answer_norm=f"postgresql-{card_id}-decision",
        sandbox_spec={
            "records": ["source_review", _DECISION],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = replace(
        second,
        instance_id=f"research-v5-pg-{card_id}-s2-dev-0001",
        stages=(second.stages[0], request_stage, decision_stage, second.stages[3]),
        answer_norm=f"postgresql-{card_id}-decision",
        sandbox_spec=first.sandbox_spec,
    )
    return first, second


__all__ = ["TaskCardId", "build_postgresql_task_card_sessions"]
