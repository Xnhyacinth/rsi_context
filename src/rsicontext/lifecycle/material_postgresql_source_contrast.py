"""Matched PostgreSQL source-swap development worlds.

The SQL documentation and COPYRIGHT are pinned upstream bytes. The project
request, actions, and receipts are constructed benchmark state, not an
observation of a running PostgreSQL server.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISIONS = {
    "16": "c372fbbd8e911f2412b80a8c39d7079366565d67",
    "17": "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e",
}
SOURCE_SHA256 = {
    "16": {
        "COPYRIGHT": "1a7d13c3ab31961b91ba256f77d6e82e0b54bf992253060fe93bdb5466df416a",
        "doc/src/sgml/ref/create_subscription.sgml": (
            "8f306cfd871d45b829bde1419e92bbc7cd58d28e068a4de823ee9208745d745d"
        ),
    },
    "17": {
        "COPYRIGHT": "9bf20ee493926a7e17a74bc7f05089fbc014269667b1540bc35a6b194a40c9de",
        "doc/src/sgml/ref/create_subscription.sgml": (
            "935c1a67d7c013410012b753ca81d75e84ed5ce2f622b195601ce1e688e97340"
        ),
    },
}
_SOURCE_URL = "https://git.postgresql.org/git/postgresql.git"
_DATE = "2026-09-26"
_PRIOR = "source_review"
_LATER = "native_capability_decision"
_REVIEW = "review-complete"
_DECISION_REVIEW = "decision-reviewed"
_NATIVE = "configure-native"
_DEFER = "defer-native"


def _source_doc(root: Path, revision: str, relative: str, doc_id: str, title: str) -> DocumentRef:
    raw = (root / relative).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = SOURCE_SHA256[revision][relative]
    if actual != expected:
        raise ValueError(
            f"pinned PostgreSQL source mismatch for {relative}: {actual} != {expected}"
        )
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n" + raw.decode("utf-8"),
        source_url=_SOURCE_URL,
        retrieved_date=_DATE,
    )


def build_postgresql_source_contrast_sessions(
    source_root: Path, *, revision: str
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one matched source variant; ``revision`` remains evaluator-only.

    The second session's visible task is identical in both variants. The
    private legal set follows the pinned CREATE SUBSCRIPTION parameter catalog.
    """
    if revision not in SOURCE_REVISIONS:
        raise ValueError(f"unsupported PostgreSQL source revision: {revision}")
    subscription = _source_doc(
        source_root,
        revision,
        "doc/src/sgml/ref/create_subscription.sgml",
        "upstream-create-subscription",
        "Pinned upstream CREATE SUBSCRIPTION source",
    )
    notice = _source_doc(source_root, revision, "COPYRIGHT", "upstream-notice", "COPYRIGHT")
    request = DocumentRef(
        doc_id="project-request",
        title="Constructed project request and action interface",
        text=(
            "[[doc:project-request]] Constructed project request and action interface\n"
            "BENCHMARK SANDBOX ONLY. This project needs a subscription whose logical "
            "slot will be available after standby promotion. Use only native "
            "CREATE SUBSCRIPTION capabilities in the supplied source; third-party "
            "extensions and manual slot recreation are outside this task. "
            "The proposed command is CREATE SUBSCRIPTION ... WITH (failover = true). "
            "Choose configure-native if that option is supported by the supplied "
            "CREATE SUBSCRIPTION parameter catalog; otherwise choose defer-native. "
            "Before finalizing native_capability_decision, request the "
            "decision-reviewed check with the chosen plan as subject and cite "
            "its environment receipt. This review check confirms local procedure "
            "review only; it does not attest SQL feature support."
        ),
        source_url="benchmark:constructed/postgresql-source-contrast-v1",
        retrieved_date=_DATE,
    )
    axes = DescriptionAxes(
        information_scale_tokens=3000,
        dependency_distance_stages=2,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=0,
    )
    first = LifecycleInstance(
        instance_id="research-v5-pg-source-swap-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="source-survey",
                kind="survey",
                prompt_text="Read the pinned upstream CREATE SUBSCRIPTION source and its notice.",
                documents=(subscription, notice),
                gold_evidence_ids=(subscription.doc_id,),
            ),
            StageSpec(
                stage_id="review-source",
                kind="act_verify",
                prompt_text=(
                    "Request review-complete for plan reviewed, then finalize "
                    "source_review citing that environment receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_PRIOR: {"status": "final"}},
                commit_precondition={
                    "record_id": _PRIOR,
                    "plan_field": "plan",
                    "legal_plans": ["reviewed"],
                    "plan_requirements": {"reviewed": {"requires_check": _REVIEW}},
                },
                verification_oracle={_REVIEW: {"reviewed": True}},
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
        answer_norm="source-conditional-native-capability",
        sandbox_spec={
            "records": [_PRIOR, _LATER],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = LifecycleInstance(
        instance_id="research-v5-pg-source-swap-s2-dev-0001",
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
                prompt_text=(
                    "Apply the constructed project request to the upstream parameter catalog."
                ),
                documents=(request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="decide-capability",
                kind="act_verify",
                prompt_text=(
                    "Commit the supported native-capability decision with current review evidence."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_LATER: {"status": "final"}},
                commit_precondition={
                    "record_id": _LATER,
                    "prior_finalized_record": _PRIOR,
                    "prior_verification": {
                        "check": _REVIEW,
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [_NATIVE, _DEFER]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [_DEFER if revision == "16" else _NATIVE],
                    "plan_requirements": {
                        _NATIVE: {"requires_check": _DECISION_REVIEW},
                        _DEFER: {"requires_check": _DECISION_REVIEW},
                    },
                },
                verification_oracle={_DECISION_REVIEW: {_NATIVE: True, _DEFER: True}},
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
        answer_norm="source-conditional-native-capability",
        sandbox_spec={
            "records": [_PRIOR, _LATER],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second


__all__ = ["SOURCE_REVISIONS", "SOURCE_SHA256", "build_postgresql_source_contrast_sessions"]
