"""The session state machine: per-session state plus a memory-op ledger.

Contract status: implements participant-interface-v1.md §State contract
clauses 3, 4, and 6 (frozen 2026-09-19; benchmark-contract-v2.md
§Protocol semantics "State-boundary contract").

A store owns the state of one registration across a sequence of
sessions. The split-boundary rule is structural: state written in one
session is namespaced under that session's id and is unreachable from
any other session — a read of session ``B`` cannot observe a byte that
was written under session ``A``. ``begin_session`` enforces the reset:
every session starts byte-empty, except that a fresh ``canary`` session
may carry injected canary tokens (the leak-probe session), so boundary
compliance is demonstrated by the absence of those bytes everywhere
else rather than by convention. ``boundary_check`` re-asserts the
namespace invariant over the recorded ops.

Two audit views are maintained per session. The **memory-op ledger**
(``MemoryOpLedger``) is the accounting view required by contract clause
4: every write/read op with its byte count. The **transcript** is the
content view: the ordered (op, post-op canonical state bytes, digest)
records whose byte form the clause requires to be logged and auditable,
and which the leak probe scans. The manifest field
``state_transcript_ref`` references the transcript.

State is untrusted-code-authored persistent data, so every write and
load runs through the canonical-serialization, cap, and validation
checks in ``session/state.py`` rather than trusting the producer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from .state import (
    StateCanonicalizationError,
    StateValidationError,
    canonical_state_bytes,
    state_schema_digest,
    validate_state_bytes,
)


class SessionKind(StrEnum):
    """Split-boundary session class (visible / gate / replay / sealed / canary)."""

    VISIBLE = "visible"
    GATE = "gate"
    REPLAY = "replay"
    SEALED = "sealed"
    CANARY = "canary"


@dataclass(frozen=True, slots=True)
class MemoryOpLedger:
    """One recorded state operation and the byte count it carried."""

    op: str
    session_id: str
    state_bytes: int

    def __post_init__(self) -> None:
        if self.op not in {"write", "read"}:
            raise ValueError("op must be write or read")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(self.state_bytes, int) or isinstance(self.state_bytes, bool):
            raise TypeError("state_bytes must be an integer")
        if self.state_bytes < 0:
            raise ValueError("state_bytes must be non-negative")


@dataclass(frozen=True, slots=True)
class TranscriptEntry:
    """One transcript position: op, post-op canonical bytes, and their digest.

    ``canonical``/``digest`` are ``None`` only for a read of an empty
    session — an op with no state bytes to log.
    """

    op: str
    canonical: bytes | None
    digest: str | None

    def __post_init__(self) -> None:
        if self.op not in {"write", "read"}:
            raise ValueError("op must be write or read")
        if self.canonical is None:
            if self.digest is not None:
                raise ValueError("digest requires canonical bytes")
        elif not isinstance(self.canonical, bytes):
            raise TypeError("canonical must be bytes or None")
        elif self.digest is None or hashlib.sha256(self.canonical).hexdigest() != self.digest:
            raise ValueError("digest must be the sha256 of the canonical bytes")


class SessionBoundaryError(RuntimeError):
    """Raised when session lifetime or split-boundary rules are violated."""


class SessionStateError(RuntimeError):
    """Raised when a state write is malformed or exceeds the session byte cap."""


def _namespace(session_id: str) -> str:
    return f"session:{session_id}"


def _decode_state(data: bytes) -> dict[str, object]:
    decoded: dict[str, object] = json.loads(data)
    return decoded


@dataclass(frozen=True, slots=True)
class _OpRecord:
    op: str
    session_id: str
    namespace: str
    state_bytes: int
    canonical: bytes | None


@dataclass(frozen=True, slots=True)
class _SessionRecord:
    byte_cap: int
    state: bytes | None
    items: tuple[str, ...]
    ops: tuple[_OpRecord, ...]


class SessionStateStore:
    """Namespaced per-session state with a full, ordered operation ledger."""

    def __init__(self, *, schema: dict[str, object]) -> None:
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dict")
        self._schema_digest = state_schema_digest(schema)
        self._sessions: dict[str, _SessionRecord] = {}
        self._kinds: dict[str, SessionKind] = {}
        self._recorded_sessions: tuple[str, ...] = ()

    @property
    def schema_digest(self) -> str:
        """The sha256 digest of the declared retainable-state schema (manifest column)."""

        return self._schema_digest

    @property
    def recorded_sessions(self) -> tuple[str, ...]:
        """Session ids in begin order — the store's session timeline."""

        return self._recorded_sessions

    def begin_session(
        self,
        kind: SessionKind,
        session_id: str,
        byte_cap: int,
        *,
        initial_state: dict[str, object] | None = None,
    ) -> None:
        """Open a new session whose persisted state starts byte-empty.

        The initial state must be empty (``None`` or ``{}``) for every
        kind except a fresh ``canary`` session, which may carry the
        injected canary tokens. Any non-empty initial state on another
        kind — or any state at all on an existing session id — is a
        split-boundary violation.
        """

        if not isinstance(kind, SessionKind):
            raise TypeError("kind must be a SessionKind")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        if session_id in self._sessions:
            raise SessionBoundaryError(f"session {session_id!r} already exists")
        if not isinstance(byte_cap, int) or isinstance(byte_cap, bool) or byte_cap <= 0:
            raise ValueError("byte_cap must be a positive integer")
        initial_bytes: bytes | None = None
        if initial_state is not None:
            if not isinstance(initial_state, dict):
                raise TypeError("initial_state must be a dict")
            if initial_state and kind is not SessionKind.CANARY:
                raise SessionBoundaryError(
                    "only a canary session may begin with non-empty injected state",
                )
            if initial_state:
                try:
                    candidate = canonical_state_bytes(initial_state)
                except StateCanonicalizationError as exc:
                    raise SessionStateError(f"injected canary state is malformed: {exc}") from exc
                try:
                    initial_bytes = validate_state_bytes(candidate, self._schema_digest, byte_cap)
                except StateValidationError as exc:
                    raise SessionStateError(f"injected canary state is rejected: {exc}") from exc
        self._sessions[session_id] = _SessionRecord(
            byte_cap=byte_cap,
            state=initial_bytes,
            items=(),
            ops=(),
        )
        self._kinds[session_id] = kind
        self._recorded_sessions = (*self._recorded_sessions, session_id)

    def session_kind(self, session_id: str) -> SessionKind:
        """Return the kind of a begun session."""

        try:
            return self._kinds[session_id]
        except KeyError as exc:
            raise SessionBoundaryError(f"session {session_id!r} has not begun") from exc

    def items(self, session_id: str) -> tuple[str, ...]:
        """Return the item ids recorded for one session, in record order."""

        return self._require_session(session_id).items

    def record_item(self, session_id: str, item_id: str) -> None:
        """Record that one item ran in this session.

        An item id belongs to exactly one session: recording it again in
        the same session, or in any other session, raises — the
        structural form of "gate sessions contain only gate items".
        """

        record = self._require_session(session_id)
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("item_id must be a non-empty string")
        if item_id in record.items:
            raise SessionBoundaryError(
                f"item {item_id!r} is already recorded in session {session_id!r}",
            )
        for other_id, other in self._sessions.items():
            if other_id != session_id and item_id in other.items:
                raise SessionBoundaryError(
                    f"item {item_id!r} is already recorded in session {other_id!r}",
                )
        self._sessions[session_id] = _SessionRecord(
            byte_cap=record.byte_cap,
            state=record.state,
            items=(*record.items, item_id),
            ops=record.ops,
        )

    def read(self, session_id: str) -> dict[str, object] | None:
        """Read one session's current state, re-validated at the load boundary."""

        record = self._require_session(session_id)
        if record.state is None:
            self._append_op(session_id, record, "read", 0, None)
            return None
        canonical = validate_state_bytes(record.state, self._schema_digest, record.byte_cap)
        self._append_op(session_id, record, "read", len(canonical), canonical)
        return _decode_state(canonical)

    def write(self, session_id: str, obj: dict[str, object]) -> None:
        """Serialize, cap-check, validate, and store one session state write."""

        if not isinstance(obj, dict):
            raise TypeError("state must be a dict")
        record = self._require_session(session_id)
        try:
            data = canonical_state_bytes(obj)
        except StateCanonicalizationError as exc:
            raise SessionStateError(f"state write is malformed: {exc}") from exc
        try:
            canonical = validate_state_bytes(data, self._schema_digest, record.byte_cap)
        except StateValidationError as exc:
            raise SessionStateError(f"state write rejected: {exc}") from exc
        self._sessions[session_id] = _SessionRecord(
            byte_cap=record.byte_cap,
            state=canonical,
            items=record.items,
            ops=record.ops,
        )
        self._append_op(session_id, self._sessions[session_id], "write", len(canonical), canonical)

    def ledger(self, session_id: str) -> tuple[MemoryOpLedger, ...]:
        """Return the full ordered memory-op ledger for one session."""

        record = self._require_session(session_id)
        return tuple(
            MemoryOpLedger(op=op.op, session_id=op.session_id, state_bytes=op.state_bytes)
            for op in record.ops
        )

    def transcript(self, session_id: str) -> tuple[TranscriptEntry, ...]:
        """Return the full ordered (op, canonical-bytes, digest) transcript."""

        record = self._require_session(session_id)
        return tuple(
            TranscriptEntry(
                op=op.op,
                canonical=op.canonical,
                digest=(
                    hashlib.sha256(op.canonical).hexdigest() if op.canonical is not None else None
                ),
            )
            for op in record.ops
        )

    def current_state_bytes(self, session_id: str) -> bytes | None:
        """Return the current canonical state bytes (audit view, no ledger op)."""

        record = self._require_session(session_id)
        if record.state is None:
            return None
        return validate_state_bytes(record.state, self._schema_digest, record.byte_cap)

    def boundary_check(self, session_id: str) -> None:
        """Assert no session recorded a state key under another session's namespace."""

        _ = self._require_session(session_id)
        for other_id, record in self._sessions.items():
            for op in record.ops:
                if op.session_id != other_id or op.namespace != _namespace(other_id):
                    raise SessionBoundaryError(
                        "cross-session state key recorded: "
                        f"{op.namespace!r} under session {other_id!r}",
                    )

    def _require_session(self, session_id: str) -> _SessionRecord:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionBoundaryError(f"session {session_id!r} has not begun") from exc

    def _append_op(
        self,
        session_id: str,
        record: _SessionRecord,
        op: str,
        state_bytes: int,
        canonical: bytes | None,
    ) -> None:
        entry = _OpRecord(
            op=op,
            session_id=session_id,
            namespace=_namespace(session_id),
            state_bytes=state_bytes,
            canonical=canonical,
        )
        self._sessions[session_id] = _SessionRecord(
            byte_cap=record.byte_cap,
            state=record.state,
            items=record.items,
            ops=(*record.ops, entry),
        )
