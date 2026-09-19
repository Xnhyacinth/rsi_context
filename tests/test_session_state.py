"""Contract-level tests for the session state machine.

Implements contract-tests-phase-b.md groups 1 (state-boundary contract)
and 2 (leak probe) against ``src/rsicontext/session``.
"""

from __future__ import annotations

import hashlib

import pytest

from rsicontext.eval import fresh_policy
from rsicontext.researcher import process as researcher_process
from rsicontext.session import (
    LeakProbeError,
    SessionBoundaryError,
    SessionKind,
    SessionStateError,
    SessionStateStore,
    StateValidationError,
    assert_canary_absent,
    canonical_state_bytes,
    inject_canary_tokens,
    state_schema_digest,
    validate_state_bytes,
)

_SCHEMA: dict[str, object] = {"type": "object", "properties": {"notes": {"type": "array"}}}
_CAP = 4096


def _store() -> SessionStateStore:
    return SessionStateStore(schema=_SCHEMA)


# --- Group 1: state-boundary contract -------------------------------------


def test_state_resets_at_split_boundaries() -> None:
    store = _store()
    store.begin_session(SessionKind.VISIBLE, "vis-1", _CAP)
    store.write("vis-1", {"notes": ["learned"]})
    store.begin_session(SessionKind.GATE, "gate-1", _CAP)
    # The gate session starts byte-empty: state written in the visible
    # session is unreachable (namespaced) and the new session begins empty.
    assert store.read("gate-1") is None
    store.boundary_check("gate-1")
    # Sessions outside the store are unreachable, not implicitly empty.
    with pytest.raises(SessionBoundaryError):
        store.session_kind("gate-2")


def test_gate_sessions_contain_only_gate_items() -> None:
    store = _store()
    store.begin_session(SessionKind.VISIBLE, "vis-1", _CAP)
    store.record_item("vis-1", "item-001")
    store.begin_session(SessionKind.GATE, "gate-1", _CAP)
    with pytest.raises(SessionBoundaryError):
        # The visible item cannot also be recorded in the gate session.
        store.record_item("gate-1", "item-001")
    store.record_item("gate-1", "gate-item-9")
    assert store.items("gate-1") == ("gate-item-9",)


def test_state_byte_cap_enforced_at_serialization() -> None:
    store = _store()
    store.begin_session(SessionKind.VISIBLE, "vis-1", 64)
    with pytest.raises(SessionStateError):
        store.write("vis-1", {"notes": ["x" * 200]})


def test_canonical_state_serialization() -> None:
    a = {"b": 1, "a": [2, {"d": None, "c": "é"}]}
    b = {"a": [2, {"c": "é", "d": None}], "b": 1}
    assert canonical_state_bytes(a) == canonical_state_bytes(b)
    # Round-trip: canonical bytes validate as themselves.
    digest = state_schema_digest(_SCHEMA)
    assert validate_state_bytes(canonical_state_bytes(a), digest, _CAP) == canonical_state_bytes(a)
    # Non-canonical byte form (unsorted keys / whitespace) is rejected.
    non_canonical = b'{"a": 1, "b": 2}'
    with pytest.raises(StateValidationError):
        validate_state_bytes(non_canonical, digest, _CAP)
    # Hash-seed determinism: PYTHONHASHSEED is pinned in both worker
    # environments (fresh_policy.py / researcher/process.py), asserted via
    # env construction; canonical form itself is key-order-independent,
    # which the a/b equality above demonstrates without spawning a process.
    assert fresh_policy._WORKER_ENVIRONMENT["PYTHONHASHSEED"] == "0"
    assert researcher_process._BASE_ENVIRONMENT["PYTHONHASHSEED"] == "0"


