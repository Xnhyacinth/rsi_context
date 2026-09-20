"""Deterministic project-state action environment (research-v1 stage 5).

Spec: ``docs/task-family-research-v1.md`` §Sandbox write step — a minimal
deterministic project-state store (create/update records with typed fields),
evaluated by objective state comparison. No general tool execution in v1 of
this family; the only writes are the typed actions below, so the evaluator
verifies the actual end state, never the stated one ("reported done" ≠
"state is correct").

This module also owns ``alias_hit`` — the alias-aware answer containment
scorer from the 2026-09-20 root-cause report (single-alias pinning with
strict substring matching mislabeled evidence-supported reader phrasings).
It lives here, next to ``ObjectiveChecker`` (its primary consumer), so
scoring and the build-time gold-entailment gate in ``material.py`` share one
normalization implementation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ActionKind = Literal["create_record", "update_record", "finalize"]

_ACTION_KINDS: tuple[str, ...] = ("create_record", "update_record", "finalize")
_PROVENANCE_FIELD = "provenance"
_ANSWER_FIELD = "answer"
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_answer_text(text: str) -> str:
    """Case-fold, strip punctuation (to spaces), and collapse whitespace.

    The single normalization shared by ``alias_hit`` scoring here and the
    build-time gold-entailment gate in ``material.py`` — one implementation
    so the two gates can never drift apart.
    """

    return _WHITESPACE.sub(" ", _NON_WORD.sub(" ", text.casefold())).strip()


def alias_hit(reply: str, aliases: tuple[str, ...]) -> bool:
    """True when ``reply`` and any alias match by normalized containment.

    Both sides are normalized (case-insensitive, punctuation replaced by
    spaces, whitespace collapsed); a hit is ``alias in reply`` OR ``reply in
    alias`` — so a verbatim evidence phrasing containing an alias ("power
    pop, punk, punk pop" vs "punk") and a short-form reply inside an alias
    ("POL" vs "Republic of Poland") both count. An empty reply never hits.
    """

    reply_norm = normalize_answer_text(reply)
    if not reply_norm:
        return False
    for alias in aliases:
        alias_norm = normalize_answer_text(alias)
        if alias_norm and (alias_norm in reply_norm or reply_norm in alias_norm):
            return True
    return False


def _require_str(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class Action:
    """One typed write into the sandboxed project state.

    ``provenance`` is required non-empty for ``finalize`` actions per the
    stage-5 semantics (task-family spec §Task structure: the check depends on
    whether the agent kept provenance, not just conclusions).
    """

    kind: ActionKind
    record_id: str
    fields: Mapping[str, object] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or self.kind not in _ACTION_KINDS:
            raise ValueError(f"action kind must be one of {_ACTION_KINDS}")
        _require_str(self.record_id, "record_id")
        if not isinstance(self.fields, Mapping):
            raise TypeError("action fields must be a mapping")
        object.__setattr__(self, "fields", dict(self.fields))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        for entry in self.provenance:
            _require_str(entry, "provenance entry")
        if self.kind == "finalize" and not self.provenance:
            raise ValueError("finalize actions require non-empty provenance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "record_id": self.record_id,
            "fields": dict(self.fields),
            "provenance": list(self.provenance),
        }


class ProjectStateError(RuntimeError):
    """Raised when an action cannot be applied to the project state."""


class ProjectState:
    """The typed record store one lifecycle writes into.

    Mutable by ``apply`` only; every applied action is appended to the
    transcript so a run record can audit the actual end state (contract
    §Protocol semantics: the full state transcript is logged and auditable).
    """

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.transcript: tuple[Action, ...] = ()

    def apply(self, action: Action) -> None:
        """Apply one typed action; invalid applications raise, never no-op."""

        if not isinstance(action, Action):
            raise TypeError("apply requires an Action value")
        if action.kind == "create_record":
            if action.record_id in self.records:
                raise ProjectStateError(
                    f"record {action.record_id!r} already exists; use update_record"
                )
            record: dict[str, Any] = dict(action.fields)
            if action.provenance:
                record[_PROVENANCE_FIELD] = list(action.provenance)
            self.records[action.record_id] = record
        elif action.kind == "update_record":
            if action.record_id not in self.records:
                raise ProjectStateError(
                    f"record {action.record_id!r} does not exist; use create_record"
                )
            target = self.records[action.record_id]
            for key, value in action.fields.items():
                target[key] = value
            self._merge_provenance(target, action.provenance)
        else:  # finalize
            if action.record_id not in self.records:
                raise ProjectStateError(
                    f"finalize target record {action.record_id!r} does not exist"
                )
            target = self.records[action.record_id]
            for key, value in action.fields.items():
                target[key] = value
            self._merge_provenance(target, action.provenance)
        self.transcript = (*self.transcript, action)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Copied records view for structural comparison."""

        return {
            record_id: {
                key: (list(value) if isinstance(value, list) else value)
                for key, value in record.items()
            }
            for record_id, record in self.records.items()
        }

    @staticmethod
    def _merge_provenance(target: dict[str, Any], provenance: tuple[str, ...]) -> None:
        if not provenance:
            return
        merged = list(target.get(_PROVENANCE_FIELD, []))
        merged.extend(entry for entry in provenance if entry not in merged)
        target[_PROVENANCE_FIELD] = merged


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Objective end-state check outcome with per-field failure detail."""

    passed: bool
    failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "failures", tuple(self.failures))
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "failures": list(self.failures)}


class ObjectiveChecker:
    """Exact structural comparison of named records against expectations.

    The expected mapping names records and the field values the final project
    state must contain. Extra records and extra fields are ignored (``expected``
    names what must hold, not what must be absent); named-but-missing records,
    missing fields, and unequal values are failures. Nested values are compared
    by equality only — v1 of this family uses flat typed fields by design.

    Alias mode: with ``aliases`` given, ``answer`` fields additionally pass
    via :func:`alias_hit` (normalized containment against the full alias set),
    fixing the single-alias pinning root cause — a committed "power pop, punk,
    punk pop" against expected "punk rock" passes when "punk" is an alias.
    All other fields stay exact regardless; ``aliases=None`` (default) is the
    original fully-exact behavior.
    """

    def check(
        self,
        state: ProjectState,
        expected: Mapping[str, object],
        aliases: tuple[str, ...] | None = None,
    ) -> CheckResult:
        if not isinstance(state, ProjectState):
            raise TypeError("check requires a ProjectState value")
        if not isinstance(expected, Mapping):
            raise TypeError("expected must be a mapping")
        records = state.records
        failures: list[str] = []
        for record_id in sorted(expected):
            expected_fields = expected[record_id]
            if not isinstance(expected_fields, Mapping):
                raise TypeError(f"expected[{record_id!r}] must be a mapping of record fields")
            if record_id not in records:
                failures.append(f"record {record_id!r}: missing")
                continue
            actual = records[record_id]
            for field_name in sorted(expected_fields):
                expected_value = expected_fields[field_name]
                if field_name not in actual:
                    failures.append(f"record {record_id!r}: field {field_name!r} missing")
                elif not self._field_equal(actual[field_name], expected_value, field_name, aliases):
                    failures.append(
                        f"record {record_id!r}: field {field_name!r} "
                        f"expected {expected_value!r}, got {actual[field_name]!r}"
                    )
        return CheckResult(passed=not failures, failures=tuple(failures))

    @staticmethod
    def _field_equal(
        actual: object, expected: object, field_name: str, aliases: tuple[str, ...] | None
    ) -> bool:
        if (
            aliases
            and field_name == _ANSWER_FIELD
            and isinstance(actual, str)
            and alias_hit(actual, aliases)
        ):
            return True
        return ObjectiveChecker._equal(actual, expected)

    @staticmethod
    def _equal(actual: object, expected: object) -> bool:
        if isinstance(actual, list) and isinstance(expected, (list, tuple)):
            return list(expected) == actual
        if isinstance(expected, list) and isinstance(actual, (list, tuple)):
            return expected == list(actual)
        return actual == expected
