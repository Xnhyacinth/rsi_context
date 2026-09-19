"""Deterministic replay of recorded reader responses over lifecycle runs.

Contract status: implements the reproduction half of the replay duality
(benchmark-contract-v2.md §Protocol semantics "Replay is dual-purpose and
both are required"; contract-tests-phase-b.md group 3) over the Phase B
packages. Archived outputs stand in for reader behavior only when the
program is unchanged: every reader call is keyed by a canonical digest of
its (query, pack) input, so a changed input policy misses the transcript
rather than silently receiving a stale answer.

``ReplayRecorder`` wraps a real reader callable — ``Callable[[str, str],
tuple[str, int, int]]`` mapping (query, pack) to (answer, tokens_in,
tokens_out) — and records every call into an ordered transcript of
``ReplayCall`` entries (input digest, response, call index). The
transcript's dict form is the canonical JSON record the manifest
references.

``replay`` re-runs a hook-driven lifecycle flow against the recorded
transcript: the reader callable it installs looks responses up by canonical
input digest and never calls the real reader; a miss raises
``ReplayMissError`` naming the digest. ``replay_transcript_equality``
(contract-tests group 3) runs the session-lifecycle flow N times against the
same recorded outputs and requires byte-identical (a) state transcript digest
sequences, (b) ``LifecycleRunRecord`` canonical dicts, and (c) memory-op
ledgers — the deterministic-replay column, distinct from fresh-request
replay's variance estimation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.session.store import SessionKind, SessionStateStore
from rsicontext.wiring.session_lifecycle import (
    SessionLifecycleRecord,
    StateHookFactory,
    StateLoad,
    StateSave,
    run_session_flow,
)

__all__ = [
    "ReaderCallable",
    "ReplayCall",
    "ReplayMissError",
    "ReplayRecorder",
    "replay",
    "replay_transcript_equality",
]

#: A real reader: (query, pack) -> (answer, tokens_in, tokens_out).
ReaderCallable = Callable[[str, str], tuple[str, int, int]]
#: A hook factory whose hooks call a reader for each stage turn.
ReadingHookFactory = Callable[[ReaderCallable], StateHookFactory]


@dataclass(frozen=True, slots=True)
class ReplayCall:
    """One recorded reader call: canonical input digest and response."""

    input_digest: str
    query: str
    pack: str
    answer: str
    tokens_in: int
    tokens_out: int
    call_index: int

    def __post_init__(self) -> None:
        for name, value in (
            ("input_digest", self.input_digest),
            ("query", self.query),
            ("pack", self.pack),
            ("answer", self.answer),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        if not self.input_digest:
            raise ValueError("input_digest must be non-empty")
        for token_name, count in (("tokens_in", self.tokens_in), ("tokens_out", self.tokens_out)):
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(f"{token_name} must be a non-negative integer")
        if not isinstance(self.call_index, int) or isinstance(self.call_index, bool):
            raise TypeError("call_index must be an integer")
        if self.call_index < 0:
            raise ValueError("call_index must be non-negative")

    def response(self) -> tuple[str, int, int]:
        return (self.answer, self.tokens_in, self.tokens_out)

    def to_dict(self) -> dict[str, object]:
        return {
            "input_digest": self.input_digest,
            "query": self.query,
            "pack": self.pack,
            "answer": self.answer,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "call_index": self.call_index,
        }


class ReplayMissError(LookupError):
    """Raised when a replayed reader call has no recorded input digest."""


def canonical_input_digest(query: str, pack: str) -> str:
    """sha256 over the canonical (query, pack) input bytes."""

    payload = json.dumps(
        [query, pack], ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ReplayRecorder:
    """Wrap a real reader, recording every call into an ordered transcript.

    The recorder is itself a ``ReaderCallable``: pass it wherever the real
    reader goes, then feed ``transcript`` to ``replay``. Digest collisions
    cannot happen (sha256); a repeated identical input records again — the
    transcript is the ordered call log, not a deduplicated map, and
    ``replay``'s lookup is by digest over first occurrence.
    """

    def __init__(self, reader: ReaderCallable) -> None:
        if not callable(reader):
            raise TypeError("reader must be callable")
        self._reader = reader
        self._calls: list[ReplayCall] = []

    def __call__(self, query: str, pack: str) -> tuple[str, int, int]:
        answer, tokens_in, tokens_out = self._reader(query, pack)
        self._calls.append(
            ReplayCall(
                input_digest=canonical_input_digest(query, pack),
                query=query,
                pack=pack,
                answer=answer,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                call_index=len(self._calls),
            )
        )
        return answer, tokens_in, tokens_out

    def transcript(self) -> tuple[ReplayCall, ...]:
        return tuple(self._calls)

    def to_dict(self) -> dict[str, object]:
        return {
            "calls": [call.to_dict() for call in self._calls],
            "call_count": len(self._calls),
        }


def _recorded_lookup(
    recorded: Sequence[ReplayCall],
) -> Callable[[str, str], tuple[str, int, int]]:
    if not recorded:
        raise ValueError("recorded transcript must not be empty")
    by_digest: dict[str, ReplayCall] = {}
    for call in recorded:
        by_digest.setdefault(call.input_digest, call)

    def lookup(query: str, pack: str) -> tuple[str, int, int]:
        digest = canonical_input_digest(query, pack)
        call = by_digest.get(digest)
        if call is None:
            raise ReplayMissError(
                f"no recorded reader response for input digest {digest} "
                f"(query={query!r}, pack head={pack[:80]!r})"
            )
        return call.response()

    return lookup


def replay(
    store: SessionStateStore,
    session_id: str,
    instances: Sequence[LifecycleInstance],
    hook_factory: ReadingHookFactory,
    recorded: Sequence[ReplayCall],
    load_state: StateLoad,
    save_state: StateSave,
    *,
    byte_cap: int,
) -> SessionLifecycleRecord:
    """Deterministically replay a session from recorded reader responses.

    Runs the same session flow as ``run_visible_session`` with the hook
    built from a reader callable that serves responses from ``recorded`` by
    canonical input digest — the real reader is never called. Any input the
    original run did not produce raises ``ReplayMissError`` with the digest:
    archived outputs never stand in for the real behavior of a changed
    input policy (benchmark contract §Protocol semantics). The session kind
    is ``REPLAY``, per the split-boundary contract.
    """

    if not isinstance(store, SessionStateStore):
        raise TypeError("store must be a SessionStateStore")
    return run_session_flow(
        store,
        SessionKind.REPLAY,
        session_id,
        instances,
        hook_factory(_recorded_lookup(recorded)),
        load_state,
        save_state,
        byte_cap=byte_cap,
    )


def _ledger_tuples(record: SessionLifecycleRecord) -> tuple[tuple[str, str, int], ...]:
    """Ledger compared across replays: op, session id, byte count in order."""

    return tuple((op.op, op.session_id, op.state_bytes) for op in record.memory_ops)


def _store_adapters(store: SessionStateStore, session_id: str) -> tuple[StateLoad, StateSave]:
    """Store-bound participant state adapters for one session."""

    def load_state() -> dict[str, object] | None:
        return store.read(session_id)

    def save_state(state: dict[str, object]) -> None:
        store.write(session_id, state)

    return load_state, save_state


def _run_dicts(record: SessionLifecycleRecord) -> tuple[dict[str, object], ...]:
    """Canonical run-record dicts with the wall-seconds column zeroed.

    ``wall_seconds`` is a timing artifact of this process, not program
    state (benchmark contract §Protocol semantics: deterministic replay
    covers program + state + ledger); the token columns stay and are
    compared byte-for-byte.
    """

    dicts: list[dict[str, object]] = []
    for run_record in record.run_records:
        payload = run_record.to_dict()
        cost = payload.get("cost")
        if isinstance(cost, dict):
            scrubbed = dict(cost)
            scrubbed["wall_seconds"] = 0.0
            payload["cost"] = scrubbed
        dicts.append(payload)
    return tuple(dicts)


def replay_transcript_equality(
    instances: Sequence[LifecycleInstance],
    hook_factory: ReadingHookFactory,
    recorded: Sequence[ReplayCall],
    *,
    schema: dict[str, object],
    byte_cap: int,
    repeats: int = 5,
) -> bool:
    """Contract-test group 3: N deterministic replays are byte-identical.

    Runs the session-lifecycle replay flow ``repeats`` times against the
    SAME recorded reader outputs and requires, against the first run:
    (a) identical state transcript digest sequences, (b) identical
    ``LifecycleRunRecord`` canonical dicts (the ``cost.wall_seconds``
    column zeroed — a timing artifact of this process, not program state),
    and (c) identical memory-op ledgers. A divergence is therefore a
    determinism failure in the wiring, not reader noise (fresh-request
    replay, the duality's other half, is a separate flow). On the first
    divergence an ``AssertionError`` names the repeat and the differing
    column with both values; a clean pass returns ``True``.

    Each repeat runs on its own store and replay session with store-bound
    state adapters — the same load-before/save-after protocol the session
    flow uses, so the compared transcripts are ordinary ledgered session
    transcripts. The equality holds the item stream fixed across repeats,
    and a store structurally forbids one item id in two sessions, so
    repeats cannot share a store.
    """

    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 2:
        raise ValueError("repeats must be an integer of at least 2")
    if not recorded:
        raise ValueError("recorded transcript must not be empty")
    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict")

    def _run_once() -> SessionLifecycleRecord:
        store = SessionStateStore(schema=schema)
        load_state, save_state = _store_adapters(store, "replay-eq")
        return replay(
            store,
            "replay-eq",
            instances,
            hook_factory,
            recorded,
            load_state,
            save_state,
            byte_cap=byte_cap,
        )

    first = _run_once()
    baseline = (
        first.transcript_digests,
        _run_dicts(first),
        _ledger_tuples(first),
    )
    for index in range(1, repeats):
        current = _run_once()
        candidate = (
            current.transcript_digests,
            _run_dicts(current),
            _ledger_tuples(current),
        )
        for name, base, cur in zip(
            ("state transcripts", "run records", "memory-op ledgers"),
            baseline,
            candidate,
            strict=True,
        ):
            if base != cur:
                raise AssertionError(
                    f"replay divergence at repeat {index}: {name} differ "
                    f"(first={base!r}, current={cur!r})"
                )
    return True
