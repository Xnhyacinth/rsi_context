"""Development-only OpenTelemetry database convention source-swap pair.

The upstream database span documents define the candidate attribute. Review
receipts, project records, and actions are constructed benchmark state.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISIONS = {
    "1.24": "cafda7127683b7f667e27cdbd3220510b6f998c9",
    "1.43": "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d",
}
SOURCE_FILES = {
    "1.24": "docs/database/database-spans.md",
    "1.43": "docs/db/database-spans.md",
}
SOURCE_SHA256 = {
    "1.24": "49a05d5eec2357782876527574b2a544163f4ebf36d193456c77c07a8b6dffa6",
    "1.43": "1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91",
}
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
_SOURCE_URL = "https://github.com/open-telemetry/semantic-conventions"
_DATE = "2026-09-26"
_OLD = "db.statement"
_NEW = "db.query.text"
_PRIOR = "convention_review"
_LATER = "query_attribute_plan"


def _source_doc(root: Path, relative: str, expected: str, doc_id: str) -> DocumentRef:
    raw = (root / relative).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(
            f"pinned OpenTelemetry source mismatch for {relative}: {actual} != {expected}"
        )
    return DocumentRef(
        doc_id=doc_id,
        title="Pinned upstream database convention source"
        if doc_id == "upstream-db"
        else "LICENSE",
        text=f"[[doc:{doc_id}]]\n" + raw.decode("utf-8"),
        source_url=_SOURCE_URL,
        retrieved_date=_DATE,
    )


def build_otel_source_contrast_sessions(
    source_root: Path, *, revision: str
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build a matched B pair; the revision and legal answer stay evaluator-side."""
    if revision not in SOURCE_REVISIONS:
        raise ValueError(f"unsupported OpenTelemetry source revision: {revision}")
    convention = _source_doc(
        source_root, SOURCE_FILES[revision], SOURCE_SHA256[revision], "upstream-db"
    )
    license_doc = _source_doc(source_root, "LICENSE", LICENSE_SHA256, "upstream-license")
    request = DocumentRef(
        doc_id="project-request",
        title="Constructed telemetry project request",
        text=(
            "[[doc:project-request]] Constructed telemetry project request\n"
            "BENCHMARK SANDBOX ONLY. Start a new database client instrumentation "
            "with one parameterized SQL SELECT query. Emit exactly one attribute "
            "for the SQL query text, choosing the attribute marked Recommended "
            "in the supplied database client span convention's call-level or "
            "span-definition table. Use that exact attribute key as the plan. "
            "This project opts into the supplied convention for "
            "new instrumentation; pre-existing instrumentation migration and "
            "dual emission are outside this task. The query uses placeholders, "
            "so no literal values are included. Request a current plan-reviewed "
            "receipt for the selected plan before finalizing query_attribute_plan. "
            "The receipt confirms local review only, not attribute correctness."
        ),
        source_url="benchmark:constructed/otel-source-contrast-v1",
        retrieved_date=_DATE,
    )
    axes = DescriptionAxes(
        information_scale_tokens=4500,
        dependency_distance_stages=2,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=0,
    )
    sandbox = {
        "records": [_PRIOR, _LATER],
        "action_kinds": ["create_record", "finalize", "request_verification"],
    }
    first = LifecycleInstance(
        instance_id="research-v5-otel-source-swap-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="source-survey",
                kind="survey",
                prompt_text="Read the full upstream database convention source and its license.",
                documents=(convention, license_doc),
                gold_evidence_ids=(convention.doc_id,),
            ),
            StageSpec(
                stage_id="review-source",
                kind="act_verify",
                prompt_text=(
                    "Request review-complete for plan reviewed; finalize convention_review "
                    "with its environment-issued PASS receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_PRIOR: {"status": "final"}},
                commit_precondition={
                    "record_id": _PRIOR,
                    "plan_field": "plan",
                    "legal_plans": ["reviewed"],
                    "plan_requirements": {"reviewed": {"requires_check": "review-complete"}},
                },
                verification_oracle={"review-complete": {"reviewed": True}},
            ),
            StageSpec(
                stage_id="pause-project",
                kind="session_end",
                prompt_text=(
                    "Session ends; only bounded carry and persistent project state survive."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-query-attribute",
        sandbox_spec=sandbox,
    )
    second = LifecycleInstance(
        instance_id="research-v5-otel-source-swap-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resume-project",
                kind="session_start",
                prompt_text="Resume the same constructed project after a process reset.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="project-request-stage",
                kind="constraint_injection",
                prompt_text="Apply the project request to the upstream database convention.",
                documents=(request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="decide-attribute",
                kind="act_verify",
                prompt_text="Commit the selected attribute with current review evidence.",
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_LATER: {"status": "final"}},
                commit_precondition={
                    "record_id": _LATER,
                    "prior_finalized_record": _PRIOR,
                    "prior_verification": {
                        "check": "review-complete",
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [_OLD, _NEW]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [_OLD if revision == "1.24" else _NEW],
                    "plan_requirements": {
                        _OLD: {"requires_check": "plan-reviewed"},
                        _NEW: {"requires_check": "plan-reviewed"},
                    },
                },
                verification_oracle={"plan-reviewed": {_OLD: True, _NEW: True}},
            ),
            StageSpec(
                stage_id="end-project",
                kind="session_end",
                prompt_text="Session ends.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-query-attribute",
        sandbox_spec=sandbox,
    )
    return first, second


__all__ = [
    "LICENSE_SHA256",
    "SOURCE_FILES",
    "SOURCE_REVISIONS",
    "SOURCE_SHA256",
    "build_otel_source_contrast_sessions",
]
