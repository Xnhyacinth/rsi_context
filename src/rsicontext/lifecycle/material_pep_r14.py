"""Historical PEP license-format contrast for a two-session B development card.

The source files are pinned upstream bytes. The archival validator, project
request, actions, and receipts are constructed benchmark state; this card does
not grade compliance with the current PyPA specification.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SourceVariant = Literal["pep621", "pep639"]

SOURCE_REVISION = "6822259db9c95f02da739b3e2830a4aa1ae35134"
SOURCE_FILES: dict[SourceVariant, tuple[str, str]] = {
    "pep621": (
        "peps/pep-0621.rst",
        "8710ea6fcc2f5d19571ea7b2610e5c2fbc93d44051c1e5669f40a685ab4bb49e",
    ),
    "pep639": (
        "peps/pep-0639.rst",
        "0143e14bdeb02b95d43484df7a29990e2d25376d81fdb119b9afef7433769f94",
    ),
}
_LEGAL = {"pep621": "license-table", "pep639": "license-string"}
_OTHER = {"pep621": "license-string", "pep639": "license-table"}
_DATE = "2026-09-26"
_SOURCE_ID = "historical-license-source"
_REVIEW_ID = "source_review"
_DECISION_ID = "license_format_decision"


def build_pep_license_sessions(
    source_root: Path, *, variant: SourceVariant
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Construct matched worlds; only the first-session source and oracle vary."""

    if variant not in SOURCE_FILES:
        raise ValueError(f"unsupported historical PEP source variant: {variant}")
    relative, expected_hash = SOURCE_FILES[variant]
    raw = (source_root / relative).read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(
            f"pinned PEP source mismatch for {relative}: {actual_hash} != {expected_hash}"
        )
    source = DocumentRef(
        doc_id=_SOURCE_ID,
        title="Pinned historical license metadata proposal",
        text=f"[[doc:{_SOURCE_ID}]] Pinned historical license metadata proposal\n"
        + raw.decode("utf-8"),
        source_url=f"https://github.com/python/peps/blob/{SOURCE_REVISION}/{relative}",
        retrieved_date=_DATE,
    )
    request = DocumentRef(
        doc_id="archive-project-request",
        title="Constructed archival validator request",
        text=(
            "[[doc:archive-project-request]] Constructed archival validator request\n"
            "BENCHMARK SANDBOX ONLY. A historical-document fixture accepts exactly "
            "the license declaration form specified by the source supplied in "
            "the previous session. It records the preferred, nondeprecated "
            "[project].license representation for the simple MIT expression. "
            "Choose plan=license-table for license = {text = \"MIT\"} or "
            "plan=license-string for license = \"MIT\". The mock fixture "
            "uses only the supplied historical source; this is not a test of "
            "current PyPA compliance or a claim that other forms are invalid "
            "in every packaging tool. Request license-review, inspect its "
            "receipt, then finalize license_format_decision with the chosen "
            "plan and that passing receipt as provenance."
        ),
        source_url="benchmark:constructed/pep-license-historical-v1",
        retrieved_date=_DATE,
    )
    axes = DescriptionAxes(
        # A common envelope prevents this visible metadata from identifying
        # which of the two historical source documents was supplied.
        information_scale_tokens=4218,
        dependency_distance_stages=3,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=0,
    )
    sandbox_spec = {
        "records": [_REVIEW_ID, _DECISION_ID],
        "action_kinds": ["create_record", "finalize", "request_verification"],
    }
    first = LifecycleInstance(
        instance_id="research-v5-pep-license-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="source-survey",
                kind="survey",
                prompt_text=(
                    "Read the complete pinned historical source. Retain how it "
                    "specifies [project].license for the archival fixture."
                ),
                documents=(source,),
                gold_evidence_ids=(_SOURCE_ID,),
            ),
            StageSpec(
                stage_id="source-review",
                kind="act_verify",
                prompt_text=(
                    "Request review-complete for plan reviewed, then finalize "
                    "source_review citing the passing receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_REVIEW_ID: {"status": "final"}},
                commit_precondition={
                    "record_id": _REVIEW_ID,
                    "plan_field": "plan",
                    "legal_plans": ["reviewed"],
                    "plan_requirements": {"reviewed": {"requires_check": "review-complete"}},
                },
                verification_oracle={"review-complete": {"reviewed": True}},
            ),
            StageSpec(
                stage_id="pause-project",
                kind="session_end",
                prompt_text="Session ends. Only bounded carry and project state persist.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="historical-license-format",
        sandbox_spec=sandbox_spec,
    )
    legal, other = _LEGAL[variant], _OTHER[variant]
    second = LifecycleInstance(
        instance_id="research-v5-pep-license-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resume-project",
                kind="session_start",
                prompt_text="Resume the archival fixture after a process reset.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="archive-request",
                kind="constraint_injection",
                prompt_text="Apply the constructed request to the earlier historical source.",
                documents=(request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="decide-license-format",
                kind="act_verify",
                prompt_text=(
                    "Commit the source-grounded archival license form with review evidence."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_DECISION_ID: {"status": "final"}},
                commit_precondition={
                    "record_id": _DECISION_ID,
                    "prior_finalized_record": _REVIEW_ID,
                    "prior_verification": {
                        "check": "review-complete",
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [legal, other]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [legal],
                    "plan_requirements": {
                        legal: {"requires_check": "license-review"},
                        other: {"requires_check": "license-review"},
                    },
                },
                verification_oracle={"license-review": {legal: True, other: True}},
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
        answer_norm="historical-license-format",
        sandbox_spec=sandbox_spec,
    )
    return first, second


__all__ = ["SOURCE_FILES", "SOURCE_REVISION", "SourceVariant", "build_pep_license_sessions"]
