"""Research-v3 variant worlds: the same dependency structure, different material.

Deliverable 6's structural axis (docs/task-card-research-v3.md
§Counterfactual variants and the review round 4 §七): stratification
records TASK STRUCTURE, not outcome tiers, and variant worlds exist to
test whether a strategy's improvement transfers when the surface
material changes while the dependency structure holds. Each variant
world below is hand-audited exactly like the main world (the legal set
is derivable from the variant's own documents); the stage grammar, the
partial-rule-change discipline, and the evaluator commit gate are
shared with the main world by construction.

Variants of ONE parent world count as ONE world for statistics (the
task card's rule); these are SEPARATE material sets (disjoint plan
names, domains, checks), which is what independent-world statistics
require — the main world plus these variants form the first
independent-world pool for research-v3.
"""

from __future__ import annotations

from collections.abc import Mapping

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

#: One hand-audited variant world spec. ``required_checks`` maps the
#: record ids a legal commit must reference to the check names they
#: carry (all at the current revision). ``rule_change_scope`` is the
#: PARTIAL supersession scope; ``legal_plans`` the derived legal set;
#: ``plan_requirements`` the per-plan constraint (finance analog:
#: domain + required check).
_VARIANT_SPECS: tuple[dict[str, object], ...] = (
    {
        "spec_id": "orinoco",
        "candidates": (
            {
                "plan": "kestrel",
                "doc_id": "doc-orinoco-kestrel",
                "title": "Kestrel rollout plan",
                "text": (
                    "Kestrel migrates the billing service with zero-downtime "
                    "switchover, validated by the soak-window check. Cost "
                    "band: mid. Exception clause: the switchover requires a "
                    "blue-green pair; this project has one."
                ),
                "domain": "billing",
                "legal": True,
            },
            {
                "plan": "lark",
                "doc_id": "doc-orinoco-lark",
                "title": "Lark rollout plan",
                "text": (
                    "Lark is the cheapest billing plan but requires a full "
                    "freeze window. Cost band: low. Exception clause: "
                    "unsupported when the billing ledger is mid-cycle; this "
                    "migration runs mid-cycle."
                ),
                "domain": "billing",
                "legal": False,
            },
            {
                "plan": "merlin",
                "doc_id": "doc-orinoco-merlin",
                "title": "Merlin rollout plan",
                "text": (
                    "Merlin serves the telemetry domain with wide margins. "
                    "Cost band: mid. Exception clause: dashboards must be "
                    "paused during cutover; unrelated to soak windows."
                ),
                "domain": "telemetry",
                "legal": True,
            },
            {
                "plan": "nightjar",
                "doc_id": "doc-orinoco-nightjar",
                "title": "Nightjar rollout plan",
                "text": (
                    "Nightjar serves the search domain. It requires a "
                    "soak-window verification before cutover. Cost band: mid. "
                    "Exception clause: the soak margin is thin — the current "
                    "protocol threshold passes it, any tightened threshold "
                    "fails it."
                ),
                "domain": "search",
                "legal": False,
            },
            {
                "plan": "osprey",
                "doc_id": "doc-orinoco-osprey",
                "title": "Osprey rollout plan",
                "text": (
                    "Osprey is the auth-domain plan with wide margins. Cost "
                    "band: low. Exception clause: requires a maintenance-mode "
                    "brief; one is scheduled."
                ),
                "domain": "auth",
                "legal": True,
            },
        ),
        "verif_db_text": (
            "The verification protocol defines: the soak-window check "
            "validates zero-downtime readiness; the retention check "
            "validates data-compliance. Protocol revision 1: soak-window "
            "threshold 99.5% availability. Zero-downtime is what "
            "billing-domain plans must support."
        ),
        "exception_memo_text": (
            "Platform notes: blue-green pairs exist. One low-salience line: "
            "search-domain workloads observe thinner soak-window margins "
            "than other domains."
        ),
        "constraint_text": (
            "Scope: this constraint applies to plans touching the billing "
            "domain only. Billing migrations must support zero-downtime "
            "switchover (verified by the soak-window check); plans outside "
            "billing are unaffected."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes the soak-window check only. "
            "Protocol revision 2 tightens the soak threshold to 99.9%; "
            "soak-window verifications under revision 1 are stale for "
            "commits relying on them. All other checks are unaffected."
        ),
        "rule_change_scope": ("soak-window",),
        "legal_plans": ("kestrel", "merlin", "osprey"),
        "required_checks": {
            "verif-soak": "soak-window",
            "verif-retention": "retention",
        },
        "plan_requirements": {"kestrel": {"domain": "billing", "requires_check": "soak-window"}},
        "plan_note": "rollout",
    },
    {
        "spec_id": "parana",
        "candidates": (
            {
                "plan": "basalt",
                "doc_id": "doc-parana-basalt",
                "title": "Basalt storage migration plan",
                "text": (
                    "Basalt moves the archive tier to cold storage with "
                    "parallel sync, validated by the checksum-drift check. "
                    "Cost band: mid. Exception clause: parallel sync needs a "
                    "quiescent writer; one is available."
                ),
                "domain": "archive",
                "legal": True,
            },
            {
                "plan": "cobble",
                "doc_id": "doc-parana-cobble",
                "title": "Cobble storage migration plan",
                "text": (
                    "Cobble is the cheapest archive plan but pauses reads "
                    "for a day. Cost band: low. Exception clause: not "
                    "supported on shards above 4 TB; this archive's largest "
                    "shard is 6 TB."
                ),
                "domain": "archive",
                "legal": False,
            },
            {
                "plan": "dacite",
                "doc_id": "doc-parana-dacite",
                "title": "Dacite storage migration plan",
                "text": (
                    "Dacite serves the logs domain. Cost band: low. "
                    "Exception clause: log shippers must buffer during "
                    "cutover; unrelated to checksum drift."
                ),
                "domain": "logs",
                "legal": True,
            },
            {
                "plan": "eldorado",
                "doc_id": "doc-parana-eldorado",
                "title": "Eldorado storage migration plan",
                "text": (
                    "Eldorado serves the metrics domain. It requires a "
                    "checksum-drift verification. Cost band: mid. Exception "
                    "clause: the drift margin is thin — the current "
                    "threshold passes it, a tightened one fails it."
                ),
                "domain": "metrics",
                "legal": False,
            },
            {
                "plan": "flint",
                "doc_id": "doc-parana-flint",
                "title": "Flint storage migration plan",
                "text": (
                    "Flint is the security-domain plan with wide margins. "
                    "Cost band: mid. Exception clause: requires a key "
                    "rotation brief; one is scheduled."
                ),
                "domain": "security",
                "legal": True,
            },
        ),
        "verif_db_text": (
            "The verification protocol defines: the checksum-drift check "
            "validates archive sync correctness; the acl-audit check "
            "validates access compliance. Protocol revision 1: "
            "checksum-drift tolerance 0.1%. Parallel sync is what "
            "archive-domain plans must support."
        ),
        "exception_memo_text": (
            "Platform notes: quiescent writers exist. One low-salience "
            "line: metrics-domain workloads observe thinner drift margins "
            "than other domains."
        ),
        "constraint_text": (
            "Scope: this constraint applies to plans touching the archive "
            "domain only. Archive migrations must support parallel sync "
            "(verified by the checksum-drift check); plans outside archive "
            "are unaffected."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes the checksum-drift check only. "
            "Protocol revision 2 tightens the drift tolerance to 0.05%; "
            "checksum-drift verifications under revision 1 are stale for "
            "commits relying on them. All other checks are unaffected."
        ),
        "rule_change_scope": ("checksum-drift",),
        "legal_plans": ("basalt", "dacite", "flint"),
        "required_checks": {
            "verif-drift": "checksum-drift",
            "verif-acl": "acl-audit",
        },
        "plan_requirements": {"basalt": {"domain": "archive", "requires_check": "checksum-drift"}},
        "plan_note": "storage",
    },
)