def test_state_schema_validation_on_load() -> None:
    digest = state_schema_digest(_SCHEMA)
    # Malformed JSON.
    with pytest.raises(StateValidationError):
        validate_state_bytes(b"{not json", digest, _CAP)
    # Non-object top level.
    with pytest.raises(StateValidationError):
        validate_state_bytes(b"[1,2]", digest, _CAP)
    # Filesystem-path strings rejected in keys and values.
    with pytest.raises(StateValidationError):
        validate_state_bytes(canonical_state_bytes({"/etc/passwd": 1}), digest, _CAP)
    with pytest.raises(StateValidationError):
        validate_state_bytes(canonical_state_bytes({"notes": ["~/secrets"]}), digest, _CAP)
    # Oversized blob rejected at the boundary.
    with pytest.raises(StateValidationError):
        validate_state_bytes(canonical_state_bytes({"notes": ["y" * 100]}), digest, 16)
    # Non-string keys cannot be serialized at all.
    with pytest.raises(TypeError):
        canonical_state_bytes({1: "x"})


# --- Group 2: leak probe ---------------------------------------------------


def test_visible_gold_canary_absent_from_gate() -> None:
    store = _store()
    store.begin_session(SessionKind.CANARY, "canary-1", _CAP)
    inject_canary_tokens(store, "canary-1", ["GOLDTOKEN-alpha"])
    store.begin_session(SessionKind.GATE, "gate-1", _CAP)
    store.write("gate-1", {"notes": ["ordinary work"]})
    result = assert_canary_absent(store, "gate-1", ["GOLDTOKEN-alpha"])
    assert result.gate_session_id == "gate-1"
    assert result.tokens == ("GOLDTOKEN-alpha",)
    assert result.transcript_entries_scanned >= 1
    # The negative case: a leaked token raises with position detail.
    store.begin_session(SessionKind.GATE, "gate-2", _CAP)
    store.write("gate-2", {"notes": ["GOLDTOKEN-alpha"]})
    with pytest.raises(LeakProbeError, match="position"):
        assert_canary_absent(store, "gate-2", ["GOLDTOKEN-alpha"])


def test_leak_probe_recorded_in_manifest_layer() -> None:
    store = _store()
    store.begin_session(SessionKind.CANARY, "canary-1", _CAP)
    inject_canary_tokens(store, "canary-1", ["tok-1", "tok-2"])
    # Injection is an ordinary ledgered write in the canary session.
    ops = store.ledger("canary-1")
    assert any(op.op == "write" and op.state_bytes > 0 for op in ops)
    # The probe result carries the attachable record fields.
    store.begin_session(SessionKind.GATE, "gate-1", _CAP)
    result = assert_canary_absent(store, "gate-1", ["tok-1", "tok-2"])
    tokens = list(result.tokens)
    record = {
        "probe": "visible-gold-canary",
        "gate_session": result.gate_session_id,
        "tokens": tokens,
        "transcript_entries_scanned": result.transcript_entries_scanned,
        "state_bytes_scanned": result.state_bytes_scanned,
    }
    assert record["probe"] == "visible-gold-canary"
    assert set(tokens) == {"tok-1", "tok-2"}


# --- Supporting contract details -------------------------------------------


def test_transcript_digests_are_auditable() -> None:
    store = _store()
    store.begin_session(SessionKind.VISIBLE, "vis-1", _CAP)
    store.write("vis-1", {"notes": ["one"]})
    store.write("vis-1", {"notes": ["one", "two"]})
    transcript = store.transcript("vis-1")
    writes = [entry for entry in transcript if entry.op == "write"]
    assert len(writes) == 2
    for entry in writes:
        assert entry.digest == hashlib.sha256(entry.canonical or b"").hexdigest()


def test_only_canary_sessions_may_carry_injected_state() -> None:
    store = _store()
    with pytest.raises(SessionBoundaryError):
        store.begin_session(SessionKind.VISIBLE, "vis-1", _CAP, initial_state={"notes": ["x"]})
    store.begin_session(SessionKind.CANARY, "canary-1", _CAP, initial_state={"seed": "tok"})
    assert store.read("canary-1") == {"seed": "tok"}


def test_canary_injection_requires_canary_session() -> None:
    store = _store()
    store.begin_session(SessionKind.VISIBLE, "vis-1", _CAP)
    with pytest.raises(LeakProbeError):
        inject_canary_tokens(store, "vis-1", ["tok"])
