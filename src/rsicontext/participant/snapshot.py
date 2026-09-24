"""Frozen learning snapshots and evaluation branches (state-boundary, phase 2).

Contract status: implements the frozen-learning-snapshot half of the
state-boundary contract (benchmark-contract-v2.md §Protocol semantics
"State-boundary contract", amended 2026-09-20; review round 4 deliverable
2). The session store (``session/store.py``) implements the SPLIT
boundary — evaluation sessions start byte-empty and never see each
other's writes. This module implements the CARRY boundary that half has
been missing: what a participant legitimately learned (code, skills,
memory) travels EQUALLY into every evaluation branch, frozen at the
moment the development session ends.

The boundary is information SOURCE, TIME, and SCOPE — never the textual
shape of what is remembered (the withdrawn "method-experience-only"
rule). A snapshot therefore carries, as one immutable unit:

- ``memory``: the dev session's final canonical state (the participant's
  retainable state Σ at freeze time);
- ``code_files`` / ``skill_files``: the participant's agent-tree files,
  split only by whether the path is Python (code) or anything else
  (skills/config/workflows — all valid state carriers per the
  participant interface). The split is bookkeeping for audits, never a
  difference in carry semantics: both enter every branch unchanged.

Freeze semantics: a snapshot is byte-frozen — its canonical bytes are
computed once and its accessor surface has no mutation path. Branches
run on their own ``SessionStateStore`` sessions whose FIRST state is the
snapshot's memory (the carry); everything a branch writes stays in that
branch's session and never touches the snapshot or sibling branches —
``run_evaluation_branch`` composes the existing ``run_session_flow``
with snapshot-aware adapters, so all store discipline (canonical form,
byte cap, schema digest, memory-op ledger, transcript) applies to branch
state unchanged, and ``run_leak_probe_then_gate`` composes on top
exactly as before: the probe still scans branch state for unauthorized
canary tokens; authorized carry is the snapshot's validated payload, not
a leak.

What this module deliberately does NOT do: decide what is "good
experience". The framework owns permissions and isolation; the
participant owns how to organize and use what it legitimately learned.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import cast

from rsicontext.lifecycle.runner import LifecycleRunRecord, ParticipantHook
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.session.state import (
    canonical_state_bytes,
    validate_state_bytes,
)
from rsicontext.session.store import SessionKind, SessionStateStore
from rsicontext.wiring import run_session_flow

__all__ = [
    "BranchKind",
    "BranchRecord",
    "FrozenSnapshot",
    "LearningCarry",
    "SnapshotBoundaryError",
    "SnapshotStateError",
    "branch_store_adapters",
    "freeze_session",
    "run_evaluation_branch",
]

_SAFE_RELATIVE = re.compile(r"\A[A-Za-z0-9_][A-Za-z0-9_.\-/]*/?\Z")
_MAX_FILE_BYTES = 1 << 20  # 1 MiB per file: agent trees are small text trees


class SnapshotBoundaryError(RuntimeError):
    """Raised when snapshot lifetime or branch rules are violated."""


class SnapshotStateError(RuntimeError):
    """Raised when snapshot material fails state validation."""


class BranchKind(StrEnum):
    """The evaluation-branch classes (contract: continuation/new-world/regression)."""

    CONTINUATION = "continuation"
    NEW_WORLD = "new_world"
    REGRESSION = "regression"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class LearningCarry:
    """The read-only carried view a branch hook receives.

    ``memory`` is the snapshot's memory object; ``code_files`` and
    ``skill_files`` map safe relative paths to file text. The same rule
    carried through any channel gets identical treatment here — the
    participant decides which channel it reads.
    """

    memory: dict[str, object]
    code_files: dict[str, str]
    skill_files: dict[str, str]

    def carries_code_and_memory_equally(self) -> bool:
        """True when both channels are populated (audit convenience)."""

        return bool(self.memory) and bool(self.code_files or self.skill_files)


def _require_safe_relative(path: str) -> None:
    """Reject unsafe relative paths, in PARITY with registration.

    The regex alone cannot reject '.'/'..'/'a/../b' segments (reviewer
    4.1). Validation mirrors ``registration._is_safe_relative_path``
    exactly — the same ``PurePosixPath`` segment semantics, so the two
    validators can never disagree on the inputs that matter; parity is
    pinned by test.
    """

    from pathlib import PurePosixPath

    if (
        not isinstance(path, str)
        or not path
        or _SAFE_RELATIVE.fullmatch(path) is None
        or PurePosixPath(path).is_absolute()
        or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
    ):
        raise SnapshotStateError(f"agent-tree path is not a safe relative path: {path!r}")


def _load_agent_tree(agent_files_root: Path | None) -> tuple[dict[str, str], dict[str, str]]:
    """Read the agent tree into code/skill file maps (safe relative paths).

    Symlinks, non-regular files, and oversized files are refusals: a
    snapshot is data, not a filesystem. Python paths land in
    ``code_files``; every other extension lands in ``skill_files``
    (skills/config/workflows are valid state carriers).
    """

    if agent_files_root is None:
        return {}, {}
    if not isinstance(agent_files_root, Path):
        raise SnapshotStateError("agent_files_root must be a Path or None")
    if not agent_files_root.is_dir():
        raise SnapshotStateError(f"agent_files_root is not a directory: {agent_files_root}")
    code: dict[str, str] = {}
    skills: dict[str, str] = {}
    for path in sorted(agent_files_root.rglob("*")):
        relative = path.relative_to(agent_files_root).as_posix()
        if relative == "":
            continue
        _require_safe_relative(relative)
        if path.is_symlink():
            raise SnapshotStateError(f"agent tree contains a symlink: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise SnapshotStateError(f"agent tree contains a non-regular file: {relative}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SnapshotStateError(f"agent file read failed: {relative}: {exc}") from exc
        if len(data) > _MAX_FILE_BYTES:
            raise SnapshotStateError(
                f"agent file exceeds the {_MAX_FILE_BYTES}-byte snapshot cap: {relative}"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SnapshotStateError(f"agent file is not UTF-8 text: {relative}") from exc
        if relative.endswith(".py"):
            code[relative] = text
        else:
            skills[relative] = text
    return code, skills


@dataclass(frozen=True, slots=True)
class FrozenSnapshot:
    """One frozen learning state: memory + code + skills, byte-frozen.

    ``canonical_bytes`` is the sorted-key JSON of the full carried
    payload; ``digest`` is its sha256. Snapshots have no mutation
    surface — ``append_note`` exists only to demonstrate refusal (and
    is used by tests to assert immutability). ``schema``/``byte_cap``
    are carried so branches enforce the same Σ discipline the dev
    session ran under.
    """

    participant_id: str
    snapshot_id: str
    memory: dict[str, object]
    code_files: dict[str, str]
    skill_files: dict[str, str]
    schema: dict[str, object]
    byte_cap: int
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("participant_id", self.participant_id),
            ("snapshot_id", self.snapshot_id),
        ):
            if not isinstance(value, str) or not value:
                raise SnapshotBoundaryError(f"{name} must be a non-empty string")
        if not isinstance(self.memory, dict):
            raise SnapshotStateError("memory must be a dict")
        for files in (self.code_files, self.skill_files):
            if not isinstance(files, dict):
                raise SnapshotStateError("file maps must be dicts")
            for key, value in files.items():
                _require_safe_relative(key)
                if not isinstance(value, str):
                    raise SnapshotStateError(f"file map value must be a string: {key!r}")
        if not isinstance(self.schema, dict):
            raise SnapshotStateError("schema must be a dict")
        if (
            not isinstance(self.byte_cap, int)
            or isinstance(self.byte_cap, bool)
            or self.byte_cap <= 0
        ):
            raise SnapshotStateError("byte_cap must be a positive integer")
        object.__setattr__(self, "digest", hashlib.sha256(self.canonical_bytes()).hexdigest())

    def canonical_bytes(self) -> bytes:
        """Deterministic sorted-key JSON of the full carried payload."""

        payload = {
            "byte_cap": self.byte_cap,
            "code_files": dict(sorted(self.code_files.items())),
            "memory": self.memory,
            "participant_id": self.participant_id,
            "schema": self.schema,
            "skill_files": dict(sorted(self.skill_files.items())),
            "snapshot_id": self.snapshot_id,
        }
        return canonical_state_bytes(payload)

    def carries_code_and_memory_equally(self) -> bool:
        return LearningCarry(
            self.memory, dict(self.code_files), dict(self.skill_files)
        ).carries_code_and_memory_equally()

    def append_note(self, note: str) -> None:
        """Refuse: a frozen snapshot is immutable."""

        raise SnapshotBoundaryError(
            f"snapshot {self.snapshot_id!r} is frozen; write to a branch session instead"
        )

    @classmethod
    def from_parts(
        cls,
        *,
        participant_id: str,
        snapshot_id: str,
        memory: dict[str, object],
        code_files: dict[str, str],
        skill_files: dict[str, str],
        schema: dict[str, object],
        byte_cap: int,
    ) -> FrozenSnapshot:
        """Build a snapshot from already-validated parts (e.g. an improver's output)."""

        return cls(
            participant_id=participant_id,
            snapshot_id=snapshot_id,
            memory=_fresh_memory(memory),
            code_files=dict(code_files),
            skill_files=dict(skill_files),
            schema=dict(schema),
            byte_cap=byte_cap,
        )


def freeze_session(
    store: SessionStateStore,
    session_id: str,
    *,
    agent_files_root: Path | None,
    participant_id: str,
    snapshot_id: str,
    byte_cap: int,
) -> FrozenSnapshot:
    """Freeze one dev session's final state + agent tree into a snapshot.

    Reads the session's CURRENT canonical bytes (an audit read: no ledger
    op), re-validates them under the store's schema digest and the
    declared ``byte_cap`` (the dev session's cap — the caller knows it),
    and pairs them with the agent tree's files. The session itself is
    untouched — freezing is read-only on the store.
    """

    if not isinstance(store, SessionStateStore):
        raise TypeError("store must be a SessionStateStore")
    if not isinstance(session_id, str) or not session_id:
        raise SnapshotBoundaryError("session_id must be a non-empty string")
    if session_id not in store.recorded_sessions:
        raise SnapshotBoundaryError(f"session {session_id!r} has not begun")
    if not isinstance(byte_cap, int) or isinstance(byte_cap, bool) or byte_cap <= 0:
        raise SnapshotStateError("byte_cap must be a positive integer")
    state_bytes = store.current_state_bytes(session_id)
    if state_bytes is None:
        raise SnapshotBoundaryError(
            f"session {session_id!r} holds no state to freeze; run the dev session first"
        )
    schema_digest = store.schema_digest
    try:
        validate_state_bytes(state_bytes, schema_digest, byte_cap)
    except Exception as exc:  # StateValidationError
        raise SnapshotStateError(f"frozen state fails validation: {exc}") from exc
    memory = json.loads(state_bytes)
    code, skills = _load_agent_tree(agent_files_root)
    return FrozenSnapshot(
        participant_id=participant_id,
        snapshot_id=snapshot_id,
        memory=memory,
        code_files=code,
        skill_files=skills,
        schema={"schema_digest": schema_digest},
        byte_cap=byte_cap,
    )


def _fresh_memory(memory: Mapping[str, object]) -> dict[str, object]:
    """A structurally independent copy of carried memory.

    ``dict(...)`` is a SHALLOW copy: nested containers stay shared by
    reference, so an in-place participant mutation
    (``state['nested']['k'] = v``) would reach the snapshot and every
    sibling branch — exactly the isolation failure the carry boundary
    exists to prevent (reviewer finding 1.1). Carried memory is
    JSON-native by construction (it passed canonical-state validation),
    so a canonical-bytes round trip is a deep, deterministic copy.
    """

    fresh: dict[str, object] = json.loads(canonical_state_bytes(dict(memory)))
    return fresh


def branch_store_adapters(
    snapshot: FrozenSnapshot,
    store: SessionStateStore,
    session_id: str,
) -> tuple[Callable[[], dict[str, object] | None], Callable[[dict[str, object]], None]]:
    """Snapshot-aware state adapters for one branch session.

    The carry is delivered until the session holds saved state: the
    FIRST load returns a structurally independent copy of the snapshot's
    memory, and so does every load BEFORE the first save — not just the
    first call (reviewer 1.2: flipping the flag at load time loses the
    carry if the hook raises before the first save, because a later
    load would read the still-empty session). After the first save,
    loads read the branch's own evolving state. All writes go through
    the store's full validation — cap, canonical form, schema digest,
    ledger, transcript.
    """

    def load_state() -> dict[str, object] | None:
        if store.current_state_bytes(session_id) is None:
            return _fresh_memory(snapshot.memory)
        return store.read(session_id)

    def save_state(state: dict[str, object]) -> None:
        store.write(session_id, state)

    return load_state, save_state


@dataclass(frozen=True, slots=True)
class BranchRecord:
    """Auditable outcome of one evaluation branch run.

    ``store`` exposes the branch's own ``SessionStateStore`` so the leak
    probe composes on top exactly as it does over plain sessions
    (reviewer 1.3): ``assert_canary_absent(record.store, session_id,
    tokens)`` and ``store.ledger``/``store.transcript`` are the audit
    surface. It is deliberately NOT serializable state — ``to_dict``
    carries the summary, the store the evidence.
    """

    branch_kind: BranchKind
    session_id: str
    snapshot_digest: str
    run_records: tuple[LifecycleRunRecord, ...]
    transcript_digests: tuple[str | None, ...]
    store: SessionStateStore | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "branch_kind": self.branch_kind.value,
            "session_id": self.session_id,
            "snapshot_digest": self.snapshot_digest,
            "run_records": [
                record.to_dict() if hasattr(record, "to_dict") else repr(record)
                for record in self.run_records
            ],
            "transcript_digests": list(self.transcript_digests),
        }


