"""Pre-registered leak probe: canary injection and gate-side absence check.

Contract status: implements participant-interface-v1.md §State contract
clause 5 (frozen 2026-09-19; benchmark-contract-v2.md §Protocol
semantics "State-boundary contract"): visible-gold canary tokens
injected in a canary session must be absent from all gate-session
state.

``inject_canary_tokens`` plants the tokens in the canary session's
state (the only session kind allowed to hold them). The injection is an
ordinary ledgered write, so it is visible and auditable in that
session's transcript.

``assert_canary_absent`` scans the target session's full state
transcript and its current state bytes for each token and raises
``LeakProbeError`` naming the session, token, and transcript position
on any hit. On a clean pass it returns a ``LeakProbeResult`` — the
probe record the caller attaches to the run manifest
(``state_transcript_ref``-adjacent, contract §Manifest extensions);
manifest persistence itself is not this module's machinery.

Tokens are matched as raw UTF-8 substrings against canonical state
bytes. State blobs are untrusted data, so the probe reads them through
the store's validated accessors rather than trusting cached bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .store import SessionKind, SessionStateStore

_CANARY_KEY = "canary_tokens"


class LeakProbeError(RuntimeError):
    """Raised when a canary token is present in a probed session."""


@dataclass(frozen=True, slots=True)
class LeakProbeResult:
    """One executed leak-probe assertion, attachable to a run manifest."""

    gate_session_id: str
    tokens: tuple[str, ...]
    transcript_entries_scanned: int
    state_bytes_scanned: int


def inject_canary_tokens(
    store: SessionStateStore,
    session_id: str,
    tokens: list[str],
) -> None:
    """Write canary tokens into a canary session's state.

    The session must have begun with kind ``CANARY``; tokens are merged
    into that session's state under the reserved ``canary_tokens`` key
    as an ordinary ledgered write.
    """

    checked = _checked_tokens(tokens)
    if store.session_kind(session_id) is not SessionKind.CANARY:
        raise LeakProbeError(f"canary tokens may only target a canary session: {session_id!r}")
    current = store.read(session_id)
    state: dict[str, object] = dict(current) if current is not None else {}
    existing = state.get(_CANARY_KEY)
    merged: list[str] = list(existing) if isinstance(existing, list) else []
    for token in checked:
        if token not in merged:
            merged.append(token)
    state[_CANARY_KEY] = merged
    store.write(session_id, state)


def assert_canary_absent(
    store: SessionStateStore,
    gate_session_id: str,
    tokens: list[str],
) -> LeakProbeResult:
    """Assert no canary token appears in the target session's state.

    Scans every transcript entry's canonical bytes and the session's
    current state bytes; raises ``LeakProbeError`` with the session,
    token, and position of any hit. Returns the probe record on a clean
    pass.
    """

    checked = _checked_tokens(tokens)
    transcript = store.transcript(gate_session_id)
    state_bytes = 0
    for position, entry in enumerate(transcript):
        if entry.canonical is None:
            continue
        state_bytes += len(entry.canonical)
        for token in checked:
            if token.encode("utf-8") in entry.canonical:
                raise LeakProbeError(
                    f"canary token {token!r} leaked into session {gate_session_id!r} "
                    f"at transcript position {position} (op {entry.op!r})",
                )
    current = store.current_state_bytes(gate_session_id)
    if current is not None:
        state_bytes += len(current)
        for token in checked:
            if token.encode("utf-8") in current:
                raise LeakProbeError(
                    f"canary token {token!r} leaked into current state of session "
                    f"{gate_session_id!r}",
                )
    return LeakProbeResult(
        gate_session_id=gate_session_id,
        tokens=tuple(checked),
        transcript_entries_scanned=len(transcript),
        state_bytes_scanned=state_bytes,
    )


def _checked_tokens(tokens: list[str]) -> list[str]:
    if not isinstance(tokens, list):
        raise TypeError("tokens must be a list of strings")
    for token in tokens:
        if not isinstance(token, str) or not token:
            raise ValueError("tokens must be non-empty strings")
    if not tokens:
        raise ValueError("tokens must not be empty")
    return list(tokens)
