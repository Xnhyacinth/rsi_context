"""research-v5 — the C-group (execution & recovery) task "c1".

Design (2026-09-23, task design over EXISTING machinery — no new env
kinds): the award decision depends on ACTION OUTCOMES, not only on
reading. The core shape:

- Session 1: the oracle marks the superficially-best supplier
  (atlas-carriage, the reading-level answer) FAIL for
  customs-preclearance (a bonding audit is pending). A NAIVE agent
  commits atlas from its notes and the award gate refuses (no passing
  env-issued evidence for the subject). A RECOVERING agent requests the
  verification, READS the fail receipt (the multi-turn loop delivers
  it), switches to meridian-carriage (oracle-pass), re-verifies,
  commits — the action outcome changed the feasible path. The recovery
  target is READABLE MATERIAL (review 892f1d0 M1, defect a): the C
  survey adds one supplier card (card-c1-meridian) so the corpus names
  TWO visibly qualified cross-border carriers — the old 'ember' oracle
  subject never appeared in any card.
- Session 2 (the MUTATION event): a 'bonding renewed' notice; the
  session-2 oracle FLIPS atlas to pass (and meridian-carriage — the
  session-1 recovery — stays pass). The notice and the re-award prompt
  state the PUBLIC re-award rule: the corridor re-award goes to the
  HIGHEST-ranked eligible carrier (standard SLA, shortest first) —
  among the passers that is atlas-carriage (36h vs meridian's 44h), so
  the legal set is atlas-only and DERIVABLE (review 892f1d0 M1, defect
  b): an agent that re-awards on its carried meridian conclusion
  (stale recovery, rule ignored) is refused; the recovering agent
  re-verifies post-mutation and commits atlas.

Two legal recovery paths (the acceptance rule): (a) read-the-receipt
and switch (session 1); (b) re-verify-on-resume (session 2 — reread or
carried-scope note both reach it). Grading: the existing commit gates +
time-point + expected deltas; the sequence's decision vector gains the
recovery decisions.
"""

from __future__ import annotations

from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY = "research-v5"
_COMMIT = "migration_commit"
_REAWARD = "corridor_reaward"

#: Session-1 oracle: the reading-level best FAILS (pending audit);
#: meridian-carriage (the second visible cross-border carrier, C-survey
#: card card-c1-meridian) passes — the recovery target.
_S1_ORACLE = {
    "customs-preclearance": {
        "atlas-carriage": False,  # the pending-audit flip
        "meridian-carriage": True,
        "pinnacle-courier": False,
        "harborline-freight": False,
    },
}

#: Session-2 oracle (the MUTATION): bonding renewed — atlas now passes;
#: meridian-carriage still passes. The re-award rule (public: SLA rank,
#: shortest standard SLA first) makes atlas the legal winner, so a stale
#: meridian recovery is refused.
_S2_ORACLE = {
    "customs-preclearance": {
        "atlas-carriage": True,  # the renewal flip
        "meridian-carriage": True,
        "pinnacle-courier": False,
        "harborline-freight": False,
    },
}


def _doc(doc_id: str, title: str, text: str, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date="2026-09-23",
    )


