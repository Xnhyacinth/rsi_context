"""Research-v4 "dossier" — the A-group main task (persistent evidence synthesis).

The R1 longitudinal slice. One mother world: a supplier-selection project
over a LARGE dossier. What makes the three long-axis commitments REAL
(not labels):

- LONG CONTEXT: a 20-supplier survey (~5K words + protocol + memo) where
  the decisive information is DISTANT — the winning candidate's
  qualification rides on an exception clause in supplier card 03 plus a
  check named only in the protocol doc, while a superficially-strong
  competitor carries a buried disqualifier in card 17. The state byte
  cap (64K) makes "retain everything verbatim + run state" costly:
  remembering vs re-reading (metered) is a genuine strategy trade.
- LONG MEMORY: two follow_up stages AFTER the commit, each requiring
  conclusions from the far-back survey — follow-up 1 answers a NEW
  in-scope question whose legality hinges on an exception clause in
  card 05; follow-up 2 arrives after a FINAL rule change that
  supersedes exactly one check, so only a participant tracking
  which-check-belongs-to-which-scope updates the right conclusion.
- LONG HORIZON: 8 stages; decisions at stages 5/7 depend on evidence
  from stage 1 (4+ stages of separation), across one commit.

Load-bearing ledger (the review's hard requirement: removing material
must remove EXPLAINABLE information, not just lower a score):
- card 03's exception clause -> the ONLY source that qualifies the
  winning candidate's domain for the required check.
- card 17's buried condition -> the ONLY disqualifier of the decoy.
- card 05's exception -> the ONLY basis for follow-up 1's legality.
- card 08's properties -> the only facts follow-up 1 asks about.
- protocol doc -> names the checks; the scope of the final rule change.
Everything else in the corpus is plausible bulk (context pressure), each
suppler real-valued (a legal-but-weak alternative exists: no card is a
lie).

Two distinct legal paths (the acceptance the review demanded):
1. Remember: retain compressed conclusions at stage 1, answer later
   stages from memory (cheap on rereads, must not lose the four
   load-bearing details).
2. Re-read: keep minimal memory, re-read the registry at each decision
   point (metered tool cost, robust to forgetting).

Simple-legal-wins rule: rereading everything is NOT penalized beyond
its metered cost; if the memory-light policy is cheaper and correct, it
wins — the task does not forbid it.
"""

from __future__ import annotations

from rsicontext.lifecycle.env import Action
from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY = "research-v4"
_COMMIT_RECORD = "migration_commit"
_STATUS_RECORD = "candidate_status"
_CONCLUSION_RECORD = "followup_conclusion"

