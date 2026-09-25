"""Behavioral checks for the offline Gate 2 admission instrument."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from qualify_r3_parent_projects import (
    _first_award,
    _irrelevant_perturbation,
    _later_c_gate_without_prior_commit,
    _run,
    _without_verification,
    inventory,
)

from rsicontext.lifecycle.material_c_group import build_c1_mirror_sessions, build_c1_sessions
from rsicontext.lifecycle.material_m2_parents import build_c2_sessions
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier


def test_verification_intervention_breaks_an_executable_reference_path() -> None:
    world = build_research_v4_dossier()
    award = _first_award(world)
    assert award is not None
    intervened = _without_verification(world, award)
    assert intervened is not None
    assert _run("A", world)["passed"] is True
    assert _run("A", intervened)["passed"] is False


def test_irrelevant_text_keeps_reference_decisions_stable() -> None:
    world = build_research_v4_dossier()
    perturbed = _irrelevant_perturbation(world)
    assert perturbed is not None
    original = _run("A", world)
    changed = _run("A", perturbed)
    assert changed["passed"] == original["passed"]
    assert changed["decisions"] == original["decisions"]


def test_c_receipt_intervention_exposes_unproven_later_dependency() -> None:
    world = list(build_c1_sessions())
    award = _first_award(world)
    assert award is not None
    intervened = _without_verification(world, award)
    assert intervened is not None
    original = _run("C", world)
    changed = _run("C", intervened)
    assert original["decisions"]["session_2_passed"] is True
    assert changed["decisions"]["session_1_passed"] is False
    assert changed["decisions"]["session_2_passed"] is True


def test_c_later_legal_gate_accepts_without_prior_commit() -> None:
    for build in (build_c1_sessions, build_c1_mirror_sessions, build_c2_sessions):
        assert _later_c_gate_without_prior_commit(list(build()))


def test_inventory_rejects_shared_lineage_and_does_not_publish_labels() -> None:
    result = inventory()
    rows = [row for group in result["groups"].values() for row in group]
    assert len(rows) == 10
    assert {row["parent_id"] for row in rows} == {"supplier-dossier-v4"}
    assert result["summary"]["qualified_worlds"] == 0
    assert all(row["qualified"] is False for row in rows)
    assert all(len(row["material_sha256"]) == 64 for row in rows)
    assert all(row["structural_ledger"] for row in rows)
    exported = json.dumps(result)
    for forbidden in (
        "gold_evidence_ids",
        "verification_oracle",
        "legal_plans",
        "answer_norm",
        "expected_state_delta",
        "atlas-carriage",
        "harborline-freight",
    ):
        assert forbidden not in exported
