"""Offline candidate exercise contracts; no model provider or candidate process."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Literal, TypedDict, cast

import pytest

from rsicontext.experiment import brokered_researcher_exercise as exercise
from rsicontext.lifecycle.brokered_policy import MeteredModelReply
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.session_sequence import SequenceRecord
from rsicontext.lifecycle.spec import DescriptionAxes, LifecycleInstance, StageSpec
from rsicontext.lifecycle.tools import ToolBudget
from rsicontext.security.policy_jail import JailSetupError, StagedPolicyJail
from rsicontext.security.policy_protocol import encode_message, read_frame

_POLICY = b"def on_turn(turn):\n    return {'pack_text': '', 'actions': ()}\n"
_POLICY_SHA = hashlib.sha256(_POLICY).hexdigest()
_PYTHON_SHA = "a" * 64


class _Inputs(TypedDict):
    candidate_root: Path
    expected_policy_sha256: str
    jail_parent: Path
    python_executable: Path
    expected_python_sha256: str
    sessions: list[LifecycleInstance]
    envs: list[ProjectState]
    budget: ToolBudget
    decision_rules: Callable[[SequenceRecord, list[LifecycleInstance]], None]


def _sessions() -> list[LifecycleInstance]:
    axes = DescriptionAxes(1, 1, 1, "strong", 0)
    return [
        LifecycleInstance(
            f"exercise-s{index}",
            "research-v5",
            (StageSpec(f"decision-{index}", "act_verify", "Choose.", (), (), {}),),
            axes,
            "answer",
            {},
        )
        for index in range(2)
    ]


def _decisions(record: SequenceRecord, _sessions: list[LifecycleInstance]) -> None:
    record.decisions.update(
        {f"decision-{index}": session.passed for index, session in enumerate(record.sessions)}
    )


def _inputs(tmp_path: Path) -> _Inputs:
    return {
        "candidate_root": tmp_path / "candidate",
        "expected_policy_sha256": _POLICY_SHA,
        "jail_parent": tmp_path / "jails",
        "python_executable": Path("/trusted/python3.12"),
        "expected_python_sha256": _PYTHON_SHA,
        "sessions": _sessions(),
        "envs": [ProjectState(), ProjectState()],
        "budget": ToolBudget(max_calls=8, max_tokens=512),
        "decision_rules": _decisions,
    }


class _TrustedFakeWorker:
    """Trusted protocol peer in a thread; it never reads candidate bytes."""

    def __init__(self, read_fd: int, write_fd: int, *, ask: bool) -> None:
        self.read_fd = os.dup(read_fd)
        self.write_fd = os.dup(write_fd)
        self.ask = ask
        self.observed: list[dict[str, object]] = []
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        try:
            with os.fdopen(self.read_fd, "rb") as reader, os.fdopen(self.write_fd, "wb") as writer:
                start = read_frame(reader)
                self.observed.append(start)
                seq = 1
                if self.ask:
                    writer.write(
                        encode_message(
                            {
                                "version": 1,
                                "seq": seq,
                                "type": "tool_request",
                                "body": {
                                    "tool": "ask_model",
                                    "args": {"prompt": "visible question"},
                                },
                            }
                        )
                    )
                    writer.flush()
                    self.observed.append(read_frame(reader))
                    seq += 2
                writer.write(
                    encode_message(
                        {
                            "version": 1,
                            "seq": seq,
                            "type": "tool_request",
                            "body": {"tool": "delegate", "args": {"query": "aux", "doc_ids": []}},
                        }
                    )
                )
                writer.flush()
                self.observed.append(read_frame(reader))
                seq += 2
                body = cast(dict[str, object], start["body"])
                writer.write(
                    encode_message(
                        {
                            "version": 1,
                            "seq": seq,
                            "type": "turn_done",
                            "body": {
                                "decision": {
                                    "pack_text": "observed",
                                    "actions": [],
                                    "memory_writes": {},
                                    "errors": [],
                                },
                                "state": body["state"],
                            },
                        }
                    )
                )
                writer.flush()
        except BaseException as exc:
            self.error = exc

    def close(self) -> None:
        self.thread.join(timeout=2)
        assert not self.thread.is_alive()
        if self.error is not None:
            raise self.error


@pytest.mark.parametrize(
    ("usage_source", "expected_status"),
    [("provider", "completed"), ("unknown", "usage-unverified")],
)
def test_all_sessions_stage_before_any_launch_and_meter_each_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    usage_source: Literal["provider", "unknown"],
    expected_status: str,
) -> None:
    staged: list[Path] = []
    launched: list[_TrustedFakeWorker] = []

    def fake_stage(candidate_root: Path, *, jail_root: Path, **kwargs: object) -> StagedPolicyJail:
        assert candidate_root == tmp_path / "candidate"
        assert kwargs["expected_policy_sha256"] == _POLICY_SHA
        staged.append(jail_root)
        return StagedPolicyJail(jail_root, _POLICY_SHA, f"{len(staged):064x}")

    def fake_launch(
        artifact: StagedPolicyJail, *, read_fd: int, write_fd: int
    ) -> _TrustedFakeWorker:
        assert len(staged) == 2
        assert artifact.root == staged[len(launched)]
        worker = _TrustedFakeWorker(read_fd, write_fd, ask=True)
        launched.append(worker)
        return worker

    monkeypatch.setattr(exercise, "stage_audited_snapshot", fake_stage)
    monkeypatch.setattr(exercise, "launch_policy_jail", fake_launch)
    calls: list[str] = []

    def responder(prompt: str) -> MeteredModelReply:
        calls.append(prompt)
        return MeteredModelReply(
            ok=True, content="answer", tokens_in=7, tokens_out=3, usage_source=usage_source
        )

    result = exercise.exercise_candidate_sequence(**_inputs(tmp_path), target_responder=responder)
    assert result.status == expected_status
    assert result.live_ready is False
    assert result.sequence is not None
    assert len(result.sequence.sessions) == 2
    assert len(result.target_calls) == 2
    assert result.target_provider_tokens_in == (14 if usage_source == "provider" else None)
    assert result.target_provider_tokens_out == (6 if usage_source == "provider" else None)
    assert result.auxiliary_calls == 0
    assert result.auxiliary_attempts_refused == 2
    assert calls == ["visible question", "visible question"]
    assert [row.session_index for row in result.target_calls] == [0, 1]
    assert all(worker.error is None for worker in launched)


def test_stage_failure_precedes_every_launch_and_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = 0
    launched = False
    called = False

    def fail_second(*_args: object, **_kwargs: object) -> StagedPolicyJail:
        nonlocal staged
        staged += 1
        if staged == 2:
            raise JailSetupError("non-root-owned path ancestor: /usr/bin")
        return StagedPolicyJail(tmp_path / "first", _POLICY_SHA, "b" * 64)

    def forbidden_launch(*_args: object, **_kwargs: object) -> None:
        nonlocal launched
        launched = True

    def forbidden_responder(_prompt: str) -> MeteredModelReply:
        nonlocal called
        called = True
        return MeteredModelReply(ok=True)

    monkeypatch.setattr(exercise, "stage_audited_snapshot", fail_second)
    monkeypatch.setattr(exercise, "launch_policy_jail", forbidden_launch)
    with pytest.raises(JailSetupError, match="/usr/bin"):
        exercise.exercise_candidate_sequence(
            **_inputs(tmp_path), target_responder=forbidden_responder
        )
    assert staged == 2
    assert not launched and not called


def test_current_host_trust_refusal_precedes_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.geteuid() != 0 or all(
        path.stat().st_uid == 0 for path in (Path("/usr/bin"), Path("/usr/lib"))
    ):
        pytest.skip("current-host trust refusal only applies to non-root-owned /usr paths")
    snapshot = tmp_path / "candidate" / "policy"
    snapshot.mkdir(parents=True)
    (snapshot / "seed.py").write_bytes(_POLICY)
    launched = False

    def forbidden_launch(*_args: object, **_kwargs: object) -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(exercise, "launch_policy_jail", forbidden_launch)
    jail_parent = Path(tempfile.mkdtemp(prefix="r14-broker-jail-", dir="/tmp"))
    os.chmod(jail_parent, 0o755)
    python = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    try:
        args = _inputs(tmp_path)
        args["jail_parent"] = jail_parent
        args["python_executable"] = python
        args["expected_python_sha256"] = hashlib.sha256(python.read_bytes()).hexdigest()
        with pytest.raises(JailSetupError, match="non-root-owned path ancestor"):
            exercise.exercise_candidate_sequence(
                **args, target_responder=lambda _: MeteredModelReply(ok=True)
            )
        assert not any((jail_parent / f"session-{i:02d}").exists() for i in range(2))
    finally:
        shutil.rmtree(jail_parent)
    assert not launched


def test_fresh_budget_required_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = ToolBudget(max_calls=2, max_tokens=20)
    budget.charge(0, 0)
    args = _inputs(tmp_path)
    args["budget"] = budget
    staged = False

    def forbidden_stage(*_args: object, **_kwargs: object) -> None:
        nonlocal staged
        staged = True

    monkeypatch.setattr(exercise, "stage_audited_snapshot", forbidden_stage)
    with pytest.raises(ValueError, match="fresh tool budget"):
        exercise.exercise_candidate_sequence(
            **args, target_responder=lambda _: MeteredModelReply(ok=True)
        )
    assert not staged


def test_missing_decision_rules_refuses_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = False

    def forbidden_stage(*_args: object, **_kwargs: object) -> None:
        nonlocal staged
        staged = True

    monkeypatch.setattr(exercise, "stage_audited_snapshot", forbidden_stage)
    args = _inputs(tmp_path)
    with pytest.raises(TypeError, match="decision_rules"):
        exercise.exercise_candidate_sequence(  # type: ignore[call-arg]
            candidate_root=args["candidate_root"],
            expected_policy_sha256=args["expected_policy_sha256"],
            jail_parent=args["jail_parent"],
            python_executable=args["python_executable"],
            expected_python_sha256=args["expected_python_sha256"],
            sessions=args["sessions"],
            envs=args["envs"],
            budget=args["budget"],
            target_responder=lambda _: MeteredModelReply(ok=True),
        )
    assert not staged


def test_failed_b_c_tasks_use_explicit_decisions_not_legacy_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = 0

    def fake_stage(*_args: object, **_kwargs: object) -> StagedPolicyJail:
        nonlocal staged
        staged += 1
        return StagedPolicyJail(tmp_path / f"jail-{staged}", _POLICY_SHA, f"{staged:064x}")

    def fake_launch(
        _artifact: StagedPolicyJail, *, read_fd: int, write_fd: int
    ) -> _TrustedFakeWorker:
        return _TrustedFakeWorker(read_fd, write_fd, ask=False)

    monkeypatch.setattr(exercise, "stage_audited_snapshot", fake_stage)
    monkeypatch.setattr(exercise, "launch_policy_jail", fake_launch)
    args = _inputs(tmp_path)
    args["sessions"] = [
        replace(
            session,
            stages=(
                replace(session.stages[0], expected_state_delta={"missing": {"status": "final"}}),
            ),
        )
        for session in args["sessions"]
    ]
    result = exercise.exercise_candidate_sequence(
        **args, target_responder=lambda _: MeteredModelReply(ok=True)
    )
    assert result.status == "completed"
    assert result.sequence is not None
    assert [session.passed for session in result.sequence.sessions] == [False, False]
    assert result.sequence.decisions == {"decision-0": False, "decision-1": False}
    assert "s2_calibration" not in result.sequence.decisions
    assert result.target_calls == ()


def test_initial_environment_hash_distinguishes_shared_and_distinct_projects() -> None:
    shared = ProjectState()
    distinct = ProjectState()
    shared_hash = exercise._environment_sha256([shared, shared])
    assert shared_hash != exercise._environment_sha256([shared, distinct])
    shared.records["prior"] = {"status": "final"}
    assert shared_hash != exercise._environment_sha256([shared, shared])


def test_staged_candidate_hash_mismatch_refuses_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = 0
    launched = False

    def wrong_policy(*_args: object, **_kwargs: object) -> StagedPolicyJail:
        nonlocal staged
        staged += 1
        return StagedPolicyJail(tmp_path / f"jail-{staged}", "0" * 64, "b" * 64)

    def forbidden_launch(*_args: object, **_kwargs: object) -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(exercise, "stage_audited_snapshot", wrong_policy)
    monkeypatch.setattr(exercise, "launch_policy_jail", forbidden_launch)
    with pytest.raises(RuntimeError, match="differs from candidate"):
        exercise.exercise_candidate_sequence(
            **_inputs(tmp_path),
            target_responder=lambda _: MeteredModelReply(ok=True),
        )
    assert staged == 2
    assert not launched


def test_later_launch_failure_keeps_prior_target_usage_and_fails_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = 0
    launched = 0

    def fake_stage(*_args: object, **_kwargs: object) -> StagedPolicyJail:
        nonlocal staged
        staged += 1
        return StagedPolicyJail(tmp_path / f"jail-{staged}", _POLICY_SHA, f"{staged:064x}")

    def fail_later_launch(
        _artifact: StagedPolicyJail, *, read_fd: int, write_fd: int
    ) -> _TrustedFakeWorker:
        nonlocal launched
        launched += 1
        if launched == 2:
            raise JailSetupError("later launch failed")
        return _TrustedFakeWorker(read_fd, write_fd, ask=True)

    monkeypatch.setattr(exercise, "stage_audited_snapshot", fake_stage)
    monkeypatch.setattr(exercise, "launch_policy_jail", fail_later_launch)
    result = exercise.exercise_candidate_sequence(
        **_inputs(tmp_path),
        target_responder=lambda _: MeteredModelReply(
            ok=True, content="answer", tokens_in=4, tokens_out=2, usage_source="provider"
        ),
    )
    assert staged == 2 and launched == 2
    assert result.status == "failed"
    assert result.error_type == "JailSetupError"
    assert result.sequence is None
    assert len(result.target_calls) == 1
    assert result.target_provider_tokens_in == 4
    assert result.target_provider_tokens_out == 2
    assert result.live_ready is False


@pytest.mark.parametrize("mode", ["exception", "failed-reply"])
def test_responder_failure_details_do_not_reach_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    staged = 0
    workers: list[_TrustedFakeWorker] = []

    def fake_stage(*_args: object, **_kwargs: object) -> StagedPolicyJail:
        nonlocal staged
        staged += 1
        return StagedPolicyJail(tmp_path / f"jail-{staged}", _POLICY_SHA, f"{staged:064x}")

    def fake_launch(
        _artifact: StagedPolicyJail, *, read_fd: int, write_fd: int
    ) -> _TrustedFakeWorker:
        worker = _TrustedFakeWorker(read_fd, write_fd, ask=True)
        workers.append(worker)
        return worker

    def responder(_prompt: str) -> MeteredModelReply:
        if mode == "exception":
            raise RuntimeError("SIFLOW_API_KEY=secret-in-provider-exception")
        return MeteredModelReply(
            ok=False,
            content="secret-in-provider-body",
            cause="SIFLOW_API_KEY=secret-in-provider-cause",
            tokens_in=5,
            tokens_out=1,
            usage_source="provider",
        )

    monkeypatch.setattr(exercise, "stage_audited_snapshot", fake_stage)
    monkeypatch.setattr(exercise, "launch_policy_jail", fake_launch)
    result = exercise.exercise_candidate_sequence(**_inputs(tmp_path), target_responder=responder)
    assert result.status == ("usage-unverified" if mode == "exception" else "completed")
    assert result.target_provider_tokens_in == (None if mode == "exception" else 10)
    assert len(result.target_calls) == 2
    assert result.sequence is not None
    for secret in (
        "secret-in-provider-exception",
        "secret-in-provider-body",
        "secret-in-provider-cause",
    ):
        assert secret not in str(result.sequence.to_dict())
        assert secret not in str([worker.observed for worker in workers])
    assert all(worker.error is None for worker in workers)
