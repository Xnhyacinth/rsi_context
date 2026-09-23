"""Phase-1 entry-completion acceptance tests (review of ab07c75, 2026-09-23).

One test per acceptance-table row:
- model channel: policy-issued context reaches the model; the reply
  enters the policy's decisions; usage is ledgered.
- intra-stage recovery: a refused action is read (receipt), corrected,
  and re-submitted WITHIN the same stage; the run passes.
- event timing: a synchronous tool verification and an action
  verification at the same logical moment carry the SAME protocol
  revision (the clock advances before the stage's observations).
- historical reread: a survey document is re-readable at a later stage;
  future material is not.
- budget enforcement: caps refuse calls BEFORE execution; refused calls
  still meter; request_verification is charged with unique ids.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

from rsicontext.lifecycle.env import Action


def _run_policy(policy_text, inst=None, responder=None, max_turns=1, budget=None):
    inst = inst or build_research_v3_instance()
    env = ProjectState()
    hook = PolicyHook({}, policy_text, tool_budget=budget or ToolBudget(), responder=responder)
    hook.bind_env(env)
    record = run_lifecycle(inst, hook, env, max_turns_per_stage=max_turns)
    return record, hook, env


# --- 1. model channel ---------------------------------------------------------------


def test_model_channel_is_metered_and_reaches_decisions() -> None:
    seen_prompts: list[str] = []

    def responder(prompt: str) -> str:
        seen_prompts.append(prompt)
        return "model says: choose aurora"

    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        reply = turn.ask_model("Summarize the candidate plans.")
        turn.state["reply_ok"] = reply.ok
        turn.state["reply_head"] = reply.content
    return {"pack_text": "ok"}
"""
    record, hook, _ = _run_policy(policy, responder=responder)
    assert hook.state["reply_ok"] is True
    assert "aurora" in hook.state["reply_head"] or "aurora" in hook.state.get("reply_full", "")
    # The policy-issued context actually reached the model...
    assert any("candidate plans" in p for p in seen_prompts)
    # ...and the usage is ledgered through the SAME budget as tools.
    assert hook.model_calls == 1 and hook.model_tokens_in > 0
    assert hook.tool_budget.calls >= 1


def test_model_channel_failure_is_named() -> None:
    def boom(prompt: str) -> str:
        raise RuntimeError("endpoint down")

    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        reply = turn.ask_model("anything")
        turn.state["cause"] = reply.cause
        turn.state["ok"] = reply.ok
    return {"pack_text": "ok"}
"""
    record, hook, _ = _run_policy(policy, responder=boom)
    assert hook.state["ok"] is False
    assert "endpoint down" in hook.state["cause"]


# --- 2. intra-stage recovery ---------------------------------------------------------


def test_refused_action_is_read_corrected_and_resubmitted_in_stage() -> None:
    policy = """
def on_turn(turn):
    kind = turn.view.kind
    if kind == "act_verify":
        # Turn 1: finalize a record that does NOT exist yet -> the env
        # refuses AT APPLY TIME with a named cause.
        if not turn.state.get("committed"):
            turn.state["committed"] = "attempted"
            return {
                "pack_text": "commit",
                "actions": (
                    turn.actions.finalize(
                        "migration_commit",
                        {"plan": "aurora", "status": "final"},
                        ("nonexistent-ref",),
                    ),
                ),
            }
        # Turn 2: read the refusal receipt, create the record + evidence,
        # and finalize properly.
        if "saw_refusal" not in turn.state:
            refusals = [r for r in turn.receipts if not r.applied]
            turn.state["saw_refusal"] = any(
                "finalize target record" in r.cause for r in refusals
            )
        if turn.state.get("recovered"):
            # Turn 3: the corrected actions were applied; close the stage.
            return {"pack_text": "done"}
        turn.state["recovered"] = True
        acts = (
            turn.actions.request_verification("verif-ok", "replica-lag", "aurora"),
            turn.actions.request_verification("verif-ok2", "online-cutover", "aurora"),
            turn.actions.create_record("candidate_status-aurora", {"plan": "aurora", "domain": "finance"}),
            turn.actions.create_record("migration_commit", {"plan": "aurora"}),
            turn.actions.finalize(
                "migration_commit",
                {"plan": "aurora", "status": "final"},
                ("verif-ok", "verif-ok2", "candidate_status-aurora"),
            ),
        )
        return {"pack_text": "recovered commit", "actions": tuple(acts)}
    return {"pack_text": "ok"}
