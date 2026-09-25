"""Offline equivalence of a staged jailed policy and the trusted parent broker."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.brokered_policy import BrokeredPolicyHook
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageView
from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef
from rsicontext.lifecycle.tools import ToolBudget
from rsicontext.security.policy_jail import (
    JailedPolicyProcess,
    JailSetupError,
    launch_policy_jail,
    stage_policy_jail,
)

_TRUSTED_POLICY = b"""def on_turn(turn):
    receipt = turn.tools.reread("d1")
    turn.state["seen"] = turn.state.get("seen", 0) + 1
    return {"pack_text": turn.documents_text, "actions": (
        turn.actions.create_record("note", {"answer": receipt.answer}),
    )}
"""


def _view() -> StageView:
    return StageView(
        stage_id="offline-stage",
        kind="survey",
        prompt_text="Read the visible evidence.",
        documents=(DocumentRef(doc_id="d1", title="Card", text="Visible evidence"),),
        axes=DescriptionAxes(
            information_scale_tokens=100,
            dependency_distance_stages=1,
            persistence_span_resets=0,
            action_dependency="strong",
            environment_changes=0,
        ),
        remaining_budget=1,
    )


def test_jailed_broker_matches_in_process_trusted_turn() -> None:
    if os.geteuid() != 0:
        pytest.skip("staging the root-owned policy jail requires host root")

    first = _view()
    second = replace(first, stage_id="offline-follow-up", kind="follow_up")
    views = (first, second)
    direct_budget = ToolBudget(max_calls=4)
    direct = PolicyHook(
        {}, _TRUSTED_POLICY.decode("utf-8"), tool_budget=direct_budget, env=ProjectState()
    )
    expected = tuple(direct.on_stage(view) for view in views)

    parent = Path(tempfile.mkdtemp(prefix="rsi-jailed-broker-", dir="/tmp"))
    os.chmod(parent, 0o755)
    child_read, host_write = os.pipe()
    host_read, child_write = os.pipe()
    handle: JailedPolicyProcess | None = None
    hook: BrokeredPolicyHook | None = None
    try:
        python = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
        try:
            artifact = stage_policy_jail(
                parent / "jail",
                _TRUSTED_POLICY,
                python_executable=python,
                expected_python_sha256=hashlib.sha256(python.read_bytes()).hexdigest(),
            )
        except JailSetupError as exc:
            if "path ancestor" in str(exc) or "untrusted runtime or launcher" in str(exc):
                pytest.skip(f"host runtime trust gate: {exc}")
            raise
        handle = launch_policy_jail(artifact, read_fd=child_read, write_fd=child_write)
        os.close(child_read)
        os.close(child_write)
        child_read = child_write = -1
        budget = ToolBudget(max_calls=4)
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state={},
            tool_budget=budget,
            env=ProjectState(),
            timeout_seconds=5,
        )
        host_read = host_write = -1
        actual = tuple(hook.on_stage(view) for view in views)

        assert [response.pack_text for response in actual] == [
            response.pack_text for response in expected
        ]
        assert [[action.to_dict() for action in response.actions] for response in actual] == [
            [action.to_dict() for action in response.actions] for response in expected
        ]
        assert hook.state == direct.state == {"seen": 2}
        assert budget.ledger() == direct_budget.ledger()
        assert [receipt.to_dict() for receipt in budget.receipts] == [
            receipt.to_dict() for receipt in direct_budget.receipts
        ]
        assert hook.model_calls == direct.model_calls == 0
    finally:
        if hook is not None:
            hook.close()
        for fd in (child_read, child_write, host_read, host_write):
            if fd >= 0:
                os.close(fd)
        if handle is not None:
            handle.close()
        shutil.rmtree(parent)
