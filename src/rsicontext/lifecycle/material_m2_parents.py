"""M2 task-validity parents — GENUINELY DIFFERENT worlds, not name-swaps.

The M2 axis (2026-09-24): the dossier family's existing variety
permutes FACTS over one dependency structure (mirror: another winner,
another superseded check). The parents below change the STRUCTURE:

- ``aurora-swap`` (research-v4): a new (winner x supersession x
  calibration) CELL, not a name-swap. The winner/decoy card-role
  assignment matches the mirror's layout (the winner's qualification
  clause on card-02, the decoy's disqualifier on card-01, the
  mother's card-03/17 demoted to plain bulk); what distinguishes it
  from BOTH existing worlds is the recombination: s7 supersedes
  CUSTOMS-preclearance (the mother's scope — so the s8 currency
  diagnosis flips to "reverify", where the mirror's cold-chain scope
  yields "current") and the calibration answer stays the mother's
  (vesper/card-08). Aurora also rephrases the winner clause itself
  ("bonded port-corridor", distinct needle strings from the mirror's
  port-side cold-chain phrasing). The s4 documentation-only rule
  change keeps its empty scope.
- ``vector`` (research-v4): the DECISION TYPE changes. The award
  constraint requires TWO passing checks (customs-preclearance AND
  cold-chain-integrity); the commit precondition's
  ``plan_requirements`` carries both under ``requires_check`` (a list
  — the runner gate demands a passing env-issued verification for
  each), and the plan that passes only one check FAILS. What "legal"
  means is different, not just which name is legal.
- ``b2`` (research-v5, B-group): a different session TOPOLOGY — FOUR
  sessions with TWO between-session mutations (a mid-pause flip of
  one check, then a second pause flipping a different one). The carry
  contract is unchanged; the second boundary stresses a carry that
  has already survived one mutation.
- ``c2`` (research-v5, C-group): a different recovery SHAPE — the
  session-1 oracle fails the top TWO ranked candidates (forcing a
  double-switch to a third), and the mutation renews only ONE of the
  two failed leaders, so the re-award answer differs from both the
  naive pick and the first recovery.

Every parent keeps the load-bearing LEDGER discipline (each decisive
proposition single-source), the TWO-distinct-legal-paths rule, and
the public-rules-match-the-gate invariant (the C-group M1 pattern).
All builders COMPOSE from the existing modules (the mother corpus,
the variant machinery, the session builders) — no new env machinery.
"""

from __future__ import annotations

from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY_V4 = "research-v4"
_FAMILY_V5 = "research-v5"
_COMMIT = "migration_commit"
_STATUS_RECORD = "candidate_status"
_CONCLUSION_RECORD = "followup_conclusion"


# =========================================================================
# A-group parent 1: aurora-swap (dependency structure inverted)
# =========================================================================
#
# The mother ledger: card-03 (atlas) carries the ONLY qualification;
# card-17 (pinnacle) the ONLY disqualifier. aurora-swap INVERTS the
# graph: card-02 (harborline, the mother's plain bulk) becomes the
# single-source qualification; card-03 becomes plain bulk; the decoy
# disqualifier moves to card-01 (northwind — the mirror's decoy slot,
# so the surface phrasing is related but the STRUCTURAL role is
# different from both existing worlds: here the winner is a tier-A
# port carrier qualified by a bonded CORRIDOR CLAUSE, not a swap of
# the mirror's cold-chain phrasing).
#
# Load-bearing ledger (aurora-swap):
# - card-02's exception clause -> the ONLY source qualifying
#   harborline-freight for customs-preclearance.
# - card-01's buried condition -> the ONLY disqualifier of the decoy
#   (northwind, superficially fine, bonding lapsed).
# - card-05 / card-08 / protocol / constraint / rule-change scopes:
#   unchanged from the mother (the follow-up decisions and the
#   long-memory traps keep their single sources).
_AURORA_WINNER = "harborline-freight"
_AURORA_WINNER_CARD = "card-02"
_AURORA_DECOY = "northwind-logistics"
_AURORA_DECOY_CARD = "card-01"
#: The decisive needle phrases (single-source pins in tests).
_AURORA_WINNER_NEEDLE = "bonded port-corridor"
_AURORA_DECOY_NEEDLE = "depot bonding lapsed"

