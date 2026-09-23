"""Task-lifecycle instance schema for the research-v1 family.

Spec: ``docs/task-family-research-v1.md`` (frozen 2026-09-19) under the v2
contract ``docs/benchmark-contract-v2.md``. One instance is one evidence
project in five stages; the five description axes are carried as metadata,
never collapsed into one difficulty score.

Evaluator-only fields: ``StageSpec.gold_evidence_ids``,
``StageSpec.expected_state_delta``, and ``StageSpec.expected_aliases`` MUST
NEVER be surfaced to ``run()`` / ``ParticipantHook`` callers — the runner
constructs ``StageView`` from a ``StageSpec`` minus exactly these fields, so
the exclusion is enforced by construction (see ``runner.py``). They exist here
for the evaluator and for instance serialization only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

StageKind = Literal[
    "survey",
    "constraint_injection",
    "delegation",
    "rule_change",
    "act_verify",
    "follow_up",
]
ActionDependency = Literal["weak", "strong"]

_STAGE_KINDS: tuple[str, ...] = (
    "survey",
    "constraint_injection",
    "delegation",
    "rule_change",
    "act_verify",
)
#: research-v4 longitudinal follow-up stages: new material AFTER the
#: commit, graded by their own expected_state_delta (a conclusion record
#: the participant must create/refresh from retained or re-read evidence).
_STAGE_KINDS_V4: tuple[str, ...] = (*_STAGE_KINDS, "follow_up")
_ACTION_DEPENDENCIES: tuple[str, ...] = ("weak", "strong")
_FAMILY_RESEARCH_V1 = "research-v1"
# research-v2: the leak-closed revision (docs/dependency-probes-20260920.md) —
# same stage grammar, no answer-bearing evidence after stage 1, stage 5 empty.
_FAMILY_RESEARCH_V2 = "research-v2"
# research-v3: the migration-decision main world (docs/task-card-research-v3.md) —
# scoped constraint, partial rule change, precondition-checked commits.
_FAMILY_RESEARCH_V3 = "research-v3"
# research-v4: the A-group main tasks (persistent evidence synthesis) —
# LONGITUDINAL grammar: the five v1/v3 stages PLUS follow-up stages after
# the commit. The horizon is longer than one commit: earlier conclusions
# must survive, be revised when superseded, and still drive later answers.
# The stage ORDER still starts with the v1 five; what v4 adds is follow-up
# material (each kind may repeat).
_FAMILY_RESEARCH_V4 = "research-v4"
_REGISTERED_FAMILIES = (
    _FAMILY_RESEARCH_V1,
    _FAMILY_RESEARCH_V2,
    _FAMILY_RESEARCH_V3,
    _FAMILY_RESEARCH_V4,
)


def _require_str(value: object, field: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty")


def _require_int(value: object, field: str, *, minimum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")


def _require_choice(value: object, field: str, options: tuple[str, ...]) -> None:
    if not isinstance(value, str) or value not in options:
        raise ValueError(f"{field} must be one of {options}")


@dataclass(frozen=True, slots=True)
class DescriptionAxes:
    """The five per-instance description axes (spec §Description axes).

    Reported in distributions; never aggregated into a single difficulty
    score. ``dependency_distance_stages`` is the 1-4 stage span between an
    information item's availability and its use.
    """

    information_scale_tokens: int
    dependency_distance_stages: int
    persistence_span_resets: int
    action_dependency: ActionDependency
    environment_changes: int

    def __post_init__(self) -> None:
        _require_int(self.information_scale_tokens, "information_scale_tokens", minimum=1)
        _require_int(self.dependency_distance_stages, "dependency_distance_stages", minimum=1)
        if self.dependency_distance_stages > 4:
            raise ValueError("dependency_distance_stages must be at most 4")
        _require_int(self.persistence_span_resets, "persistence_span_resets", minimum=0)
        _require_choice(self.action_dependency, "action_dependency", _ACTION_DEPENDENCIES)
        _require_int(self.environment_changes, "environment_changes", minimum=0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "information_scale_tokens": self.information_scale_tokens,
            "dependency_distance_stages": self.dependency_distance_stages,
            "persistence_span_resets": self.persistence_span_resets,
            "action_dependency": self.action_dependency,
            "environment_changes": self.environment_changes,
        }


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """One real document embedded in the project's document base.

    Provenance is a typed field per the spec (§Instance material): every
    document carries ``source_url`` and ``retrieved_date`` so stage-4
    supersession detection can depend on retained provenance, not just
    conclusions. ``superseded_by`` marks the rule-change supersession signal.
    ``text`` may embed ``[[doc:ID]]`` markers emitted by ``material``.
    """

    doc_id: str
    title: str
    text: str
    source_url: str = ""
    retrieved_date: str = ""
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        _require_str(self.doc_id, "doc_id")
        _require_str(self.title, "title")
        _require_str(self.text, "text", allow_empty=True)
        _require_str(self.source_url, "source_url", allow_empty=True)
        _require_str(self.retrieved_date, "retrieved_date", allow_empty=True)
        if self.superseded_by is not None:
            _require_str(self.superseded_by, "superseded_by")

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "source_url": self.source_url,
            "retrieved_date": self.retrieved_date,
            "superseded_by": self.superseded_by,
        }


@dataclass(frozen=True, slots=True)
class StageSpec:
    """One lifecycle stage.

    ``gold_evidence_ids``, ``expected_state_delta``, and ``expected_aliases``
    are evaluator-only fields (see module docstring): they must never appear in
    any view handed to a participant. ``expected_state_delta`` is required
    (non-None) for ``act_verify`` stages — it is what the final project state
    must contain. ``expected_aliases`` (act_verify stages only) carries the
    answer's full alias set so final checks can be alias-aware instead of
    pinned on the primary answer alone.
    """

    stage_id: str
    kind: StageKind
    prompt_text: str
    documents: tuple[DocumentRef, ...]
    gold_evidence_ids: tuple[str, ...]
    expected_state_delta: Mapping[str, object] | None = None
    expected_aliases: tuple[str, ...] = ()
    commit_precondition: Mapping[str, object] | None = None
    verification_oracle: Mapping[str, Mapping[str, bool]] | None = None
    rule_change_effect: int | None = None

    def __post_init__(self) -> None:
        _require_str(self.stage_id, "stage_id")
        _require_choice(self.kind, "kind", (*_STAGE_KINDS, "follow_up"))
        _require_str(self.prompt_text, "prompt_text")
        object.__setattr__(self, "documents", tuple(self.documents))
        object.__setattr__(self, "gold_evidence_ids", tuple(self.gold_evidence_ids))
        if any(not isinstance(document, DocumentRef) for document in self.documents):
            raise TypeError("stage documents must be DocumentRef values")
        for evidence_id in self.gold_evidence_ids:
            _require_str(evidence_id, "gold_evidence_ids entry")
        known_doc_ids = frozenset(document.doc_id for document in self.documents)
        if any(evidence_id not in known_doc_ids for evidence_id in self.gold_evidence_ids):
            raise ValueError("gold evidence ids must reference stage documents")
        if self.verification_oracle is not None:
            if self.kind != "act_verify":
                raise ValueError("only act_verify stages carry verification_oracle")
            if not isinstance(self.verification_oracle, Mapping):
                raise TypeError("verification_oracle must be a mapping or None")
            object.__setattr__(self, "verification_oracle", self._copy_oracle())
        if self.rule_change_effect is not None:
            if self.kind != "rule_change":
                raise ValueError("only rule_change stages carry rule_change_effect")
            if not isinstance(self.rule_change_effect, int) or isinstance(
                self.rule_change_effect, bool
            ):
                raise TypeError("rule_change_effect must be an int or None")
            if self.rule_change_effect < 1:
                raise ValueError("rule_change_effect must be a positive revision")
        if self.expected_state_delta is not None:
            if not isinstance(self.expected_state_delta, Mapping):
                raise TypeError("expected_state_delta must be a mapping or None")
            object.__setattr__(self, "expected_state_delta", dict(self.expected_state_delta))
        object.__setattr__(self, "expected_aliases", tuple(self.expected_aliases))
        for alias in self.expected_aliases:
            _require_str(alias, "expected_aliases entry")
        if self.kind == "act_verify" and self.expected_state_delta is None:
            raise ValueError("act_verify stages require expected_state_delta")
        if self.kind not in ("act_verify", "follow_up") and self.expected_state_delta is not None:
            raise ValueError("only act_verify/follow_up stages carry expected_state_delta")
        if self.kind not in ("act_verify", "follow_up") and self.expected_aliases:
            raise ValueError("only act_verify/follow_up stages carry expected_aliases")
        if self.commit_precondition is not None:
            if self.kind != "act_verify":
                raise ValueError("only act_verify stages carry commit_precondition")
            if not isinstance(self.commit_precondition, Mapping):
                raise TypeError("commit_precondition must be a mapping or None")
            object.__setattr__(self, "commit_precondition", dict(self.commit_precondition))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "prompt_text": self.prompt_text,
            "documents": [document.to_dict() for document in self.documents],
            "gold_evidence_ids": list(self.gold_evidence_ids),
            "expected_state_delta": (
                None if self.expected_state_delta is None else dict(self.expected_state_delta)
            ),
            "expected_aliases": list(self.expected_aliases),
            "commit_precondition": (
                None if self.commit_precondition is None else dict(self.commit_precondition)
            ),
            "verification_oracle": (
                None
                if self.verification_oracle is None
                else {check: dict(subjects) for check, subjects in self.verification_oracle.items()}
            ),
            "rule_change_effect": self.rule_change_effect,
        }

    def _copy_oracle(self) -> dict[str, dict[str, bool]]:
        """A structurally independent copy of a JSON-native oracle."""

        return {
            check: dict(subjects)
            for check, subjects in self.verification_oracle.items()  # type: ignore[union-attr]
            if isinstance(subjects, Mapping)
        }


@dataclass(frozen=True, slots=True)
class LifecycleInstance:
    """A complete five-stage research-v1 evidence project.

    ``answer_aliases`` is the full PopQA ``possible_answers`` alias set;
    ``answer_norm`` remains the primary answer the act_verify prompt asks the
    agent to commit. Default empty tuple keeps older constructors/payloads
    loadable (alias-unaware).
    """

    instance_id: str
    family: str
    stages: tuple[StageSpec, ...]
    axes: DescriptionAxes
    answer_norm: str
    sandbox_spec: Mapping[str, object]
    answer_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_str(self.instance_id, "instance_id")
        _require_str(self.family, "family")
        if self.family not in _REGISTERED_FAMILIES:
            raise ValueError(f"family must be one of {_REGISTERED_FAMILIES!r}, got {self.family!r}")
        object.__setattr__(self, "stages", tuple(self.stages))
        if any(not isinstance(stage, StageSpec) for stage in self.stages):
            raise TypeError("instance stages must be StageSpec values")
        if not self.stages:
            raise ValueError("an instance requires at least one stage")
        kinds = [stage.kind for stage in self.stages]
        if self.family == _FAMILY_RESEARCH_V4:
            # Longitudinal grammar: the v1 five stages, then follow-up
            # material (kinds may repeat). The horizon extends past the
            # first commit: earlier conclusions must survive, be revised
            # when superseded, and still drive later answers.
            if kinds[:5] != list(_STAGE_KINDS):
                raise ValueError(
                    "research-v4 instances begin with the five v1 stages "
                    f"(survey, constraint_injection, delegation, rule_change, act_verify); got {kinds[:5]}"
                )
            if len(kinds) <= 5:
                raise ValueError("research-v4 instances carry follow-up stages after act_verify")
        elif kinds != list(_STAGE_KINDS):
            raise ValueError(
                "research-v1 instances run the five stages in order (survey, "
                "constraint_injection, delegation, rule_change, act_verify); got {kinds}"
            )
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("stage ids must be unique within an instance")
        if not isinstance(self.axes, DescriptionAxes):
            raise TypeError("axes must be a DescriptionAxes value")
        _require_str(self.answer_norm, "answer_norm")
        if not isinstance(self.sandbox_spec, Mapping):
            raise TypeError("sandbox_spec must be a mapping")
        object.__setattr__(self, "sandbox_spec", dict(self.sandbox_spec))
        object.__setattr__(self, "answer_aliases", tuple(self.answer_aliases))
        for alias in self.answer_aliases:
            _require_str(alias, "answer_aliases entry")
        if self.answer_aliases and self.answer_norm not in self.answer_aliases:
            raise ValueError("answer_aliases must contain answer_norm when non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "family": self.family,
            "stages": [stage.to_dict() for stage in self.stages],
            "axes": self.axes.to_dict(),
            "answer_norm": self.answer_norm,
            "sandbox_spec": dict(self.sandbox_spec),
            "answer_aliases": list(self.answer_aliases),
        }


def _load_str(d: Mapping[str, object], key: str, *, allow_empty: bool = False) -> str:
    value = d.get(key)
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    if not allow_empty and not value:
        raise ValueError(f"{key} must not be empty")
    return value


def _load_optional_str(d: Mapping[str, object], key: str) -> str:
    value = d.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string when present")
    return value


def _load_int(d: Mapping[str, object], key: str) -> int:
    value = d.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer")
    return value


def _load_choice(d: Mapping[str, object], key: str, options: tuple[str, ...]) -> str:
    value = d.get(key)
    if not isinstance(value, str) or value not in options:
        raise ValueError(f"{key} must be one of {options}")
    return value


def _load_str_list(d: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = d.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list")
    entries: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise TypeError(f"{key} entries must be strings")
        entries.append(entry)
    return tuple(entries)


def _load_document(d: Mapping[str, object]) -> DocumentRef:
    superseded_by = d.get("superseded_by")
    if superseded_by is not None and not isinstance(superseded_by, str):
        raise TypeError("superseded_by must be a string or null")
    return DocumentRef(
        doc_id=_load_str(d, "doc_id"),
        title=_load_str(d, "title"),
        text=_load_str(d, "text", allow_empty=True),
        source_url=_load_optional_str(d, "source_url"),
        retrieved_date=_load_optional_str(d, "retrieved_date"),
        superseded_by=superseded_by,
    )


def _load_stage(d: Mapping[str, object]) -> StageSpec:
    raw_documents = d.get("documents", [])
    if not isinstance(raw_documents, list):
        raise TypeError("stage documents must be a list")
    documents: list[DocumentRef] = []
    for raw_document in raw_documents:
        if not isinstance(raw_document, Mapping):
            raise TypeError("each stage document must be a mapping")
        documents.append(_load_document(raw_document))
    raw_delta = d.get("expected_state_delta")
    expected: Mapping[str, object] | None
    if raw_delta is None:
        expected = None
    elif isinstance(raw_delta, Mapping):
        expected = dict(raw_delta)
    else:
        raise TypeError("expected_state_delta must be a mapping or null")
    raw_precondition = d.get("commit_precondition")
    precondition: Mapping[str, object] | None
    if raw_precondition is None:
        precondition = None
    elif isinstance(raw_precondition, Mapping):
        precondition = dict(raw_precondition)
    else:
        raise TypeError("commit_precondition must be a mapping or null")
    raw_oracle = d.get("verification_oracle")
    oracle: Mapping[str, Mapping[str, bool]] | None
    if raw_oracle is None:
        oracle = None
    elif isinstance(raw_oracle, Mapping):
        oracle = {
            check: dict(subjects)
            for check, subjects in raw_oracle.items()  # type: ignore[union-attr]
        }
    else:
        raise TypeError("verification_oracle must be a mapping or null")
    raw_effect = d.get("rule_change_effect")
    effect: int | None
    if raw_effect is None:
        effect = None
    elif isinstance(raw_effect, int) and not isinstance(raw_effect, bool) and raw_effect >= 1:
        effect = raw_effect
    else:
        raise TypeError("rule_change_effect must be a positive integer or null")
    return StageSpec(
        stage_id=_load_str(d, "stage_id"),
        kind=cast(StageKind, _load_choice(d, "kind", (*_STAGE_KINDS, "follow_up"))),
        prompt_text=_load_str(d, "prompt_text"),
        documents=tuple(documents),
        gold_evidence_ids=_load_str_list(d, "gold_evidence_ids"),
        expected_state_delta=expected,
        expected_aliases=_load_str_list(d, "expected_aliases"),
        commit_precondition=precondition,
        verification_oracle=oracle,
        rule_change_effect=effect,
    )


def _load_axes(d: Mapping[str, object]) -> DescriptionAxes:
    return DescriptionAxes(
        information_scale_tokens=_load_int(d, "information_scale_tokens"),
        dependency_distance_stages=_load_int(d, "dependency_distance_stages"),
        persistence_span_resets=_load_int(d, "persistence_span_resets"),
        action_dependency=cast(
            ActionDependency, _load_choice(d, "action_dependency", _ACTION_DEPENDENCIES)
        ),
        environment_changes=_load_int(d, "environment_changes"),
    )


def load_instance(d: Mapping[str, object]) -> LifecycleInstance:
    """Rebuild a ``LifecycleInstance`` from its canonical mapping form."""

    if not isinstance(d, Mapping):
        raise TypeError("instance payload must be a mapping")
    raw_axes = d.get("axes")
    if not isinstance(raw_axes, Mapping):
        raise TypeError("axes must be a mapping")
    raw_stages = d.get("stages")
    if not isinstance(raw_stages, list):
        raise TypeError("instance stages must be a list")
    stages: list[StageSpec] = []
    for raw_stage in raw_stages:
        if not isinstance(raw_stage, Mapping):
            raise TypeError("each stage must be a mapping")
        stages.append(_load_stage(raw_stage))
    raw_sandbox = d.get("sandbox_spec", {})
    if not isinstance(raw_sandbox, Mapping):
        raise TypeError("sandbox_spec must be a mapping")
    return LifecycleInstance(
        instance_id=_load_str(d, "instance_id"),
        family=_load_str(d, "family"),
        stages=tuple(stages),
        axes=_load_axes(raw_axes),
        answer_norm=_load_str(d, "answer_norm"),
        sandbox_spec=dict(raw_sandbox),
        answer_aliases=_load_str_list(d, "answer_aliases"),
    )


def dump_instance(inst: LifecycleInstance) -> dict[str, Any]:
    """Canonical mapping form of ``inst`` (sorted-key JSON byte-stable)."""

    if not isinstance(inst, LifecycleInstance):
        raise TypeError("dump_instance requires a LifecycleInstance")
    return inst.to_dict()


def canonical_instance_json(inst: LifecycleInstance) -> str:
    """Sorted-key, deterministic JSON encoding used for byte-stability checks."""

    return json.dumps(
        dump_instance(inst), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
