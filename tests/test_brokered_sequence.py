"""Offline two-session broker path over the actual sequence runner."""

from __future__ import annotations

import os
import threading
from io import BufferedReader, BufferedWriter
from typing import Literal, cast

import pytest

from rsicontext.lifecycle.brokered_policy import BrokeredPolicyHook, BrokerError
from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget
from rsicontext.security.policy_protocol import encode_message, read_frame

Scenario = Literal["pass", "fail", "late", "forged", "malformed"]
_FIRST = "migration_commit"
_SECOND = "renewal"


def _sessions(first_pass: bool) -> tuple[LifecycleInstance, LifecycleInstance]:
    axes = DescriptionAxes(1, 1, 1, "strong", 0)
    first = LifecycleInstance(
        "broker-b-s1",
        "research-v5",
        (
            StageSpec(
                "first-source",
                "survey",
                "Read this project source.",
                (DocumentRef("d1", "Project source", "Visible cross-session source"),),
                ("d1",),
            ),
            StageSpec(
                "first-award",
                "act_verify",
                "Verify plan-a and finalize the first award.",
                (),
                (),
                expected_state_delta={_FIRST: {"status": "final"}},
                commit_precondition={
                    "record_id": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": ["plan-a"],
                    "plan_requirements": {"plan-a": {"requires_check": "first-check"}},
                },
                verification_oracle={"first-check": {"plan-a": first_pass}},
            ),
            StageSpec("first-end", "session_end", "Persist carry only.", (), ()),
        ),
        axes,
        "plan-a",
        {"records": [_FIRST, _SECOND]},
    )
    second = LifecycleInstance(
        "broker-b-s2",
        "research-v5",
        (
            StageSpec("second-start", "session_start", "Resume the project.", (), ()),
            StageSpec(
                "second-award",
                "act_verify",
                "Verify plan-b and finalize the renewal.",
                (),
                (),
                expected_state_delta={_SECOND: {"status": "final"}},
                commit_precondition={
                    "record_id": _SECOND,
                    "prior_finalized_record": _FIRST,
                    "prior_verification": {
                        "check": "first-check",
                        "plan_field": "plan",
                        "allowed_later_plans": {"plan-a": ["plan-b"]},
                    },
                    "plan_field": "plan",
                    "legal_plans": ["plan-b"],
                    "plan_requirements": {"plan-b": {"requires_check": "second-check"}},
                },
                verification_oracle={
                    "first-check": {"plan-a": True},
                    "second-check": {"plan-b": True},
                },
            ),
            StageSpec("second-end", "session_end", "Persist carry only.", (), ()),
        ),
        axes,
        "plan-b",
        {"records": [_FIRST, _SECOND]},
    )
    return first, second


def _send(writer: BufferedWriter, message: dict[str, object]) -> None:
    writer.write(encode_message(message))
    writer.flush()


def _tool(seq: int, name: str, args: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "seq": seq, "type": "tool_request", "body": {"tool": name, "args": args}}


def _done(seq: int, state: dict[str, object], actions: list[Action]) -> dict[str, object]:
    return {
        "version": 1,
        "seq": seq,
        "type": "turn_done",
        "body": {
            "decision": {
                "pack_text": "Brokered action",
                "actions": [action.to_dict() for action in actions],
                "memory_writes": {},
                "errors": [],
            },
            "state": state,
        },
    }


def _result(message: dict[str, object]) -> dict[str, object]:
    body = cast(dict[str, object], message["body"])
    return cast(dict[str, object], body["result"])