_AURORA_WINNER_CLAUSE = (
    "Exception clause: Harborline Freight's port cluster is bonded "
    "under the northern customs corridor agreement — the bonded "
    "port-corridor satisfies the customs-preclearance check for all "
    "five northern checkpoints, the only tier-A carrier so qualified."
)
_AURORA_DECOY_CLAUSE = (
    "On paper a strong regional candidate. Buried condition: their "
    "depot bonding lapsed last quarter and is pending renewal, so the "
    "customs-preclearance check fails for Northwind Logistics until "
    "renewal completes."
)
#: card-03's mother text becomes plain bulk (the tail after the
#: exception clause, closed off — worded to avoid the extractor's
#: "exception clause" needle so the card reads as bulk to a
#: clause-scanning worker too).
_AURORA_CARD03_PLAIN = (
    "Atlas Carriage runs cross-border carriage with customs bonding. "
    "Standard SLA 36h. Pricing tier B. Corridor coverage is marketed "
    "but carries no current exception provisions."
)
#: card-17's mother decoy becomes plain bulk.
_AURORA_CARD17_PLAIN = (
    "Pinnacle Courier runs same-day metro delivery with the newest "
    "fleet and the best headline SLA (2h) at tier B. Bonding paperwork "
    "is current and routine."
)

_AURORA_ORACLE: dict[str, dict[str, bool]] = {
    "customs-preclearance": {
        "harborline-freight": True,
        "northwind-logistics": False,
        "atlas-carriage": False,
        "pinnacle-courier": False,
    },
    "cold-chain-integrity": {
        "atlas-carriage": True,
        "harborline-freight": True,
        "pinnacle-courier": False,
    },
}

_AURORA_LEGAL = ("harborline-freight",)


def build_aurora_swap(
    *,
    instance_id: str = "research-v4-aurora-swap-0001",
) -> LifecycleInstance:
    """Build the aurora-swap A-parent (the dependency graph inverted).

    Reuses the mother constructor with the supplier tuple patched (the
    same patch discipline ``dossier_variants`` established), then
    adjusts the three world-specific pins: the s5 gate's legal set and
    requirement (keyed to the new winner), and nothing else — the s4
    empty-scope rule change and the s7 customs supersession keep their
    structure (the aurora-swap axis is WHERE the load-bearing clause
    lives, not how the rule changes behave).
    """

    import rsicontext.lifecycle.material_v4_dossier as dossier
    from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier

    original_suppliers = dossier._SUPPLIERS
    original_oracle = dossier._VERIFICATION_ORACLE
    original_legal = dossier._LEGAL_PLANS
    patched: list[dict[str, object]] = []
    for supplier in original_suppliers:
        entry = dict(supplier)
        if entry["id"] == _AURORA_WINNER_CARD:
            base = str(entry["text"]).split("Their cold-chain")[0].rstrip()
            entry["text"] = base + " " + _AURORA_WINNER_CLAUSE
        elif entry["id"] == _AURORA_DECOY_CARD:
            base = str(entry["text"]).split("Depot maintenance")[0].rstrip()
            entry["text"] = base + " " + _AURORA_DECOY_CLAUSE
        elif entry["id"] == "card-03":
            entry["text"] = _AURORA_CARD03_PLAIN
        elif entry["id"] == "card-17":
            entry["text"] = _AURORA_CARD17_PLAIN
        patched.append(entry)
    dossier._SUPPLIERS = tuple(patched)
    dossier._VERIFICATION_ORACLE = _AURORA_ORACLE
    dossier._LEGAL_PLANS = _AURORA_LEGAL
    try:
        inst = build_research_v4_dossier(instance_id=instance_id)
        # The constructor's s5 plan_requirements is keyed to
        # atlas-carriage; re-key to the aurora winner (the same
        # late-report fix discipline the mirror variant carries).
        stages = list(inst.stages)
        # The constructor's s1 gold ids point at the MOTHER's
        # load-bearing cards; aurora's own are card-02 (the winner
        # qualification), card-01 (the decoy disqualifier), card-05
        # and card-08 (the follow-ups' facts, unchanged).
        s1 = stages[0]
        gold = (
            *(
                str(supplier["id"])
                for supplier in patched
                if str(supplier["id"]) in ("card-02", "card-01", "card-05", "card-08")
            ),
            "doc-v4-verif-db",
        )
        stages[0] = s1.__class__(
            stage_id=s1.stage_id,
            kind=s1.kind,
            prompt_text=s1.prompt_text,
            documents=s1.documents,
            gold_evidence_ids=gold,
        )
        s5 = stages[4]
        precondition = dict(s5.commit_precondition or {})
        precondition["legal_plans"] = list(_AURORA_LEGAL)
        precondition["plan_requirements"] = {
            _AURORA_WINNER: {
                "domain": "shipping",
                "requires_check": "customs-preclearance",
            }
        }
        stages[4] = s5.__class__(
            stage_id=s5.stage_id,
            kind=s5.kind,
            prompt_text=s5.prompt_text,
            documents=s5.documents,
            gold_evidence_ids=s5.gold_evidence_ids,
            expected_state_delta=s5.expected_state_delta,
            expected_aliases=s5.expected_aliases,
            commit_precondition=precondition,
            verification_oracle=s5.verification_oracle,
            rule_change_effect=s5.rule_change_effect,
            rule_change_scope=s5.rule_change_scope,
        )
        import dataclasses

        return dataclasses.replace(inst, stages=tuple(stages))
    finally:
        dossier._SUPPLIERS = original_suppliers
        dossier._VERIFICATION_ORACLE = original_oracle
        dossier._LEGAL_PLANS = original_legal


