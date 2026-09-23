"""Dossier evaluation variants (stats-contract §4 — same-family transfer).

Variants change the DECISIVE FACTS, not the structure: which supplier
wins, which check the final rule change supersedes, which supplier the
calibration follow-up names. They are generated from the same world
template and are REPORTED as same-family transfer — never as
independent projects. Nothing from them enters any improvement input
(structural: the researcher feedback builder consumes dev runs only).
"""

from __future__ import annotations

from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier

#: Variant overwrites: applied to the mother world's supplier cards and
#: stage texts. Each variant keeps the load-bearing LEDGER SHAPE (one
#: qualification, one decoy disqualifier, one calibration answer) but
#: assigns them to DIFFERENT suppliers/checks.
_VARIANTS: dict[str, dict[str, object]] = {
    "mirror": {
        # Winner: harborline (card-02); decoy: northwind (card-01);
        # calibration: orbit-hosting (card-11); superseded at s7:
        # cold-chain-integrity (so the award evidence on customs stays
        # current -> the correct s8 diagnosis FLIPS to 'current').
        "winner": "harborline-freight",
        "winner_card": "card-02",
        "winner_clause": (
            "Exception clause: Harborline Freight's port-side cold chain "
            "is bonded under the northern customs corridor agreement, "
            "which satisfies the customs-preclearance check for all five "
            "northern checkpoints."
        ),
        "decoy": "northwind-logistics",
        "decoy_card": "card-01",
        "decoy_clause": (
            "Exception clause: Northwind's customs bonding was suspended "
            "last quarter pending audit, so the customs-preclearance "
            "check fails for Northwind Logistics until the audit clears."
        ),
        "calibration": "orbit-hosting",
        "calibration_card": "card-11",
        "calibration_clause": (
            "Exception clause: Orbit Hosting maintains the northern "
            "service hub under the same corridor agreement framework, "
            "covering all five northern checkpoints."
        ),
        "final_scope": ("cold-chain-integrity",),
        "fu2_stale": "current",  # award evidence NOT superseded
        "legal": ["harborline-freight"],
        "oracle": {
            "customs-preclearance": {
                "harborline-freight": True,
                "northwind-logistics": False,
                "atlas-carriage": False,
                "pinnacle-courier": False,
            },
            "cold-chain-integrity": {
                "harborline-freight": True,
                "northwind-logistics": False,
            },
        },
        "fu1_answer": "orbit-hosting",
    },
}


def dossier_variant_ids() -> tuple[str, ...]:
    return tuple(_VARIANTS)


def build_dossier_variant(variant_id: str) -> LifecycleInstance:
    """Build one evaluation variant (facts permuted, structure fixed)."""

    spec = _VARIANTS.get(variant_id)
    if spec is None:
        raise ValueError(f"unknown dossier variant: {variant_id!r}")
    import rsicontext.lifecycle.material_v4_dossier as dossier

    original = list(dossier._SUPPLIERS)
    patched = []
    for supplier in original:
        entry = dict(supplier)
        if entry["id"] == spec["winner_card"]:
            base = str(entry["text"]).split("Exception clause:")[0].rstrip()
            entry["text"] = base + " " + str(spec["winner_clause"])
        elif entry["id"] == spec["decoy_card"]:
            base = str(entry["text"]).split("Exception clause:")[0].rstrip()
            entry["text"] = base + " On paper a strong candidate. " + str(spec["decoy_clause"])
        elif entry["id"] == spec["calibration_card"]:
            base = str(entry["text"]).split("Exception clause:")[0].rstrip()
            entry["text"] = base + " " + str(spec["calibration_clause"])
        elif entry["id"] == "card-03":
            # The mother winner becomes plain bulk in the variant.
            base = str(entry["text"]).split("Exception clause:")[0].rstrip()
            entry["text"] = base + " No exceptional clauses apply."
        elif entry["id"] == "card-17":
            base = str(entry["text"]).split("Buried condition:")[0].rstrip()
            entry["text"] = base + " No exceptional clauses apply."
        elif entry["id"] == "card-08":
            base = str(entry["text"]).split("Their northern service hub")[0].rstrip()
            entry["text"] = base + " Recalibration is handled regionally."
        patched.append(entry)

    original_suppliers = dossier._SUPPLIERS
    original_oracle = dossier._VERIFICATION_ORACLE
    original_legal = dossier._LEGAL_PLANS
    dossier._SUPPLIERS = tuple(patched)
    dossier._VERIFICATION_ORACLE = dict(spec["oracle"])  # type: ignore[arg-type]
    dossier._LEGAL_PLANS = tuple(str(p) for p in spec["legal"])  # type: ignore[arg-type]
    try:
        inst = build_research_v4_dossier(instance_id=f"research-v4-dossier-{variant_id}-0001")
        # Variant-specific stage adjustments: the final rule-change
        # scope flips to the OTHER check, and the expected fu2 value
        # flips accordingly (the derivation handles this at grade time —
        # the followup's expected placeholder is overridden anyway).
        stages = list(inst.stages)
        s7 = stages[6]
        stages[6] = s7.__class__(
            stage_id=s7.stage_id,
            kind=s7.kind,
            prompt_text=s7.prompt_text,
            documents=(
                DocumentRef(
                    doc_id=s7.documents[0].doc_id,
                    title=s7.documents[0].title,
                    text=(
                        "[[doc:"
                        + s7.documents[0].doc_id
                        + "]] "
                        + s7.documents[0].title
                        + "\nScope: this revision supersedes the "
                        "cold-chain-integrity check only. Protocol "
                        "revision 3 tightens cold-chain requirements. "
                        "cold-chain-integrity verifications performed "
                        "under earlier revisions are stale for any NEW "
                        "decision; customs-preclearance evidence remains "
                        "valid."
                    ),
                    source_url=s7.documents[0].source_url,
                    retrieved_date=s7.documents[0].retrieved_date,
                ),
            ),
            gold_evidence_ids=(),
            rule_change_effect=3,
            rule_change_scope=tuple(str(c) for c in spec["final_scope"]),  # type: ignore[arg-type]
        )
        # fu2 expectation: the derivation overrides the placeholder, but
        # keep the static value consistent for readers.
        s8 = stages[7]
        stages[7] = s8.__class__(
            stage_id=s8.stage_id,
            kind=s8.kind,
            prompt_text=s8.prompt_text,
            documents=s8.documents,
            gold_evidence_ids=(),
            expected_state_delta={
                "followup_conclusion-corridor": {"status": str(spec["fu2_stale"])}
            },
            commit_precondition=s8.commit_precondition,
        )
        import dataclasses

        inst = dataclasses.replace(inst, stages=tuple(stages))
        # fu1 answer override (the follow-up asks about the variant's
        # calibration supplier).
        fu1 = stages[5]
        stages[5] = fu1.__class__(
            stage_id=fu1.stage_id,
            kind=fu1.kind,
            prompt_text=fu1.prompt_text,
            documents=fu1.documents,
            gold_evidence_ids=(),
            expected_state_delta={
                "followup_conclusion-calibration": {"supplier": str(spec["fu1_answer"])}
            },
        )
        inst = dataclasses.replace(inst, stages=tuple(stages))
        return inst
    finally:
        dossier._SUPPLIERS = original_suppliers
        dossier._VERIFICATION_ORACLE = original_oracle
        dossier._LEGAL_PLANS = original_legal
