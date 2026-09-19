"""Session-driven lifecycle wiring: the store drives the participant loop.

Contract status: implements the wired form of the state-boundary contract
(benchmark-contract-v2.md §Protocol semantics "State-boundary contract";
participant-interface-v1.md §State contract, frozen 2026-09-19) over the
Phase B packages ``session/`` and ``lifecycle/``. This module owns no state
and no protocol of its own: it composes ``SessionStateStore`` sessions with
``run_lifecycle`` instances and records the auditable outcome.

The composition per instance is load / hook / run / save: the wiring loads
the session's current participant state through the injected ``load_state``
adapter (a ledgered, load-boundary-validated read), builds a fresh hook via
``hook_factory`` — the participant evolves that state dict in place as it
acts — runs ``run_lifecycle``, then persists the evolved state through the
injected ``save_state`` adapter (the serialization boundary: cap, schema
pairing, canonical form, memory-op ledger, transcript). Split boundaries are
structural: ``begin_session`` opens every session byte-empty, so a gate
session's ``load_state`` reads only the gate session's own (empty) state —
participant state never carries across sessions. The wiring does not and
cannot inspect what an injected adapter reads; boundary violations are
detected by the pre-registered leak probe (``run_leak_probe_then_gate``),
not by trust.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.runner import LifecycleRunRecord, ParticipantHook, run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.session.probe import (
    LeakProbeError,
    LeakProbeResult,
    assert_canary_absent,
    inject_canary_tokens,
)
from rsicontext.session.store import MemoryOpLedger, SessionKind, SessionStateStore

__all__ = [
    "HookFactory",
    "LeakProbeError",
    "SessionLifecycleRecord",
    "SessionPlan",
    "StateHookFactory",
    "StateLoad",
    "StateSave",
    "run_gate_session",
    "run_leak_probe_then_gate",
    "run_session_flow",
    "run_visible_session",
]

StateLoad = Callable[[], dict[str, object] | None]
StateSave = Callable[[dict[str, object]], None]
StateHookFactory = Callable[[dict[str, object]], ParticipantHook]
#: Alias kept for call sites that read better with the unqualified name.
HookFactory = StateHookFactory


@dataclass(frozen=True, slots=True)
class SessionPlan:
    """The declared session split for one registration run.

    Carries the visible/gate item split (structurally disjoint — gate
    sessions contain only gate items, contract group 1), the state byte cap
    ``B`` and retainable-state schema ``Σ`` the store is constructed from,
    and the pre-registered canary tokens for the leak probe.
    """

    visible_instance_ids: tuple[str, ...]
    gate_instance_ids: tuple[str, ...]
    byte_cap: int
    schema: dict[str, object]
    canary_tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "visible_instance_ids", tuple(self.visible_instance_ids))
        object.__setattr__(self, "gate_instance_ids", tuple(self.gate_instance_ids))
        object.__setattr__(self, "canary_tokens", tuple(self.canary_tokens))
        for field, ids in (
            ("visible_instance_ids", self.visible_instance_ids),
            ("gate_instance_ids", self.gate_instance_ids),
        ):
            for item_id in ids:
                if not isinstance(item_id, str) or not item_id:
                    raise ValueError(f"{field} entries must be non-empty strings")
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field} entries must be unique")
        overlap = set(self.visible_instance_ids) & set(self.gate_instance_ids)
        if overlap:
            raise ValueError(f"gate items must be disjoint from visible items: {sorted(overlap)}")
        if (
            not isinstance(self.byte_cap, int)
            or isinstance(self.byte_cap, bool)
            or self.byte_cap <= 0
        ):
            raise ValueError("byte_cap must be a positive integer")
        if not isinstance(self.schema, dict):
            raise TypeError("schema must be a dict")
        for token in self.canary_tokens:
            if not isinstance(token, str) or not token:
                raise ValueError("canary_tokens entries must be non-empty strings")
        if len(self.canary_tokens) != len(set(self.canary_tokens)):
            raise ValueError("canary_tokens entries must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "visible_instance_ids": list(self.visible_instance_ids),
            "gate_instance_ids": list(self.gate_instance_ids),
            "byte_cap": self.byte_cap,
            "schema": dict(self.schema),
            "canary_tokens": list(self.canary_tokens),
        }


@dataclass(frozen=True, slots=True)
class SessionLifecycleRecord:
    """The auditable outcome of one wired session over its instances.

    ``transcript_digests`` is the session's ordered post-op state digest
    sequence (``None`` marks a read of an empty session); ``memory_ops`` is
    the full ordered memory-op ledger required by state-contract clause 4.
    ``run_records`` carries measured ``wall_seconds`` in each run's ``cost``
    column — a timing artifact, not a replay column (benchmark contract
    §Protocol semantics: replay compares program, state, and ledger).
    """

    session_id: str
    kind: SessionKind
    instance_ids: tuple[str, ...]
    run_records: tuple[LifecycleRunRecord, ...]
    transcript_digests: tuple[str | None, ...]
    memory_ops: tuple[MemoryOpLedger, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(self.kind, SessionKind):
            raise TypeError("kind must be a SessionKind")
        object.__setattr__(self, "instance_ids", tuple(self.instance_ids))
        object.__setattr__(self, "run_records", tuple(self.run_records))
        object.__setattr__(self, "transcript_digests", tuple(self.transcript_digests))
        object.__setattr__(self, "memory_ops", tuple(self.memory_ops))
        if any(not isinstance(record, LifecycleRunRecord) for record in self.run_records):
            raise TypeError("run_records entries must be LifecycleRunRecord values")

    @property
    def memory_op_totals(self) -> dict[str, int]:
        """Totals over the ledger: op counts and bytes moved, per op class."""

        writes = [op for op in self.memory_ops if op.op == "write"]
        reads = [op for op in self.memory_ops if op.op == "read"]
        return {
            "writes": len(writes),
            "reads": len(reads),
            "bytes_written": sum(op.state_bytes for op in writes),
            "bytes_read": sum(op.state_bytes for op in reads),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "kind": self.kind.value,
            "instance_ids": list(self.instance_ids),
            "run_records": [record.to_dict() for record in self.run_records],
            "transcript_digests": list(self.transcript_digests),
            "memory_ops": [
                {"op": op.op, "session_id": op.session_id, "state_bytes": op.state_bytes}
                for op in self.memory_ops
            ],
            "memory_op_totals": self.memory_op_totals,
        }


def run_session_flow(
    store: SessionStateStore,
    kind: SessionKind,
    session_id: str,
    instances: Sequence[LifecycleInstance],
    hook_factory: StateHookFactory,
    load_state: StateLoad,
    save_state: StateSave,
    *,
    byte_cap: int,
) -> SessionLifecycleRecord:
    """Run one session: load / hook / run / save, per instance, in order.

    This is the shared engine behind ``run_visible_session`` and
    ``run_gate_session`` (and the replay flow in ``wiring.replay``). It
    begins the session (byte-empty by ``begin_session``'s rule), then per
    instance: loads the participant state through ``load_state``, builds a
    fresh hook from that state via ``hook_factory``, runs ``run_lifecycle``
    on a fresh ``ProjectState``, and persists the evolved state through
    ``save_state`` — the load-before/save-after composition. Item ids are
    recorded via ``store.record_item``: one item belongs to exactly one
    session, so a store structurally forbids repeating an item stream
    across sessions — repeats run on fresh stores.
    """

    if not isinstance(store, SessionStateStore):
        raise TypeError("store must be a SessionStateStore")
    if not isinstance(kind, SessionKind):
        raise TypeError("kind must be a SessionKind")
    if not callable(hook_factory) or not callable(load_state) or not callable(save_state):
        raise TypeError("hook_factory, load_state, and save_state must be callable")
    instances = tuple(instances)
    if any(not isinstance(instance, LifecycleInstance) for instance in instances):
        raise TypeError("instances entries must be LifecycleInstance values")
    store.begin_session(kind, session_id, byte_cap)
    run_records: list[LifecycleRunRecord] = []
    for instance in instances:
        loaded = load_state()
        state: dict[str, object] = dict(loaded) if loaded is not None else {}
        hook = hook_factory(state)
        record = run_lifecycle(instance, hook, ProjectState())
        save_state(state)
        store.record_item(session_id, instance.instance_id)
        run_records.append(record)
    store.boundary_check(session_id)
    return SessionLifecycleRecord(
        session_id=session_id,
        kind=kind,
        instance_ids=tuple(instance.instance_id for instance in instances),
        run_records=tuple(run_records),
        transcript_digests=tuple(entry.digest for entry in store.transcript(session_id)),
        memory_ops=store.ledger(session_id),
    )


def run_visible_session(
    store: SessionStateStore,
    session_id: str,
    instances: Sequence[LifecycleInstance],
    hook_factory: StateHookFactory,
    load_state: StateLoad,
    save_state: StateSave,
    *,
    byte_cap: int,
) -> SessionLifecycleRecord:
    """Run a visible session: participant state carries across instances.

    ``load_state`` / ``save_state`` are the participant-facing state
    adapters injected by the caller, bound to this session; state saved
    after one instance is the state loaded before the next, so the session
    evolves within its own boundary.
    """

    return run_session_flow(
        store,
        SessionKind.VISIBLE,
        session_id,
        instances,
        hook_factory,
        load_state,
        save_state,
        byte_cap=byte_cap,
    )


def run_gate_session(
    store: SessionStateStore,
    session_id: str,
    instances: Sequence[LifecycleInstance],
    hook_factory: StateHookFactory,
    load_state: StateLoad,
    save_state: StateSave,
    *,
    byte_cap: int,
) -> SessionLifecycleRecord:
    """Run a gate session: a NEW session whose participant state starts empty.

    ``session_id`` must not already exist (``begin_session`` enforces this),
    and the injected ``load_state`` must read the GATE session's own state —
    never the visible session's. The wiring cannot inspect an injected
    adapter, so the boundary is demonstrated structurally (the gate session
    begins byte-empty and is namespaced apart) and enforced by the leak
    probe, not by trust in the adapter.
    """

    return run_session_flow(
        store,
        SessionKind.GATE,
        session_id,
        instances,
        hook_factory,
        load_state,
        save_state,
        byte_cap=byte_cap,
    )


def run_leak_probe_then_gate(
    store: SessionStateStore,
    canary_tokens: Sequence[str],
    gate_runner: Callable[[], object],
    *,
    canary_session_id: str = "canary-probe",
    byte_cap: int,
) -> tuple[object, LeakProbeResult]:
    """Inject canary tokens, run the gate, then assert their absence.

    Order (participant-interface-v1.md §State clause 5): a fresh canary
    session is begun on ``store`` and the tokens injected through
    ``inject_canary_tokens`` (an ordinary ledgered write, auditable in the
    canary session's transcript); ``gate_runner`` then runs the gate —
    typically ``run_gate_session`` over the gate instances, closing over its
    own session id; finally every gate session the runner began is probed
    with ``assert_canary_absent``, so a leak raises ``LeakProbeError``
    naming the session, token, and transcript position. Returns
    ``(gate_result, probe_result)`` where ``probe_result`` is the record for
    the last probed gate session (all probed sessions passed, or the call
    raised); a gate runner that began no gate session on the store also
    raises ``LeakProbeError`` — a probe that probed nothing is not a pass.
    ``byte_cap`` is required because the canary session's ``begin_session``
    enforces the cap at its serialization boundary.
    """

    if not isinstance(store, SessionStateStore):
        raise TypeError("store must be a SessionStateStore")
    if not callable(gate_runner):
        raise TypeError("gate_runner must be callable")
    if not isinstance(canary_session_id, str) or not canary_session_id:
        raise ValueError("canary_session_id must be a non-empty string")
    tokens = list(canary_tokens)
    known = set(store.recorded_sessions)
    store.begin_session(SessionKind.CANARY, canary_session_id, byte_cap)
    inject_canary_tokens(store, canary_session_id, tokens)
    gate_result = gate_runner()
    new_gate_sessions = tuple(
        session_id
        for session_id in store.recorded_sessions
        if session_id not in known and store.session_kind(session_id) is SessionKind.GATE
    )
    if not new_gate_sessions:
        raise LeakProbeError("the gate runner began no gate session on the store")
    result: LeakProbeResult | None = None
    for gate_session_id in new_gate_sessions:
        result = assert_canary_absent(store, gate_session_id, tokens)
    assert result is not None  # new_gate_sessions is non-empty here
    return gate_result, result
