"""The multi-SESSION sequence runner (B-group, research-v5).

Design (bgroup agent, 2026-09-23): one session = one run_lifecycle over
one instance; between sessions the hook is DESTROYED and rebuilt from
exactly two survivors — the persistence contract's carry (state['carry']
flushed through SessionStateStore, byte-capped) and the external world
(the DocumentRegistry's revealed set, the per-project ProjectState, the
arm's shared ToolBudget). A refused flush (over-cap / non-canonical) is
a named receipt delivered at the next session's first view; the next
session starts from the LAST SUCCESSFUL flush.

The graded output is the six-decision vector (per the design): each
decision keyed to the gate/derivation that grades it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from rsicontext.lifecycle.env import Action, ProjectState, Receipt
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget
from rsicontext.session.state import canonical_state_bytes, validate_state_bytes
from rsicontext.session.store import SessionKind, SessionStateStore

#: The persistence contract: the ONE state subtree that survives the
#: boundary. Everything else in the hook's working state is destroyed.
CARRY_KEY = "carry"

_SCHEMA: dict[str, object] = {"type": "object"}
_BYTE_CAP = 65536  # configs/budget_v1.json state.byte_cap


@dataclass
class SessionRecord:
    """One session's auditable outcome within the sequence."""

    session_index: int
    instance_id: str
    persist_ok: bool
    persist_cause: str = ""
    carry_bytes: int = 0
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    policy_errors: list[str] = field(default_factory=list)
    actions_applied: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "session_index": self.session_index,
            "instance_id": self.instance_id,
            "persist_ok": self.persist_ok,
            "persist_cause": self.persist_cause,
            "carry_bytes": self.carry_bytes,
            "passed": self.passed,
            "failures": list(self.failures),
            "policy_errors": list(self.policy_errors),
            "actions_applied": self.actions_applied,
        }


@dataclass
class SequenceRecord:
    """The three-session sequence's outcome + the decision vector."""

    sessions: list[SessionRecord] = field(default_factory=list)
    decisions: dict[str, bool] = field(default_factory=dict)
    failure_detail: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "decisions": dict(self.decisions),
            "failure_detail": {k: list(v) for k, v in self.failure_detail.items()},
        }


def run_session_sequence(
    sessions: list[LifecycleInstance],
    hook_factory: Callable[[dict[str, object]], object],
    *,
    envs: list[ProjectState] | None = None,
    budget: ToolBudget | None = None,
    registry: DocumentRegistry | None = None,
    max_turns_per_stage: int = 2,
) -> SequenceRecord:
    """Run the sessions in order with the persistence contract enforced.

    ``hook_factory(state)`` builds a fresh participant for each session
    from the state dict (the caller passes the same factory each time —
    what differs is the STATE: session k>1 starts with
    {'carry': <last successful flush>} only).

    ``envs``: the ProjectState per session. SAME instance = the project
    continues (records, revisions, oracle threaded); a FRESH instance =
    a new project (session 3's misapplication traps). Defaults: one
    fresh env per session.

    ``budget``/``registry``: shared across sessions (the arm's cost
    ledger and the legally-revealed material set persist; the working
    context does not).
    """

    budget = budget if budget is not None else ToolBudget()
    registry = registry if registry is not None else DocumentRegistry()
    store = SessionStateStore(schema=_SCHEMA)
    record = SequenceRecord()
    carry: dict[str, object] = {}

    envs = envs if envs is not None else [ProjectState() for _ in sessions]
    oracle_installed = {id(e) for e in envs}

    for index, inst in enumerate(sessions):
        env = envs[index]
        state: dict[str, object] = {CARRY_KEY: json.loads(json.dumps(carry))}
        hook = hook_factory(state)
        # Bind the session's env on the hook (the tool surface's
        # verification path needs the live ProjectState; the runner
        # installs the oracle per its own begin_instance logic).
        if hasattr(hook, "bind_env"):
            hook.bind_env(env)
        # The session's view of the world: reveal its documents.
        for stage in inst.stages:
            registry.reveal(stage.documents)
        # Install the oracle only once per env (begin_instance resets it).
        if id(env) in oracle_installed:
            oracle_installed.discard(id(env))
        lifecycle_record = run_lifecycle(inst, hook, env, max_turns_per_stage=max_turns_per_stage)
        # The persist flush (harness-side, after the last turn): the
        # carry subtree ONLY, canonical bytes, byte-capped.
        session_id = f"b1-session-{index}"
        persist_ok = True
        persist_cause = ""
        carry_bytes = 0
        candidate = state.get(CARRY_KEY)
        if isinstance(candidate, dict):
            try:
                payload = json.loads(canonical_state_bytes(dict(candidate)))
                blob = canonical_state_bytes(payload)
                carry_bytes = len(blob)
                if carry_bytes > _BYTE_CAP:
                    raise ValueError(f"carry exceeds the {_BYTE_CAP}-byte cap ({carry_bytes})")
                store.begin_session(SessionKind.GATE, session_id, _BYTE_CAP)
                store.write(session_id, payload)
                carry = payload
            except Exception as exc:
                persist_ok = False
                persist_cause = f"{type(exc).__name__}: {exc}"
        record.sessions.append(
            SessionRecord(
                session_index=index,
                instance_id=inst.instance_id,
                persist_ok=persist_ok,
                persist_cause=persist_cause,
                carry_bytes=carry_bytes,
                passed=lifecycle_record.final_check.passed,
                failures=list(lifecycle_record.final_check.failures)[:10],
                policy_errors=getattr(hook, "policy_errors", [])[:8],
                actions_applied=sum(sr.actions_applied for sr in lifecycle_record.stage_records),
            )
        )
    _derive_decisions(record, sessions, envs)
    return record


def _derive_decisions(
    record: SequenceRecord,
    sessions: list[LifecycleInstance],
    envs: list[ProjectState],
) -> None:
    """The six-decision vector, from the sessions' own failure sets."""

    if not record.sessions:
        return
    s1, s2, s3 = (record.sessions + [None, None, None])[:3]

    def _decision(key: str, session: SessionRecord | None, needle: str) -> None:
        failures = session.failures if session else []
        record.decisions[key] = not any(needle in f for f in failures)
        hits = [f for f in failures if needle in f]
        if hits:
            record.failure_detail.setdefault(key, []).extend(hits[:3])

    if s1:
        _decision("s1_award", s1, "commit gate")
    if s2:
        _decision("s2_calibration", s2, "s9-followup-calibration")
        _decision("s2_currency", s2, "s10-followup-currency")
        _decision("s2_reaward_fresh", s2, "commit gate[s11-re-award]")
    if s3:
        _decision("s3_award", s3, "commit gate")
        _decision("s3_calibration", s3, "n6-followup-calibration")


__all__ = ["CARRY_KEY", "SequenceRecord", "SessionRecord", "run_session_sequence"]