# =========================================================================
# A-group parent 2: vector (the decision TYPE: two required checks)
# =========================================================================
#
# The mother's "legal" = one passing customs-preclearance verification.
# vector's "legal" = TWO passing checks (customs-preclearance AND
# cold-chain-integrity) on the SAME subject. The mother corpus already
# carries cold-chain facts (card-02's certified add-on); vector adds a
# cold-chain exception clause to the MOTHER winner's card (card-03) so
# the winner's cold-chain qualification is also SINGLE-SOURCE, and
# makes card-14 (delta-catering, cold-chain certified but NOT
# customs-bonded) the one-check passer that must now FAIL.
#
# Load-bearing ledger (vector):
# - card-03's bonded-corridor clause -> customs qualification (mother).
# - card-03's NEW cold-chain exception clause -> the ONLY source
#   qualifying the winner for cold-chain-integrity (single-source).
# - card-14 (delta-catering) is the one-check trap: cold-chain
#   certified, NOT a bonded carrier — reading either card alone
#   misleads; the DECISION TYPE (both checks) is what carries.
_VECTOR_WINNER = "atlas-carriage"
_VECTOR_WINNER_CARD = "card-03"
_VECTOR_ONE_CHECK_TRAP = "delta-catering"
_VECTOR_COLD_CHAIN_NEEDLE = "cold-chain-annex"
_VECTOR_COLD_CHAIN_CLAUSE = (
    "Cold-chain exception clause: under the corridor's cold-chain-annex, "
    "Atlas Carriage's bonded corridor also satisfies the "
    "cold-chain-integrity check for the same five northern checkpoints."
)

_VECTOR_ORACLE: dict[str, dict[str, bool]] = {
    "customs-preclearance": {
        "atlas-carriage": True,
        "pinnacle-courier": False,
        "harborline-freight": False,
        "northwind-logistics": False,
    },
    "cold-chain-integrity": {
        "atlas-carriage": True,
        "delta-catering": True,
        "harborline-freight": False,
        "pinnacle-courier": False,
    },
}

_VECTOR_LEGAL = ("atlas-carriage",)