"""
    record, hook, _ = _run_policy(policy, max_turns=3)
    assert hook.state["saw_refusal"] is True
    assert record.final_check.passed, record.final_check.failures


# --- 3. event timing -----------------------------------------------------------------


def test_sync_tool_and_action_verifications_share_revision() -> None:
    policy = """
def on_turn(turn):
    if turn.view.kind == "rule_change":
        # Synchronous tool call DURING the rule-change stage...
        r = turn.tools.request_verification("replica-lag", "aurora")
        turn.state["sync_verdict"] = r.answer
        # ...and an action verification from the same turn.
        return {
            "pack_text": "both channels",
            "actions": (
                turn.actions.request_verification("act-ver", "replica-lag", "aurora"),
            ),
        }
    return {"pack_text": "ok"}
"""
    record, hook, env = _run_policy(policy)
    # Both records carry the SAME (post-rule-change) revision 2.
    sync = env.records.get("tool-verif-1")
    act = env.records.get("act-ver")
    assert sync is not None and act is not None
    assert sync["protocol_revision"] == 2
    assert act["protocol_revision"] == 2


# --- 4. historical reread ------------------------------------------------------------


def test_reread_resolves_previously_revealed_documents() -> None:
    policy = """
def on_turn(turn):
    if turn.view.kind == "rule_change":
        r = turn.tools.reread("doc-cand-a")
        turn.state["reread_ok"] = r.ok
        turn.state["reread_head"] = r.answer[:30]
        # Future material must refuse.
        f = turn.tools.reread("doc-rule-change") if turn.view.kind == "rule_change" else None
    if turn.view.kind == "act_verify":
        # doc-rule-change WAS revealed by then; doc-cand-d too.
        d = turn.tools.reread("doc-rule-change")
        turn.state["late_reread_ok"] = d.ok
    return {"pack_text": "ok"}
"""
    record, hook, _ = _run_policy(policy)
    assert hook.state["reread_ok"] is True
    assert "Aurora" in hook.state["reread_head"]


def test_document_registry_blocks_future_material() -> None:
    registry = DocumentRegistry()
    inst = build_research_v3_instance()
    survey_docs = inst.stages[0].documents
    registry.reveal(survey_docs)
    # Not yet revealed: the constraint-stage document.
    assert registry.get("doc-cand-a") is not None
    assert registry.get("doc-constraint-k") is None


# --- 5. budget enforcement -----------------------------------------------------------


def test_budget_caps_refuse_before_execution_and_still_meter() -> None:
    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        a = turn.tools.reread("doc-cand-a")
        b = turn.tools.reread("doc-cand-b")
        c = turn.tools.reread("doc-cand-c")
        turn.state["results"] = [a.ok, b.ok, c.ok]
        turn.state["cause"] = c.cause
    return {"pack_text": "ok"}
"""
    budget = ToolBudget(max_calls=2)
    record, hook, _ = _run_policy(policy, budget=budget)
    ok_results = hook.state["results"]
    assert ok_results[:2] == [True, True]
    assert ok_results[2] is False
    assert "call cap 2 reached" in hook.state["cause"]
    # The refused call still meters (a call is a call).
    assert budget.calls == 3


def test_request_verification_is_charged_with_unique_ids() -> None:
    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        turn.tools.reread("doc-cand-a")  # consumes one call slot
        v = turn.tools.request_verification("replica-lag", "aurora")
        turn.state["verdict"] = v.answer
    return {"pack_text": "ok"}
"""
    record, hook, env = _run_policy(policy)
    assert hook.state["verdict"] in ("pass", "fail", "unverifiable")
    # The verification record id is sequential, not colliding with reread's.
    assert "tool-verif-1" in env.records
    assert hook.tool_budget.calls == 2
