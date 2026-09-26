"""Evaluator-only, offline B/C exercise of an exact jailed policy snapshot.

This module does not request researcher or worker models. A caller supplies an
offline target responder; delegation has no runner, so no auxiliary model can
be dispatched through this path. A separate trusted-host and provider gate is
still required before any live researcher experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from rsicontext.experiment.brokered_researcher_pretest import stage_audited_snapshot
from rsicontext.lifecycle.brokered_policy import BrokeredPolicyHook, MeteredModelReply
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget
from rsicontext.security.policy_jail import StagedPolicyJail, launch_policy_jail

ExerciseStatus = Literal["completed", "usage-unverified", "failed"]


@dataclass(frozen=True, slots=True)
class TargetCall:
    session_index: int
    stage_id: str
    ok: bool
    usage_source: Literal["provider", "estimated", "unknown"]
    charged_tokens_in: int
    charged_tokens_out: int
    provider_tokens_in: int | None
    provider_tokens_out: int | None


@dataclass(frozen=True, slots=True)
class ExerciseResult:
    """Private evaluator result; never show ``sequence`` to the researcher."""

    status: ExerciseStatus
    candidate_sha256: str
    task_sha256: str
    initial_environment_sha256: str
    jail_manifest_sha256: tuple[str, ...]
    sequence: SequenceRecord | None
    target_calls: tuple[TargetCall, ...]
    target_provider_tokens_in: int | None
    target_provider_tokens_out: int | None
    auxiliary_calls: int
    auxiliary_attempts_refused: int
    tool_ledger: dict[str, int | None]
    error_type: str | None = None
    live_ready: bool = False


def _canonical_sha256(value: object) -> str:
    material = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _task_sha256(sessions: list[LifecycleInstance]) -> str:
    return _canonical_sha256([session.to_dict() for session in sessions])


def _environment_sha256(envs: list[ProjectState]) -> str:
    """Bind initial records and whether successive sessions share a project."""

    return _canonical_sha256(
        [
            {
                "shared_with_session": next(i for i, other in enumerate(envs) if other is env),
                "records": env.snapshot(),
                "transcript": [action.to_dict() for action in env.transcript],
                "protocol_revision": env.protocol_revision,
                "check_revisions": env.check_revisions,
                "verification_record_ids": sorted(env.verification_record_ids),
                "finalized_record_ids": sorted(env.finalized_record_ids),
                "pending_receipts": [receipt.to_dict() for receipt in env.pending_receipts],
            }
            for env in envs
        ]
    )


def _target_calls(hooks: list[BrokeredPolicyHook]) -> tuple[TargetCall, ...]:
    calls: list[TargetCall] = []
    for session_index, hook in enumerate(hooks):
        if len(hook.model_transcript) != hook.model_calls:
            raise RuntimeError("broker target-call transcript is incomplete")
        for row in hook.model_transcript:
            source = cast(Literal["provider", "estimated", "unknown"], row["usage_source"])
            calls.append(
                TargetCall(
                    session_index=session_index,
                    stage_id=cast(str, row["stage_id"]),
                    ok=cast(bool, row["ok"]),
                    usage_source=source,
                    charged_tokens_in=cast(int, row["tokens_in"]),
                    charged_tokens_out=cast(int, row["tokens_out"]),
                    provider_tokens_in=(
                        cast(int, row["adapter_tokens_in"]) if source == "provider" else None
                    ),
                    provider_tokens_out=(
                        cast(int, row["tokens_out"]) if source == "provider" else None
                    ),
                )
            )
    return tuple(calls)


def _redacted_responder(
    responder: Callable[[str], MeteredModelReply],
) -> Callable[[str], MeteredModelReply]:
    """Keep adapter exceptions and failure bodies out of candidate observations."""

    def call(prompt: str) -> MeteredModelReply:
        try:
            reply = responder(prompt)
        except Exception:
            return MeteredModelReply(ok=False, cause="target model unavailable")
        if not isinstance(reply, MeteredModelReply):
            return MeteredModelReply(ok=False, cause="target model unavailable")
        return MeteredModelReply(
            ok=reply.ok,
            content=reply.content if reply.ok else "",
            cause="" if reply.ok else "target model unavailable",
            tokens_in=reply.tokens_in,
            tokens_out=reply.tokens_out,
            usage_source=reply.usage_source,
        )

    return call


def _launch_hook(
    artifact: StagedPolicyJail,
    state: dict[str, object],
    *,
    budget: ToolBudget,
    registry: DocumentRegistry,
    responder: Callable[[str], MeteredModelReply],
    timeout_seconds: float,
) -> BrokeredPolicyHook:
    child_read = host_write = host_read = child_write = -1
    worker = None
    try:
        child_read, host_write = os.pipe()
        host_read, child_write = os.pipe()
        worker = launch_policy_jail(artifact, read_fd=child_read, write_fd=child_write)
        os.close(child_read)
        os.close(child_write)
        child_read = child_write = -1
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state=state,
            tool_budget=budget,
            env=ProjectState(),  # run_session_sequence binds the actual evaluator state
            registry=registry,
            responder=responder,
            delegate_runner=None,
            timeout_seconds=timeout_seconds,
            owned_worker=worker,
        )
        host_read = host_write = -1
        worker = None
        return hook
    finally:
        for fd in (child_read, child_write, host_read, host_write):
            if fd >= 0:
                with suppress(OSError):
                    os.close(fd)
        if worker is not None:
            worker.close()


def exercise_candidate_sequence(
    *,
    candidate_root: Path,
    expected_policy_sha256: str,
    jail_parent: Path,
    python_executable: Path,
    expected_python_sha256: str,
    sessions: list[LifecycleInstance],
    envs: list[ProjectState],
    budget: ToolBudget,
    target_responder: Callable[[str], MeteredModelReply],
    decision_rules: Callable[[SequenceRecord, list[LifecycleInstance]], None],
    max_turns_per_stage: int = 2,
    timeout_seconds: float = 5,
) -> ExerciseResult:
    """Stage all exact snapshots before launch, then use the real B/C runner.

    The caller owns the immutable sessions, environment, and jail-parent
    lifecycle. Staging failure raises before any candidate is launched. A
    broker/runner failure returns ``failed`` with the calls observed so far.
    """

    if not sessions or len(envs) != len(sessions):
        raise ValueError("nonempty sessions and one evaluator environment per session required")
    if any(not isinstance(env, ProjectState) for env in envs):
        raise TypeError("each evaluator environment must be ProjectState")
    if any(session.family != "research-v5" for session in sessions):
        raise ValueError("brokered B/C exercise requires research-v5 sessions")
    if (
        type(budget.max_calls) is not int
        or budget.max_calls < 1
        or type(budget.max_tokens) is not int
        or budget.max_tokens < 1
    ):
        raise ValueError("brokered B/C exercise requires positive call and token caps")
    if budget.calls or budget.tokens_in or budget.tokens_out or budget.receipts:
        raise ValueError("brokered B/C exercise requires a fresh tool budget")
    if type(max_turns_per_stage) is not int or not 1 <= max_turns_per_stage <= 8:
        raise ValueError("max_turns_per_stage must be between 1 and 8")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    if not callable(target_responder):
        raise TypeError("target_responder must be callable")
    if not callable(decision_rules):
        raise TypeError("evaluator-owned decision_rules must be callable")

    task_sha = _task_sha256(sessions)
    initial_environment_sha = _environment_sha256(envs)
    artifacts = [
        stage_audited_snapshot(
            candidate_root,
            expected_policy_sha256=expected_policy_sha256,
            jail_root=jail_parent / f"session-{index:02d}",
            python_executable=python_executable,
            expected_python_sha256=expected_python_sha256,
        )
        for index in range(len(sessions))
    ]
    if any(artifact.policy_sha256 != expected_policy_sha256 for artifact in artifacts):
        raise RuntimeError("staged session policy differs from candidate")

    registry = DocumentRegistry()
    hooks: list[BrokeredPolicyHook] = []
    safe_responder = _redacted_responder(target_responder)

    def factory(state: dict[str, object]) -> BrokeredPolicyHook:
        artifact = artifacts[len(hooks)]
        hook = _launch_hook(
            artifact,
            state,
            budget=budget,
            registry=registry,
            responder=safe_responder,
            timeout_seconds=timeout_seconds,
        )
        hooks.append(hook)
        return hook

    sequence: SequenceRecord | None = None
    error_type: str | None = None
    try:
        sequence = run_session_sequence(
            sessions,
            factory,
            envs=envs,
            budget=budget,
            registry=registry,
            max_turns_per_stage=max_turns_per_stage,
            decision_rules=decision_rules,
        )
    except Exception as exc:
        error_type = type(exc).__name__
    calls = _target_calls(hooks)
    provider_complete = all(call.usage_source == "provider" for call in calls)
    if task_sha != _task_sha256(sessions):
        raise RuntimeError("evaluator task material changed during candidate exercise")
    status: ExerciseStatus = (
        "failed" if error_type else "completed" if provider_complete else "usage-unverified"
    )
    return ExerciseResult(
        status=status,
        candidate_sha256=expected_policy_sha256,
        task_sha256=task_sha,
        initial_environment_sha256=initial_environment_sha,
        jail_manifest_sha256=tuple(artifact.manifest_sha256 for artifact in artifacts),
        sequence=sequence,
        target_calls=calls,
        target_provider_tokens_in=(
            sum(cast(int, call.provider_tokens_in) for call in calls) if provider_complete else None
        ),
        target_provider_tokens_out=(
            sum(cast(int, call.provider_tokens_out) for call in calls)
            if provider_complete
            else None
        ),
        auxiliary_calls=0,
        auxiliary_attempts_refused=sum(
            receipt.tool == "delegate" and not receipt.ok for receipt in budget.receipts
        ),
        tool_ledger=budget.ledger(),
        error_type=error_type,
    )
