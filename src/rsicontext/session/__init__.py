"""Session state machine: state-boundary contract for participant state.

Implements the state contract of
``docs/participant-interface-v1.md`` (§State, frozen 2026-09-19) for
Phase B: canonical serialization with load-side re-validation, a
namespaced per-session store with a memory-op ledger, and the
pre-registered leak probe. Status: contract-level module; the lifecycle
runtime wires it into runs.
"""

from .probe import LeakProbeError, LeakProbeResult, assert_canary_absent, inject_canary_tokens
from .state import (
    StateCanonicalizationError,
    StateValidationError,
    canonical_state_bytes,
    state_schema_digest,
    validate_state_bytes,
)
from .store import (
    MemoryOpLedger,
    SessionBoundaryError,
    SessionKind,
    SessionStateError,
    SessionStateStore,
    TranscriptEntry,
)

__all__ = [
    "LeakProbeError",
    "LeakProbeResult",
    "MemoryOpLedger",
    "SessionBoundaryError",
    "SessionKind",
    "SessionStateError",
    "SessionStateStore",
    "StateCanonicalizationError",
    "StateValidationError",
    "TranscriptEntry",
    "assert_canary_absent",
    "canonical_state_bytes",
    "inject_canary_tokens",
    "state_schema_digest",
    "validate_state_bytes",
]
