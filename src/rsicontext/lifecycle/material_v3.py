"""Research-v3 instance construction: the migration-decision main world.

Spec: ``docs/task-card-research-v3.md`` (frozen 2026-09-21 BEFORE this
constructor). One instance is one data-warehouse migration project: five
candidate plans with buried exception clauses, a scoped constraint, an
optional delegation surface, a PARTIAL rule change (only in-scope
verifications are invalidated), and a migration commit whose finalize
carries checkable preconditions over the sandbox's actual records.

Hand-audited material: the five candidates' properties below are
enumerable by hand from the documents this module emits (the task
card's semantic-validity layer). The legal plan set is DERIVED, not
hidden: after the stage-4 rule change, a plan is legal for the
migration commit iff

  (a) it does not fall under the stage-2 constraint's scope with an
      unsatisfied requirement (finance-domain plans need an
      online-cutover verification record), and
  (b) any replica-lag verification it relies on carries the current
      protocol revision (stage 4 superseded exactly that check).

Plan  "aurora"  — finance domain, supports online cutover (its exception
clause requires a read-replica window, which the migration has).
Plan  "borealis" — finance domain, NO online-cutover support (its
exception: unsupported on clusters below v9; the project cluster is
v8): the stage-2 constraint makes it illegal.
Plan  "cumulus"  — non-finance, no in-scope exposure: legal via the
avoidance path.
Plan  "draco"    — non-finance, replica-lag verification REQUIRED under
the old protocol; the new revision's threshold fails it: legal only
with a post-supersession re-verification, which for draco FAILS the new
threshold — illegal after stage 4 (legal before it: the world rewards
scope-aware invalidation, and committing draco AFTER the rule change
with stale pre-supersession evidence is exactly failure class 2).
Plan  "ember"    — non-finance, passes everything: legal.

Legal set: {aurora (with online-cutover verification), cumulus, ember}.
The engine-validity tests drive all four legal solution paths from the
task card through scripted hooks.
"""

from __future__ import annotations

from rsicontext.lifecycle.env import Action
from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY = "research-v3"
_COMMIT_RECORD = "migration_commit"
_STATUS_RECORD = "candidate_status"
_VERIF_RECORD = "verification_run"
_PROTOCOL_REVISION_OLD = 1
_PROTOCOL_REVISION_NEW = 2
_REVISION_SCOPE = ("replica-lag",)
_FINANCE_CONSTRAINT = {"domain": "finance", "requires_check": "online-cutover"}
_LEGAL_PLANS = ("aurora", "cumulus", "ember")

#: The evaluator-owned verification oracle: which (check, subject) pairs the
#: environment can execute, and their verdicts. Evidence records exist ONLY
#: through ``request_verification`` against this table, so "verified" can no
#: longer be self-declared. The in-scope check (replica-lag) passes for every
#: plan except draco (its thin margin fails the tightened revision-2
#: threshold — the world's designed failure class 2); online-cutover passes
#: exactly for the plans whose documents say it is supported (all but
#: borealis).
_VERIFICATION_ORACLE: dict[str, dict[str, bool]] = {
    "replica-lag": {
        "aurora": True,
        "borealis": True,
        "cumulus": True,
        "draco": False,
        "ember": True,
    },
    "online-cutover": {
        "aurora": True,
        "borealis": False,
        "cumulus": True,
        "draco": True,
        "ember": True,
    },
}