def build_vector(
    *,
    instance_id: str = "research-v4-vector-0001",
) -> LifecycleInstance:
    """Build the vector A-parent (the two-check decision type).

    Composes from the mother corpus with one card patched (card-03
    gains the cold-chain exception clause — the winner's SECOND
    qualification, single-source), the two-check constraint doc, and a
    commit precondition whose ``requires_check`` is a LIST. The s4
    doc-only trap and s7 customs supersession are unchanged; the
    vector axis is the gate's decision type.
    """

    import rsicontext.lifecycle.material_v4_dossier as dossier
    from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier

    original_suppliers = dossier._SUPPLIERS
    original_oracle = dossier._VERIFICATION_ORACLE
    original_legal = dossier._LEGAL_PLANS
    patched: list[dict[str, object]] = []
    for supplier in original_suppliers:
        entry = dict(supplier)
        if entry["id"] == _VECTOR_WINNER_CARD:
            base = str(entry["text"]).rstrip()
            entry["text"] = base + " " + _VECTOR_COLD_CHAIN_CLAUSE
        patched.append(entry)
    dossier._SUPPLIERS = tuple(patched)
    dossier._VERIFICATION_ORACLE = _VECTOR_ORACLE
    dossier._LEGAL_PLANS = _VECTOR_LEGAL
    try:
        inst = build_research_v4_dossier(instance_id=instance_id)
        stages = list(inst.stages)
        # The two-check constraint doc (s2) — the public rule that
        # makes the two-check legal set DERIVABLE from the material.
        vector_constraint = DocumentRef(
            doc_id="doc-v4-constraint",
            title="Award constraint",
            text=(
                "[[doc:doc-v4-constraint]] Award constraint\n"
                "Scope: this constraint applies to the primary award only. "
                "The awarded carrier must hold BOTH a PASSING "
                "customs-preclearance verification AND a PASSING "
                "cold-chain-integrity verification at the current protocol "
                "revision. A candidate passing only one of the two checks "
                "is ineligible; the two checks are cumulative, not "
                "alternatives."
            ),
            source_url="v4:doc-v4-constraint",
            retrieved_date="2026-09-23",
        )
        s2 = stages[1]
        stages[1] = s2.__class__(
            stage_id=s2.stage_id,
            kind=s2.kind,
            prompt_text=(
                "A new constraint arrives (document attached). From "
                "your retained notes, determine which candidate "
                "carriers fall under its scope and what it requires."
            ),
            documents=(vector_constraint,),
            gold_evidence_ids=(),
        )
        # The two-check gate: requires_check as a LIST (the vector
        # decision type — every named check needs a passing env-issued
        # verification for the committed subject).
        s5 = stages[4]
        precondition = dict(s5.commit_precondition or {})
        precondition["legal_plans"] = list(_VECTOR_LEGAL)
        precondition["plan_requirements"] = {
            _VECTOR_WINNER: {
                "domain": "shipping",
                "requires_check": ["customs-preclearance", "cold-chain-integrity"],
            }
        }
        stages[4] = s5.__class__(
            stage_id=s5.stage_id,
            kind=s5.kind,
            prompt_text=(
                "Commit the primary award: create and finalize "
                f"record {_COMMIT} naming the chosen carrier with "
                "candidate status records and verification runs it "
                "relies on. The award gate requires BOTH a passing "
                "customs-preclearance verification AND a passing "
                "cold-chain-integrity verification at the CURRENT "
                "protocol revision — one check alone is not enough."
            ),
            documents=s5.documents,
            gold_evidence_ids=s5.gold_evidence_ids,
            expected_state_delta=s5.expected_state_delta,
            expected_aliases=s5.expected_aliases,
            commit_precondition=precondition,
            verification_oracle=s5.verification_oracle,
            rule_change_effect=s5.rule_change_effect,
            rule_change_scope=s5.rule_change_scope,
        )
        # The verification protocol doc names BOTH checks as required
        # for the primary award (the second public rule source).
        survey_docs = list(stages[0].documents)
        vector_protocol = DocumentRef(
            doc_id="doc-v4-verif-db",
            title="Supplier verification protocol",
            text=(
                "[[doc:doc-v4-verif-db]] Supplier verification protocol\n"
                "The verification protocol defines two checks for this "
                "project: the customs-preclearance check (bonded-corridor "
                "coverage) and the cold-chain-integrity check. Protocol "
                "revision 1 applies to both. Cross-border carriage "
                "candidates for the primary award must carry a PASSING "
                "verification on BOTH checks at the current protocol "
                "revision — the checks are cumulative, not alternatives."
            ),
            source_url="v4:doc-v4-verif-db",
            retrieved_date="2026-09-23",
        )
        stages[0] = stages[0].__class__(
            stage_id=stages[0].stage_id,
            kind=stages[0].kind,
            prompt_text=stages[0].prompt_text,
            documents=tuple(
                vector_protocol if doc.doc_id == "doc-v4-verif-db" else doc for doc in survey_docs
            ),
            gold_evidence_ids=stages[0].gold_evidence_ids,
        )
        import dataclasses

        return dataclasses.replace(inst, stages=tuple(stages))
    finally:
        dossier._SUPPLIERS = original_suppliers
        dossier._VERIFICATION_ORACLE = original_oracle
        dossier._LEGAL_PLANS = original_legal


