"""Offline trusted-pipe checks for the parent policy broker."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from io import BufferedReader, BufferedWriter
from typing import Any, cast

import pytest

from rsicontext.lifecycle.brokered_policy import BrokeredPolicyHook, BrokerError, MeteredModelReply
from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.runner import StageView
from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef
from rsicontext.lifecycle.tools import ToolBudget, ToolSurface
from rsicontext.security.policy_protocol import encode_message, read_frame


def _stage(stage_id: str = "s1") -> StageView:
    return StageView(
        stage_id=stage_id,
        kind="survey",
        prompt_text="Use the visible card.",
        documents=(DocumentRef(doc_id="d1", title="Card", text="Visible evidence"),),
        axes=DescriptionAxes(
            information_scale_tokens=100,
            dependency_distance_stages=1,
            persistence_span_resets=0,
            action_dependency="strong",
            environment_changes=0,
        ),
        remaining_budget=2,
    )


def _send(writer: BufferedWriter, message: dict[str, object]) -> None:
    writer.write(encode_message(message))
    writer.flush()


def _result(message: dict[str, object]) -> dict[str, object]:
    body = cast(dict[str, object], message["body"])
    return cast(dict[str, object], body["result"])


def _request(seq: int, tool: str, args: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "seq": seq, "type": "tool_request", "body": {"tool": tool, "args": args}}


def _done(
    seq: int, *, state: dict[str, object], actions: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "version": 1,
        "seq": seq,
        "type": "turn_done",
        "body": {
            "decision": {
                "pack_text": "[[doc:d1]] Visible evidence",
                "actions": [] if actions is None else actions,
                "memory_writes": {"seen": state["seen"]} if "seen" in state else {},
                "errors": [],
            },
            "state": state,
        },
    }


def _peer(
    script: Callable[[BufferedReader, BufferedWriter], None],
    *,
    budget: ToolBudget | None = None,
    responder: Callable[[str], MeteredModelReply] | None = None,
    timeout: float = 1.0,
) -> tuple[BrokeredPolicyHook, threading.Thread, list[BaseException]]:
    worker_read, host_write = os.pipe()
    host_read, worker_write = os.pipe()
    failures: list[BaseException] = []

    def run() -> None:
        try:
            with os.fdopen(worker_read, "rb") as reader, os.fdopen(worker_write, "wb") as writer:
                script(reader, writer)
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    hook = BrokeredPolicyHook(
        read_fd=host_read,
        write_fd=host_write,
        state={},
        tool_budget=budget if budget is not None else ToolBudget(max_calls=8),
        env=ProjectState(),
        timeout_seconds=timeout,
        responder=responder,
    )
    return hook, thread, failures


def _finish(
    hook: BrokeredPolicyHook, thread: threading.Thread, failures: list[BaseException]
) -> None:
    hook.close()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not failures


def test_visible_projection_tool_equivalence_and_long_lived_state() -> None:
    observed: list[dict[str, Any]] = []

    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        for index in range(2):
            start = read_frame(reader)
            assert start["type"] == "stage_start"
            assert start["seq"] == 0
            observed.append(start)
            _send(writer, _request(1, "reread", {"doc_id": "d1", "span": None}))
            reply = read_frame(reader)
            assert reply["seq"] == 2
            assert _result(reply)["answer"] == "Visible evidence"
            action = Action(
                kind="create_record",
                record_id=f"r{index}",
                fields={"answer": "visible"},
            )
            _send(
                writer,
                _done(
                    3,
                    state={"seen": index + 1},
                    actions=[action.to_dict()],
                ),
            )

    budget = ToolBudget(max_calls=8)
    hook, thread, failures = _peer(worker, budget=budget)
    try:
        first = hook.on_stage(_stage())
        second = hook.on_stage(_stage("s2"))
        assert first.actions[0].record_id == "r0"
        assert second.actions[0].record_id == "r1"
        assert hook.state == {"seen": 2}
        assert budget.calls == 2
        direct = ToolSurface(documents=_stage().documents, env=ProjectState(), budget=ToolBudget())
        assert budget.receipts[0].answer == direct.reread("d1").answer
        view = observed[0]["body"]["view"]
        assert set(view) == {
            "stage_id",
            "kind",
            "prompt_text",
            "documents",
            "axes",
            "remaining_budget",
            "receipts",
        }
        assert observed[1]["body"]["state"] == {"seen": 1}
    finally:
        _finish(hook, thread, failures)


def test_overbudget_model_request_is_refused_without_dispatch() -> None:
    result: dict[str, object] = {}

    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(1, "ask_model", {"prompt": "Explain this"}))
        result.update(_result(read_frame(reader)))
        _send(writer, _done(3, state={}))

    calls: list[str] = []

    def responder(prompt: str) -> MeteredModelReply:
        calls.append(prompt)
        return MeteredModelReply(ok=True, content="should not run", tokens_in=2, tokens_out=3)

    budget = ToolBudget(max_calls=0)
    hook, thread, failures = _peer(worker, budget=budget, responder=responder)
    try:
        hook.on_stage(_stage())
        assert not calls
        assert result["ok"] is False
        assert "call cap" in str(result["cause"])
        assert budget.calls == 1
        assert budget.receipts[-1].tool == "ask_model"
    finally:
        _finish(hook, thread, failures)


def test_provider_usage_is_separate_from_local_budget_charge() -> None:
    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(1, "ask_model", {"prompt": "Explain this"}))
        reply = read_frame(reader)
        assert _result(reply)["answer"] == "Answer"
        _send(writer, _done(3, state={}))

    hook, thread, failures = _peer(
        worker,
        responder=lambda _prompt: MeteredModelReply(
            ok=True, content="Answer", tokens_in=7, tokens_out=4, usage_source="provider"
        ),
    )
    try:
        hook.on_stage(_stage())
        assert hook.tool_budget.ledger()["tool_tokens_in"] == 7
        assert hook.provider_tokens_in == 7
        assert hook.provider_tokens_out == 4
        assert hook.model_transcript[0]["usage_source"] == "provider"
    finally:
        _finish(hook, thread, failures)


def test_verification_actions_are_rebuilt_and_budget_gated() -> None:
    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        actions = [
            Action(
                kind="request_verification",
                record_id=record_id,
                fields={"check": "eligibility", "subject": "plan-a"},
            ).to_dict()
            for record_id in ("v1", "v2")
        ]
        _send(writer, _done(1, state={"seen": 1}, actions=actions))

    budget = ToolBudget(max_calls=1)
    hook, thread, failures = _peer(worker, budget=budget)
    try:
        result = hook.on_stage(_stage())
        assert [action.record_id for action in result.actions] == ["v1"]
        assert hook.state == {"seen": 1}
        assert budget.calls == 2
        assert any("action dropped" in error for error in hook.policy_errors)
    finally:
        _finish(hook, thread, failures)


def test_model_failure_keeps_unknown_usage_separate_from_provider_counts() -> None:
    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(1, "ask_model", {"prompt": "Explain this"}))
        reply = read_frame(reader)
        assert _result(reply)["ok"] is False
        _send(writer, _done(3, state={}))

    def fail(_prompt: str) -> MeteredModelReply:
        raise RuntimeError("transport failed")

    hook, thread, failures = _peer(worker, responder=fail)
    try:
        hook.on_stage(_stage())
        assert hook.tool_budget.calls == 1
        assert hook.tool_budget.tokens_in == 2  # local input estimate, not provider usage
        assert hook.provider_tokens_in == 0
        assert hook.model_transcript[0]["usage_source"] == "unknown"
    finally:
        _finish(hook, thread, failures)


def test_unknown_usage_reply_still_charges_local_input_estimate() -> None:
    observed: dict[str, object] = {}

    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(1, "ask_model", {"prompt": "Explain this"}))
        observed.update(_result(read_frame(reader)))
        _send(writer, _done(3, state={}))

    hook, thread, failures = _peer(
        worker,
        responder=lambda _prompt: MeteredModelReply(
            ok=False, cause="provider did not report usage", usage_source="unknown"
        ),
    )
    try:
        hook.on_stage(_stage())
        assert hook.tool_budget.calls == 1
        assert hook.tool_budget.tokens_in == 2
        assert observed["tokens_in"] == 2
        assert hook.provider_tokens_in == 0
        assert hook.model_transcript[0]["adapter_tokens_in"] == 0
        assert hook.model_transcript[0]["usage_source"] == "unknown"
    finally:
        _finish(hook, thread, failures)


def test_query_and_verification_route_through_environment() -> None:
    observations: list[dict[str, object]] = []

    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(1, "query_sandbox", {"pattern": "plan-a"}))
        observations.append(_result(read_frame(reader)))
        _send(
            writer,
            _request(3, "request_verification", {"check": "eligibility", "subject": "plan-a"}),
        )
        observations.append(_result(read_frame(reader)))
        _send(writer, _done(5, state={}))

    hook, thread, failures = _peer(worker)
    hook.env.begin_instance({"eligibility": {"plan-a": True}})
    hook.env.submit(Action(kind="create_record", record_id="plan-a", fields={"plan": "plan-a"}))
    try:
        hook.on_stage(_stage())
        assert "plan-a" in str(observations[0]["answer"])
        assert observations[1]["ok"] is True
        assert observations[1]["answer"] == "pass"
        assert hook.tool_budget.calls == 2
    finally:
        _finish(hook, thread, failures)


def test_oversized_header_poison_does_not_update_state() -> None:
    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        writer.write(b"\xff\xff\xff\xff")
        writer.flush()

    hook, thread, failures = _peer(worker)
    try:
        with pytest.raises(BrokerError, match="invalid policy frame length"):
            hook.on_stage(_stage())
        assert hook.state == {}
        with pytest.raises(BrokerError, match="closed"):
            hook.on_stage(_stage("s2"))
    finally:
        _finish(hook, thread, failures)


def test_wrong_sequence_poison_closes_hook() -> None:
    def worker(reader: BufferedReader, writer: BufferedWriter) -> None:
        read_frame(reader)
        _send(writer, _request(2, "reread", {"doc_id": "d1", "span": None}))

    hook, thread, failures = _peer(worker)
    try:
        with pytest.raises(BrokerError, match="wrong message sequence"):
            hook.on_stage(_stage())
        with pytest.raises(BrokerError, match="closed"):
            hook.on_stage(_stage("s2"))
        assert hook.policy_errors
    finally:
        _finish(hook, thread, failures)


def test_silent_worker_deadline_poison() -> None:
    def worker(reader: BufferedReader, _writer: BufferedWriter) -> None:
        read_frame(reader)
        time.sleep(0.15)

    hook, thread, failures = _peer(worker, timeout=0.03)
    try:
        with pytest.raises(BrokerError, match="deadline exceeded"):
            hook.on_stage(_stage())
        with pytest.raises(BrokerError, match="closed"):
            hook.on_stage(_stage("s2"))
    finally:
        _finish(hook, thread, failures)