def variant_world_specs() -> tuple[dict[str, object], ...]:
    """The hand-audited variant specs (copy; callers may not mutate ours)."""

    return tuple(dict(spec) for spec in _VARIANT_SPECS)


def build_research_v3_variant(spec_id: str, *, instance_id: str | None = None) -> LifecycleInstance:
    """Build one variant world instance from its spec id."""

    for spec in _VARIANT_SPECS:
        if spec["spec_id"] == spec_id:
            return _build(spec, instance_id or f"research-v3-{spec_id}-0001")
    raise ValueError(f"unknown research-v3 variant spec: {spec_id!r}")


def _doc(doc_id: str, title: str, text: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=f"v3-variant:{doc_id}",
        retrieved_date="2026-09-21",
    )


def _build(spec: Mapping[str, object], instance_id: str) -> LifecycleInstance:
    candidates = spec["candidates"]
    assert isinstance(candidates, tuple)
    survey_docs = tuple(
        _doc(
            str(candidate["doc_id"]),
            str(candidate["title"]),
            str(candidate["text"]),
        )
        for candidate in candidates
    )
    survey_docs = (
        *survey_docs,
        _doc("doc-verif-db", "Verification protocol", str(spec["verif_db_text"])),
        _doc("doc-exception-x", "Platform constraints memo", str(spec["exception_memo_text"])),
    )
    constraint_doc = _doc(
        "doc-constraint-k",
        "New migration constraint",
        str(spec["constraint_text"]),
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
    base_rule_change = _doc(
        "doc-rule-change",
        "Verification protocol revision notice",
        str(spec["rule_change_text"]),
    )
    rule_change_doc = DocumentRef(
        doc_id=base_rule_change.doc_id,
        title=base_rule_change.title,
        text=base_rule_change.text,
        source_url=base_rule_change.source_url,
        retrieved_date=base_rule_change.retrieved_date,
        superseded_by="doc-verif-db",
    )
    legal_plans = spec["legal_plans"]
    assert isinstance(legal_plans, tuple)
    required_checks = spec["required_checks"]
    assert isinstance(required_checks, dict)
    scope = spec["rule_change_scope"]
    assert isinstance(scope, tuple)
    plan_requirements = spec["plan_requirements"]
    assert isinstance(plan_requirements, dict)

    information_scale_tokens = sum(1 + len(doc.text.split()) for doc in survey_docs)
    return LifecycleInstance(
        instance_id=instance_id,
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    f"[{str(spec['plan_note']).capitalize()} project] Survey the "
                    "plan documents and the verification protocol. Build your "
                    "working notes; they are your only carry-forward — later "
                    "stages will not re-show these documents (re-reading is "
                    "available at a ledgered cost through your own tool "
                    "surface)."
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
                    "and satisfy the domain constraint. No documents are "
                    "attached."
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
                    "legal_plans": list(legal_plans),
                    "plan_requirements": {
                        plan: dict(requirement) for plan, requirement in plan_requirements.items()
                    },
                    "current_revision": 2,
                    "revision_scope": list(scope),
                },
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=legal_plans[0],
        sandbox_spec={
            "records": [_COMMIT_RECORD, _STATUS_RECORD, _VERIF_RECORD],
            "action_kinds": ["create_record", "update_record", "finalize"],
        },
        answer_aliases=legal_plans,
    )


def variant_commit_action(spec_id: str, plan: str, *, refs: tuple[str, ...]) -> Action:
    """The participant-emitted commit finalize for a variant world."""

    for spec in _VARIANT_SPECS:
        if spec["spec_id"] == spec_id:
            scope = spec["rule_change_scope"]
            assert isinstance(scope, tuple)
            plan_requirements = spec["plan_requirements"]
            assert isinstance(plan_requirements, dict)
            requirement = plan_requirements.get(plan)
            return Action(
                kind="finalize",
                record_id=_COMMIT_RECORD,
                fields={"plan": plan, "status": "final"},
                provenance=refs,
                precondition_refs=refs,
                precondition_current_revision=2,
                precondition_revision_scope=scope,
                precondition_scope_constraint=(
                    dict(requirement) if isinstance(requirement, Mapping) else None
                ),
            )
    raise ValueError(f"unknown research-v3 variant spec: {spec_id!r}")


__all__ = [
    "build_research_v3_variant",
    "variant_commit_action",
    "variant_world_specs",
]