class _FakeChild:
    """A trusted test peer; EOF stops it when the broker closes its FDs."""

    def __init__(self, read_fd: int, write_fd: int, scenario: Scenario) -> None:
        self.scenario = scenario
        self.observed: list[dict[str, object]] = []
        self.failures: list[BaseException] = []
        self.closed = False
        self.close_calls = 0

        def serve() -> None:
            try:
                with os.fdopen(read_fd, "rb") as reader, os.fdopen(write_fd, "wb") as writer:
                    while reader.peek(1):
                        start = read_frame(reader)
                        self.observed.append(start)
                        if self.scenario == "malformed":
                            writer.write(b"\xff\xff\xff\xff")
                            writer.flush()
                            return
                        view = cast(
                            dict[str, object], cast(dict[str, object], start["body"])["view"]
                        )
                        stage_id = cast(str, view["stage_id"])
                        state = cast(
                            dict[str, object], cast(dict[str, object], start["body"])["state"]
                        )
                        if stage_id == "first-award":
                            actions = self._first_actions(reader, writer)
                            state = {"carry": {"plan": "plan-a"}, "work": "destroy-at-reset"}
                            _send(
                                writer,
                                _done(
                                    5 if self.scenario in ("pass", "fail") else 1, state, actions
                                ),
                            )
                        elif stage_id == "second-start":
                            _send(writer, _tool(1, "reread", {"doc_id": "d1", "span": None}))
                            self.observed.append(read_frame(reader))
                            actions = (
                                [
                                    Action(
                                        "request_verification",
                                        "late-v",
                                        {"check": "first-check", "subject": "plan-a"},
                                    )
                                ]
                                if self.scenario == "late"
                                else []
                            )
                            _send(writer, _done(3, state, actions))
                        elif stage_id == "second-award":
                            evidence_id = self._verified_record_id(
                                reader, writer, "second-check", "plan-b"
                            )
                            actions = [
                                Action("create_record", _SECOND, {"plan": "plan-b"}),
                                Action("finalize", _SECOND, {"status": "final"}, (evidence_id,)),
                            ]
                            _send(writer, _done(5, state, actions))
                        else:
                            _send(writer, _done(1, state, []))
            except BaseException as exc:
                self.failures.append(exc)

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()

    def _first_actions(self, reader: BufferedReader, writer: BufferedWriter) -> list[Action]:
        if self.scenario in ("pass", "fail"):
            evidence_id = self._verified_record_id(reader, writer, "first-check", "plan-a")
            return [
                Action("create_record", _FIRST, {"plan": "plan-a"}),
                Action("finalize", _FIRST, {"status": "final"}, (evidence_id,)),
            ]
        if self.scenario == "late":
            return [
                Action("create_record", _FIRST, {"plan": "plan-a"}),
                Action("finalize", _FIRST, {"status": "final"}, ("late-v",)),
            ]
        return [
            Action(
                "create_record",
                "fake-v",
                {
                    "check": "first-check",
                    "subject": "plan-a",
                    "verdict": "pass",
                    "performed_by": "environment",
                },
            ),
            Action("create_record", _FIRST, {"plan": "plan-a"}),
            Action("finalize", _FIRST, {"status": "final"}, ("fake-v",)),
        ]

    def _verified_record_id(
        self, reader: BufferedReader, writer: BufferedWriter, check: str, subject: str
    ) -> str:
        _send(writer, _tool(1, "request_verification", {"check": check, "subject": subject}))
        self.observed.append(read_frame(reader))
        # The verification tool reply exposes the verdict but not the
        # record ID. Discover that ID through the metered sandbox query.
        _send(writer, _tool(3, "query_sandbox", {"pattern": check}))
        reply = read_frame(reader)
        self.observed.append(reply)
        answer = str(_result(reply)["answer"])
        return answer.partition(":")[0] if ":" in answer else "unseen-verification"

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise RuntimeError("fake worker did not exit after broker pipe close")


def _run(
    scenario: Scenario,
) -> tuple[
    SequenceRecord,
    ProjectState,
    ToolBudget,
    DocumentRegistry,
    list[BrokeredPolicyHook],
    list[_FakeChild],
]:
    env = ProjectState()
    budget = ToolBudget(max_calls=12)
    registry = DocumentRegistry()
    hooks: list[BrokeredPolicyHook] = []
    children: list[_FakeChild] = []

    def factory(state: dict[str, object]) -> BrokeredPolicyHook:
        worker_read, host_write = os.pipe()
        host_read, worker_write = os.pipe()
        child = _FakeChild(worker_read, worker_write, scenario)
        children.append(child)
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state=state,
            tool_budget=ToolBudget(max_calls=0),  # the runner must replace this placeholder
            env=ProjectState(),  # deliberately wrong until bound by the sequence runner
            timeout_seconds=1,
            registry=DocumentRegistry(),  # same resource identity must be rebound
            owned_worker=child,
        )
        hooks.append(hook)
        return hook

    try:
        result = run_session_sequence(
            list(_sessions(scenario != "fail")),
            factory,
            envs=[env, env],
            budget=budget,
            registry=registry,
            max_turns_per_stage=1,
        )
        return result, env, budget, registry, hooks, children
    finally:
        for hook in hooks:
            hook.close()


