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

from typing import cast

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.material_v3_variant import (
    build_research_v3_variant,
    variant_world_specs,
)
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle

_COMMIT = "migration_commit"


def _spec_id(spec: dict[str, object]) -> str:
    value = spec["spec_id"]
    assert isinstance(value, str)
    return value


def _required_checks(spec: dict[str, object]) -> dict[str, str]:
    value = spec["required_checks"]
    assert isinstance(value, dict)
    assert all(isinstance(key, str) and isinstance(check, str) for key, check in value.items())
    return cast(dict[str, str], value)


def _candidates(spec: dict[str, object]) -> tuple[dict[str, object], ...]:
    value = spec["candidates"]
    assert isinstance(value, tuple)
    assert all(isinstance(candidate, dict) for candidate in value)
    return cast(tuple[dict[str, object], ...], value)


def _legal_plans(precondition: dict[str, object]) -> list[str]:
    value = precondition["legal_plans"]
    assert isinstance(value, list)
    assert all(isinstance(plan, str) for plan in value)
    return cast(list[str], value)


class _LegalPathHook:
    """Executes a named plan's legal path over the env verification service.

    ``request_at`` controls WHEN each check is requested: "early" (before
    the rule change — evidence ages with the protocol clock) or "current"
    (after it — current-revision evidence). The environment issues the
    records; the commit only cites them.
    """

    def __init__(
        self,
        plan: str,
        *,
        request_at: dict[str, str],
        checks: dict[str, str],
    ) -> None:
        self.plan = plan
        self.request_at = request_at
        self.checks = checks
        self._early_refs: list[str] = []
        self._current_refs: list[str] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind == "constraint_injection":
            early = [
                Action(
                    kind="request_verification",
                    record_id=record_id,
                    fields={"check": check, "subject": self.plan},
                )
                for record_id, check in self.checks.items()
                if self.request_at.get(record_id) == "early"
            ]
            self._early_refs = [action.record_id for action in early]
            return StageResponse(pack_text="variant notes", actions=tuple(early))
        if stage.kind == "rule_change":
            current = [
                Action(
                    kind="request_verification",
                    record_id=record_id,
                    fields={"check": check, "subject": self.plan},
                )
                for record_id, check in self.checks.items()
                if self.request_at.get(record_id) != "early"
            ]
            self._current_refs = [action.record_id for action in current]
            return StageResponse(pack_text="variant re-verify", actions=tuple(current))
        if stage.kind != "act_verify":
            return StageResponse(pack_text="variant notes")
        refs = [*self._current_refs, *self._early_refs]
        actions: list[Action] = []
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
        inst = build_research_v3_variant(_spec_id(spec))
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
        inst = build_research_v3_variant(_spec_id(spec))
        precondition = inst.stages[4].commit_precondition
        assert isinstance(precondition, dict)
        legal_sets.append(set(_legal_plans(precondition)))
        candidates = _candidates(spec)
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
    inst = build_research_v3_variant(_spec_id(spec))
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    plan = _legal_plans(precondition)[0]
    checks = _required_checks(spec)
    hook = _LegalPathHook(
        plan,
        request_at={record: "current" for record in checks},
        checks=checks,
    )
    record = run_lifecycle(inst, hook, ProjectState())
    # The finalize itself is plain; the EVALUATOR gate must pass the
    # legal plan with env-issued current-revision evidence.
    assert record.final_check.passed, record.final_check.failures


def test_variant_stale_evidence_fails_the_gate() -> None:
    specs = variant_world_specs()
    spec = specs[0]
    inst = build_research_v3_variant(_spec_id(spec))
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    plan = _legal_plans(precondition)[0]
    scope = precondition["revision_scope"]
    assert isinstance(scope, (tuple, list))
    scope_checks = set(scope)
    request_at = {}
    checks = _required_checks(spec)
    for record_id, check in checks.items():
        # The in-scope check is requested EARLY (the env stamps revision 1
        # — evidence that aged past the rule change); out-of-scope checks
        # stay current. A revision label can no longer be self-declared:
        # the staleness is the environment's own clock.
        request_at[record_id] = "early" if check in scope_checks else "current"
    hook = _LegalPathHook(
        plan,
        request_at=request_at,
        checks=checks,
    )
    record = run_lifecycle(inst, hook, ProjectState())
    assert not record.final_check.passed
    assert any("stale" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_variant_illegal_plan_fails_the_gate() -> None:
    specs = variant_world_specs()
    spec = specs[0]
    inst = build_research_v3_variant(_spec_id(spec))
    checks = _required_checks(spec)
    hook = _LegalPathHook(
        "not-a-plan",
        request_at={record: "current" for record in checks},
        checks=checks,
    )
    record = run_lifecycle(inst, hook, ProjectState())
    assert not record.final_check.passed
    assert any("legal set" in failure for failure in record.final_check.failures), (
        record.final_check.failures
    )


def test_main_world_remains_a_variant_of_the_same_grammar() -> None:
    main = build_research_v3_instance()
    variant = build_research_v3_variant(_spec_id(variant_world_specs()[0]))
    # Same stage grammar, same axes semantics, disjoint candidate material.
    assert main.family == variant.family == "research-v3"
    from rsicontext.lifecycle.material_v3 import _CANDIDATES

    main_titles = {str(candidate["title"]) for candidate in _CANDIDATES}
    specs = variant_world_specs()
    candidates = _candidates(specs[0])
    variant_titles = {str(candidate["title"]) for candidate in candidates}
    assert main_titles.isdisjoint(variant_titles)
