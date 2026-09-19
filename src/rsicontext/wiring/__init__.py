"""Wiring layer composing the Phase B packages into session-driven runs.

Contract status: implements the wired state-boundary contract (benchmark-
contract-v2.md §Protocol semantics; participant-interface-v1.md §State) by
composing ``session/`` (state machine, store, leak probe) with
``lifecycle/`` (instances, runner) — no protocol of its own is invented
here. ``session_lifecycle`` drives run_lifecycle over a store-backed
session with injected participant state adapters; ``replay`` records and
deterministically replays reader responses, with transcript-equality as
the contract-tests group 3 gate.
"""

from rsicontext.wiring.replay import (
    ReaderCallable,
    ReplayCall,
    ReplayMissError,
    ReplayRecorder,
    replay,
    replay_transcript_equality,
)
from rsicontext.wiring.session_lifecycle import (
    HookFactory,
    LeakProbeError,
    SessionLifecycleRecord,
    SessionPlan,
    StateHookFactory,
    StateLoad,
    StateSave,
    run_gate_session,
    run_leak_probe_then_gate,
    run_session_flow,
    run_visible_session,
)

__all__ = [
    "HookFactory",
    "LeakProbeError",
    "ReaderCallable",
    "ReplayCall",
    "ReplayMissError",
    "ReplayRecorder",
    "SessionLifecycleRecord",
    "SessionPlan",
    "StateHookFactory",
    "StateLoad",
    "StateSave",
    "replay",
    "replay_transcript_equality",
    "run_gate_session",
    "run_leak_probe_then_gate",
    "run_session_flow",
    "run_visible_session",
]