#: The supplier dossier. Each card is ~10 lines of plausible bulk plus,
#: where marked, one load-bearing line. Suppliers are named (not
#: single-letter) so extraction must read content, not doc order.
_SUPPLIERS: tuple[dict[str, object], ...] = (
    {
        "id": "card-01",
        "name": "northwind-logistics",
        "domain": "shipping",
        "text": (
            "Northwind Logistics operates regional freight with a mixed "
            "fleet. Standard SLA 48h. Pricing tier B. Regional coverage "
            "spans three districts; customs handling is outsourced. "
            "Insurance coverage is standard. The fleet renewal plan "
            "schedules partial replacement next year. Depot maintenance "
            "runs monthly. No exceptional clauses apply."
        ),
    },
    {
        "id": "card-02",
        "name": "harborline-freight",
        "domain": "shipping",
        "text": (
            "Harborline Freight specializes in port-to-port container "
            "moves. Standard SLA 24h. Pricing tier A. Their cold-chain "
            "add-on is certified. Documentation turnaround is two days. "
            "Track-and-trace covers port legs only. Holiday surcharges "
            "apply in peak season. Customs paperwork is handled in-house."
        ),
    },
    {
        "id": "card-03",
        "name": "atlas-carriage",
        "domain": "shipping",
        "text": (
            "Atlas Carriage runs cross-border carriage with customs "
            "bonding. Standard SLA 36h. Pricing tier B. Exception clause: "
            "Atlas Carriage is the only tier-B carrier whose bonded "
            "corridor satisfies the customs-preclearance check — the "
            "corridor agreement covers all five northern checkpoints."
        ),
        # LOAD-BEARING: the ONLY qualification of the winning candidate.
    },
    {
        "id": "card-04",
        "name": "quill-stationery",
        "domain": "office",
        "text": (
            "Quill Stationery supplies standard office consumables. "
            "Pricing tier C. Delivery is weekly consolidated. Catalog "
            "spans 4000 SKUs. Contract minimums are low. No special "
            "clauses; they are a bulk supplier."
        ),
    },
    {
        "id": "card-05",
        "name": "beacon-power",
        "domain": "energy",
        "text": (
            "Beacon Power provides grid-tied supply for industrial sites. "
            "Pricing tier B. Their standard contract has a curtailment "
            "clause during regional shortages. Exception clause: "
            "hospital-adjacent facilities are exempt from curtailment "
            "under the mutual-aid annex, and this exemption transfers "
            "with the site's supply contract."
        ),
        # LOAD-BEARING: follow-up 1's legality basis.
    },
    {
        "id": "card-06",
        "name": "granite-consulting",
        "domain": "services",
        "text": (
            "Granite Consulting offers process audits. Pricing tier A. "
            "Engagements run six weeks. Their auditors are certified in "
            "two frameworks. Reports include an executive summary. "
            "Follow-up workshops are billed separately."
        ),
    },
    {
        "id": "card-07",
        "name": "sable-cleaning",
        "domain": "services",
        "text": (
            "Sable Cleaning covers facility maintenance contracts. "
            "Pricing tier C. Night shifts carry a small premium. "
            "Equipment is owned by Sable. Staffing rotates weekly. "
            "No exceptional clauses apply."
        ),
    },
    {
        "id": "card-08",
        "name": "vesper-instruments",
        "domain": "lab",
        "text": (
            "Vesper Instruments manufactures calibration probes. Pricing "
            "tier A. Their calibration certificates are accredited to "
            "the national metrology institute. Probe recalibration is "
            "annual. Shipping requires protective crating. Their "
            "northern service hub covers the five northern checkpoints "
            "under the same corridor agreement framework."
        ),
        # LOAD-BEARING: follow-up 1's asked-about facts.
    },
    {
        "id": "card-09",
        "name": "lumen-lighting",
        "domain": "office",
        "text": (
            "Lumen Lighting supplies commercial fixtures. Pricing tier B. "
            "Their catalog covers 1200 models. Lead times are two weeks. "
            "Bulk discounts start at fifty units. Returns require "
            "original packaging. No special clauses."
        ),
    },
    {
        "id": "card-10",
        "name": "kestrel-messaging",
        "domain": "services",
        "text": (
            "Kestrel Messaging runs courier routes in the metro area. "
            "Standard SLA 4h. Pricing tier C. Riders carry insurance. "
            "Cash-on-delivery is supported. Coverage excludes the "
            "northern industrial zone after 22:00."
        ),
    },
    {
        "id": "card-11",
        "name": "orbit-hosting",
        "domain": "it",
        "text": (
            "Orbit Hosting provides colocation racks. Pricing tier A. "
            "Uptime SLA 99.9%. Remote hands are billed hourly. Their "
            "fire suppression is gas-based. Rack migration support "
            "costs extra. No exceptional clauses."
        ),
    },
    {
        "id": "card-12",
        "name": "ferrous-alloys",
        "domain": "materials",
        "text": (
            "Ferrous Alloys supplies structural stock. Pricing tier B. "
            "Mill certificates ship with each lot. Minimum order is one "
            "tonne. Lead times vary by grade. Their rolling schedule "
            "runs quarterly."
        ),
    },
    {
        "id": "card-13",
        "name": "pinewood-furniture",
        "domain": "office",
        "text": (
            "Pinewood Furniture manufactures bench seating. Pricing tier "
            "C. Assembly is tool-free. Warranty runs three years. Bulk "
            "orders ship flat-packed. No special clauses apply."
        ),
    },
    {
        "id": "card-14",
        "name": "delta-catering",
        "domain": "services",
        "text": (
            "Delta Catering covers event food service. Pricing tier B. "
            "Minimum headcount is twenty. Their cold chain is certified. "
            "Menu rotation is seasonal. Staffing is per-event."
        ),
    },
    {
        "id": "card-15",
        "name": "cobalt-chemicals",
        "domain": "materials",
        "text": (
            "Cobalt Chemicals supplies reagent grades. Pricing tier A. "
            "Hazmat shipping is mandatory. Certificates of analysis "
            "accompany each batch. Storage temperature bands are strict."
        ),
    },
    {
        "id": "card-16",
        "name": "ridgefield-security",
        "domain": "services",
        "text": (
            "Ridgefield Security offers site guarding. Pricing tier A. "
            "Response SLA 10 minutes. Guards are licensed. Patrol "
            "reporting is digital. Coverage maps are audited yearly."
        ),
    },
    {
        "id": "card-17",
        "name": "pinnacle-courier",
        "domain": "shipping",
        "text": (
            "Pinnacle Courier runs same-day metro delivery with the "
            "newest fleet and the best headline SLA (2h) at tier B — "
            "on paper the strongest candidate. Buried condition: their "
            "customs bonding lapsed last quarter and is pending renewal, "
            "so the customs-preclearance check fails for Pinnacle "
            "Couriers until renewal completes."
        ),
        # LOAD-BEARING: the decoy's disqualifier.
    },
    {
        "id": "card-18",
        "name": "willow-packaging",
        "domain": "materials",
        "text": (
            "Willow Packaging supplies custom crates. Pricing tier C. "
            "Design lead time is five days. Their protective crating "
            "meets transit standards. Reuse programs are available."
        ),
    },
    {
        "id": "card-19",
        "name": "silverline-audit",
        "domain": "services",
        "text": (
            "Silverline Audit performs financial reviews. Pricing tier "
            "B. Engagements run four weeks. Two partner sign-off is "
            "standard. Their sampling methodology is documented."
        ),
    },
    {
        "id": "card-20",
        "name": "ember-heating",
        "domain": "energy",
        "text": (
            "Ember Heating installs site boilers. Pricing tier B. "
            "Servicing is semi-annual. Their engineers hold pressure-"
            "system certification. Warranty covers parts only."
        ),
    },
)