_CANDIDATES: tuple[dict[str, object], ...] = (
    {
        "plan": "aurora",
        "doc_id": "doc-cand-a",
        "title": "Aurora migration plan",
        "text": (
            "Aurora migrates the finance schema with online cutover: dual-write "
            "during the window, verified by the replica-lag check under the "
            "verification protocol. Cost band: mid. Exception clause: the "
            "online-cutover path requires a read-replica window; this project "
            "has one, so the exception is satisfied."
        ),
        "domain": "finance",
        "online_cutover": True,
        "replica_lag_passes_new": True,
    },
    {
        "plan": "borealis",
        "doc_id": "doc-cand-b",
        "title": "Borealis migration plan",
        "text": (
            "Borealis is the cheapest finance-schema plan. It cuts over with a "
            "hard freeze — no online path. Cost band: low. Exception clause: "
            "unsupported on clusters below v9; this project's cluster is v8, "
            "so the plan's freeze path is the only option."
        ),
        "domain": "finance",
        "online_cutover": False,
        "replica_lag_passes_new": True,
    },
    {
        "plan": "cumulus",
        "doc_id": "doc-cand-c",
        "title": "Cumulus migration plan",
        "text": (
            "Cumulus handles the reporting domain only. Cost band: low. "
            "Exception clause: nightly-batch dependency means the migration "
            "window must avoid the 02:00 rollup; unrelated to cutover or "
            "replica lag."
        ),
        "domain": "reporting",
        "online_cutover": True,
        "replica_lag_passes_new": True,
    },
    {
        "plan": "draco",
        "doc_id": "doc-cand-d",
        "title": "Draco migration plan",
        "text": (
            "Draco serves the analytics domain. It requires a replica-lag "
            "verification under the protocol before cutover. Cost band: mid. "
            "Exception clause: the replica-lag margin is thin — under the "
            "current protocol revision the lag passes, but any tightened "
            "threshold would fail it."
        ),
        "domain": "analytics",
        "online_cutover": True,
        "replica_lag_passes_new": False,
    },
    {
        "plan": "ember",
        "doc_id": "doc-cand-e",
        "title": "Ember migration plan",
        "text": (
            "Ember is the operations-domain plan with wide margins. Cost "
            "band: mid. Exception clause: requires a maintenance-mode "
            "brief; the team already scheduled one."
        ),
        "domain": "operations",
        "online_cutover": True,
        "replica_lag_passes_new": True,
    },
)


def _doc(doc_id: str, title: str, text: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=f"v3:{doc_id}",
        retrieved_date="2026-09-21",
    )


