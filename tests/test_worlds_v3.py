"""Variant-world constructor tests for research-v3 (deliverable 6, structural axis).

The main world's dependency structure (five candidates with buried
exception clauses, scoped constraint, partial rule change,
precondition-checked commit) instantiated over DIFFERENT material: a
different domain set, different plan names, a different in-scope check,
and a different legal set. The structure — not the topic — is what
stratification axes record, and what a transferable strategy must work
over. All worlds share the v3 stage grammar and the commit gate; the
legal set is derived per world from its own material.
"""

from __future__ import annotations

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.material_v3_variant import (
    build_research_v3_variant,
    variant_world_specs,
)
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle

_COMMIT = "migration_commit"


class _LegalPathHook:
    """Executes a named plan's legal path (records + plain finalize)."""

    def __init__(
        self, plan: str, *, verif_revisions: dict[str, int], checks: dict[str, tuple[str, ...]]
    ) -> None:
        self.plan = plan
        self.verif_revisions = verif_revisions
        self.checks = checks

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            return StageResponse(pack_text="variant notes")
        actions: list[Action] = []
        refs: list[str] = []
        for record_id, check in self.checks.items():
            actions.append(
                Action(
                    kind="create_record",
                    record_id=record_id,
                    fields={
                        "check": check,
                        "protocol_revision": self.verif_revisions.get(record_id, 2),
                    },
                )
            )
            refs.append(record_id)
        actions.append(
            Action(
                kind="create_record",
                record_id=f"candidate_status-{self.plan}",
                fields={"plan": self.plan, "domain": "domain"},
            )
        )
        refs.append(f"candidate_status-{self.plan}")
        actions.append(Action(kind="create_record", record_id=_COMMIT, fields={"plan": self.plan}))
        actions.append(
            Action(
                kind="finalize",
                record_id=_COMMIT,
                fields={"status": "final"},
                provenance=tuple(refs),
            )
        )
        return StageResponse(pack_text=f"variant commit {self.plan}", actions=tuple(actions))


def test_variant_worlds_cover_the_structural_axes() -> None:
    specs = variant_world_specs()
    # More than one independent material set, all sharing the v3 grammar.
    assert len(specs) >= 2
    for spec in specs:
        inst = build_research_v3_variant(spec["spec_id"])
        assert inst.family == "research-v3"
        assert [stage.kind for stage in inst.stages] == [
            "survey",
            "constraint_injection",
            "delegation",
            "rule_change",
            "act_verify",
        ]
        # Structure constants: stage-5 empty, stage-1 carries the full set.
        assert inst.stages[4].documents == ()
        assert len(inst.stages[0].documents) == 7
        # The commit gate is present and parameterized per world.
        precondition = inst.stages[4].commit_precondition
        assert isinstance(precondition, dict)
        assert isinstance(precondition["legal_plans"], list) and precondition["legal_plans"]
        assert "commit gate" not in str(inst.stages[4].prompt_text)


def test_variant_worlds_differ_in_material_not_structure() -> None:
    specs = variant_world_specs()
    legal_sets = []
    plans = []
    for spec in specs:
        inst = build_research_v3_variant(spec["spec_id"])
        precondition = inst.stages[4].commit_precondition
        assert isinstance(precondition, dict)
        legal_sets.append(set(precondition["legal_plans"]))
        candidates = spec["candidates"]
        assert isinstance(candidates, tuple)
        titles = {str(candidate["title"]) for candidate in candidates}
        plans.append(titles)
    # Different material: no two worlds share their legal set or
    # candidate titles (the shared protocol/memo docs are grammar, not
    # material).
    for i in range(len(legal_sets)):
        for j in range(i + 1, len(legal_sets)):
            assert legal_sets[i] != legal_sets[j]
            assert plans[i].isdisjoint(plans[j])


def test_variant_legal_path_passes_the_gate() -> None:
    specs = variant_world_specs()
    spec = specs[0]
    inst = build_research_v3_variant(spec["spec_id"])
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    plan = precondition["legal_plans"][0]
    hook = _LegalPathHook(
        plan,
        verif_revisions={record: 2 for record in spec["required_checks"]},
        checks=dict(spec["required_checks"]),
    )
    record = run_lifecycle(inst, hook, ProjectState())
    # The finalize itself is plain; the EVALUATOR gate must pass the
    # legal plan with current-revision in-scope checks.
    assert record.final_check.passed, record.final_check.failures


def test_variant_stale_evidence_fails_the_gate() -> None:
    specs = variant_world_specs()
    spec = specs[0]
    inst = build_research_v3_variant(spec["spec_id"])
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    plan = precondition["legal_plans"][0]
    scope_checks = set(precondition["revision_scope"])
    stale_revisions = {}
    for record_id, check in spec["required_checks"].items():
        stale_revisions[record_id] = 1 if check in scope_checks else 2
    hook = _LegalPathHook(
        plan,
        verif_revisions=stale_revisions,
        checks=dict(spec["required_checks"]),
    )
    record = run_lifecycle(inst, hook, ProjectState())
    assert not record.final_check.passed
    assert any("stale" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_variant_illegal_plan_fails_the_gate() -> None:
    specs = variant_world_specs()
    spec = specs[0]
    inst = build_research_v3_variant(spec["spec_id"])
    hook = _LegalPathHook(
        "not-a-plan",
        verif_revisions={record: 2 for record in spec["required_checks"]},
        checks=dict(spec["required_checks"]),
    )
    record = run_lifecycle(inst, hook, ProjectState())
    assert not record.final_check.passed
    assert any("legal set" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_main_world_remains_a_variant_of_the_same_grammar() -> None:
    main = build_research_v3_instance()
    variant = build_research_v3_variant(variant_world_specs()[0]["spec_id"])
    # Same stage grammar, same axes semantics, disjoint candidate material.
    assert main.family == variant.family == "research-v3"
    from rsicontext.lifecycle.material_v3 import _CANDIDATES  # type: ignore[reportPrivateUsage]

    main_titles = {str(candidate["title"]) for candidate in _CANDIDATES}
    specs = variant_world_specs()
    candidates = specs[0]["candidates"]
    assert isinstance(candidates, tuple)
    variant_titles = {str(candidate["title"]) for candidate in candidates}
    assert main_titles.isdisjoint(variant_titles)
