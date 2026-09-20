"""Coupled task-lifecycle runtime for RSIBench-Context v2 (Phase B).

Implements the research-v1 lifecycle instrument specified in
``docs/task-family-research-v1.md`` under the v2 contract
(``docs/benchmark-contract-v2.md``): a five-stage evidence project whose
stages are executed against a participant-agnostic hook, with evaluator-only
fields never surfaced to ``run()`` callers.
"""

from .env import Action, CheckResult, ObjectiveChecker, ProjectState, alias_hit
from .material import build_example_instance, gold_entailment_sane
from .runner import LifecycleRunRecord, ParticipantHook, StageResponse, StageView, run_lifecycle
from .spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageKind,
    StageSpec,
    dump_instance,
    load_instance,
)

__all__ = [
    "Action",
    "CheckResult",
    "DescriptionAxes",
    "DocumentRef",
    "LifecycleInstance",
    "LifecycleRunRecord",
    "ObjectiveChecker",
    "ParticipantHook",
    "ProjectState",
    "StageKind",
    "StageResponse",
    "StageSpec",
    "StageView",
    "alias_hit",
    "build_example_instance",
    "dump_instance",
    "gold_entailment_sane",
    "load_instance",
    "run_lifecycle",
]