def build_c1_sessions() -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build the two session instances of task c1 (in order)."""

    from rsicontext.lifecycle.material_v4_dossier import (
        _SUPPLIERS,
        _doc as mother_doc,
    )

    survey_docs = (
        *tuple(
            mother_doc(str(s["id"]), f"Supplier card: {s['name']}", str(s["text"]))
            for s in _SUPPLIERS
        ),
        # Review 892f1d0 M1 (defect a): the recovery target must be
        # READABLE MATERIAL. The mother corpus names exactly ONE visible
        # cross-border carrier (atlas, card-03); this card adds a SECOND
        # one so the session-1 recovery candidate is discoverable from
        # the survey — plain plausible text, no oracle leak (the card
        # says qualified-not-pending, the env decides verdicts).
        _doc(
            "card-c1-meridian",
            "Supplier card: meridian-carriage",
            (
                "Meridian Carriage runs cross-border carriage with customs "
                "bonding. Standard SLA 44h. Pricing tier B. Exception "
                "clause: Meridian Carriage's bonded corridor satisfies the "
                "customs-preclearance check for the northern checkpoints."
            ),
            "v5:c1:meridian",
        ),
        _doc(
            "doc-c1-verif-db",
            "Supplier verification protocol",
            (
                "The verification protocol defines the customs-preclearance "
                "check (bonded-corridor coverage). Protocol revision 1 "
                "applies. The awarded carrier must hold a PASSING "
                "customs-preclearance verification at the current protocol "
                "revision — VERIFICATION OUTCOMES GOVERN: a candidate "
                "whose verification FAILS is ineligible regardless of "
                "reading-level preference."
            ),
            "v5:c1:protocol",
        ),
    )

    session1 = LifecycleInstance(
        instance_id="research-v5-c1-s1-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="c1-survey",
                kind="survey",
                prompt_text=(
                    "[Supplier-selection project] Survey the supplier "
                    "cards and the verification protocol. The protocol "
                    "states: verification OUTCOMES govern eligibility. "
                    "Request verifications for the candidates you "
                    "consider; the environment will answer each."
                ),
                documents=survey_docs,
                gold_evidence_ids=tuple(doc.doc_id for doc in survey_docs),
            ),
            StageSpec(
                stage_id="c1-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "Constraint (document attached): the awarded carrier "
                    "must hold a passing customs-preclearance "
                    "verification. Verify your candidates before "
                    "committing."
                ),
                documents=(
                    _doc(
                        "doc-c1-constraint",
                        "Award constraint",
                        (
                            "Scope: the primary award requires a PASSING "
                            "customs-preclearance verification (env-issued) "
                            "for the committed carrier at the current "
                            "protocol revision. A FAILED verification makes "
                            "the carrier ineligible."
                        ),
                        "v5:c1:constraint",
                    ),
                ),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c1-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the primary award: request verifications for "
                    "your candidate(s), read the outcomes, and finalize "
                    f"record {_COMMIT} naming a carrier whose verification "
                    "PASSED. The gate refuses a commit whose cited "
                    "evidence failed or is missing."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition={
                    "record_id": _COMMIT,
                    "plan_field": "plan",
                    "legal_plans": ["meridian-carriage", "atlas-carriage"],
                    "plan_requirements": {
                        "meridian-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        },
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        },
                    },
                    "current_revision": 1,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=_S1_ORACLE,
            ),
            StageSpec(
                stage_id="c1-session-end",
                kind="session_end",
                prompt_text=(
                    "SESSION END. Working state destroyed; only "
                    "state['carry'] persists. Distill what you must keep."
                ),
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
        answer_norm="meridian-carriage",
        sandbox_spec={
            "records": [_COMMIT, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("meridian-carriage",),
    )

    session2 = LifecycleInstance(
        instance_id="research-v5-c1-s2-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="c1-s2-start",
                kind="session_start",
                prompt_text=(
                    "SESSION RESUME. The project continues. Carried state "
                    "attached; everything else empty. The sandbox is "
                    "queryable; the registry re-read is available."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c1-mutation",
                kind="rule_change",
                prompt_text=(
                    "Notice (document attached; arrived while paused). "
                    "Determine what changed and whether your retained "
                    "conclusions still hold."
                ),
                documents=(
                    _doc(
                        "doc-c1-mutation",
                        "Bonding renewal notice",
                        (
                            "Atlas Carriage's bonding audit has CLEARED: "
                            "their bonded corridor now satisfies the "
                            "customs-preclearance check. Prior FAILED "
                            "verifications for atlas-carriage are "
                            "superseded by this notice; re-verification "
                            "reflects the renewed state. Meridian Carriage "
                            "remains eligible. RE-AWARD RULE: the corridor "
                            "re-award goes to the HIGHEST-ranked eligible "
                            "carrier — ranked by STANDARD SLA, shortest "
                            "first."
                        ),
                        "v5:c1:mutation",
                    ),
                ),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="c1-re-award",
                kind="act_verify",
                prompt_text=(
                    "The corridor contract renews: create and finalize "
                    f"record {_REAWARD} naming the awarded carrier. The "
                    "award requires a passing customs-preclearance "
                    "verification at the CURRENT revision for the "
                    "committed carrier — re-verify before committing. "
                    "Re-award the HIGHEST-ranked eligible carrier "
                    "(standard SLA, shortest first) per the renewal "
                    "notice's rule."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_REAWARD: {"status": "final"}},
                commit_precondition={
                    "record_id": _REAWARD,
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
                verification_oracle=_S2_ORACLE,
            ),
            StageSpec(
                stage_id="c1-s2-end",
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
            "records": [_COMMIT, _REAWARD],
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


def build_c1_mirror_sessions() -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build the two session instances of task c1-mirror (in order).

    The EVAL twin of c1 (r3design §6 — the C machinery PERMUTED over the
    mirror corpus, stage kinds and recovery paths IDENTICAL): the
    mirror's own award oracle (dossier_variants._VARIANTS["mirror"])
    passes harborline-freight and fails atlas-carriage, so the
    reading-level best for c1-mirror session 1 is harborline — and the
    session-1 oracle flips it to FAIL (a pending customs-bonding audit),
    while a recovery target (atlas-carriage, the oracle's other passer
    inverted to True here) passes — atlas stays a VISIBLE carriage
    candidate in the mirror corpus (card-03, plain bulk there), so the
    recovery target is readable material (review 892f1d0 M1, defect a).
    The session-2 mutation RENEWS harborline's bonding and states the
    PUBLIC re-award rule (highest-ranked eligible carrier, standard SLA
    shortest first — harborline 24h beats atlas 36h), so the re-award
    legal set is {harborline-freight} at rev 2 and DERIVABLE (defect b)
    — an agent that re-awards on its carried atlas recovery (stale,
    rule ignored) is refused. Stage ids stay c1-* so the
    existing decision derivations keep working.
    """

    from rsicontext.lifecycle.dossier_variants import build_dossier_variant

    c1 = build_c1_sessions()
    mirror = build_dossier_variant("mirror")
    # The mirror's supplier cards (patched facts) + c1's own protocol and
    # constraint docs (world-neutral text — composed, never re-written).
    mirror_cards = tuple(
        d for d in mirror.stages[0].documents if d.doc_id not in ("doc-v4-verif-db", "doc-v4-memo")
    )
    c1_protocol = c1[0].stages[0].documents[-1]
    c1_constraint = c1[0].stages[1].documents[0]

    #: Session-1 oracle: the mirror's reading-level best (harborline)
    #: FAILS (pending audit); atlas passes — the recovery target.
    s1_oracle = {
        "customs-preclearance": {
            "harborline-freight": False,  # the pending-audit flip
            "atlas-carriage": True,
            "northwind-logistics": False,
            "pinnacle-courier": False,
        },
    }
    #: Session-2 oracle (the MUTATION): bonding renewed — harborline now
    #: passes; atlas still passes. The re-award rule (public: SLA rank,
    #: shortest first — harborline's 24h beats atlas's 36h) makes
    #: harborline the legal winner, so a stale atlas recovery is refused.
    s2_oracle = {
        "customs-preclearance": {
            "harborline-freight": True,  # the renewal flip
            "atlas-carriage": True,
            "northwind-logistics": False,
            "pinnacle-courier": False,
        },
    }

    survey_docs = (*mirror_cards, c1_protocol)

    session1 = LifecycleInstance(
        instance_id="research-v5-c1m-s1-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="c1-survey",
                kind="survey",
                prompt_text=c1[0].stages[0].prompt_text,
                documents=survey_docs,
                gold_evidence_ids=tuple(doc.doc_id for doc in survey_docs),
            ),
            StageSpec(
                stage_id="c1-constraint",
                kind="constraint_injection",
                prompt_text=c1[0].stages[1].prompt_text,
                documents=(c1_constraint,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c1-act-verify",
                kind="act_verify",
                prompt_text=c1[0].stages[2].prompt_text,
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition={
                    "record_id": _COMMIT,
                    "plan_field": "plan",
                    "legal_plans": ["harborline-freight", "atlas-carriage"],
                    "plan_requirements": {
                        "harborline-freight": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        },
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        },
                    },
                    "current_revision": 1,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=s1_oracle,
            ),
            StageSpec(
                stage_id="c1-session-end",
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
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )

    session2 = LifecycleInstance(
        instance_id="research-v5-c1m-s2-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="c1-s2-start",
                kind="session_start",
                prompt_text=c1[1].stages[0].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="c1-mutation",
                kind="rule_change",
                prompt_text=c1[1].stages[1].prompt_text,
                documents=(
                    _doc(
                        "doc-c1m-mutation",
                        "Bonding renewal notice",
                        (
                            "Harborline Freight's customs bonding audit has "
                            "CLEARED: their port-side cold chain is bonded "
                            "under the northern customs corridor agreement "
                            "and now satisfies the customs-preclearance "
                            "check. Prior FAILED verifications for "
                            "harborline-freight are superseded by this "
                            "notice; re-verification reflects the renewed "
                            "state. Atlas Carriage remains eligible. "
                            "RE-AWARD RULE: the corridor re-award goes to "
                            "the HIGHEST-ranked eligible carrier — ranked "
                            "by STANDARD SLA, shortest first."
                        ),
                        "v5:c1m:mutation",
                    ),
                ),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="c1-re-award",
                kind="act_verify",
                prompt_text=c1[1].stages[2].prompt_text,
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_REAWARD: {"status": "final"}},
                commit_precondition={
                    "record_id": _REAWARD,
                    "plan_field": "plan",
                    "legal_plans": ["harborline-freight"],
                    "plan_requirements": {
                        "harborline-freight": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 2,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=s2_oracle,
            ),
            StageSpec(
                stage_id="c1-s2-end",
                kind="session_end",
                prompt_text=c1[1].stages[3].prompt_text,
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
        answer_norm="harborline-freight",
        sandbox_spec={
            "records": [_COMMIT, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("harborline-freight",),
    )
    return session1, session2


__all__ = ["build_c1_mirror_sessions", "build_c1_sessions"]