#: The world's checks: customs-preclearance (the commit's requirement,
#: superseded by the FINAL rule change — the long-memory trap) and
#: cold-chain-integrity (unaffected, so follow-up 2 must NOT touch it).
_VERIFICATION_ORACLE: dict[str, dict[str, bool]] = {
    "customs-preclearance": {
        "atlas-carriage": True,
        "pinnacle-courier": False,
        "harborline-freight": False,
        "northwind-logistics": False,
    },
    "cold-chain-integrity": {
        "atlas-carriage": True,
        "harborline-freight": True,
        "pinnacle-courier": False,
    },
}

_LEGAL_PLANS: tuple[str, ...] = ("atlas-carriage",)


def _doc(doc_id: str, title: str, text: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=f"v4:{doc_id}",
        retrieved_date="2026-09-23",
    )


def _filler_cards(count: int) -> tuple[dict[str, object], ...]:
    """Deterministic bulk supplier cards for corpus scaling.

    LONG-CONTEXT scaling (the honest axis): the load-bearing facts stay
    single-source; the filler enlarges the search space so the reread-
    vs-remember trade and the information-selection pressure grow with
    ``bulks``. Filler cards are plausible, never lie, and never repeat
    a load-bearing string.
    """

    out: list[dict[str, object]] = []
    adjectives = ("regional", "metro", "coastal", "inland", "highland", "valley")
    services = (
        "packaging review",
        "route planning",
        "inventory audit",
        "staff training",
        "site survey",
        "records archiving",
    )
    tiers = ("C", "B", "A")
    for index in range(count):
        name = f"filling-{index:03d}-partners"
        out.append(
            {
                "id": f"card-f{index:03d}",
                "name": name,
                "domain": "services",
                "text": (
                    f"{name.replace('-', ' ').title()} provides "
                    f"{services[index % len(services)]} on a "
                    f"{adjectives[index % len(adjectives)]} basis. Pricing "
                    f"tier {tiers[index % len(tiers)]}. Contracts run "
                    "monthly. Their intake desk answers within two days. "
                    "Reporting is quarterly. No exceptional clauses apply."
                ),
            }
        )
    return tuple(out)


