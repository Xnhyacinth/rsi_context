"""Development-only A parent grounded in pinned OTel database conventions.

The upstream excerpts describe telemetry conventions. The team's rollout,
candidate plans, validation receipt, and writable records below are constructed
benchmark material; none asserts that OpenTelemetry approved a real migration.
The source ledger and immutable file hashes are in docs/reviews/r4-otel-parent.md.
"""

from __future__ import annotations

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

_SOURCE_BASE = (
    "https://github.com/open-telemetry/semantic-conventions/blob/"
    "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/"
)
_SOURCE_DATE = "2026-09-25"

# Verbatim lines 35-39 of docs/db/database-spans.md at the pinned commit.
_MIGRATION_EXCERPT = (
    ">   * `database` - emit the stable database conventions, and stop emitting\n"
    ">     the experimental database conventions that the instrumentation emitted\n"
    ">     previously.\n"
    ">   * `database/dup` - emit both the experimental and stable database conventions,\n"
    ">     allowing for a phased rollout of the stable semantic conventions."
)

# Verbatim lines 178-179 of docs/db/sql.md at the pinned commit.
_QUERY_EXCERPT = (
    "**[13] `db.query.text`:** Non-parameterized query text SHOULD NOT be collected by default "
    "unless there is sanitization that excludes sensitive data, e.g. by redacting all literal "
    "values present in the query text. See [Sanitization of `db.query.text`]"
    "(/docs/db/database-spans.md#sanitization-of-dbquerytext).\n"
    "Parameterized query text SHOULD be collected by default (the query parameter values "
    "themselves are opt-in, see [`db.query.parameter.<key>`]"
    "(/docs/registry/attributes/db.md))."
)


def _doc(doc_id: str, title: str, text: str, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date=_SOURCE_DATE,
    )


def build_otel_database_migration_parent(
    *, instance_id: str = "research-v4-otel-db-migration-dev-0001"
) -> LifecycleInstance:
    """Build one compact, independent development candidate for A.

    The correct rollout mode depends on the pinned OTel source plus a
    constructed local constraint. The follow-up requires a different source
    proposition from the same parent. This is an executable construction
    check, not a claim of model difficulty or Gate 2 qualification.
    """

    migration = _doc(
        "otel-db-modes",
        "Pinned OTel database migration options (source excerpt)",
        _MIGRATION_EXCERPT,
        _SOURCE_BASE + "docs/db/database-spans.md#L35-L39",
    )
    query = _doc(
        "otel-sql-query-text",
        "Pinned OTel SQL query text rule (source excerpt)",
        _QUERY_EXCERPT,
        _SOURCE_BASE + "docs/db/sql.md#L178-L179",
    )
    brief = _doc(
        "local-rollout-brief",
        "Constructed local rollout brief",
        (
            "BENCHMARK SANDBOX ONLY. An existing database instrumentation still emits "
            "the old experimental conventions. For the first rollout window, the legacy "
            "collector must keep receiving them while a new collector receives the stable "
            "conventions. Select an opt-in mode supported by the pinned OTel excerpt. "
            "A local validation receipt is required before a migration record may be finalized."
        ),
        "benchmark:constructed/otel-db-rollout",
    )
    constraint = _doc(
        "local-transition-constraint",
        "Constructed transition constraint",
        (
            "BENCHMARK SANDBOX ONLY. The first transition must carry BOTH the legacy "
            "experimental conventions and the stable conventions. The alternate stable-only "
            "transition is premature while the local legacy collector is attached."
        ),
        "benchmark:constructed/otel-db-rollout",
    )
    delegation = _doc(
        "local-validation-protocol",
        "Constructed validation surface",
        (
            "BENCHMARK SANDBOX ONLY. Request the environment's dual-emission validation "
            "for the chosen opt-in mode. A participant-written pass claim is not evidence."
        ),
        "benchmark:constructed/otel-db-rollout",
    )
    documentation_change = _doc(
        "local-documentation-update",
        "Constructed documentation update",
        (
            "BENCHMARK SANDBOX ONLY. Revision 2 corrects wording in the local rollout "
            "guide. It changes no dual-emission validation condition and does not "
            "invalidate an earlier validation receipt."
        ),
        "benchmark:constructed/otel-db-rollout",
    )
    followup = _doc(
        "local-query-followup",
        "Constructed query text follow-up",
        (
            "BENCHMARK SANDBOX ONLY. A later local instrumenter proposes collecting "
            "raw, non-parameterized SQL query text by default, with literal values intact "
            "and no sanitizer. Record query_text_decision.status='hold' if this proposal "
            "must wait for sanitization, or 'allow' if it may ship as described. Use the "
            "earlier pinned SQL source; that excerpt is not re-attached."
        ),
        "benchmark:constructed/otel-db-rollout",
    )

    survey = (brief, migration, query)
    return LifecycleInstance(
        instance_id=instance_id,
        family="research-v4",
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    "Review the pinned source excerpts and constructed local rollout brief. "
                    "Keep the relevant distinctions: later stages do not re-attach source "
                    "material, although the normal document reread surface remains available."
                ),
                documents=survey,
                gold_evidence_ids=(migration.doc_id, query.doc_id, brief.doc_id),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text="Apply the new local transition constraint to the source options.",
                documents=(constraint,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text=(
                    "A bounded helper may check a named option against the local validation."
                ),
                documents=(delegation,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text="A local guide revision arrives. Determine its validation scope.",
                documents=(documentation_change,),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Choose and validate the migration mode. Create and finalize "
                    "migration_commit with plan=<mode>, citing an environment-issued "
                    "dual-emission validation receipt and a local candidate record."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={"migration_commit": {"status": "final"}},
                commit_precondition={
                    "record_id": "migration_commit",
                    "plan_field": "plan",
                    "legal_plans": ["database/dup"],
                    "plan_requirements": {
                        "database/dup": {
                            "domain": "telemetry",
                            "requires_check": "dual-emission",
                        }
                    },
                    "current_revision": 1,
                    "revision_scope": ["dual-emission"],
                },
                verification_oracle={"dual-emission": {"database/dup": True, "database": False}},
            ),
            StageSpec(
                stage_id="s6-followup-query-text",
                kind="follow_up",
                prompt_text=(
                    "Assess the later local query text proposal from retained source "
                    "notes or a metered reread, and write query_text_decision."
                ),
                documents=(followup,),
                gold_evidence_ids=(),
                expected_state_delta={"query_text_decision": {"status": "hold"}},
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(len(doc.text.split()) for doc in survey),
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="database/dup",
        answer_aliases=("database/dup",),
        sandbox_spec={
            "records": ["candidate_status", "migration_commit", "query_text_decision"],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
    )


__all__ = ["build_otel_database_migration_parent"]