# =========================================================================
# B-group parent: b2 (four sessions, TWO between-session mutations)
# =========================================================================
#
# b1's topology: 3 sessions, ONE between-session mutation (rev-3
# customs supersession). b2's: FOUR sessions, TWO mutations —
#   session 1: the project's first phase (survey -> commit at rev 1),
#              the SAME six-stage shape as b1's session 1;
#   [pause 1]  mutation A (between sessions 1-2): customs superseded
#              to rev 3 (b1's own between-session notice);
#   session 2: resume, re-award with fresh rev-3 evidence;
#   [pause 2]  mutation B (between sessions 2-3): a SECOND notice
#              superseding cold-chain-integrity to rev 4 — a DIFFERENT
#              check from mutation A, so a carry distilled after pause
#              1 can be stale in a NEW way after pause 2;
#   session 3: resume again, a calibration + currency follow-up pair
#              (the currency diagnosis must now see BOTH mutations);
#   session 4: the fresh-project non-transfer trap (b1's session-3
#              shape, the mirror corpus) — misapplying sessions 1-3's
#              conclusions must fail.
#
# Nine graded decisions (the panel's _b_decision_rules): the six b1
# needles (s1_award, s2_calibration, s2_currency, s2_reaward_fresh,
# s3_* renamed s4_* for b2's fourth session) plus the three the
# second boundary adds (b2_s3_calibration, b2_s3_currency,
# b2_s3_reaward_fresh).
_B2_ORACLE = {
    "customs-preclearance": {
        "atlas-carriage": True,
        "pinnacle-courier": False,
        "harborline-freight": False,
        "northwind-logistics": False,
    },
    "cold-chain-integrity": {
        "atlas-carriage": True,
        "harborline-freight": True,
    },
}