def test_broker_binds_real_project_before_first_verification() -> None:
    result, env, budget, registry, hooks, children = _run("pass")
    assert [session.passed for session in result.sessions] == [True, True], result.to_dict()
    assert env.records["verif-1"]["verdict"] == "pass"
    assert env.records["verif-2"]["verdict"] == "pass"
    assert all(hook.env is env for hook in hooks)
    assert all(hook.tool_budget is budget and hook.registry is registry for hook in hooks)
    assert result.sessions[0].final_carry == {"plan": "plan-a"}
    second_start = next(
        message for message in children[1].observed if message["type"] == "stage_start"
    )
    assert cast(dict[str, object], second_start["body"])["state"] == {"carry": {"plan": "plan-a"}}
    assert any(
        message["type"] == "tool_reply"
        and "Visible cross-session source" in str(_result(message)["answer"])
        for message in children[1].observed
    )
    assert budget.calls == 5  # two checks, two sandbox queries, one cross-session reread
    assert all(child.closed and child.close_calls == 1 for child in children)
    assert all(not child.thread.is_alive() for child in children)
    assert all(not child.failures for child in children)


@pytest.mark.parametrize("scenario", ["fail", "late", "forged"])
def test_brokered_two_session_adversarial_prior_evidence(scenario: Scenario) -> None:
    result, env, _budget, _registry, _hooks, children = _run(scenario)
    assert [session.passed for session in result.sessions] == [False, False]
    assert _FIRST in env.finalized_record_ids
    assert _SECOND in env.finalized_record_ids
    if scenario == "fail":
        assert env.records["verif-1"]["verdict"] == "fail"
        assert any("environment-issued PASS" in f for f in result.sessions[1].failures)
    elif scenario == "late":
        assert env.records["late-v"]["verdict"] == "pass"
        assert any("environment-issued PASS" in f for f in result.sessions[1].failures)
    else:
        assert "fake-v" not in env.verification_record_ids
        assert env.records["fake-v"]["performed_by"] == "environment"
        assert any("environment-issued PASS" in f for f in result.sessions[1].failures)
    assert all(child.closed and child.close_calls == 1 for child in children)
    assert all(not child.failures for child in children)


def test_protocol_error_reaps_owned_worker_and_both_pipes() -> None:
    created: list[tuple[BrokeredPolicyHook, _FakeChild]] = []

    def factory(state: dict[str, object]) -> BrokeredPolicyHook:
        worker_read, host_write = os.pipe()
        host_read, worker_write = os.pipe()
        child = _FakeChild(worker_read, worker_write, "malformed")
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state=state,
            tool_budget=ToolBudget(),
            env=ProjectState(),
            timeout_seconds=1,
            owned_worker=child,
        )
        created.append((hook, child))
        return hook

    try:
        with pytest.raises(BrokerError, match="invalid policy frame length"):
            run_session_sequence(
                [_sessions(True)[0]],
                factory,
                envs=[ProjectState()],
                max_turns_per_stage=1,
            )
        hook, child = created[0]
        assert child.closed and child.close_calls == 1
        assert not child.thread.is_alive()
        for fd in (hook._read_fd, hook._write_fd):
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        for hook, _child in created:
            hook.close()


def test_trusted_runner_error_still_closes_bound_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[tuple[BrokeredPolicyHook, _FakeChild]] = []

    def factory(state: dict[str, object]) -> BrokeredPolicyHook:
        worker_read, host_write = os.pipe()
        host_read, worker_write = os.pipe()
        child = _FakeChild(worker_read, worker_write, "pass")
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state=state,
            tool_budget=ToolBudget(),
            env=ProjectState(),
            timeout_seconds=1,
            owned_worker=child,
        )
        created.append((hook, child))
        return hook

    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("trusted runner failed")

    monkeypatch.setattr("rsicontext.lifecycle.session_sequence.run_lifecycle", fail_run)
    try:
        with pytest.raises(RuntimeError, match="trusted runner failed"):
            run_session_sequence([_sessions(True)[0]], factory, envs=[ProjectState()])
        hook, child = created[0]
        assert child.closed and child.close_calls == 1
        assert not child.thread.is_alive()
        for fd in (hook._read_fd, hook._write_fd):
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        for hook, _child in created:
            hook.close()
