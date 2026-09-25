"""Failed policy model and delegation attempts consume the shared budget."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.spec import DocumentRef
from rsicontext.lifecycle.tools import ToolBudget, ToolSurface


def test_model_exception_consumes_attempt_and_prompt_estimate() -> None:
    attempts: list[str] = []

    def failing_responder(prompt: str) -> str:
        attempts.append(prompt)
        raise RuntimeError("endpoint down")

    budget = ToolBudget(max_calls=1)
    hook = PolicyHook(
        {},
        "def on_turn(turn):\n    return {'pack_text': 'ok'}\n",
        tool_budget=budget,
        responder=failing_responder,
    )
    failed = hook._ask_model("read this evidence")
    refused = hook._ask_model("try again")

    assert attempts == ["read this evidence"]
    assert not failed.ok and "endpoint down" in failed.cause
    assert failed.tokens_in == 3 and failed.tokens_out == 0
    assert not refused.ok and "call cap 1 reached" in refused.cause
    assert hook.model_calls == budget.calls == 1
    assert hook.model_tokens_in == budget.tokens_in == 3
    assert hook.model_tokens_out == budget.tokens_out == 0
    assert len(hook.model_transcript) == 1
    assert hook.model_transcript[0]["ok"] is False
    assert hook.model_transcript[0]["tokens_in"] == 3


@pytest.mark.parametrize("failure", ["no_runner", "no_docs", "runner_error"])
def test_delegate_failure_consumes_attempt_and_refuses_next_call(failure: str) -> None:
    attempts: list[tuple[str, Sequence[str]]] = []

    def failing_runner(query: str, docs: Sequence[str]) -> str:
        attempts.append((query, docs))
        raise RuntimeError("delegate endpoint down")

    budget = ToolBudget(max_calls=1)
    document = DocumentRef(doc_id="seen", title="Seen", text="known fact")
    surface = ToolSurface(
        documents=(document,),
        env=ProjectState(),
        budget=budget,
        delegate_runner=None if failure == "no_runner" else failing_runner,
    )
    doc_ids = ("absent",) if failure == "no_docs" else ("seen",)
    failed = surface.delegate("investigate", doc_ids)
    refused = surface.delegate("retry", ("seen",))

    assert not failed.ok
    if failure == "no_runner":
        assert failed.cause == "no delegate runner installed"
    elif failure == "no_docs":
        assert failed.cause == "no known documents named"
    else:
        assert "delegate endpoint down" in failed.cause
    assert not refused.ok and "call cap 1 reached" in refused.cause
    assert len(attempts) == (1 if failure == "runner_error" else 0)
    assert budget.calls == 2
    assert budget.receipts == [failed, refused]
    assert budget.tokens_in == failed.tokens_in
    assert budget.tokens_out == failed.tokens_out == 0
    if failure == "runner_error":
        assert failed.tokens_in > 0
        assert failed.to_dict()["tokens_in"] == failed.tokens_in
    else:
        assert failed.tokens_in == 0


def test_failed_dispatch_exhausts_token_cap_without_provider_usage() -> None:
    def model_failure(_prompt: str) -> str:
        raise RuntimeError("model unavailable")

    model_budget = ToolBudget(max_tokens=3)
    hook = PolicyHook(
        {},
        "def on_turn(turn):\n    return {'pack_text': 'ok'}\n",
        tool_budget=model_budget,
        responder=model_failure,
    )
    failed_model = hook._ask_model("one two three")
    refused_model = hook._ask_model("retry")
    assert failed_model.tokens_in == 3 and failed_model.tokens_out == 0
    assert "token cap 3 reached" in refused_model.cause
    assert hook.model_calls == model_budget.calls == 1

    def delegate_failure(_query: str, _docs: Sequence[str]) -> str:
        raise RuntimeError("delegate unavailable")

    delegate_budget = ToolBudget(max_tokens=65)
    surface = ToolSurface(
        documents=(DocumentRef(doc_id="seen", title="Seen", text="known fact"),),
        env=ProjectState(),
        budget=delegate_budget,
        delegate_runner=delegate_failure,
    )
    failed_delegate = surface.delegate("investigate", ("seen",))
    refused_delegate = surface.delegate("retry", ("seen",))
    assert failed_delegate.tokens_in == 66 and failed_delegate.tokens_out == 0
    assert "token cap 65 reached" in refused_delegate.cause
    assert delegate_budget.receipts == [failed_delegate, refused_delegate]
    assert delegate_budget.calls == 2


def test_successful_dispatch_still_counts_once() -> None:
    budget = ToolBudget()
    surface = ToolSurface(
        documents=(DocumentRef(doc_id="seen", title="Seen", text="known fact"),),
        env=ProjectState(),
        budget=budget,
        delegate_runner=lambda _query, _docs: "valid finding",
    )
    receipt = surface.delegate("investigate", ("seen",))
    assert receipt.ok and receipt.tokens_in > 0 and receipt.tokens_out > 0
    assert budget.calls == 1
    assert budget.tokens_in == receipt.tokens_in
    assert budget.tokens_out == receipt.tokens_out


def test_malformed_delegate_result_is_named_and_metered() -> None:
    def malformed_runner(_query: str, _docs: Sequence[str]) -> str:
        return cast(str, None)

    budget = ToolBudget(max_calls=1)
    surface = ToolSurface(
        documents=(DocumentRef(doc_id="seen", title="Seen", text="known fact"),),
        env=ProjectState(),
        budget=budget,
        delegate_runner=malformed_runner,
    )
    failed = surface.delegate("investigate", ("seen",))
    refused = surface.delegate("retry", ("seen",))
    assert not failed.ok and "delegate call failed: TypeError" in failed.cause
    assert failed.tokens_in > 0 and failed.tokens_out == 0
    assert "call cap 1 reached" in refused.cause
    assert budget.calls == 2 and budget.receipts == [failed, refused]


@pytest.mark.parametrize(
    "doc_ids",
    [cast(Sequence[str], None), cast(Sequence[str], (["unhashable"],)), "seen"],
)
def test_malformed_delegate_doc_ids_are_named_and_metered(doc_ids: Sequence[str]) -> None:
    budget = ToolBudget(max_calls=1)
    surface = ToolSurface(
        documents=(DocumentRef(doc_id="seen", title="Seen", text="known fact"),),
        env=ProjectState(),
        budget=budget,
        delegate_runner=lambda _query, _docs: "unused",
    )
    failed = surface.delegate("investigate", doc_ids)
    refused = surface.delegate("retry", ("seen",))
    assert not failed.ok and "invalid delegate documents: TypeError" in failed.cause
    assert failed.tokens_in == failed.tokens_out == 0
    assert "call cap 1 reached" in refused.cause
    assert budget.calls == 2 and budget.receipts == [failed, refused]
