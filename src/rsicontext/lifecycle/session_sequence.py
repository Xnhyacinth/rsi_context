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

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.runner import ParticipantHook, run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget
from rsicontext.session.state import canonical_state_bytes
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
    # Cost + audit surface (the r3 unified entry's requirement): the
    # model channel's metered usage and the per-call transcript — the
    # same fields _run_arm exports for single lifecycles, so sequence-
    # shaped runs are not second-class in cost accounting or
    # diagnosability.
    model_calls: int = 0
    model_tokens_in: int = 0
    model_tokens_out: int = 0
    model_transcript: list[dict[str, object]] = field(default_factory=list)
    tool_ledger: dict[str, object] | None = None
    # GAP 1 (r3design): the per-session stage records — build_trace_doc
    # iterates them; without them the B/C trace has zero turns.
    stage_records: list[dict[str, object]] = field(default_factory=list)
    # GAP 2: the end-of-session hook state SNAPSHOT — the hook is
    # destroyed at each boundary, so memory_delivered / obs (the gate's
    # fingerprint source and the trace's E_t/o_t) must be captured here.
    final_memory_delivered: list[object] = field(default_factory=list)
    final_obs: list[object] = field(default_factory=list)
    final_carry: dict[str, object] | None = None

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
            "model_calls": self.model_calls,
            "model_tokens_in": self.model_tokens_in,
            "model_tokens_out": self.model_tokens_out,
            "model_transcript": list(self.model_transcript),
            "tool_ledger": self.tool_ledger,
            "stage_records": list(self.stage_records),
            "final_memory_delivered": list(self.final_memory_delivered),
            "final_obs": list(self.final_obs),
            "final_carry": self.final_carry,
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
            "cost": self.cost(),
        }

    def cost(self) -> dict[str, object]:
        """The sequence's aggregated cost ledger (the r3 contract: the
        same accounting shape a single _run_arm run carries)."""

        return {
            "model_calls": sum(s.model_calls for s in self.sessions),
            "model_tokens_in": sum(s.model_tokens_in for s in self.sessions),
            "model_tokens_out": sum(s.model_tokens_out for s in self.sessions),
            "tool_ledger": (self.sessions[-1].tool_ledger if self.sessions else None),
        }


def run_session_sequence(
    sessions: list[LifecycleInstance],
    hook_factory: Callable[[dict[str, object]], ParticipantHook],
    *,
    envs: list[ProjectState] | None = None,
    budget: ToolBudget | None = None,
    registry: DocumentRegistry | None = None,
    max_turns_per_stage: int = 2,
    decision_rules: Callable[[SequenceRecord, list[LifecycleInstance]], None] | None = None,
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
    ledger and the accumulated revealed-material set persist; the
    working context does not). The registry is fed by the RUNNER on
    presentation — each stage's documents are revealed only when that
    stage runs, so a session's LATER material stays unreachable until
    presented (and a session boundary does not pre-reveal the next
    session's docs either).
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
        # Install the oracle only once per env (begin_instance resets it).
        if id(env) in oracle_installed:
            oracle_installed.discard(id(env))
        # The registry is threaded INTO the runner: documents are
        # revealed on PRESENTATION (review 892f1d0 M1) — the pre-reveal
        # loop that ran here made the whole session's future material
        # (later stages' rule changes, follow-ups) rereadable before the
        # session ran. The runner now reveals each stage's documents
        # right before building that stage's view.
        lifecycle_record = run_lifecycle(
            inst,
            hook,
            env,
            max_turns_per_stage=max_turns_per_stage,
            registry=registry,
        )
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
                failures=list(lifecycle_record.final_check.failures),
                policy_errors=getattr(hook, "policy_errors", [])[:8],
                model_calls=getattr(hook, "model_calls", 0),
                model_tokens_in=getattr(hook, "model_tokens_in", 0),
                model_tokens_out=getattr(hook, "model_tokens_out", 0),
                model_transcript=list(getattr(hook, "model_transcript", []) or []),
                tool_ledger=dict(budget.ledger()) if budget else None,
                actions_applied=sum(sr.actions_applied for sr in lifecycle_record.stage_records),
                # GAP 1: the per-session stage records (dict form) — the
                # B/C trace's turn source.
                stage_records=[sr.to_dict() for sr in lifecycle_record.stage_records],
                # GAP 2: the end-of-session hook-state snapshot — captured
                # BEFORE the hook is destroyed at the next boundary.
                final_memory_delivered=list(
                    (getattr(hook, "state", {}) or {}).get("memory_delivered", []) or []
                ),
                final_obs=list((getattr(hook, "state", {}) or {}).get("obs", []) or []),
                final_carry=(
                    dict((getattr(hook, "state", {}) or {}).get("carry", {}) or {})
                    if isinstance((getattr(hook, "state", {}) or {}).get("carry", None), dict)
                    else None
                ),
            )
        )
    if decision_rules is not None:
        decision_rules(record, sessions)
    else:
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
    s1, s2, s3 = [*record.sessions, None, None, None][:3]

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
