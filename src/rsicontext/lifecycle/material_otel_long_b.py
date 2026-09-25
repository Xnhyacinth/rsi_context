"""Two-session OTel development candidate over pinned, full source documents.

The source describes OpenTelemetry conventions. The rollout, two collectors,
validation service, and privacy proposal are constructed benchmark material.
The source files are read only after exact-byte SHA256 checks; this builder
does not acquire an upstream branch or expose evaluator-only verdicts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d"
SOURCE_SHA256 = {
    "docs/db/database-spans.md": "1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91",
    "docs/db/sql.md": "e451e533f90fbcc01ecc23f6d60aaa49d249dad79227f79ddeef548288eb32ea",
}
_SOURCE_URL = "https://github.com/open-telemetry/semantic-conventions/blob/" + SOURCE_REVISION + "/"
_DATE = "2026-09-25"
_FIRST = "migration_commit"
_SECOND = "query_text_rollout"
_DUAL = "dual-emission"
_PRIVACY = "query-text-safety"
_DUAL_MODE = "database/dup"
_SAFE_QUERY_PLAN = "hold-raw-enable-parameterized"


def _pinned_document(root: Path, relative: str, doc_id: str, title: str) -> DocumentRef:
    path = root / relative
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = SOURCE_SHA256[relative]
    if actual != expected:
        raise ValueError(f"pinned OTel source mismatch for {relative}: {actual} != {expected}")
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n" + raw.decode("utf-8"),
        source_url=_SOURCE_URL + relative,
        retrieved_date=_DATE,
    )


def _local_document(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\nBENCHMARK SANDBOX ONLY. {body}",
        source_url="benchmark:constructed/otel-two-session-rollout-v1",
        retrieved_date=_DATE,
    )


def build_otel_long_b_sessions(source_root: Path) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one unqualified B candidate using the exact pinned OTel files.

    The source root is supplied by the evaluator after the registry's pinned
    acquisition preflight. A wrong or partial checkout fails before any world
    is returned. Session 2 receives no source document; the real sequence
    runner destroys transient participant state and retains only ``carry``.
    """

    spans = _pinned_document(
        source_root,
        "docs/db/database-spans.md",
        "otel-database-spans-full",
        "Pinned database client spans, complete file",
    )
    sql = _pinned_document(
        source_root,
        "docs/db/sql.md",
        "otel-sql-full",
        "Pinned SQL conventions, complete file",
    )
    rollout = _local_document(
        "local-dual-collector-window",
        "First rollout window",
        "An existing instrumentation emits the experimental database conventions. "
        "For this window, the legacy collector must still receive those events while "
        "the new collector receives the stable conventions. Select the OTel opt-in "
        "mode that emits both. Finalize migration_commit only after an environment "
        "dual-emission validation passes for that mode.",
    )
    privacy = _local_document(
        "local-query-text-proposal",
        "Later query-text proposal",
        "After the migration, an instrumenter proposes two defaults: (1) collect "
        "raw non-parameterized SQL query text, including literal values, with no "
        "sanitizer; (2) collect parameterized query text without parameter values. "
        "Decide each default from the earlier OTel source. An environment "
        "query-text-safety check is required before the rollout is finalized.",
    )

    first = LifecycleInstance(
        instance_id="research-v5-otel-long-b-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="otel-long-source-review",
                kind="survey",
                prompt_text=(
                    "Review both complete pinned OTel source files. Retain the migration "
                    "mode distinction and the two query-text default rules for later use."
                ),
                documents=(spans, sql),
                gold_evidence_ids=(spans.doc_id, sql.doc_id),
            ),
            StageSpec(
                stage_id="otel-dual-collector-constraint",
                kind="constraint_injection",
                prompt_text="Apply the constructed first-window collector requirement.",
                documents=(rollout,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="otel-migration-award",
                kind="act_verify",
                prompt_text=(
                    "Choose an OTel mode, request dual-emission validation, inspect its "
                    "receipt, and finalize migration_commit with the passing mode and "
                    "the environment-issued receipt as provenance."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_FIRST: {"status": "final"}},
                commit_precondition={
                    "record_id": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": [_DUAL_MODE],
                    "plan_requirements": {_DUAL_MODE: {"requires_check": _DUAL}},
                    "current_revision": 1,
                    "revision_scope": [_DUAL],
                },
                verification_oracle={_DUAL: {_DUAL_MODE: True, "database": False}},
            ),
            StageSpec(
                stage_id="otel-s1-end",
                kind="session_end",
                prompt_text="Session ends; only the bounded carry state persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            # Schema metadata uses the project's existing whitespace estimate;
            # this is not a target-tokenizer measurement.
            information_scale_tokens=sum(len(doc.text.split()) for doc in (spans, sql)),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_DUAL_MODE,
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = LifecycleInstance(
        instance_id="research-v5-otel-long-b-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="otel-s2-start",
                kind="session_start",
                prompt_text=(
                    "Resume the same project. The earlier finalized migration is a "
                    "prerequisite for a query-text rollout; only carry state survives."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="otel-query-text-proposal",
                kind="constraint_injection",
                prompt_text=(
                    "Assess the constructed proposal against the earlier pinned OTel "
                    "rules using retained notes or a metered source reread."
                ),
                documents=(privacy,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="otel-query-text-rollout",
                kind="act_verify",
                prompt_text=(
                    "State the raw non-parameterized and parameterized query-text "
                    "defaults in query_text_rollout. Request query-text-safety validation "
                    "for your plan; inspect its receipt; finalize only if it passes. "
                    "A primary migration finalized before this session is required."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={
                    _SECOND: {
                        "status": "final",
                        "raw_nonparameterized": "hold",
                        "parameterized_without_values": "allow",
                    }
                },
                commit_precondition={
                    "record_id": _SECOND,
                    "prior_finalized_record": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": [_SAFE_QUERY_PLAN],
                    "plan_requirements": {_SAFE_QUERY_PLAN: {"requires_check": _PRIVACY}},
                    "current_revision": 1,
                    "revision_scope": [_PRIVACY],
                },
                verification_oracle={
                    _PRIVACY: {
                        _SAFE_QUERY_PLAN: True,
                        "enable-raw-query-text": False,
                    }
                },
            ),
            StageSpec(
                stage_id="otel-s2-end",
                kind="session_end",
                prompt_text="Session ends; only the bounded carry state persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=len(privacy.text.split()),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_SAFE_QUERY_PLAN,
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second


__all__ = ["SOURCE_REVISION", "SOURCE_SHA256", "build_otel_long_b_sessions"]