def build_research_v4_dossier(
    *,
    instance_id: str = "research-v4-dossier-0001",
    bulk_cards: int = 0,
) -> LifecycleInstance:
    """Build the dossier mother world (one per A-group slice).

    ``bulk_cards`` deterministically enlarges the survey corpus (the
    long-context scaling axis). At 0 the slice exercises STRUCTURE
    (horizon + memory, both load-bearing); higher values add
    information-selection pressure. The load-bearing ledger is
    unchanged: filler never carries decisive strings.
    """

    suppliers = (*_SUPPLIERS, *_filler_cards(bulk_cards))
    survey_docs = tuple(
        _doc(str(supplier["id"]), f"Supplier card: {supplier['name']}", str(supplier["text"]))
        for supplier in suppliers
    )
    survey_docs = (
        *survey_docs,
        _doc(
            "doc-v4-verif-db",
            "Supplier verification protocol",
            (
                "The verification protocol defines two checks for this "
                "project: the customs-preclearance check (bonded-corridor "
                "coverage) and the cold-chain-integrity check. Protocol "
                "revision 1 applies to both. Cross-border carriage "
                "candidates for the primary award must carry a passing "
                "customs-preclearance verification at the current "
                "protocol revision."
            ),
        ),
        _doc(
            "doc-v4-memo",
            "Sourcing memo",
            (
                "Procurement notes: the primary award is a cross-border "
                "carriage contract. Award eligibility is determined by the "
                "verification protocol's checks — read the supplier cards "
                "carefully; headline SLA alone is not a basis for award. "
                "Keep working notes — later questions will not re-show "
                "these cards (re-reading is available at a ledgered cost "
                "through your own tool surface)."
            ),
        ),
    )
    constraint_doc = _doc(
        "doc-v4-constraint",
        "Award constraint",
        (
            "Scope: this constraint applies to the primary award only. "
            "The awarded carrier must hold a PASSING customs-preclearance "
            "verification at the current protocol revision; candidates "
            "without bonded-corridor coverage are ineligible."
        ),
    )
    delegation_doc = _doc(
        "doc-v4-delegation",
        "Delegation surface",
        (
            "A bounded sub-agent may be asked to verify a named supplier "
            "card against a named check. A usable return carries finding, "
            "source doc id, and applicability condition."
        ),
    )
    rule_change_doc = _doc(
        "doc-v4-rule-change-1",
        "Protocol revision notice (mid-project)",
        (
            "Scope: this revision supersedes the cold-chain-integrity "
            "check documentation only (documentation update; no threshold "
            "change). Protocol revision 2 applies to documentation. The "
            "customs-preclearance check is unaffected."
        ),
    )
    followup_1_doc = _doc(
        "doc-v4-followup-1",
        "Follow-up request: calibration partner",
        (
            "A lab calibration partner is needed for the awarded "
            "corridor's checkpoints. Answer with the instrument supplier "
            "whose northern service hub covers the same five northern "
            "checkpoints under the corridor agreement framework, and "
            "create a followup_conclusion record naming that supplier. "
            "No supplier cards are re-attached."
        ),
    )
    final_rule_change_doc = _doc(
        "doc-v4-rule-change-2",
        "Protocol revision notice (final)",
        (
            "Scope: this revision supersedes the customs-preclearance "
            "check only. Protocol revision 3 tightens corridor "
            "requirements. customs-preclearance verifications performed "
            "under revision 1 are stale for any NEW award decision; "
            "evidence for unaffected checks (cold-chain-integrity) "
            "remains valid."
        ),
    )
    followup_2_doc = _doc(
        "doc-v4-followup-2",
        "Follow-up request: corridor re-award review",
        (
            "The corridor contract is up for a scope review. Determine "
            "whether the customs-preclearance evidence backing the "
            "current award is still current, and create a followup_"
            "conclusion record with status='reverify' if the evidence is "
            "stale under the current protocol revision, or "
            "status='current' otherwise. No supplier cards are "
            "re-attached."
        ),
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
                    "[Supplier-selection project] Survey the supplier "
                    "cards and the verification protocol. Build your "
                    "working notes; they are your only carry-forward — "
                    "later stages and FOLLOW-UP REQUESTS will not re-show "
                    "these cards (re-reading is available at a ledgered "
                    "cost through your own tool surface)."
                ),
                documents=survey_docs,
                # Gold ids are DERIVED from the supplier tuple (minus the
                # protocol doc) so corpus modifications (removal
                # simulations) stay grammar-consistent automatically.
                gold_evidence_ids=(
                    *(
                        str(supplier["id"])
                        for supplier in suppliers
                        if str(supplier["id"]) in ("card-03", "card-17", "card-05", "card-08")
                    ),
                    "doc-v4-verif-db",
                ),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A new constraint arrives (document attached). From "
                    "your retained notes, determine which candidate "
                    "carriers fall under its scope and what it requires."
                ),
                documents=(constraint_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text=(
                    "You may delegate verification of a candidate to a "
                    "bounded sub-agent over the attached surface."
                ),
                documents=(delegation_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached): the verification "
                    "protocol revision changed. Note the SCOPE of the "
                    "supersession."
                ),
                documents=(rule_change_doc,),
                gold_evidence_ids=(),
                rule_change_effect=2,
                # R1.1: documentation-only update — EMPTY scope. The
                # wall clock advances; no check's evidence is
                # invalidated (the s4 trap: the public rule says the
                # cold-chain update affects documentation only, so the
                # env must NOT let it stale the customs evidence a
                # correct system acquired at s2 and never re-verified).
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the primary award: create and finalize "
                    f"record {_COMMIT_RECORD} naming the chosen carrier "
                    "with candidate status records and verification runs "
                    "it relies on. The award gate requires a passing "
                    "customs-preclearance verification at the CURRENT "
                    "protocol revision."
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
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 1,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=_VERIFICATION_ORACLE,
            ),
            StageSpec(
                stage_id="s6-followup-1",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Answer from "
                    "retained conclusions or re-read at cost, then write "
                    "the conclusion record."
                ),
                documents=(followup_1_doc,),
                gold_evidence_ids=(),
                expected_state_delta={
                    f"{_CONCLUSION_RECORD}-calibration": {"supplier": "vesper-instruments"}
                },
            ),
            StageSpec(
                stage_id="s7-rule-change-2",
                kind="rule_change",
                prompt_text=(
                    "Final rule change (document attached). Determine "
                    "which of your retained conclusions are invalidated."
                ),
                documents=(final_rule_change_doc,),
                gold_evidence_ids=(),
                rule_change_effect=3,
                # R1.1: the REAL supersession — customs-preclearance only.
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="s8-followup-2",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Record the "
                    "currency status of the award's backing evidence."
                ),
                documents=(followup_2_doc,),
                gold_evidence_ids=(),
                expected_state_delta={
                    # Placeholder: overridden at grade time by the
                    # evidence_currency derivation (R1.1 Option A) —
                    # the correct answer depends on the ACTUAL evidence
                    # history (any stale in-scope citation -> reverify;
                    # all current -> current; no in-scope evidence
                    # cited -> no-evidence).
                    f"{_CONCLUSION_RECORD}-corridor": {"status": "reverify"}
                },
                commit_precondition={
                    "evidence_currency": {
                        "commit_record": _COMMIT_RECORD,
                        "check": "customs-preclearance",
                        "record_id": f"{_CONCLUSION_RECORD}-corridor",
                        "field": "status",
                        "stale_value": "reverify",
                        "current_value": "current",
                        # A commit citing no in-scope evidence: an
                        # explicit third diagnosis (never the optimistic
                        # 'current' default) — the participant's answer
                        # mismatches it and the follow-up fails.
                        "missing_value": "no-evidence",
                    }
                },
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=6,
            action_dependency="strong",
            environment_changes=2,
        ),
        answer_norm=_LEGAL_PLANS[0],
        sandbox_spec={
            "records": [_COMMIT_RECORD, _STATUS_RECORD, "followup_conclusion"],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=_LEGAL_PLANS,
    )


def followup_conclusion_action(record_id: str, fields: dict[str, object]) -> Action:
    """A follow-up conclusion write (the v4 longitudinal answer records)."""

    return Action(kind="create_record", record_id=record_id, fields=dict(fields))


__all__ = ["build_research_v4_dossier", "followup_conclusion_action"]
