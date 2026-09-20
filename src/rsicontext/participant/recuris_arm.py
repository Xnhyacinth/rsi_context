"""Recuris-style participant arm: component-scoped, validation-gated memory evolution.

This module is the review step-5 small-fidelity integration: it proves the
participant interface (docs/participant-interface-v1.md) admits a
Recuris-STYLE improvement process with its core mechanisms preserved, not a
plain file editor. The improved object is a memory package
``M = (E, W, rho, C)`` in the sense of the pinned Recuris checkout
(``external/recuris``, Apache-2.0, arXiv:2608.24876): experiential cards, a
working-memory contract, an invocation policy, and checkers — evolved one
component-scoped patch per round under a deterministic
accept-only-if-repair-and-regression gate.

Restricted feedback consumed by this build (a documented subset of the frozen
F schema; anything else parses as an empty report and the round admits
nothing — a round that admits nothing is a valid outcome)::

    {"signals": [
      {"kind": "stage_failure", "item_id": "i2", "stage": "verify",
       "missing_skill": "verify_citations"},
      {"kind": "usage_anomaly", "item_id": "i3", "budget_tokens": 12000,
       "stages": ["retrieve", "read"]},
      {"kind": "unknown_state_field", "item_id": "i4", "field": "open_queries"}
    ]}

Cross-round participant state (``Sigma``) carries the patch ledger and the
previous round's feedback (the regression evidence). The memory package
itself travels as the agent data file ``memory_package.json`` — skills,
config, and workflows are valid state carriers under the participant
interface, so strategy code stays byte-frozen while the package evolves.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final, Literal

from rsicontext.participant.registration import (
    ImprovementRoundInput,
    ImprovementRoundOutput,
    canonical_json_bytes,
)
from rsicontext.participant.usage import UsageReport

MEMORY_PACKAGE_FILENAME: Final = "memory_package.json"
_SIGNAL_KINDS: Final = frozenset({"stage_failure", "usage_anomaly", "unknown_state_field"})
_KIND_ORDER: Final = {"stage_failure": 0, "usage_anomaly": 1, "unknown_state_field": 2}
_EM_TYPES: Final = frozenset({"knowledge", "procedure", "action_result"})
_PACKAGE_KEYS: Final = frozenset({"name", "E", "W", "rho", "C"})
_CARD_KEYS: Final = frozenset(
    {"id", "type", "stage", "handles", "requires_field", "body", "source"}
)
_WM_KEYS: Final = frozenset({"goals", "state_fields", "base_token_cost"})
_RHO_KEYS: Final = frozenset({"invoked_on_stages", "max_cards_per_stage", "per_card_token_cost"})


class RecurisArmError(ValueError):
    """Raised when this arm violates its own memory-package or state contract."""


# --- Failure signals: the restricted-feedback subset this build localizes ---


@dataclass(frozen=True, slots=True)
class FailureSignal:
    """One structured failure observation from the restricted feedback ``F``.

    ``signal_id`` is the deterministic identity the regression gate compares
    across rounds. Optional fields are populated per ``kind``; a signal whose
    kind-required fields are absent is malformed and never localized.
    """

    kind: str
    item_id: str
    stage: str | None = None
    missing_skill: str | None = None
    field_name: str | None = None
    budget_tokens: int | None = None
    stages: tuple[str, ...] = ()

    @property
    def signal_id(self) -> str:
        if self.kind == "stage_failure":
            return f"stage_failure:{self.item_id}:{self.stage}:{self.missing_skill}"
        if self.kind == "usage_anomaly":
            return f"usage_anomaly:{self.item_id}:{self.budget_tokens}:{','.join(self.stages)}"
        return f"unknown_state_field:{self.item_id}:{self.field_name}"

    def to_mapping(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "item_id": self.item_id,
            "stage": self.stage,
            "missing_skill": self.missing_skill,
            "field": self.field_name,
            "budget_tokens": self.budget_tokens,
            "stages": list(self.stages),
        }


def _try_signal(entry: Mapping[str, object]) -> FailureSignal | None:
    """Tolerant signal parse: malformed entries drop to None, never raise.

    Benchmark-owned feedback bytes are untrusted input of unknown shape, so
    this never raises — unknown kinds and bad fields simply yield no signal.
    """

    kind = entry.get("kind")
    item_id = entry.get("item_id")
    stage = entry.get("stage")
    missing_skill = entry.get("missing_skill")
    field_name = entry.get("field")
    budget = entry.get("budget_tokens")
    raw_stages = entry.get("stages")
    if not isinstance(kind, str) or kind not in _SIGNAL_KINDS:
        return None
    if not isinstance(item_id, str) or not item_id:
        return None
    if stage is not None and not isinstance(stage, str):
        return None
    if missing_skill is not None and not isinstance(missing_skill, str):
        return None
    if field_name is not None and not isinstance(field_name, str):
        return None
    if budget is not None and (not isinstance(budget, int) or isinstance(budget, bool)):
        return None
    stages: list[str] = []
    if raw_stages is not None:
        if not isinstance(raw_stages, list):
            return None
        for value in raw_stages:
            if not isinstance(value, str):
                return None
            stages.append(value)
    if kind == "stage_failure" and (stage is None or missing_skill is None):
        return None
    if kind == "usage_anomaly" and budget is None:
        return None
    if kind == "unknown_state_field" and field_name is None:
        return None
    return FailureSignal(
        kind=kind,
        item_id=item_id,
        stage=stage,
        missing_skill=missing_skill,
        field_name=field_name,
        budget_tokens=budget,
        stages=tuple(stages),
    )


@dataclass(frozen=True, slots=True)
class FeedbackReport:
    """Parsed restricted feedback: the only evidence the localizer sees."""

    signals: tuple[FailureSignal, ...] = ()

    @classmethod
    def parse(cls, raw: bytes) -> FeedbackReport:
        """Tolerant parse of benchmark-owned feedback bytes (never raises)."""

        try:
            payload: object = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return cls()
        if not isinstance(payload, dict):
            return cls()
        raw_signals = payload.get("signals")
        if not isinstance(raw_signals, list):
            return cls()
        signals = []
        for entry in raw_signals:
            if not isinstance(entry, dict):
                continue
            signal = _try_signal(entry)
            if signal is not None:
                signals.append(signal)
        return cls(tuple(signals))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> FeedbackReport:
        """Strict parse for participant-owned state round-trips (raises)."""

        raw_signals = payload.get("signals")
        if not isinstance(raw_signals, list):
            raise RecurisArmError("feedback record must carry a signals list")
        signals: list[FailureSignal] = []
        for entry in raw_signals:
            if not isinstance(entry, Mapping):
                raise RecurisArmError("feedback signal entries must be objects")
            signal = _try_signal(entry)
            if signal is None:
                raise RecurisArmError("feedback signal entry is malformed")
            signals.append(signal)
        return cls(tuple(signals))

    def to_mapping(self) -> dict[str, object]:
        return {"signals": [signal.to_mapping() for signal in self.signals]}


# --- The memory package M = (E, W, rho): data, one component per patch ---


@dataclass(frozen=True, slots=True)
class EEntry:
    """One experiential card (Recuris ``em/<type>/<id>.md``, one card per file).

    ``handles`` names the situation classes the card covers (Recuris routes by
    card type and trigger; here delivery is keyed on stage plus handles).
    ``requires_field`` makes invocation state-grounded: the card is delivered
    only when working memory tracks that field.
    """

    id: str
    type: str
    stage: str
    handles: tuple[str, ...]
    requires_field: str | None
    body: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise RecurisArmError("card id must be a non-empty string")
        if self.type not in _EM_TYPES:
            raise RecurisArmError(f"card type must be one of {sorted(_EM_TYPES)}: {self.type!r}")
        if not isinstance(self.stage, str) or not self.stage:
            raise RecurisArmError("card stage must be a non-empty string")

    def to_mapping(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type,
            "stage": self.stage,
            "handles": list(self.handles),
            "requires_field": self.requires_field,
            "body": self.body,
            "source": self.source,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> EEntry:
        if set(payload) != _CARD_KEYS:
            raise RecurisArmError(f"card keys must be exactly {sorted(_CARD_KEYS)}")
        handles_raw = payload["handles"]
        if not isinstance(handles_raw, list):
            raise RecurisArmError("card handles must be a list")
        handles: list[str] = []
        for value in handles_raw:
            if not isinstance(value, str):
                raise RecurisArmError("card handles must be strings")
            handles.append(value)
        requires_field = payload["requires_field"]
        if requires_field is not None and not isinstance(requires_field, str):
            raise RecurisArmError("card requires_field must be a string or null")
        return cls(
            id=_strict_str(payload["id"], "card id"),
            type=_strict_str(payload["type"], "card type"),
            stage=_strict_str(payload["stage"], "card stage"),
            handles=tuple(handles),
            requires_field=requires_field,
            body=_strict_str(payload["body"], "card body"),
            source=_strict_str(payload["source"], "card source"),
        )


@dataclass(frozen=True, slots=True)
class WorkingMemory:
    """W: the working-memory contract — goals, tracked state fields, base cost.

    Mirrors the Recuris manifest ``wm:`` block (entry schema, manager, limits):
    the tracked-field set is what card delivery is grounded on, and the base
    token cost is the standing cost of rendering working state each round.
    """

    goals: tuple[str, ...]
    state_fields: Mapping[str, object]
    base_token_cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.base_token_cost, int) or isinstance(self.base_token_cost, bool):
            raise RecurisArmError("base_token_cost must be an integer")
        if self.base_token_cost < 0:
            raise RecurisArmError("base_token_cost must be non-negative")

    def to_mapping(self) -> dict[str, object]:
        return {
            "goals": list(self.goals),
            "state_fields": dict(self.state_fields),
            "base_token_cost": self.base_token_cost,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> WorkingMemory:
        if set(payload) != _WM_KEYS:
            raise RecurisArmError(f"working-memory keys must be exactly {sorted(_WM_KEYS)}")
        goals_raw = payload["goals"]
        if not isinstance(goals_raw, list):
            raise RecurisArmError("working-memory goals must be a list")
        goals: list[str] = []
        for value in goals_raw:
            if not isinstance(value, str):
                raise RecurisArmError("working-memory goals must be strings")
            goals.append(value)
        fields_raw = payload["state_fields"]
        if not isinstance(fields_raw, Mapping):
            raise RecurisArmError("working-memory state_fields must be an object")
        for key in fields_raw:
            if not isinstance(key, str):
                raise RecurisArmError("working-memory state field names must be strings")
        base = payload["base_token_cost"]
        if not isinstance(base, int) or isinstance(base, bool):
            raise RecurisArmError("base_token_cost must be an integer")
        return cls(
            goals=tuple(goals),
            state_fields=dict(fields_raw),
            base_token_cost=base,
        )


@dataclass(frozen=True, slots=True)
class InvocationPolicy:
    """rho: the invocation policy — a small deterministic delivery rule.

    Stands for the Recuris manifest ``delivery:`` list: which stages invoke
    memory at all, how many cards a stage may receive per round (the cap that
    keeps usage inside its budget), and the per-card token cost of delivery.
    """

    invoked_on_stages: tuple[str, ...]
    max_cards_per_stage: int
    per_card_token_cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.max_cards_per_stage, int) or isinstance(
            self.max_cards_per_stage, bool
        ):
            raise RecurisArmError("max_cards_per_stage must be an integer")
        if self.max_cards_per_stage < 1:
            raise RecurisArmError("max_cards_per_stage must be at least 1")
        if not isinstance(self.per_card_token_cost, int) or isinstance(
            self.per_card_token_cost, bool
        ):
            raise RecurisArmError("per_card_token_cost must be an integer")
        if self.per_card_token_cost < 0:
            raise RecurisArmError("per_card_token_cost must be non-negative")

    def delivered(
        self,
        entries: Sequence[EEntry],
        stage: str,
        state_fields: Mapping[str, object],
    ) -> tuple[EEntry, ...]:
        """State-grounded invocation decision for one stage.

        A card is delivered when its stage matches (or is wildcard), its
        grounding field is tracked in working memory, and it survives the
        per-stage cap in deterministic id order. A stage that does not invoke
        memory receives nothing — that is the routing case the localizer
        distinguishes from a missing card.
        """

        if stage not in self.invoked_on_stages:
            return ()
        matching = [
            entry
            for entry in entries
            if entry.stage in (stage, "*")
            and (entry.requires_field is None or entry.requires_field in state_fields)
        ]
        matching.sort(key=lambda entry: entry.id)
        return tuple(matching[: self.max_cards_per_stage])

    def to_mapping(self) -> dict[str, object]:
        return {
            "invoked_on_stages": list(self.invoked_on_stages),
            "max_cards_per_stage": self.max_cards_per_stage,
            "per_card_token_cost": self.per_card_token_cost,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> InvocationPolicy:
        if set(payload) != _RHO_KEYS:
            raise RecurisArmError(f"invocation-policy keys must be exactly {sorted(_RHO_KEYS)}")
        stages_raw = payload["invoked_on_stages"]
        if not isinstance(stages_raw, list):
            raise RecurisArmError("invoked_on_stages must be a list")
        stages: list[str] = []
        for value in stages_raw:
            if not isinstance(value, str):
                raise RecurisArmError("invoked_on_stages entries must be strings")
            stages.append(value)
        cap = payload["max_cards_per_stage"]
        cost = payload["per_card_token_cost"]
        if not isinstance(cap, int) or isinstance(cap, bool):
            raise RecurisArmError("max_cards_per_stage must be an integer")
        if not isinstance(cost, int) or isinstance(cost, bool):
            raise RecurisArmError("per_card_token_cost must be an integer")
        return cls(
            invoked_on_stages=tuple(stages),
            max_cards_per_stage=cap,
            per_card_token_cost=cost,
        )


def _strict_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise RecurisArmError(f"{name} must be a string")
    return value


@dataclass(frozen=True, slots=True)
class CheckerContract:
    """C: the declared acceptance gate — data, while the gate itself is code.

    Mirrors the Recuris manifest ``checkers:`` block (``docs/skill-memory-
    format.md``): the package declares which checkers must hold; the kernel
    implements them. Here the single declared gate is the validation gate
    itself — accept only if the patch repairs its failure and regresses at
    most ``reg_cap`` previously repaired signals (Recuris ``reg_cap=0``
    default, ``--reg-cap`` flag in their README). The implementation lives in
    this module's ``_run_gate``; the package carries the configuration.
    """

    gate: str
    reg_cap: int

    def __post_init__(self) -> None:
        if self.gate != "repair_and_regression":
            raise RecurisArmError(f"unknown checker gate: {self.gate!r}")
        if not isinstance(self.reg_cap, int) or isinstance(self.reg_cap, bool):
            raise RecurisArmError("reg_cap must be an integer")
        if self.reg_cap < 0:
            raise RecurisArmError("reg_cap must be non-negative")

    def to_mapping(self) -> dict[str, object]:
        return {"gate": self.gate, "reg_cap": self.reg_cap}

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CheckerContract:
        if set(payload) != {"gate", "reg_cap"}:
            raise RecurisArmError("checker keys must be exactly ['gate', 'reg_cap']")
        return cls(
            gate=_strict_str(payload["gate"], "checker gate"),
            reg_cap=_strict_int(payload["reg_cap"], "reg_cap"),
        )


def _strict_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RecurisArmError(f"{name} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class MemoryPackage:
    """The evolving agent artifact: ``M = (E, W, rho, C)`` as pure data.

    Field mapping to the Recuris package format (``docs/skill-memory-
    format.md``: manifest.yaml + ``em/`` cards, one per file):

    - ``entries`` is E, the experiential cards;
    - ``working_memory`` is W, the working-memory contract;
    - ``invocation`` is rho, the invocation policy;
    - ``checkers`` is C, the declared acceptance gate.

    Everything that could be data, is data (their format's own principle):
    the package serializes to canonical JSON, so the improvement loop's whole
    edit surface is one auditable file the harness applies.
    """

    name: str
    entries: tuple[EEntry, ...]
    working_memory: WorkingMemory
    invocation: InvocationPolicy
    checkers: CheckerContract

    def to_mapping(self) -> dict[str, object]:
        return {
            "name": self.name,
            "E": [entry.to_mapping() for entry in self.entries],
            "W": self.working_memory.to_mapping(),
            "rho": self.invocation.to_mapping(),
            "C": self.checkers.to_mapping(),
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_mapping())

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> MemoryPackage:
        if set(payload) != _PACKAGE_KEYS:
            raise RecurisArmError(f"memory package keys must be exactly {sorted(_PACKAGE_KEYS)}")
        raw_entries = payload["E"]
        if not isinstance(raw_entries, list):
            raise RecurisArmError("package E must be a list of cards")
        entries = tuple(EEntry.from_mapping(entry) for entry in raw_entries)
        raw_w = payload["W"]
        if not isinstance(raw_w, Mapping):
            raise RecurisArmError("package W must be an object")
        raw_rho = payload["rho"]
        if not isinstance(raw_rho, Mapping):
            raise RecurisArmError("package rho must be an object")
        raw_c = payload["C"]
        if not isinstance(raw_c, Mapping):
            raise RecurisArmError("package C must be an object")
        return cls(
            name=_strict_str(payload["name"], "package name"),
            entries=entries,
            working_memory=WorkingMemory.from_mapping(raw_w),
            invocation=InvocationPolicy.from_mapping(raw_rho),
            checkers=CheckerContract.from_mapping(raw_c),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> MemoryPackage:
        try:
            payload: object = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RecurisArmError("memory package is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RecurisArmError("memory package must be a JSON object")
        return cls.from_mapping(payload)


def neutral_seed_package() -> MemoryPackage:
    """The deterministic neutral seed (Recuris ``--base neutral``).

    ``external/recuris/README.md``: "--base neutral starts from a deterministic
    seed package, so no hand-written domain profile enters the loop." Empty E,
    a one-goal working memory, memory invoked on the standard research-stage
    loop, and the repair-and-regression gate at ``reg_cap=0``.
    """

    return MemoryPackage(
        name="neutral",
        entries=(),
        working_memory=WorkingMemory(
            goals=("answer_accurately_within_budget",),
            state_fields={},
            base_token_cost=100,
        ),
        invocation=InvocationPolicy(
            invoked_on_stages=("retrieve", "read", "verify", "synthesize"),
            max_cards_per_stage=1,
            per_card_token_cost=100,
        ),
        checkers=CheckerContract(gate="repair_and_regression", reg_cap=0),
    )


# --- Diagnosis: the deterministic localizer (replaces Recuris's Meta-Agent) ---

ComponentName = Literal["E", "W", "RHO"]
PatchAction = Literal["add_card", "set_max_cards", "add_state_field"]
KindToComponent: Final[Mapping[str, ComponentName]] = {
    "stage_failure": "E",
    "usage_anomaly": "RHO",
    "unknown_state_field": "W",
}


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """One localized failure cluster: component, trigger, evidence.

    Recuris Phase D produces one ``plan.json`` cluster per failure family,
    each attributed to exactly one component with cited evidence
    (``external/recuris/src/recuris/metaagent/plan_schema.py``); this is its
    deterministic stand-in. The trigger is the first signal in a fixed
    (kind, item, signal-id) order, so localization never depends on feedback
    list order.
    """

    component: ComponentName
    trigger: FailureSignal
    evidence: tuple[FailureSignal, ...]


def _localize(report: FeedbackReport) -> Diagnosis | None:
    """Attribute the round's first failure to one component of ``M``.

    The mapping is the review's specified diagnostic: failures naming a
    specific stage mean a missing E card; usage anomalies mean rho; state-
    schema issues mean W. No signals means nothing to localize — a round that
    admits nothing is a valid outcome.
    """

    if not report.signals:
        return None
    ordered = sorted(report.signals, key=lambda s: (_KIND_ORDER[s.kind], s.item_id, s.signal_id))
    trigger = ordered[0]
    component = KindToComponent[trigger.kind]
    evidence = tuple(signal for signal in ordered if signal.kind == trigger.kind)
    return Diagnosis(component=component, trigger=trigger, evidence=evidence)


@dataclass(frozen=True, slots=True)
class PatchRecord:
    """One component-scoped patch proposal: (component, action, target).

    The triple is the ledger key Recuris blocks exact repeats of
    (``plan_schema.ledger_key``; ``gates.Ledger.is_repeat``): a patch rejected
    with a regression is not proposed again.
    """

    component: ComponentName
    action: PatchAction
    target: str
    trigger_signal_id: str
    evidence_signal_ids: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.component, self.action, self.target)

    def to_mapping(self) -> dict[str, object]:
        return {
            "component": self.component,
            "action": self.action,
            "target": self.target,
            "trigger_signal_id": self.trigger_signal_id,
            "evidence_signal_ids": list(self.evidence_signal_ids),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PatchRecord:
        if set(payload) != {
            "component",
            "action",
            "target",
            "trigger_signal_id",
            "evidence_signal_ids",
        }:
            raise RecurisArmError("patch record keys are unexpected")
        component = payload["component"]
        action = payload["action"]
        if component not in ("E", "W", "RHO"):
            raise RecurisArmError(f"patch component must be E, W, or RHO: {component!r}")
        if action not in ("add_card", "set_max_cards", "add_state_field"):
            raise RecurisArmError(f"patch action is unknown: {action!r}")
        raw_evidence = payload["evidence_signal_ids"]
        if not isinstance(raw_evidence, list):
            raise RecurisArmError("patch evidence_signal_ids must be a list")
        evidence: list[str] = []
        for value in raw_evidence:
            if not isinstance(value, str):
                raise RecurisArmError("patch evidence ids must be strings")
            evidence.append(value)
        return cls(
            component=component,
            action=action,
            target=_strict_str(payload["target"], "patch target"),
            trigger_signal_id=_strict_str(payload["trigger_signal_id"], "patch trigger id"),
            evidence_signal_ids=tuple(evidence),
        )


def _card_id(stage: str, skill: str) -> str:
    """Deterministic snake_case card id from the failure's stage and skill."""

    return re.sub(r"[^a-z0-9_]+", "_", f"{stage}_{skill}".lower()).strip("_")


def _projected_usage(package: MemoryPackage) -> int:
    """Deterministic standing cost of running one round under this package.

    The base working-memory render cost plus every card rho would deliver,
    priced per card — the quantity a usage-anomaly patch must bring back
    inside the budget.
    """

    rho = package.invocation
    total = package.working_memory.base_token_cost
    for stage in rho.invoked_on_stages:
        delivered = rho.delivered(package.entries, stage, package.working_memory.state_fields)
        total += len(delivered) * rho.per_card_token_cost
    return total


def _repairs(package: MemoryPackage, signal: FailureSignal, token_budget: int) -> bool:
    """Does this package resolve one signal? The repair predicate (in code).

    A stage failure is repaired only by a card rho actually delivers at that
    stage — a card that exists but never fires does not repair anything
    (Recuris architecture.md: "a card that exists but never fires is a routing
    failure, and it looks exactly like a knowledge gap from the score alone").
    A usage anomaly is repaired when projected usage fits the budget. A state-
    schema issue is repaired when the field is tracked.
    """

    if signal.kind == "stage_failure":
        if signal.stage is None or signal.missing_skill is None:
            return False
        delivered = package.invocation.delivered(
            package.entries, signal.stage, package.working_memory.state_fields
        )
        return any(signal.missing_skill in entry.handles for entry in delivered)
    if signal.kind == "usage_anomaly":
        return _projected_usage(package) <= token_budget
    return (
        signal.field_name is not None and signal.field_name in package.working_memory.state_fields
    )


def _propose(
    diagnosis: Diagnosis,
    package: MemoryPackage,
    token_budget: int,
) -> PatchRecord | None:
    """Propose at most one component-scoped patch for the diagnosed failure.

    Per-component proposals (the actions mirror Recuris
    ``ACTIONS_BY_COMPONENT``: E -> add_card, RHO -> set_delivery-equivalent,
    W -> set_wm):

    - E: append one procedure card for the missing skill, unless a card
      already covers it (then the failure is routing, not knowledge, and this
      build abstains — routing repair needs Recuris's activation probe).
    - RHO: lower ``max_cards_per_stage`` by one, when observed and projected
      usage both exceed the budget and the cap is not already at its floor.
    - W: track the unknown field, unless it is already tracked.
    """

    trigger = diagnosis.trigger
    evidence_ids = tuple(signal.signal_id for signal in diagnosis.evidence)
    if diagnosis.component == "E":
        if trigger.stage is None or trigger.missing_skill is None:
            return None
        covered = any(
            entry.stage in (trigger.stage, "*") and trigger.missing_skill in entry.handles
            for entry in package.entries
        )
        if covered:
            return None
        return PatchRecord(
            component="E",
            action="add_card",
            target=_card_id(trigger.stage, trigger.missing_skill),
            trigger_signal_id=trigger.signal_id,
            evidence_signal_ids=evidence_ids,
        )
    if diagnosis.component == "RHO":
        if trigger.budget_tokens is None or trigger.budget_tokens <= token_budget:
            return None
        if _projected_usage(package) <= token_budget:
            return None
        if package.invocation.max_cards_per_stage <= 1:
            return None
        return PatchRecord(
            component="RHO",
            action="set_max_cards",
            target="max_cards_per_stage",
            trigger_signal_id=trigger.signal_id,
            evidence_signal_ids=evidence_ids,
        )
    if trigger.field_name is None or trigger.field_name in package.working_memory.state_fields:
        return None
    return PatchRecord(
        component="W",
        action="add_state_field",
        target=trigger.field_name,
        trigger_signal_id=trigger.signal_id,
        evidence_signal_ids=evidence_ids,
    )


def _apply_patch(
    package: MemoryPackage,
    record: PatchRecord,
    trigger: FailureSignal,
) -> MemoryPackage:
    """Apply exactly one component of ``M``; the other three pass through.

    ``dataclasses.replace`` keeps the untouched component objects by
    reference, so a component-scoped edit is observably scoped: the patched
    package's W and rho are the pre-patch objects themselves.
    """

    if record.component == "E" and record.action == "add_card":
        stage = trigger.stage
        skill = trigger.missing_skill
        if stage is None or skill is None:
            raise RecurisArmError("E add_card trigger lacks stage/missing_skill")
        card = EEntry(
            id=record.target,
            type="procedure",
            stage=stage,
            handles=(skill,),
            requires_field=None,
            body=(
                f"Procedure for {skill} at the {stage} stage: run the step, "
                "check its outcome against the tracked task state, and only "
                "then continue. Placeholder identifiers only; never a task's "
                "answer (the one prohibition)."
            ),
            source=record.trigger_signal_id,
        )
        return replace(
            package,
            entries=tuple(sorted((*package.entries, card), key=lambda entry: entry.id)),
        )
    if record.component == "RHO" and record.action == "set_max_cards":
        rho = package.invocation
        return replace(
            package,
            invocation=replace(rho, max_cards_per_stage=rho.max_cards_per_stage - 1),
        )
    if record.component == "W" and record.action == "add_state_field":
        fields = dict(package.working_memory.state_fields)
        fields[record.target] = None
        return replace(
            package,
            working_memory=replace(package.working_memory, state_fields=fields),
        )
    raise RecurisArmError(f"unknown patch shape: {record.component}/{record.action}")


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """The deterministic gate's decision plus the arithmetic behind it."""

    accepted: bool
    reason: str
    repaired: bool
    regressions: tuple[str, ...]


def _run_gate(
    pre: MemoryPackage,
    patched: MemoryPackage,
    trigger: FailureSignal,
    previous: FeedbackReport,
    token_budget: int,
    reg_cap: int,
) -> GateVerdict:
    """The validation gate: accept only if the patch repairs and does not regress.

    Recuris ``gates.py``: "A model proposes; whether the proposal is kept is
    decided by arithmetic... Nothing here consults a model." Their admission
    test is a paired held-out bootstrap with a regression cap; this build's
    evidence universe is the restricted feedback instead of a hidden split,
    so the same two-sided discipline becomes: (i) the patch must repair the
    very failure that motivated it, and (ii) replaying the previous round's
    feedback through the patched package must not newly fail any signal the
    pre-patch package resolved (regression cap ``reg_cap``, default 0).
    """

    if not _repairs(patched, trigger, token_budget):
        return GateVerdict(
            accepted=False,
            reason="patch does not repair the diagnosed failure",
            repaired=False,
            regressions=(),
        )
    regressions = tuple(
        signal.signal_id
        for signal in previous.signals
        if _repairs(pre, signal, token_budget) and not _repairs(patched, signal, token_budget)
    )
    if len(regressions) > reg_cap:
        return GateVerdict(
            accepted=False,
            reason=f"{len(regressions)} previously repaired signal(s) regress (cap {reg_cap})",
            repaired=True,
            regressions=regressions,
        )
    return GateVerdict(
        accepted=True,
        reason="repair confirmed with no regression",
        repaired=True,
        regressions=regressions,
    )


# --- Cross-round participant state: the ledger plus the regression evidence ---


@dataclass(frozen=True, slots=True)
class ParticipantState:
    """The Sigma-side memory of the improvement loop.

    Recuris keeps cross-round memory in files the driver writes and re-injects
    every round — "never the model's own context" (``driver.py`` docstring) —
    and the load-bearing pieces are the ledger (do-not-repeat) and the
    regression suspects. Here that memory is the declared participant state:
    the accepted/rejected ledger with reasons, and the previous round's
    feedback, which is the replay set the gate regresses against. The memory
    package itself travels as the agent data file, so state and package
    advance together but stay separately auditable.
    """

    accepted: tuple[PatchRecord, ...] = ()
    rejected: tuple[tuple[PatchRecord, str], ...] = ()
    previous_feedback: FeedbackReport = field(default_factory=FeedbackReport)
    last_round_index: int | None = None

    def ledger_blocks(self, key: tuple[str, str, str]) -> bool:
        """Do-not-repeat: an accepted or rejected (component, action, target)."""

        return key in {record.key for record in self.accepted} | {
            record.key for record, _ in self.rejected
        }

    def advance(
        self,
        *,
        report: FeedbackReport,
        round_index: int,
        record: PatchRecord | None = None,
        accepted: bool = False,
        reason: str = "",
    ) -> ParticipantState:
        """Roll the state forward one round: ledger entry plus new replay set."""

        accepted_list = self.accepted
        rejected_list = self.rejected
        if record is not None and accepted:
            accepted_list = (*self.accepted, record)
        elif record is not None:
            rejected_list = (*self.rejected, (record, reason))
        return ParticipantState(
            accepted=accepted_list,
            rejected=rejected_list,
            previous_feedback=report,
            last_round_index=round_index,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": 1,
            "accepted": [record.to_mapping() for record in self.accepted],
            "rejected": [
                {"record": record.to_mapping(), "reason": reason}
                for record, reason in self.rejected
            ],
            "previous_feedback": self.previous_feedback.to_mapping(),
            "last_round_index": self.last_round_index,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_mapping())

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ParticipantState:
        """Strict parse: participant-authored state is re-validated at load."""

        if set(payload) != {
            "version",
            "accepted",
            "rejected",
            "previous_feedback",
            "last_round_index",
        }:
            raise RecurisArmError("participant state keys are unexpected")
        if payload["version"] != 1:
            raise RecurisArmError(f"unsupported participant state version: {payload['version']!r}")
        raw_accepted = payload["accepted"]
        if not isinstance(raw_accepted, list):
            raise RecurisArmError("accepted ledger must be a list")
        accepted = tuple(PatchRecord.from_mapping(entry) for entry in raw_accepted)
        raw_rejected = payload["rejected"]
        if not isinstance(raw_rejected, list):
            raise RecurisArmError("rejected ledger must be a list")
        rejected: list[tuple[PatchRecord, str]] = []
        for entry in raw_rejected:
            if not isinstance(entry, Mapping) or set(entry) != {"record", "reason"}:
                raise RecurisArmError("rejected ledger entries must be record+reason objects")
            rejected.append(
                (PatchRecord.from_mapping(entry["record"]), _strict_str(entry["reason"], "reason"))
            )
        raw_feedback = payload["previous_feedback"]
        if not isinstance(raw_feedback, Mapping):
            raise RecurisArmError("previous_feedback must be an object")
        last_round = payload["last_round_index"]
        if last_round is not None and (
            not isinstance(last_round, int) or isinstance(last_round, bool)
        ):
            raise RecurisArmError("last_round_index must be an integer or null")
        return cls(
            accepted=accepted,
            rejected=tuple(rejected),
            previous_feedback=FeedbackReport.from_mapping(raw_feedback),
            last_round_index=last_round,
        )

    @classmethod
    def load(cls, state_path: Path | None) -> ParticipantState:
        """Load state from the declared store; a missing file is a fresh state.

        Malformed state raises: participant-authored persistent data is
        re-validated (cap, schema, parse) at every load, and the failure must
        be loud here, not silent later.
        """

        if state_path is None:
            return cls()
        try:
            raw = state_path.read_bytes()
        except FileNotFoundError:
            return cls()
        try:
            payload: object = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RecurisArmError("participant state is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RecurisArmError("participant state must be a JSON object")
        return cls.from_mapping(payload)


# --- The arm ---


@dataclass(frozen=True, slots=True)
class _RoundPipeline:
    """One read-only pass of the loop: what was loaded and what the gate said."""

    package: MemoryPackage
    state: ParticipantState
    report: FeedbackReport
    record: PatchRecord | None = None
    patched: MemoryPackage | None = None
    verdict: GateVerdict | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RecurisStyleImprover:
    """Recuris-style validation-gated memory evolution, as one participant arm.

    A small-fidelity integration of the pinned Recuris checkout
    (``external/recuris``, Apache-2.0, arXiv:2608.24876): the interface's
    claim that "an in-process improvement loop (e.g. a Recuris-style
    validation-gated memory updater) is equally registrable"
    (docs/participant-interface-v1.md) is discharged by running this arm
    through the ordinary participant machinery — same round input, same
    restricted feedback, same qualification — with the mechanism preserved
    rather than simulated as a plain file editor.

    **Preserved mechanisms** (verified against the pinned checkout):

    - Component taxonomy ``M = (E, W, rho, C)`` — ``external/recuris/docs/
      architecture.md`` §"M = (E, W, rho, C)" and ``docs/skill-memory-
      format.md``; the patchable-component and action menus in
      ``src/recuris/metaagent/plan_schema.py`` (``PATCHABLE_COMPONENTS``,
      ``ACTIONS_BY_COMPONENT``). Here: ``EEntry``/``WorkingMemory``/
      ``InvocationPolicy``/``CheckerContract``, one patch per component.
    - Localization — Phase D attributes each failure cluster to exactly one
      component with cited evidence (``plan_schema.py``, ``driver.py`` round
      workflow). Here: the deterministic localizer maps stage failures to E,
      usage anomalies to rho, state-schema issues to W.
    - One-edit-per-component — "Each cluster owns exactly one component and
      contains only that component's actions" (``plan_schema.py``). Here:
      ``_propose`` emits at most one ``PatchRecord`` per round and
      ``_apply_patch`` replaces exactly one component.
    - Validation gate — "A model proposes; whether the proposal is kept is
      decided by arithmetic over held-out outcomes... Nothing here consults a
      model" (``src/recuris/metaagent/gates.py``); accept requires repair of
      the motivating failure and no more than ``reg_cap`` regressed items.
      Here: accept requires ``_repairs(patched, trigger)`` and that replaying
      the previous round's feedback through the patched package newly fails
      at most ``reg_cap`` previously repaired signals.
    - Bounded loop / do-not-repeat ledger — ``gates.Ledger.is_repeat`` blocks
      exact (component, action, target) repeats. Here: ``ParticipantState.
      ledger_blocks``.
    - File-based cross-round memory — "Memory across rounds = files the
      driver injects every round... never the model's own context"
      (``driver.py`` docstring). Here: the package travels as the agent data
      file ``memory_package.json``, the ledger as declared Sigma state.
    - Neutral deterministic seed — ``--base neutral`` (README) via
      ``neutral_seed_package``.
    - Card discipline — placeholder-only bodies, provenance ``source``
      (``docs/skill-memory-format.md``: "Never write a task's answer into a
      card"; "A card whose provenance nobody can state is a card nobody can
      decide to remove").

    **Replaced mechanisms** (and by what):

    - Their Meta-Agent (an upstream LLM session reading trajectories and
      writing ``plan.json``) is replaced by the deterministic localizer and
      patch templates in this module — the mechanism under test is the loop,
      not the diagnosis quality, so no LLM is called in this build.
    - Their Claude-Code/driver harness (subprocess campaign over tau2/
      SkillFlow/TB2.1) is replaced by the participant protocol: one
      ``improve(round_input)`` in, one ``ImprovementRoundOutput`` out, with
      the benchmark applying outputs.
    - Their paired held-out split with bootstrap CI (``held_out_paired_gate``)
      is replaced by the repair-plus-regression predicate over the restricted
      feedback — the benchmark owns evaluation; an improver may not run its
      own hidden comparisons.
    - Their TurnRuntime delivery of cards inside a live turn loop
      (``runtime.py``) is replaced by ``InvocationPolicy.delivered``, the
      deterministic delivery simulation the gate itself checks.

    Usage is honest for this build: zero model tokens, real wall time. A
    full adaptation (docs/recuris-integration-notes-20260920.md) would put
    their trace format and checker LLM behind the same gate and carry those
    tokens in ``usage``.
    """

    byte_cap: int
    token_budget: int = 4096
    seed_package: MemoryPackage = field(default_factory=neutral_seed_package)
    _usage: list[UsageReport] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.byte_cap, int) or isinstance(self.byte_cap, bool):
            raise RecurisArmError("byte_cap must be an integer")
        if self.byte_cap <= 0:
            raise RecurisArmError("byte_cap must be positive")
        if not isinstance(self.token_budget, int) or isinstance(self.token_budget, bool):
            raise RecurisArmError("token_budget must be an integer")
        if self.token_budget <= 0:
            raise RecurisArmError("token_budget must be positive")

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        started = time.perf_counter()
        pipeline = self._pipeline(round_input)

        accepted = pipeline.verdict is not None and pipeline.verdict.accepted
        new_state = pipeline.state.advance(
            report=pipeline.report,
            round_index=round_input.round_index,
            record=pipeline.record,
            accepted=accepted,
            reason=pipeline.verdict.reason if pipeline.verdict is not None else "",
        )
        state_bytes = new_state.to_bytes()
        if len(state_bytes) > self.byte_cap:
            raise RecurisArmError(
                "participant state exceeds the declared byte cap: "
                f"{len(state_bytes)} > {self.byte_cap}"
            )

        changed: dict[str, str] = {}
        if accepted and pipeline.patched is not None:
            changed[MEMORY_PACKAGE_FILENAME] = pipeline.patched.to_bytes().decode("utf-8")

        usage = UsageReport(
            input_tokens=0,
            output_tokens=0,
            wall_seconds=time.perf_counter() - started,
            dollar_estimate=None,
        )
        self._usage.append(usage)
        return ImprovementRoundOutput(
            agent_files_changed=changed,
            state_update=state_bytes,
            usage=usage,
        )

    def gate_reason_of(self, round_input: ImprovementRoundInput) -> str:
        """The gate's reason for one round, without advancing any state.

        Test/diagnostic hook: runs the same localize-propose-gate pipeline
        read-only, so a qualification or a test can ask why a round would
        admit nothing. Never called by ``improve``.
        """

        return self._pipeline(round_input).reason

    def usage_reports(self) -> tuple[UsageReport, ...]:
        """Accumulated per-round usage (the C_improve column source)."""

        return tuple(self._usage)

    def _pipeline(self, round_input: ImprovementRoundInput) -> _RoundPipeline:
        """One pass of localize -> propose -> gate over a round input.

        Pure with respect to participant state: loads, decides, and returns
        everything ``improve`` needs to roll the state forward. Both the
        mutating path (``improve``) and the read-only path (``gate_reason_of``)
        run this same code, so the two can never diverge on what the gate saw.
        """

        package = self._load_package(round_input.current_agent_dir)
        state = ParticipantState.load(round_input.state_path)
        report = FeedbackReport.parse(round_input.restricted_feedback_bytes)
        diagnosis = _localize(report)
        if diagnosis is None:
            return _RoundPipeline(
                package=package,
                state=state,
                report=report,
                reason="no patchable signal",
            )
        proposal = _propose(diagnosis, package, self.token_budget)
        if proposal is None:
            return _RoundPipeline(
                package=package,
                state=state,
                report=report,
                reason="no proposal for the diagnosed component",
            )
        if state.ledger_blocks(proposal.key):
            return _RoundPipeline(
                package=package,
                state=state,
                report=report,
                reason="ledger blocks a repeat of a previous patch",
            )
        patched = _apply_patch(package, proposal, diagnosis.trigger)
        verdict = _run_gate(
            pre=package,
            patched=patched,
            trigger=diagnosis.trigger,
            previous=state.previous_feedback,
            token_budget=self.token_budget,
            reg_cap=package.checkers.reg_cap,
        )
        return _RoundPipeline(
            package=package,
            state=state,
            report=report,
            record=proposal,
            patched=patched,
            verdict=verdict,
            reason=verdict.reason,
        )

    def _load_package(self, agent_dir: Path) -> MemoryPackage:
        """Load the package from the agent directory; seed when absent."""

        package_path = agent_dir / MEMORY_PACKAGE_FILENAME
        try:
            raw = package_path.read_bytes()
        except FileNotFoundError:
            return self.seed_package
        return MemoryPackage.from_bytes(raw)


__all__ = [
    "MEMORY_PACKAGE_FILENAME",
    "CheckerContract",
    "Diagnosis",
    "EEntry",
    "FailureSignal",
    "FeedbackReport",
    "GateVerdict",
    "InvocationPolicy",
    "MemoryPackage",
    "ParticipantState",
    "PatchRecord",
    "RecurisArmError",
    "RecurisStyleImprover",
    "WorkingMemory",
    "neutral_seed_package",
]