def build_research_v3_instance(*, instance_id: str = "research-v3-main-0001") -> LifecycleInstance:
    """Build the hand-audited main world instance (one per parent world)."""

    survey_docs = tuple(
        _doc(str(candidate["doc_id"]), str(candidate["title"]), str(candidate["text"]))
        for candidate in _CANDIDATES
    )
    survey_docs = (
        *survey_docs,
        _doc(
            "doc-verif-db",
            "Verification protocol",
            (
                "The verification protocol defines: the replica-lag check "
                "validates online-cutover readiness; the disk-encryption check "
                "validates at-rest compliance. Protocol revision 1: replica-lag "
                "threshold 500 ms. The cutover property is what finance-domain "
                "plans must support for online migration."
            ),
        ),
        _doc(
            "doc-exception-x",
            "Platform constraints memo",
            (
                "Misc platform notes: the shared read replica exists. "
                "One low-salience line: analytics workloads observe thinner "
                "replica-lag margins than other domains."
            ),
        ),
    )
    constraint_doc = _doc(
        "doc-constraint-k",
        "New migration constraint",
        (
            "Scope: this constraint applies to plans touching the finance "
            "domain only. Finance-domain migrations must support online "
            "cutover (verified by the protocol's cutover check); plans "
            "outside the finance domain are unaffected."
        ),
    )
    delegation_doc = _doc(
        "doc-delegation-targets",
        "Delegation surface",
        (
            "A bounded sub-agent may be asked to verify a named document "
            "against a named check. A usable return carries finding, source "
            "doc id, and applicability condition; a return without those "
            "fields cannot justify a conclusion."
        ),
    )
    rule_change_doc = _doc(
        "doc-rule-change",
        "Verification protocol revision notice",
        (
            "Scope: this revision supersedes the replica-lag check only. "
            "Protocol revision 2 tightens the replica-lag threshold to 300 ms; "
            "replica-lag verifications performed under revision 1 are stale "
            "for migration commits relying on them. All other checks "
            "(disk-encryption and others) are unaffected."
        ),
    )
    rule_change_doc = DocumentRef(
        doc_id=rule_change_doc.doc_id,
        title=rule_change_doc.title,
        text=rule_change_doc.text,
        source_url=rule_change_doc.source_url,
        retrieved_date=rule_change_doc.retrieved_date,
        superseded_by="doc-verif-db",
    )

    information_scale_tokens = sum(1 + len(doc.text.split()) for doc in survey_docs)
    return LifecycleInstance(
        instance_id=instance_id,
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    "[Migration project] Survey the plan documents and the "
                    "verification protocol. Build your working notes; they are "
                    "your only carry-forward — later stages will not re-show "
                    "these documents (re-reading is available at a ledgered "
                    "cost through your own tool surface)."
                ),
                documents=survey_docs,
                gold_evidence_ids=tuple(doc.doc_id for doc in survey_docs),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A new constraint arrives (document attached). From your "
                    "retained notes, determine which candidate plans fall "
                    "under its scope and what it requires of them."
                ),
                documents=(constraint_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text=(
                    "You may delegate verification of a candidate to a bounded "
                    "sub-agent over the attached surface. A usable return "
                    "carries finding, source doc id, and applicability "
                    "condition. Record usable findings in your sandbox state; "
                    "treat unusable returns as verification failures."
                ),
                documents=(delegation_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached): the verification "
                    "protocol revision changed. Determine which of your "
                    "retained conclusions are invalidated — note the SCOPE of "
                    "the supersession — and what must be re-verified before a "
                    "commit."
                ),
                documents=(rule_change_doc,),
                gold_evidence_ids=(),
                rule_change_effect=_PROTOCOL_REVISION_NEW,
                rule_change_scope=tuple(_REVISION_SCOPE),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the migration: create and finalize record "
                    f"{_COMMIT_RECORD} naming the chosen plan, with candidate "
                    f"status records ({_STATUS_RECORD}) and verification runs "
                    f"({_VERIF_RECORD}) it relies on. Finalization is refused "
                    "unless the referenced records exist, are valid under the "
                    "current protocol revision where the rule change applies, "
                    "and satisfy the finance-domain constraint. No documents "
                    "are attached."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={
                    _COMMIT_RECORD: {"status": "final"},
                },
                expected_aliases=(),
                commit_precondition={
                    "record_id": _COMMIT_RECORD,
                    "plan_field": "plan",
                    "legal_plans": list(_LEGAL_PLANS),
                    "plan_requirements": {
                        "aurora": dict(_FINANCE_CONSTRAINT),
                    },
                    "current_revision": _PROTOCOL_REVISION_NEW,
                    "revision_scope": list(_REVISION_SCOPE),
                },
                verification_oracle=_VERIFICATION_ORACLE,
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_LEGAL_PLANS[0],
        sandbox_spec={
            "records": [_COMMIT_RECORD, _STATUS_RECORD, _VERIF_RECORD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=_LEGAL_PLANS,
    )


def commit_action(
    plan: str,
    *,
    refs: tuple[str, ...],
) -> Action:
    """The migration-commit finalize, with the world's preconditions attached.

    Precondition semantics (env v3): every ref must exist; in-scope
    (replica-lag) verifications must carry the CURRENT protocol revision;
    if a referenced candidate is finance-domain, an online-cutover
    verification must be among the refs.
    """

    return Action(
        kind="finalize",
        record_id=_COMMIT_RECORD,
        fields={"plan": plan, "status": "final"},
        provenance=refs,
        precondition_refs=refs,
        precondition_current_revision=_PROTOCOL_REVISION_NEW,
        precondition_revision_scope=_REVISION_SCOPE,
        precondition_scope_constraint=_FINANCE_CONSTRAINT,
    )


__all__ = [
    "build_research_v3_instance",
    "commit_action",
]