def build_b2_sessions() -> tuple[LifecycleInstance, ...]:
    """Build the four session instances of task b2 (in order).

    Composed from b1's own builders (sessions 1-2 of b1 become
    sessions 1-2 of b2 verbatim — the first mutation IS b1's); the new
    material is session 3 (the second mutation's resume + follow-ups)
    and session 4 (the fresh-project trap, b1's session-3 shape).
    """

    from rsicontext.lifecycle.dossier_variants import build_dossier_variant
    from rsicontext.lifecycle.material_b_group import build_b1_sessions
    from rsicontext.lifecycle.spec import DocumentRef as _Doc

    b1 = build_b1_sessions()
    mirror = build_dossier_variant("mirror")

    def _doc(doc_id: str, title: str, text: str, source: str) -> _Doc:
        return _Doc(
            doc_id=doc_id,
            title=title,
            text=f"[[doc:{doc_id}]] {title}\n{text}",
            source_url=source,
            retrieved_date="2026-09-23",
        )

    # --- Session 1: b1's session 1 (survey -> commit rev 1), re-id'd --
    import dataclasses as _dc

    session1 = _dc.replace(b1[0], instance_id="research-v5-b2-s1-0001")

    # --- Session 2: b1's session 2 (mutation A + re-award), re-id'd --
    session2 = _dc.replace(b1[1], instance_id="research-v5-b2-s2-0001")

    # --- Session 3: mutation B (cold-chain -> rev 4) + follow-ups ----
    session3 = LifecycleInstance(
        instance_id="research-v5-b2-s3-0001",
        family=_FAMILY_V5,
        stages=(
            StageSpec(
                stage_id="b2-s3-start",
                kind="session_start",
                prompt_text=(
                    "SESSION RESUME (second pause). The project continues. "
                    "Carried state attached; everything else empty. The "
                    "sandbox is queryable; the registry re-read is "
                    "available at ledgered cost."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="b2-s3-rule-change-2",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached; arrived while the "
                    "project was paused AGAIN). Determine which of your "
                    "retained conclusions are NOW invalidated."
                ),
                documents=(
                    _doc(
                        "doc-b2-rule-change-2",
                        "Protocol revision notice (second pause)",
                        (
                            "Scope: this revision supersedes the "
                            "cold-chain-integrity check only. Protocol "
                            "revision 4 tightens cold-chain requirements. "
                            "cold-chain-integrity verifications performed "
                            "under earlier revisions are stale for any "
                            "NEW decision; customs-preclearance evidence "
                            "(already at revision 3) remains valid."
                        ),
                        "v5:b2:rule2",
                    ),
                ),
                gold_evidence_ids=(),
                rule_change_effect=4,
                rule_change_scope=("cold-chain-integrity",),
            ),
            StageSpec(
                stage_id="b2-s3-followup-calibration",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Answer from "
                    "carried conclusions or re-read at cost, then write "
                    "the conclusion record."
                ),
                documents=(b1[1].stages[2].documents[0],),
                gold_evidence_ids=(),
                expected_state_delta=b1[1].stages[2].expected_state_delta,
            ),
            StageSpec(
                stage_id="b2-s3-followup-currency",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Record the "
                    "currency status of the award's backing evidence "
                    "under the CURRENT protocol state (note: TWO "
                    "revisions have landed since the original award)."
                ),
                documents=(b1[1].stages[3].documents[0],),
                gold_evidence_ids=(),
                expected_state_delta=b1[1].stages[3].expected_state_delta,
                commit_precondition=b1[1].stages[3].commit_precondition,
            ),
            StageSpec(
                stage_id="b2-s3-re-award",
                kind="act_verify",
                prompt_text=(
                    "The corridor contract renews AGAIN: create and "
                    "finalize record corridor_reaward_2 (a NEW renewal "
                    "contract superseding corridor_reaward) naming the "
                    "awarded carrier. A second "
                    "renewal requires corridor_reaward to have been "
                    "finalized before this session began. The gate requires "
                    "customs-preclearance evidence at the CURRENT protocol "
                    "revision (revision 3 — unchanged by the second "
                    "notice); evidence issued under earlier revisions is "
                    "stale for this decision."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={"corridor_reaward_2": {"status": "final"}},
                commit_precondition={
                    "record_id": "corridor_reaward_2",
                    "plan_field": "plan",
                    "legal_plans": ["atlas-carriage"],
                    "plan_requirements": {
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 3,
                    "revision_scope": ["customs-preclearance"],
                    "prior_finalized_record": "corridor_reaward",
                },
            ),
            StageSpec(
                stage_id="b2-s3-end",
                kind="session_end",
                prompt_text="SESSION END. Only state['carry'] persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=1,
            dependency_distance_stages=4,
            persistence_span_resets=3,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION_RECORD, "corridor_reaward", "corridor_reaward_2"],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )

    # --- Session 4: the fresh-project trap (b1's session-3 shape) ----
    session4 = LifecycleInstance(
        instance_id="research-v5-b2-s4-0001",
        family=_FAMILY_V5,
        stages=(
            StageSpec(
                stage_id="n1-survey",
                kind="survey",
                prompt_text=b1[2].stages[0].prompt_text,
                documents=mirror.stages[0].documents,
                gold_evidence_ids=tuple(doc.doc_id for doc in mirror.stages[0].documents),
            ),
            StageSpec(
                stage_id="n2-constraint",
                kind="constraint_injection",
                prompt_text=b1[2].stages[1].prompt_text,
                documents=mirror.stages[1].documents,
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="n4-rule-change",
                kind="rule_change",
                prompt_text=b1[2].stages[2].prompt_text,
                documents=mirror.stages[3].documents,
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="n5-award",
                kind="act_verify",
                prompt_text=b1[2].stages[3].prompt_text,
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition=mirror.stages[4].commit_precondition,
                verification_oracle=mirror.stages[4].verification_oracle,
            ),
            StageSpec(
                stage_id="n6-followup-calibration",
                kind="follow_up",
                prompt_text=b1[2].stages[4].prompt_text,
                documents=mirror.stages[5].documents,
                gold_evidence_ids=(),
                expected_state_delta=mirror.stages[5].expected_state_delta,
            ),
            StageSpec(
                stage_id="n7-session-end",
                kind="session_end",
                prompt_text="SESSION END. Only state['carry'] persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(
                1 + len(d.text.split()) for d in mirror.stages[0].documents
            ),
            dependency_distance_stages=4,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="harborline-freight",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION_RECORD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("harborline-freight",),
    )
    return session1, session2, session3, session4


# =========================================================================
# C-group parent: c2 (double-switch recovery shape)
# =========================================================================
#
# c1's shape: session-1 oracle fails the TOP-ranked candidate (atlas),
# recovery = ONE switch to meridian. c2's shape: the oracle fails the
# top TWO ranked candidates — atlas (36h, the reading-level best) AND
# harborline (24h, the mother's tier-A port carrier, ranked second by
# SLA among visible customs-bonded candidates) — forcing a
# DOUBLE-SWITCH to a third carrier (card-c2-thule, added to the C
# survey exactly as card-c1-meridian was). The mutation renews only
# ONE of the two failed leaders (atlas), so the session-2 re-award
# answer (the public SLA rule: shortest first among eligible) is
# atlas — differing from BOTH the naive pick and the first recovery.
#
# Load-bearing ledger (c2): card-c2-thule is the ONLY visible third
# cross-border carrier (readable recovery target — the c1 M1 fix's
# pattern); the renewal notice names atlas ONLY (harborline's failure
# persists — the notice's eligibility sentence says so).
_C2_S1_ORACLE = {
    "customs-preclearance": {
        "atlas-carriage": False,  # leader 1: pending audit
        "harborline-freight": False,  # leader 2: bonded audit ALSO pending
        "thule-carriage": True,  # the double-switch recovery target
        "pinnacle-courier": False,
    },
}

_C2_S2_ORACLE = {
    "customs-preclearance": {
        "atlas-carriage": True,  # the mutation renews atlas ONLY
        "harborline-freight": False,  # its audit is still pending
        "thule-carriage": True,
        "pinnacle-courier": False,
    },
}


def build_c2_sessions() -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build the two session instances of task c2 (in order).

    Composes from c1's builders (the protocol/constraint/mutation doc
    texts and the session shapes); the differences are the two-leader
    failure oracle, the third recovery card, and the renewal notice's
    "harborline still pending" sentence.
    """

    from rsicontext.lifecycle.material_c_group import build_c1_sessions
    from rsicontext.lifecycle.material_v4_dossier import _SUPPLIERS
    from rsicontext.lifecycle.material_v4_dossier import _doc as mother_doc

    c1 = build_c1_sessions()

    survey_docs = (
        *tuple(
            mother_doc(str(s["id"]), f"Supplier card: {s['name']}", str(s["text"]))
            for s in _SUPPLIERS
        ),
        _c2_doc(
            "card-c2-thule",
            "Supplier card: thule-carriage",
            (
                "Thule Carriage runs cross-border carriage with customs "
                "bonding. Standard SLA 52h. Pricing tier B. Exception "
                "clause: Thule Carriage's bonded corridor satisfies the "
                "customs-preclearance check for the northern checkpoints."
            ),
            "v5:c2:thule",
        ),
        _c2_doc(
            "doc-c2-verif-db",
            "Supplier verification protocol",
            str(c1[0].stages[0].documents[-1].text),
            "v5:c2:protocol",
        ),
    )

    session1 = LifecycleInstance(
        instance_id="research-v5-c2-s1-0001",
        family=_FAMILY_V5,
        stages=(
            StageSpec(
                stage_id="c2-survey",
                kind="survey",
                prompt_text=c1[0].stages[0].prompt_text,
                documents=survey_docs,
                gold_evidence_ids=tuple(doc.doc_id for doc in survey_docs),
            ),
            StageSpec(
                stage_id="c2-constraint",
                kind="constraint_injection",
                prompt_text=c1[0].stages[1].prompt_text,
                documents=c1[0].stages[1].documents,
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c2-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the primary award: request verifications for "
                    "your candidate(s), read the outcomes, and finalize "
                    f"record {_COMMIT} naming a carrier whose verification "
                    "PASSED. The gate refuses a commit whose cited "
                    "evidence failed or is missing. Expect failures: the "
                    "top candidates' audits are pending this quarter."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition={
                    "record_id": _COMMIT,
                    "plan_field": "plan",
                    "legal_plans": ["thule-carriage"],
                    "plan_requirements": {
                        "thule-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 1,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=_C2_S1_ORACLE,
            ),
            StageSpec(
                stage_id="c2-session-end",
                kind="session_end",
                prompt_text=c1[0].stages[3].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(1 + len(d.text.split()) for d in survey_docs),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="thule-carriage",
        sandbox_spec={
            "records": [_COMMIT, "corridor_reaward"],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("thule-carriage",),
    )

    # The renewal notice is PUBLIC WORLD MATERIAL, attached to BOTH the
    # mutation stage and the re-award stage (review defect 3): the
    # re-award decision is GOVERNED by the notice's ranking rule, so
    # the world presents it at the decision point — a participant (or
    # the panel's reference worker) re-reads the terms it acts under.
    c2_mutation_doc = _c2_doc(
        "doc-c2-mutation",
        "Bonding renewal notice",
        (
            "Atlas Carriage's bonding audit has CLEARED: "
            "their bonded corridor now satisfies the "
            "customs-preclearance check. Prior FAILED "
            "verifications for atlas-carriage are "
            "superseded by this notice; re-verification "
            "reflects the renewed state. Harborline "
            "Freight's bonded audit is STILL PENDING — "
            "their prior failed verdicts stand. Thule "
            "Carriage remains eligible. RE-AWARD RULE: the "
            "corridor re-award goes to the HIGHEST-ranked "
            "eligible carrier — ranked by STANDARD SLA, "
            "shortest first."
        ),
        "v5:c2:mutation",
    )

    session2 = LifecycleInstance(
        instance_id="research-v5-c2-s2-0001",
        family=_FAMILY_V5,
        stages=(
            StageSpec(
                stage_id="c2-s2-start",
                kind="session_start",
                prompt_text=c1[1].stages[0].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c2-mutation",
                kind="rule_change",
                prompt_text=c1[1].stages[1].prompt_text,
                documents=(c2_mutation_doc,),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="c2-re-award",
                kind="act_verify",
                prompt_text=(
                    "The corridor contract renews: create and finalize "
                    "record corridor_reaward naming the awarded carrier. "
                    f"The prior primary award record {_COMMIT} must already "
                    "have been finalized before this session began. "
                    "The award requires a passing customs-preclearance "
                    "verification at the CURRENT revision for the "
                    "committed carrier — re-verify before committing. "
                    "Re-award the HIGHEST-ranked eligible carrier "
                    "(standard SLA, shortest first) per the renewal "
                    "notice's rule; note which leaders are STILL pending."
                ),
                documents=(c2_mutation_doc,),
                gold_evidence_ids=(),
                expected_state_delta={"corridor_reaward": {"status": "final"}},
                commit_precondition={
                    "record_id": "corridor_reaward",
                    "prior_finalized_record": _COMMIT,
                    "plan_field": "plan",
                    "legal_plans": ["atlas-carriage"],
                    "plan_requirements": {
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 2,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=_C2_S2_ORACLE,
            ),
            StageSpec(
                stage_id="c2-s2-end",
                kind="session_end",
                prompt_text="SESSION END. Only state['carry'] persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=1,
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, "corridor_reaward"],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )
    return session1, session2


def _c2_doc(doc_id: str, title: str, text: str, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date="2026-09-23",
    )


__all__ = [
    "build_aurora_swap",
    "build_b2_sessions",
    "build_c2_sessions",
    "build_vector",
]
