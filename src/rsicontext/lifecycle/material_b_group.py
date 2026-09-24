"""research-v5 — the B-group (cross-session state recovery) task "b1".

Design: docs (bgroup agent, 2026-09-23) — three SESSIONS over the
dossier corpus; the transient model context is destroyed at each
session_end; only the persistence contract's carry (state["carry"],
<=64K through SessionStateStore) survives. The rule change lands
BETWEEN sessions (the participant meets it only as session-2 material);
session 3 is a fresh-project instantiation of the MIRROR variant's
facts (labeled same-family transfer), where misapplying session-1
conclusions must fail.

Six graded decisions (existing graders only):
  s1_award          time-point commit gate (session 1's own env state)
  s2_calibration    memory across the boundary (carry or metered reread)
  s2_currency       stale-conclusion detection (evidence_currency derivation)
  s2_reaward_fresh  fresh-evidence gate at revision 3 (scoped check)
  s3_award          non-transfer: the mirror's own gate
  s3_calibration    the mirror's expected delta
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
_CONCLUSION = "followup_conclusion"

_ORACLE = {
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


def _doc(doc_id: str, title: str, text: str, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date="2026-09-23",
    )


def build_b1_sessions() -> tuple[LifecycleInstance, LifecycleInstance, LifecycleInstance]:
    """Build the three session instances of task b1 (in order)."""

    from rsicontext.lifecycle.material_v4_dossier import (
        _SUPPLIERS as MOTHER_SUPPLIERS,
        _VERIFICATION_ORACLE as MOTHER_ORACLE,
        _doc as mother_doc,
    )
    from rsicontext.lifecycle.dossier_variants import build_dossier_variant

    # --- Session 1: the original project, phase one (mother facts) ----
    survey_docs = tuple(
        mother_doc(str(s["id"]), f"Supplier card: {s['name']}", str(s["text"]))
        for s in MOTHER_SUPPLIERS
    ) + (
        mother_doc(
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
    )
    session1 = LifecycleInstance(
        instance_id="research-v5-b1-s1-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    "[Supplier-selection project] Survey the supplier "
                    "cards and the verification protocol. Build working "
                    "notes — but note: at SESSION END your working state "
                    "is DESTROYED; only what you write into "
                    "state['carry'] persists (byte-capped). Distill what "
                    "you must KEEP."
                ),
                documents=survey_docs,
                gold_evidence_ids=tuple(doc.doc_id for doc in survey_docs),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A new constraint arrives (document attached). From "
                    "your retained notes, determine which candidate "
                    "carriers fall under its scope."
                ),
                documents=(
                    _doc(
                        "doc-v4-constraint",
                        "Award constraint",
                        (
                            "Scope: this constraint applies to the primary "
                            "award only. The awarded carrier must hold a "
                            "PASSING customs-preclearance verification at "
                            "the current protocol revision; candidates "
                            "without bonded-corridor coverage are "
                            "ineligible."
                        ),
                        "v5:b1:constraint",
                    ),
                ),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached): the verification "
                    "protocol revision changed. Note the SCOPE."
                ),
                documents=(
                    _doc(
                        "doc-v4-rule-change-1",
                        "Protocol revision notice (mid-project)",
                        (
                            "Scope: this revision supersedes the "
                            "cold-chain-integrity check documentation "
                            "only (documentation update; no threshold "
                            "change). The customs-preclearance check is "
                            "unaffected."
                        ),
                        "v5:b1:rule1",
                    ),
                ),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the primary award: create and finalize "
                    f"record {_COMMIT} naming the chosen carrier with "
                    "the verifications it relies on. The award gate "
                    "requires a passing customs-preclearance "
                    "verification at the CURRENT protocol revision."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition={
                    "record_id": _COMMIT,
                    "plan_field": "plan",
                    "legal_plans": ["atlas-carriage"],
                    "plan_requirements": {
                        "atlas-carriage": {
                            "domain": "shipping",
                            "requires_check": "customs-preclearance",
                        }
                    },
                    "current_revision": 1,
                    "revision_scope": ["customs-preclearance"],
                },
                verification_oracle=_ORACLE,
            ),
            StageSpec(
                stage_id="s6-session-end",
                kind="session_end",
                prompt_text=(
                    "SESSION END. The project pauses: your working state "
                    "(notes, model context, everything outside "
                    "state['carry']) is destroyed. Only state['carry'] "
                    "persists (byte-capped). Write what you must keep."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(1 + len(d.text.split()) for d in survey_docs),
            dependency_distance_stages=4,
            persistence_span_resets=2,
            action_dependency="strong",
            environment_changes=2,
        ),
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )

    # --- Session 2: continue the project (same facts; rev-3 landed) ---
    # The rule change arrived BETWEEN sessions — it appears only here.
    session2 = LifecycleInstance(
        instance_id="research-v5-b1-s2-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s7-session-start",
                kind="session_start",
                prompt_text=(
                    "SESSION RESUME. The project continues. Your carried "
                    "state (state['carry']) is attached; everything else "
                    "starts empty. The sandbox is queryable; the registry "
                    "re-read is available at ledgered cost."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s8-rule-change-between",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached; arrived while the "
                    "project was paused). Determine which of your "
                    "retained conclusions are invalidated."
                ),
                documents=(
                    _doc(
                        "doc-v4-rule-change-2",
                        "Protocol revision notice (arrived between sessions)",
                        (
                            "Scope: this revision supersedes the "
                            "customs-preclearance check only. Protocol "
                            "revision 3 tightens corridor requirements. "
                            "customs-preclearance verifications performed "
                            "under earlier revisions are stale for any "
                            "NEW decision; evidence for unaffected "
                            "checks remains valid."
                        ),
                        "v5:b1:rule2",
                    ),
                ),
                gold_evidence_ids=(),
                rule_change_effect=3,
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="s9-followup-calibration",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Answer from "
                    "carried conclusions or re-read at cost, then write "
                    "the conclusion record."
                ),
                documents=(
                    _doc(
                        "doc-v4-followup-1",
                        "Follow-up request: calibration partner",
                        (
                            "A lab calibration partner is needed for the "
                            "awarded corridor's checkpoints. Answer with "
                            "the instrument supplier whose northern "
                            "service hub covers the same five northern "
                            "checkpoints under the corridor agreement "
                            "framework, and create a followup_conclusion "
                            "record naming that supplier. No supplier "
                            "cards are re-attached."
                        ),
                        "v5:b1:fu1",
                    ),
                ),
                gold_evidence_ids=(),
                expected_state_delta={
                    f"{_CONCLUSION}-calibration": {"supplier": "vesper-instruments"}
                },
            ),
            StageSpec(
                stage_id="s10-followup-currency",
                kind="follow_up",
                prompt_text=(
                    "Follow-up request (document attached). Record the "
                    "currency status of the award's backing evidence."
                ),
                documents=(
                    _doc(
                        "doc-v4-followup-2",
                        "Follow-up request: corridor re-award review",
                        (
                            "The corridor contract is up for a scope "
                            "review. Determine whether the "
                            "customs-preclearance evidence backing the "
                            "current award is still current, and create a "
                            "followup_conclusion record with "
                            "status='reverify' if the evidence is stale "
                            "under the current protocol revision, or "
                            "status='current' otherwise."
                        ),
                        "v5:b1:fu2",
                    ),
                ),
                gold_evidence_ids=(),
                expected_state_delta={f"{_CONCLUSION}-corridor": {"status": "reverify"}},
                commit_precondition={
                    "evidence_currency": {
                        "commit_record": _COMMIT,
                        "check": "customs-preclearance",
                        "record_id": f"{_CONCLUSION}-corridor",
                        "field": "status",
                        "stale_value": "reverify",
                        "current_value": "current",
                    }
                },
            ),
            StageSpec(
                stage_id="s11-re-award",
                kind="act_verify",
                prompt_text=(
                    "The corridor contract renews: create and finalize "
                    f"record {_REAWARD} (superseding {_COMMIT}) naming "
                    "the awarded carrier. The gate requires "
                    "customs-preclearance evidence at the CURRENT "
                    "protocol revision (revision 3) — evidence issued "
                    "under earlier revisions is stale for this decision."
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
                    "current_revision": 3,
                    "revision_scope": ["customs-preclearance"],
                },
            ),
            StageSpec(
                stage_id="s12-session-end",
                kind="session_end",
                prompt_text=("SESSION END. Working state destroyed; only state['carry'] persists."),
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=1,
            dependency_distance_stages=4,
            persistence_span_resets=2,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )

    # --- Session 3: a NEW project (the mirror variant's facts) -------
    # Fresh env; registry + carry persist per participant. Misapplying
    # session-1 conclusions must fail (atlas not in the mirror legal
    # set; vesper not the mirror calibration answer).
    mirror = build_dossier_variant("mirror")
    mirror_survey = mirror.stages[0].documents
    session3 = LifecycleInstance(
        instance_id="research-v5-b1-s3-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="n1-survey",
                kind="survey",
                prompt_text=(
                    "A NEW supplier-selection project begins (fresh "
                    "project, fresh sandbox). Your carried state is "
                    "attached; using it is your risk. Survey the "
                    "supplier cards and the protocol."
                ),
                documents=mirror_survey,
                gold_evidence_ids=tuple(doc.doc_id for doc in mirror_survey),
            ),
            StageSpec(
                stage_id="n2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A new constraint arrives (document attached). "
                    "Determine which candidates fall under its scope."
                ),
                documents=mirror.stages[1].documents,
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="n4-rule-change",
                kind="rule_change",
                prompt_text="Rule change (document attached). Note the scope.",
                documents=mirror.stages[3].documents,
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="n5-award",
                kind="act_verify",
                prompt_text=(
                    "Commit the primary award: create and finalize "
                    f"record {_COMMIT} naming the chosen carrier with "
                    "the verifications it relies on. The award gate "
                    "requires a passing customs-preclearance "
                    "verification at the current protocol revision."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition=mirror.stages[4].commit_precondition,
                # The mirror's own oracle, so the fresh env can ISSUE
                # evidence for the mirror's winner (r3 fix, 2026-09-24):
                # without it every session-3 verification came back
                # 'unverifiable' and the award gate was unpassable for
                # ANY policy — s3_award measured impossibility, not
                # transfer. Misapplication still fails (the legal set
                # rejects the carried winner regardless).
                verification_oracle=mirror.stages[4].verification_oracle,
            ),
            StageSpec(
                stage_id="n6-followup-calibration",
                kind="follow_up",
                prompt_text=("Follow-up request (document attached). Write the conclusion record."),
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
            information_scale_tokens=sum(1 + len(d.text.split()) for d in mirror_survey),
            dependency_distance_stages=4,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="harborline-freight",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("harborline-freight",),
    )
    return session1, session2, session3


def build_b1_reverse_sessions() -> tuple[LifecycleInstance, LifecycleInstance, LifecycleInstance]:
    """Build the three session instances of task b1-reverse (in order).

    The EVAL twin of b1 (r3design §6 — same-family transfer, worlds
    SWAPPED, structure identical): sessions 1-2 run the MIRROR variant's
    facts as the continuing project (winner harborline-freight,
    calibration orbit-hosting, the SAME between-session rev-3
    customs supersession), session 3 is a fresh project on the MOTHER's
    facts (atlas/vesper) — misapplying session-1's harborline
    conclusions there must fail. Stage ids and decision keys are
    IDENTICAL to b1 (the six-decision vector's needles are stage-id
    based); every world-specific piece is COMPOSED from the existing
    builders, never re-written.
    """

    from rsicontext.lifecycle.dossier_variants import build_dossier_variant
    from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier

    b1 = build_b1_sessions()
    mother = build_research_v4_dossier()
    mirror = build_dossier_variant("mirror")

    # Sessions 1-2's project: the MIRROR's facts (cards + protocol; the
    # memo is excluded exactly as in b1's session-1 survey).
    mirror_survey = tuple(d for d in mirror.stages[0].documents if d.doc_id != "doc-v4-memo")
    # Session 3's fresh project: the MOTHER's facts (full survey, as in
    # b1's session 3).
    mother_survey = mother.stages[0].documents

    # --- Session 1: the continuing project, phase one (MIRROR facts) --
    session1 = LifecycleInstance(
        instance_id="research-v5-b1r-s1-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=b1[0].stages[0].prompt_text,
                documents=mirror_survey,
                gold_evidence_ids=tuple(doc.doc_id for doc in mirror_survey),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=b1[0].stages[1].prompt_text,
                documents=mirror.stages[1].documents,
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=b1[0].stages[2].prompt_text,
                documents=mirror.stages[3].documents,
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=b1[0].stages[3].prompt_text,
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_COMMIT: {"status": "final"}},
                commit_precondition=mirror.stages[4].commit_precondition,
                verification_oracle=mirror.stages[4].verification_oracle,
            ),
            StageSpec(
                stage_id="s6-session-end",
                kind="session_end",
                prompt_text=b1[0].stages[4].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(1 + len(d.text.split()) for d in mirror_survey),
            dependency_distance_stages=4,
            persistence_span_resets=2,
            action_dependency="strong",
            environment_changes=2,
        ),
        answer_norm="harborline-freight",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("harborline-freight",),
    )

    # --- Session 2: continue the project (MIRROR facts; rev-3 landed) -
    # The between-session rule change KEEPS b1's rev-3 customs scope
    # (the cross-session recovery machinery — the dossier variant's own
    # cold-chain supersession is a v4-axis concern, not this one).
    session2 = LifecycleInstance(
        instance_id="research-v5-b1r-s2-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s7-session-start",
                kind="session_start",
                prompt_text=b1[1].stages[0].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s8-rule-change-between",
                kind="rule_change",
                prompt_text=b1[1].stages[1].prompt_text,
                documents=b1[1].stages[1].documents,
                gold_evidence_ids=(),
                rule_change_effect=3,
                rule_change_scope=("customs-preclearance",),
            ),
            StageSpec(
                stage_id="s9-followup-calibration",
                kind="follow_up",
                prompt_text=b1[1].stages[2].prompt_text,
                documents=mirror.stages[5].documents,
                gold_evidence_ids=(),
                expected_state_delta=mirror.stages[5].expected_state_delta,
            ),
            StageSpec(
                stage_id="s10-followup-currency",
                kind="follow_up",
                prompt_text=b1[1].stages[3].prompt_text,
                documents=b1[1].stages[3].documents,
                gold_evidence_ids=(),
                expected_state_delta=b1[1].stages[3].expected_state_delta,
                commit_precondition=b1[1].stages[3].commit_precondition,
            ),
            StageSpec(
                stage_id="s11-re-award",
                kind="act_verify",
                prompt_text=b1[1].stages[4].prompt_text,
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
                    "current_revision": 3,
                    "revision_scope": ["customs-preclearance"],
                },
            ),
            StageSpec(
                stage_id="s12-session-end",
                kind="session_end",
                prompt_text=b1[1].stages[5].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=1,
            dependency_distance_stages=4,
            persistence_span_resets=2,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="harborline-freight",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION, _REAWARD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("harborline-freight",),
    )

    # --- Session 3: a NEW project (the MOTHER's facts) ---------------
    # Fresh env; carry persists per participant. Misapplying session-1
    # conclusions must fail (harborline not in the mother legal set;
    # orbit not the mother calibration answer).
    session3 = LifecycleInstance(
        instance_id="research-v5-b1r-s3-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="n1-survey",
                kind="survey",
                prompt_text=b1[2].stages[0].prompt_text,
                documents=mother_survey,
                gold_evidence_ids=tuple(doc.doc_id for doc in mother_survey),
            ),
            StageSpec(
                stage_id="n2-constraint",
                kind="constraint_injection",
                prompt_text=b1[2].stages[1].prompt_text,
                documents=mother.stages[1].documents,
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="n4-rule-change",
                kind="rule_change",
                prompt_text=b1[2].stages[2].prompt_text,
                documents=mother.stages[3].documents,
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
                commit_precondition=mother.stages[4].commit_precondition,
                verification_oracle=mother.stages[4].verification_oracle,
            ),
            StageSpec(
                stage_id="n6-followup-calibration",
                kind="follow_up",
                prompt_text=b1[2].stages[4].prompt_text,
                documents=mother.stages[5].documents,
                gold_evidence_ids=(),
                expected_state_delta=mother.stages[5].expected_state_delta,
            ),
            StageSpec(
                stage_id="n7-session-end",
                kind="session_end",
                prompt_text=b1[2].stages[5].prompt_text,
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(1 + len(d.text.split()) for d in mother_survey),
            dependency_distance_stages=4,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="atlas-carriage",
        sandbox_spec={
            "records": [_COMMIT, _CONCLUSION],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=("atlas-carriage",),
    )
    return session1, session2, session3


__all__ = ["build_b1_reverse_sessions", "build_b1_sessions"]
