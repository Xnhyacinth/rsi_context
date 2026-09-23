"""R2b acceptance tests — the model-call audit transcript and the
non-adaptive search arm, pinned."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import r2b_compare
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget


def test_model_transcript_records_prompts_and_replies() -> None:
    # The R2a live failure was unexplainable because prompts/replies
    # were not recorded. Now every ask_model call appends an audit
    # record with stage context, prompt digest/head, reply head, ok,
    # and token counts.
    env = ProjectState()
    hook = PolicyHook(
        {},
        strong_model_fixed_policy_text(),
        tool_budget=ToolBudget(),
        responder=lambda prompt: "notes: nothing decisive",
    )
    hook.bind_env(env)
    record = run_lifecycle(build_research_v4_dossier(), hook, env, max_turns_per_stage=2)
    assert len(hook.model_transcript) == hook.model_calls
    assert hook.model_calls > 0
    entry = hook.model_transcript[0]
    assert set(entry) == {
        "stage_kind",
        "prompt_sha256",
        "prompt_head",
        "ok",
        "reply_head",
        "cause",
        "tokens_in",
        "tokens_out",
    }
    assert entry["stage_kind"] == "survey"
    assert entry["ok"] is True
    assert "supplier-selection" in entry["prompt_head"]
    assert entry["reply_head"] == "notes: nothing decisive"


def test_model_transcript_records_failures() -> None:
    def boom(prompt):
        raise RuntimeError("endpoint down")

    env = ProjectState()
    hook = PolicyHook(
        {}, strong_model_fixed_policy_text(), tool_budget=ToolBudget(), responder=boom
    )
    hook.bind_env(env)
    run_lifecycle(build_research_v4_dossier(), hook, env, max_turns_per_stage=2)
    failed = [e for e in hook.model_transcript if not e["ok"]]
    assert failed and "endpoint down" in failed[0]["cause"]
    assert failed[0]["reply_head"] == ""


def test_award_prompt_demands_the_card_id() -> None:
    # Q5 from the live diagnosis: the worker answered with a display
    # name ('Harborline') while the gate checks kebab-case ids. The
    # award prompt must pin the id format (name normalization removed
    # from the failure surface).
    text = strong_model_fixed_policy_text()
    assert "kebab-case id" in text
    assert "Supplier card:" in text


def test_search_rounds_are_independent() -> None:
    # Non-adaptive: each candidate proposal gets the SAME baseline and
    # experience; no candidate sees another's output.
    import inspect

    source = inspect.getsource(r2b_compare._search_candidate_rounds)
    # The loop must NOT pass a prior policy into the round.
    assert "baseline, dev_experience" in source
    assert "NOT fed into the next round" in source
    assert "updated_policy" not in source


def test_declared_selection_rule_is_order_not_score() -> None:
    import inspect

    source = inspect.getsource(r2b_compare.main)
    # The selection rule: first usable candidate with zero policy
    # errors — declared, deterministic, not dev-score or eval based.
    assert 'policy_errors" == []' in source or 'policy_errors"] == []' in source
    assert "first usable" in source or "proposal order" in source