def run_evaluation_branch(
    snapshot: FrozenSnapshot,
    kind: BranchKind,
    session_id: str,
    *,
    instances: Sequence[LifecycleInstance],
    hook_factory: Callable[[dict[str, object], LearningCarry], object],
    byte_cap: int,
) -> BranchRecord:
    """Run one evaluation branch from a frozen snapshot.

    A fresh ``SessionStateStore`` is built per branch (its schema comes
    from the snapshot's carried schema digest), the session is begun with
    the branch kind's session kind, and the loop is the existing
    ``run_session_flow`` with snapshot-aware adapters: the first load
    carries the snapshot's memory, subsequent loads read the branch's own
    state, and every save lands only in this branch's session. The hook
    receives the evolving state plus the read-only ``LearningCarry``
    (memory + code + skill files) so it can use any channel.
    """

    if not isinstance(snapshot, FrozenSnapshot):
        raise TypeError("snapshot must be a FrozenSnapshot")
    # Freeze integrity (external review 4.4): the digest was computed once
    # at __post_init__ over the payload the object carries; a snapshot
    # whose memory/file dicts were mutated IN PLACE since (``frozen=True``
    # blocks re-assignment, not ``dict['k'] = v``) must not silently serve
    # tampered carry into every branch — recompute and refuse on drift.
    current_digest = hashlib.sha256(snapshot.canonical_bytes()).hexdigest()
    if current_digest != snapshot.digest:
        raise SnapshotStateError(
            f"snapshot {snapshot.snapshot_id!r} fails its own digest: the "
            "frozen payload changed after freeze (in-place mutation); "
            f"expected {snapshot.digest!r}, recomputed {current_digest!r}"
        )
    if not isinstance(kind, BranchKind):
        raise TypeError("kind must be a BranchKind")
    if not isinstance(session_id, str) or not session_id:
        raise SnapshotBoundaryError("session_id must be a non-empty string")
    instances = tuple(instances)
    if any(not isinstance(instance, LifecycleInstance) for instance in instances):
        raise TypeError("instances entries must be LifecycleInstance values")
    if not callable(hook_factory):
        raise TypeError("hook_factory must be callable")

    schema: dict[str, object] = {
        "type": "object",
        "properties": {"carry": {"digest": snapshot.schema.get("schema_digest")}},
    }
    store = SessionStateStore(schema=schema)
    session_kind = SessionKind.REPLAY if kind is BranchKind.REPLAY else SessionKind.GATE
    load_state, save_state = branch_store_adapters(snapshot, store, session_id)
    carry = LearningCarry(
        memory=_fresh_memory(snapshot.memory),
        code_files=dict(snapshot.code_files),
        skill_files=dict(snapshot.skill_files),
    )

    def _hook_factory(state: dict[str, object]) -> ParticipantHook:
        return cast("ParticipantHook", hook_factory(state, carry))

    record = run_session_flow(
        store,
        session_kind,
        session_id,
        instances,
        _hook_factory,
        load_state,
        save_state,
        byte_cap=byte_cap,
    )
    return BranchRecord(
        branch_kind=kind,
        session_id=session_id,
        snapshot_digest=snapshot.digest,
        run_records=record.run_records,
        transcript_digests=record.transcript_digests,
        store=store,
    )
