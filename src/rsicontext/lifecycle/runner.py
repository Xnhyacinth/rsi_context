"""Participant-agnostic stage runner for research-v1 lifecycles.

Spec: ``docs/task-family-research-v1.md`` §Task structure and
``docs/benchmark-contract-v2.md`` §Protocol semantics. The runner executes
the five stages in order against an injected ``ParticipantHook`` — it never
calls a reader itself, so participants (fixed / experience-only / open-S
arms; adapters land in other workstreams) drive behavior through the hook.

Evaluator-only fields (``StageSpec.gold_evidence_ids`` and
``StageSpec.expected_state_delta``) are never surfaced to the hook: the
runner builds ``StageView`` from a ``StageSpec`` minus exactly those fields,
and ``StageView`` has no attribute or serialization surface that can carry
them. The two-column cost split is honored in miniature: token counts are
placeholders the hook caller fills (reader accounting lands with the cost
ledger workstream), wall seconds are measured here.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from rsicontext.lifecycle.env import Action, CheckResult, ObjectiveChecker, ProjectState
from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

_DOC_MARKER = re.compile(r"\[\[doc:([^]]+)\]\]")


@dataclass(frozen=True, slots=True)
class StageView:
    """What a participant sees for one stage — evaluator-only fields excluded.

    Constructed by the runner from ``StageSpec`` minus ``gold_evidence_ids``
    and ``expected_state_delta``; there is no code path from this type to
    either field. ``remaining_budget`` counts stages left including this one.
    """

    stage_id: str
    kind: str
    prompt_text: str
    documents: tuple[DocumentRef, ...]
    axes: DescriptionAxes
    remaining_budget: int

    def cited_doc_ids(self, pack_text: str) -> tuple[str, ...]:
        """Doc ids referenced by ``[[doc:ID]]`` markers in ``pack_text``."""

        return tuple(_DOC_MARKER.findall(pack_text))


@dataclass(frozen=True, slots=True)
class StageResponse:
    """One participant turn: the pack it would act on plus its writes."""

    pack_text: str
    actions: tuple[Action, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.pack_text, str):
            raise TypeError("pack_text must be a string")
        object.__setattr__(self, "actions", tuple(self.actions))
        if any(not isinstance(action, Action) for action in self.actions):
            raise TypeError("stage actions must be Action values")


class ParticipantHook(Protocol):
    """The participant-facing surface of one lifecycle run.

    ``on_stage`` receives only ``StageView`` data (see its docstring) and
    returns the pack text plus any sandbox writes. Implementations hold the
    participant's retainable state Σ; the runner holds none.
    """

    def on_stage(self, stage: StageView) -> StageResponse: ...


@dataclass(frozen=True, slots=True)
class StageRecord:
    """Evaluator-side record of one executed stage.

    ``stale_fact_rate`` and ``delegation_completeness`` are placeholder
    record fields — family-qualification deliverables computed by the
    qualification battery (contract-tests §5), not by this runtime.
    """

    stage_id: str
    kind: str
    cited_doc_ids: tuple[str, ...]
    available_doc_ids: tuple[str, ...]
    provenance_retention: float
    actions_applied: int
    stale_fact_rate: float
    delegation_completeness: float
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "cited_doc_ids": list(self.cited_doc_ids),
            "available_doc_ids": list(self.available_doc_ids),
            "provenance_retention": self.provenance_retention,
            "actions_applied": self.actions_applied,
            "stale_fact_rate": self.stale_fact_rate,
            "delegation_completeness": self.delegation_completeness,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class LifecycleRunRecord:
    """The auditable outcome of one lifecycle run.

    ``cost`` carries the two-column split in miniature: ``tokens_in`` /
    ``tokens_out`` are placeholders the hook caller fills; ``wall_seconds``
    is measured. ``sandbox_final_state`` is the deep-copied end state the
    final check was computed against.
    """

    instance_id: str
    family: str
    final_check: CheckResult
    stage_records: tuple[StageRecord, ...]
    cost: Mapping[str, float]
    axes: DescriptionAxes
    sandbox_final_state: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "family": self.family,
            "final_check": self.final_check.to_dict(),
            "stage_records": [record.to_dict() for record in self.stage_records],
            "cost": dict(self.cost),
            "axes": self.axes.to_dict(),
            "sandbox_final_state": {
                record_id: dict(record) for record_id, record in self.sandbox_final_state.items()
            },
        }


def _provenance_retention(
    stage: StageSpec, cited: tuple[str, ...], available: tuple[str, ...]
) -> float:
    """Share of gold evidence the acting context cited, over available docs.

    Per task-family spec §Metrics: "did the acting context cite evidence that
    exists in the gold-support set". Cites of doc ids not in the stage's
    documents do not count (they are recorded in the stage record's notes).
    """

    gold = frozenset(stage.gold_evidence_ids)
    if not gold:
        return 1.0
    available_set = frozenset(available)
    valid_cites = frozenset(cited) & available_set
    return len(gold & valid_cites) / len(gold)


def _stage_notes(stage: StageSpec, cited: tuple[str, ...]) -> tuple[str, ...]:
    available = frozenset(document.doc_id for document in stage.documents)
    unknown = sorted(frozenset(cited) - available)
    return (f"cited unknown doc ids: {unknown}",) if unknown else ()


def _build_stage_view(stage: StageSpec, axes: DescriptionAxes, *, remaining: int) -> StageView:
    """Build the participant view of one stage — evaluator fields excluded.

    ``StageView`` is constructed from ``stage``'s participant-visible fields
    only; ``gold_evidence_ids`` and ``expected_state_delta`` are never read
    here, so no view (or serialization of one) can leak them.
    """

    return StageView(
        stage_id=stage.stage_id,
        kind=stage.kind,
        prompt_text=stage.prompt_text,
        documents=stage.documents,
        axes=axes,
        remaining_budget=remaining,
    )


def run_lifecycle(
    inst: LifecycleInstance, hook: ParticipantHook, env: ProjectState
) -> LifecycleRunRecord:
    """Execute ``inst``'s stages in order against ``hook``, writing into ``env``.

    Applies each stage's actions to ``env`` as they arrive (act_verify
    included), then checks the final sandbox state against the act_verify
    stage's ``expected_state_delta`` via ``ObjectiveChecker``. Raises on any
    invalid action application — a mid-run crash is an engineering record,
    not a silent zero.
    """

    if not isinstance(inst, LifecycleInstance):
        raise TypeError("run_lifecycle requires a LifecycleInstance")
    if not isinstance(env, ProjectState):
        raise TypeError("run_lifecycle requires a ProjectState")
    started = time.monotonic()
    stage_records: list[StageRecord] = []
    total_stages = len(inst.stages)
    for index, stage in enumerate(inst.stages):
        view = _build_stage_view(stage, inst.axes, remaining=total_stages - index)
        response = hook.on_stage(view)
        if not isinstance(response, StageResponse):
            raise TypeError(
                f"hook returned {type(response).__name__} for stage "
                f"{stage.stage_id!r}; expected StageResponse"
            )
        for action in response.actions:
            env.apply(action)
        cited = view.cited_doc_ids(response.pack_text)
        available = tuple(document.doc_id for document in stage.documents)
        stage_records.append(
            StageRecord(
                stage_id=stage.stage_id,
                kind=stage.kind,
                cited_doc_ids=cited,
                available_doc_ids=available,
                provenance_retention=_provenance_retention(stage, cited, available),
                actions_applied=len(response.actions),
                stale_fact_rate=0.0,
                delegation_completeness=0.0,
                notes=_stage_notes(stage, cited),
            )
        )
    act_verify = inst.stages[-1]
    expected = act_verify.expected_state_delta
    if expected is None:  # guarded by StageSpec.__post_init__; kept for mypy
        raise ValueError("act_verify stage lacks expected_state_delta")
    final_check = ObjectiveChecker().check(env, expected)
    wall_seconds = time.monotonic() - started
    return LifecycleRunRecord(
        instance_id=inst.instance_id,
        family=inst.family,
        final_check=final_check,
        stage_records=tuple(stage_records),
        cost={"tokens_in": 0.0, "tokens_out": 0.0, "wall_seconds": wall_seconds},
        axes=inst.axes,
        sandbox_final_state=env.snapshot(),
    )
