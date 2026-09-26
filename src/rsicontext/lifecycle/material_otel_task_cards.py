"""Source-adjudicated OTel database task cards for development intake.

The DBMS system key is a different project decision from the query-text key.
Both revisions require that field for a new PostgreSQL client span. This
module constructs only that card; other proposed cards need separate review.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from rsicontext.lifecycle.material_otel_source_contrast import (
    SOURCE_FILES,
    build_otel_source_contrast_sessions,
)
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance

CARD_ID = "dbms-system-key"
SYSTEM_KEYS = {"1.24": "db.system", "1.43": "db.system.name"}
# Inclusive line numbers and SHA256 of the complete source line, including LF.
SYSTEM_ROW = {
    "1.24": (68, "99e1986e9cd0d98faf560eaafc5992f0e7343e4420ddf43e0d5fb531824087a3"),
    "1.43": (116, "22e5b0916dbaa212cc0298745320c20f9fa1090d8ff7ecf91061fa231102149c"),
}


def system_row_sha256(source_root: Path, *, revision: str) -> str:
    """Check the source's Required DBMS row against its pinned line identity."""

    if revision not in SYSTEM_ROW:
        raise ValueError(f"unsupported OpenTelemetry source revision: {revision}")
    line_no, expected = SYSTEM_ROW[revision]
    raw = (source_root / SOURCE_FILES[revision]).read_bytes()
    row = raw.splitlines(keepends=True)[line_no - 1]
    actual = hashlib.sha256(row).hexdigest()
    if actual != expected:
        raise ValueError(f"pinned OpenTelemetry DBMS row mismatch: {actual} != {expected}")
    return actual


def build_otel_dbms_system_card_sessions(
    source_root: Path, *, revision: str
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build a matched B pair; source-dependent legal keys stay private."""

    first, second = build_otel_source_contrast_sessions(source_root, revision=revision)
    system_row_sha256(source_root, revision=revision)
    old_key, new_key = SYSTEM_KEYS["1.24"], SYSTEM_KEYS["1.43"]
    legal_key = SYSTEM_KEYS[revision]
    request = DocumentRef(
        doc_id="project-request",
        title="Constructed PostgreSQL client instrumentation request",
        text=(
            "[[doc:project-request]] Constructed PostgreSQL client instrumentation request\n"
            "BENCHMARK SANDBOX ONLY. Start new database client span instrumentation. "
            "The client library and actual server are both PostgreSQL, so their DBMS "
            "identity agrees. Emit exactly one attribute for the DBMS product, choosing "
            "the key marked Required in the supplied database client span convention. "
            "Use that exact key as the plan. This is new instrumentation and does not "
            "migrate or dual-emit older instrumentation. Request a current plan-reviewed "
            "receipt before finalizing dbms_system_plan. The receipt confirms local "
            "review only, not attribute correctness."
        ),
        source_url="benchmark:constructed/otel-dbms-system-key-v1",
        retrieved_date="2026-09-26",
    )
    survey = first.stages[0]
    first = replace(
        first,
        instance_id="research-v5-otel-dbms-system-s1-dev-0001",
        stages=(
            replace(
                survey,
                prompt_text="Read the full upstream database convention source and its license.",
            ),
            *first.stages[1:],
        ),
        answer_norm="source-conditional-dbms-system-key",
        sandbox_spec={
            "records": ["convention_review", "dbms_system_plan"],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    request_stage = second.stages[1]
    decision = second.stages[2]
    second = replace(
        second,
        instance_id="research-v5-otel-dbms-system-s2-dev-0001",
        stages=(
            second.stages[0],
            replace(
                request_stage,
                documents=(request,),
                prompt_text="Apply the project request to the upstream database convention.",
            ),
            replace(
                decision,
                prompt_text="Commit the selected DBMS attribute with current review evidence.",
                expected_state_delta={"dbms_system_plan": {"status": "final"}},
                commit_precondition={
                    "record_id": "dbms_system_plan",
                    "prior_finalized_record": "convention_review",
                    "prior_verification": {
                        "check": "review-complete",
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [old_key, new_key]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [legal_key],
                    "plan_requirements": {
                        old_key: {"requires_check": "plan-reviewed"},
                        new_key: {"requires_check": "plan-reviewed"},
                    },
                },
                verification_oracle={"plan-reviewed": {old_key: True, new_key: True}},
            ),
            second.stages[3],
        ),
        answer_norm="source-conditional-dbms-system-key",
        sandbox_spec={
            "records": ["convention_review", "dbms_system_plan"],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second


__all__ = [
    "CARD_ID",
    "SYSTEM_KEYS",
    "SYSTEM_ROW",
    "build_otel_dbms_system_card_sessions",
    "system_row_sha256",
]
