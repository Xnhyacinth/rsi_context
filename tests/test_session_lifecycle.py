"""Contract-level tests for the session-driven lifecycle wiring.

Implements the WS-6 scope of ``docs/contract-tests-phase-b.md``: the
state-boundary contract as wired (groups 1 and 2, through
``run_visible_session`` / ``run_gate_session`` / ``run_leak_probe_then_gate``)
and replay duality group 3 (``replay_transcript_equality``) over
``src/rsicontext/wiring``. No real reader: instances are built via
``build_example_instance`` over synthetic PopQA-shaped rows, the
participant is a scripted state-evolving hook, and the reader is a
deterministic fake.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from rsicontext.lifecycle import (
    Action,
    DocumentRef,
    LifecycleInstance,
    ProjectState,
    StageResponse,
    StageView,
    build_example_instance,
    run_lifecycle,
)
from rsicontext.session import (
    LeakProbeError,
    SessionBoundaryError,
    SessionStateError,
    SessionStateStore,
)
from rsicontext.wiring import (
    ReaderCallable,
    ReplayCall,
    ReplayMissError,
    ReplayRecorder,
    SessionPlan,
    replay,
    replay_transcript_equality,
    run_gate_session,
    run_leak_probe_then_gate,
    run_visible_session,
)

_CAP = 4096
_SCHEMA: dict[str, object] = {"type": "object", "properties": {"notes": {"type": "array"}}}
_CANARY = "GOLDTOKEN-alpha"


def popqa_row(row_id: int, question: str, answer: str, seed: str) -> dict[str, object]:
    """One synthetic PopQA-shaped row: same fields as the real corpus rows."""

    return {
        "id": row_id,
        "question": question,
        "possible_answers": f'["{answer}", "{answer} music"]',
        "ctxs": [
            {
                "id": f"{row_id}-gold",
                "title": f"Gold source {seed}",
                "text": f"The verified answer is {answer}; source {seed} holds the gold span.",
                "score": 0.71,
                "has_answer": True,
            },
            {
                "id": f"{row_id}-noise-1",
                "title": f"Noise doc one {seed}",
                "text": "Unrelated filler passage for survey bulk.",
                "score": 0.66,
                "has_answer": False,
            },
            {
                "id": f"{row_id}-noise-2",
                "title": f"Noise doc two {seed}",
                "text": "More unrelated filler; carries no gold evidence.",
                "score": 0.61,
                "has_answer": False,
            },
        ],
    }


def visible_instances() -> list[LifecycleInstance]:
    return [
        build_example_instance(popqa_row(101, "What genre is Alpha?", "alpha rock", "alpha")),
        build_example_instance(popqa_row(102, "What genre is Beta?", "beta jazz", "beta")),
    ]


def gate_instances() -> list[LifecycleInstance]:
    return [build_example_instance(popqa_row(201, "What genre is Gate?", "gate soul", "gate"))]


def fake_reader(prefix: str) -> ReaderCallable:
    """A deterministic fake reader: canned answers keyed on the query."""

    def reader(query: str, pack: str) -> tuple[str, int, int]:
        return (f"{prefix}-answer::{query}", 11, 7)

    return reader


class ScriptedParticipant:
    """A state-evolving participant hook.

    Per stage it calls the reader once, records a cite of the instance's
    gold doc (read from the participant-visible stage documents — never the
    evaluator-only gold ids), and appends a note to the injected state so
    the session's persisted state grows. The act_verify stage commits the
    answer record the instance's expected state delta names.
    """

    def __init__(self, state: dict[str, object], reader: ReaderCallable) -> None:
        self.state = state
        self.reader = reader
        self.reader_calls: list[tuple[str, str]] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        anchor = self._anchor_doc(stage)
        query = f"{stage.stage_id}:{anchor.doc_id}"
        answer, _tokens_in, _tokens_out = self.reader(query, anchor.text)
        self.reader_calls.append((query, anchor.text))
        notes = self.state.setdefault("notes", [])
        cast(list[str], notes).append(f"{stage.stage_id}:{answer}")
        if stage.kind == "act_verify":
            record_id = "answer_project"
            return StageResponse(
                pack_text=f"final commit [[doc:{anchor.doc_id}]] {answer}",
                actions=(
                    Action(kind="create_record", record_id=record_id, fields={}),
                    Action(
                        kind="finalize",
                        record_id=record_id,
                        fields={"answer": answer.split("::")[1]},
                        provenance=(anchor.doc_id,),
                    ),
                ),
            )
        return StageResponse(pack_text=f"notes [[doc:{anchor.doc_id}]] {answer}", actions=())

    @staticmethod
    def _anchor_doc(stage: StageView) -> DocumentRef:
        return max(stage.documents, key=lambda document: len(document.text))


def store_adapters(
    store: SessionStateStore, session_id: str
) -> tuple[Callable[[], dict[str, object] | None], Callable[[dict[str, object]], None]]:
    """Participant-facing state adapters bound to one session on the store."""

    def load_state() -> dict[str, object] | None:
        return store.read(session_id)

    def save_state(state: dict[str, object]) -> None:
        store.write(session_id, state)

    return load_state, save_state


def reading_hook_factory(
    reader: ReaderCallable,
) -> Callable[[dict[str, object]], ScriptedParticipant]:
    def hook_factory(state: dict[str, object]) -> ScriptedParticipant:
        return ScriptedParticipant(state, reader)

    return hook_factory


# --- (i) visible session: state grows across instances -----------------------


def test_visible_session_state_grows_and_items_recorded() -> None:
    store = SessionStateStore(schema=_SCHEMA)
    load_state, save_state = store_adapters(store, "vis-1")
    record = run_visible_session(
        store,
        "vis-1",
        visible_instances(),
        reading_hook_factory(fake_reader("vis")),
        load_state,
        save_state,
        byte_cap=_CAP,
    )
    # State evolves within the session: each instance loaded the prior
    # instance's saved state and appended its own notes.
    notes = store.read("vis-1")
    assert isinstance(notes, dict)
    assert len(cast(list[str], notes["notes"])) == 10  # 5 stages x 2 instances
    # The transcript shows the writes; digests evolve with the state.
    writes = [entry for entry in store.transcript("vis-1") if entry.op == "write"]
    assert len(writes) == 2  # one save per instance
    distinct_digests = {entry.digest for entry in writes}
    assert None not in distinct_digests and len(distinct_digests) == 2
    assert record.transcript_digests[-1] == writes[-1].digest
    # Items recorded, in order, in the visible session.
    assert store.items("vis-1") == tuple(inst.instance_id for inst in visible_instances())
    assert record.instance_ids == store.items("vis-1")
    # Memory-op ledger: per instance, one read-before and one write-after.
    assert record.memory_op_totals == {
        "writes": 2,
        "reads": 2,
        "bytes_written": sum(op.state_bytes for op in record.memory_ops if op.op == "write"),
        "bytes_read": sum(op.state_bytes for op in record.memory_ops if op.op == "read"),
    }


def test_visible_session_state_carries_across_instances() -> None:
    # The load-before/save-after composition is the contract: instance 2
    # starts from instance 1's saved state, visible in the hook's own view.
    store = SessionStateStore(schema=_SCHEMA)
    seen_loads: list[dict[str, object] | None] = []

    def hook_factory(state: dict[str, object]) -> ScriptedParticipant:
        seen_loads.append(dict(state))
        return ScriptedParticipant(state, fake_reader("vis"))

    load_state, save_state = store_adapters(store, "vis-1")
    run_visible_session(
        store, "vis-1", visible_instances(), hook_factory, load_state, save_state, byte_cap=_CAP
    )
    assert seen_loads[0] == {}  # first instance starts byte-empty
    assert isinstance(seen_loads[1], dict) and seen_loads[1]  # second sees the grown state


# --- (ii) gate session: the split boundary -----------------------------------


def test_gate_session_load_state_sees_empty_state() -> None:
    store = SessionStateStore(schema=_SCHEMA)
    load_vis, save_vis = store_adapters(store, "vis-1")
    run_visible_session(
        store,
        "vis-1",
        visible_instances(),
        reading_hook_factory(fake_reader("vis")),
        load_vis,
        save_vis,
        byte_cap=_CAP,
    )
    assert store.read("vis-1")  # the visible session holds state

    load_gate, save_gate = store_adapters(store, "gate-1")
    observed: list[dict[str, object] | None] = []

    def gate_hook_factory(state: dict[str, object]) -> ScriptedParticipant:
        observed.append(dict(state))
        return ScriptedParticipant(state, fake_reader("gate"))

    record = run_gate_session(
        store,
        "gate-1",
        gate_instances(),
        gate_hook_factory,
        load_gate,
        save_gate,
        byte_cap=_CAP,
    )
    # The gate session's own load_state read byte-empty state at every
    # instance: participant state did not carry across the split boundary.
    assert observed == [{}]
    assert store.session_kind("gate-1").value == "gate"
    assert record.kind.value == "gate"
    store.boundary_check("gate-1")


def test_gate_session_id_must_be_new() -> None:
    store = SessionStateStore(schema=_SCHEMA)
    load, save = store_adapters(store, "vis-1")
    run_visible_session(
        store,
        "vis-1",
        visible_instances(),
        reading_hook_factory(fake_reader("vis")),
        load,
        save,
        byte_cap=_CAP,
    )
    # A gate session over an existing id is refused: sessions are one
    # lifetime, the boundary is structural.
    with pytest.raises(SessionBoundaryError, match="already exists"):
        run_gate_session(
            store,
            "vis-1",
            gate_instances(),
            reading_hook_factory(fake_reader("g")),
            load,
            save,
            byte_cap=_CAP,
        )


def test_state_byte_cap_enforced_through_wiring() -> None:
    # The wiring persists through the store's serialization boundary, so
    # a grown state over the cap raises there — never silent truncation.
    store = SessionStateStore(schema=_SCHEMA)
    load, save = store_adapters(store, "vis-1")
    with pytest.raises(SessionStateError, match="exceeding"):
        run_visible_session(
            store,
            "vis-1",
            visible_instances(),
            reading_hook_factory(fake_reader("vis")),
            load,
            save,
            byte_cap=64,
        )


# --- (iii) canary leak probe ----------------------------------------------------


def test_canary_probe_tokens_absent_from_gate() -> None:
    store = SessionStateStore(schema=_SCHEMA)

    def gate_runner() -> object:
        load, save = store_adapters(store, "gate-1")
        return run_gate_session(
            store,
            "gate-1",
            gate_instances(),
            reading_hook_factory(fake_reader("gate")),
            load,
            save,
            byte_cap=_CAP,
        )

    gate_result, probe = run_leak_probe_then_gate(
        store, [_CANARY, "GOLDTOKEN-beta"], gate_runner, byte_cap=_CAP
    )
    assert isinstance(gate_result, object)
    assert probe.gate_session_id == "gate-1"
    assert set(probe.tokens) == {_CANARY, "GOLDTOKEN-beta"}
    # Injection is a ledgered write in the canary session; the gate
    # session's transcript carries no canary bytes.
    assert store.session_kind("canary-probe").value == "canary"
    canary_ops = store.ledger("canary-probe")
    assert any(op.op == "write" and op.state_bytes > 0 for op in canary_ops)
    assert not any(
        _CANARY.encode() in (entry.canonical or b"") for entry in store.transcript("gate-1")
    )


def test_canary_probe_catches_leaking_load_state() -> None:
    store = SessionStateStore(schema=_SCHEMA)

    # A deliberately-leaking participant: its load_state is wired to the
    # CANARY session instead of the gate session, so canary state crosses
    # the boundary into the gate run.
    def leaking_load() -> dict[str, object] | None:
        return store.read("canary-probe")

    def gate_runner() -> object:
        def leaky_factory(state: dict[str, object]) -> ScriptedParticipant:
            return ScriptedParticipant(state, fake_reader("gate"))

        return run_gate_session(
            store,
            "gate-1",
            gate_instances(),
            leaky_factory,
            leaking_load,
            store_adapters(store, "gate-1")[1],
            byte_cap=_CAP,
        )

    with pytest.raises(LeakProbeError, match=_CANARY):
        run_leak_probe_then_gate(store, [_CANARY], gate_runner, byte_cap=_CAP)


# --- (iv) deterministic replay: transcript equality ----------------------------


def _recorded_for(instances: list[LifecycleInstance]) -> tuple[ReplayCall, ...]:
    """Record the fake reader once over the instance stream."""

    recorder = ReplayRecorder(fake_reader("replay"))
    for instance in instances:
        participant = ScriptedParticipant({}, recorder)
        run_lifecycle(instance, participant, ProjectState())
    return recorder.transcript()


def test_replay_transcript_equality_five_repeats() -> None:
    instances = visible_instances()
    recorded = _recorded_for(instances)
    # All repeats draw identical (state transcripts, run records,
    # memory-op ledgers); wall-seconds is a timing artifact, zeroed.
    assert (
        replay_transcript_equality(
            instances,
            reading_hook_factory,
            recorded,
            schema=_SCHEMA,
            byte_cap=_CAP,
            repeats=5,
        )
        is True
    )


def test_replay_produces_byte_identical_records() -> None:
    instances = visible_instances()
    recorded = _recorded_for(instances)
    records = []
    for _ in range(2):
        store = SessionStateStore(schema=_SCHEMA)
        records.append(
            replay(
                store,
                "replay-run",
                instances,
                reading_hook_factory,
                recorded,
                *store_adapters(store, "replay-run"),
                byte_cap=_CAP,
            )
        )
    first, second = records
    # Byte-identical modulo the wall-seconds timing artifact.
    assert first.transcript_digests == second.transcript_digests
    first_dicts = [
        {key: value for key, value in record.to_dict().items() if key != "cost"}
        for record in first.run_records
    ]
    second_dicts = [
        {key: value for key, value in record.to_dict().items() if key != "cost"}
        for record in second.run_records
    ]
    assert first_dicts == second_dicts
    assert first.run_records[0].cost["tokens_in"] == second.run_records[0].cost["tokens_in"]
    assert first.memory_ops == second.memory_ops


# --- (v) replay miss: unseen pack raises ---------------------------------------


def test_replay_miss_on_unseen_pack() -> None:
    instances = visible_instances()
    recorded = _recorded_for(instances)
    store = SessionStateStore(schema=_SCHEMA)

    # A hook whose reader input never appeared in the recorded transcript
    # (a changed input policy) misses by digest, never by silence.
    def shifted_factory(
        reader: ReaderCallable,
    ) -> Callable[[dict[str, object]], ScriptedParticipant]:
        def shifted_reader(query: str, pack: str) -> tuple[str, int, int]:
            return reader(f"shifted:{query}", pack)

        def hook_factory(state: dict[str, object]) -> ScriptedParticipant:
            return ScriptedParticipant(state, shifted_reader)

        return hook_factory

    load_state, save_state = store_adapters(store, "replay-miss")
    with pytest.raises(ReplayMissError, match=r"[0-9a-f]{64}"):
        replay(
            store,
            "replay-miss",
            instances,
            shifted_factory,
            recorded,
            load_state,
            save_state,
            byte_cap=_CAP,
        )


# --- session plan ---------------------------------------------------------------


def test_session_plan_split_and_validation() -> None:
    plan = SessionPlan(
        visible_instance_ids=("i-1", "i-2"),
        gate_instance_ids=("g-1",),
        byte_cap=_CAP,
        schema=_SCHEMA,
        canary_tokens=(_CANARY,),
    )
    assert plan.to_dict() == {
        "visible_instance_ids": ["i-1", "i-2"],
        "gate_instance_ids": ["g-1"],
        "byte_cap": _CAP,
        "schema": _SCHEMA,
        "canary_tokens": [_CANARY],
    }
    with pytest.raises(ValueError, match="disjoint"):
        SessionPlan(("i-1",), ("i-1",), _CAP, _SCHEMA, ())
    with pytest.raises(ValueError, match="positive"):
        SessionPlan(("i-1",), ("g-1",), 0, _SCHEMA, ())
