"""R2b acceptance tests — the model-call audit transcript and the
non-adaptive search arm, pinned."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import json

from rsicontext.participant.recuris_real_arm import (
    R2B_NEUTRAL_SEED,
    RecurisAdaptedImprover,
)

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
        "stage_id",
        "prompt_sha256",
        "prompt_head",
        "ok",
        "reply_head",
        "cause",
        "tokens_in",
        "tokens_out",
    }
    assert entry["stage_kind"] == "survey"
    assert entry["stage_id"] == "s1-survey"
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


def test_fu1_prompt_pins_the_id_format() -> None:
    # The fu1 break was answer FORM: the worker knew the right supplier
    # (notes retained; replies world-following) but replied the display
    # form ('Vesper'/'Orbit') against the exact-match id. The fu1
    # prompt now pins the id format exactly as the award prompt does.
    text = strong_model_fixed_policy_text()
    count = text.count("kebab-case id")
    assert count >= 2  # award + fu1 (any future prompts follow suit)


def test_policy_load_gate_rejects_truncated_policies() -> None:
    # The R2b "no-policy" failure was a mid-string truncation that
    # passed the substring check and failed to compile at runtime.
    # The selection-time gate must reject it.
    from r2a_compare import _policy_loadable

    truncated = 'def on_turn(turn):\n    return {"pack_text": "unterminated'
    assert "def on_turn" in truncated  # the old check would accept it
    assert not _policy_loadable(truncated)
    assert _policy_loadable(strong_model_fixed_policy_text())


def test_four_arm_offline_artifact_shape() -> None:
    # The r2b artifact now carries FIVE cells: the original three arms
    # + the recuris S0-matched control + the recuris_adapted arm (the
    # REAL loop: improver record with rounds, final package, eval run
    # on the LAST package), and the Δ_update_recuris delta against the
    # S0-matched cell (memory evolution, policy form constant).
    import json

    artifact = Path("artifacts/rsi-core-v1/r2b-offline.json")
    if not artifact.exists():
        import subprocess

        subprocess.run(
            [sys.executable, "scripts/r2b_compare.py", "--offline", "--output", str(artifact)],
            check=True, capture_output=True,
        )
    payload = json.loads(artifact.read_text())
    arms = payload["arms"]
    assert set(arms) == {
        "strong_model_fixed",
        "unassisted_update",
        "non_adaptive_search",
        "recuris_s0_matched",
        "recuris_adapted",
    }
    # The S0-matched cell runs the memory-aware policy with the NEUTRAL
    # seed: same decisions as the strong-fixed baseline (nothing
    # smuggled in by the policy form — the control's license).
    s0 = arms["recuris_s0_matched"]["dev"]
    fixed = arms["strong_model_fixed"]["dev"]
    assert s0["decisions"] == fixed["decisions"]
    # The improver's rounds are recorded; when dev passes fully (the
    # offline scripted worker), the rounds BOUNCE ('nothing failed') —
    # the no-repair-target discipline, never a silent accept.
    rounds = arms["recuris_adapted"]["improver_record"]["rounds"]
    assert len(rounds) == 2
    for record in rounds:
        assert record["outcome"].startswith(
            "bounced: nothing failed"
        ), record["outcome"]
    # Δ_update_recuris (vs S0-matched) is reported per decision.
    assert "recuris_update_vs_s0matched_eval" in payload["deltas"]
    assert "per_decision_recuris_update" in payload["deltas"]


def test_canonical_seed_is_stage_compatible() -> None:
    # The canonical r2b seed's rho stages are THIS environment's stage
    # kinds (the simulation's neutral_seed_package uses Recuris's own
    # retrieve/read/verify/synthesize — delivery would never fire).
    from rsicontext.participant.recuris_real_arm import R2B_NEUTRAL_SEED

    stages = R2B_NEUTRAL_SEED["invocation"]["invoked_on_stages"]
    our_kinds = {
        "survey", "constraint_injection", "rule_change", "act_verify", "follow_up",
    }
    assert set(stages) <= our_kinds
    assert "entries" in R2B_NEUTRAL_SEED and "invocation" in R2B_NEUTRAL_SEED


def test_live_mode_requires_key_and_writes_nothing() -> None:
    # The wiring audit's live-skip pin: without SIFLOW_API_KEY the
    # entry exits rc=2 BEFORE any run (the check precedes all arms).
    import os
    import subprocess

    env = dict(os.environ)
    env.pop("SIFLOW_API_KEY", None)
    out = Path("artifacts/rsi-core-v1/tmp-live-skip.json")
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/r2b_compare.py",
            "--output",
            str(out),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert not out.exists()


def test_offline_delta_values_and_cost_ledger() -> None:
    # Value pins (offline-deterministic): all recuris deltas 0; the
    # package never mutates without a repair target; the cost ledger
    # fields exist and the dev cell is the improver's own final run.
    import json

    artifact = Path("artifacts/rsi-core-v1/r2b-offline.json")
    if not artifact.exists():
        import subprocess

        subprocess.run(
            [sys.executable, "scripts/r2b_compare.py", "--offline", "--output", str(artifact)],
            check=True, capture_output=True,
        )
    payload = json.loads(artifact.read_text())
    deltas = payload["deltas"]
    assert deltas["recuris_update_vs_s0matched_eval"] == 0
    assert all(v == 0 for v in deltas["per_decision_recuris_update"].values())
    record = payload["arms"]["recuris_adapted"]["improver_record"]
    assert record["final_package_digest"] == record["rounds"][0]["package_digest_before"]
    assert payload["arms"]["recuris_adapted"]["final_package"]["entries"] == []
    # Cost ledger: per-attempt meta records, internal dev runs, the
    # final incumbent run (the audit's accounting gap).
    assert "meta_attempts" in record and len(record["meta_attempts"]) == 2
    assert "dev_runs_internal" in record and len(record["dev_runs_internal"]) >= 1
    assert "final_incumbent_run" in record
    # The dev cell IS the improver's final incumbent run (no redundant
    # re-run inflating the dev-run column).
    assert (
        payload["arms"]["recuris_adapted"]["dev"]["decisions"]
        == record["final_incumbent_run"]["decisions"]
    )
    # The S0-matched control's eval cell is present (the delta's
    # denominator must be a real run, not a dev-only stand-in).
    assert "eval_mirror" in payload["arms"]["recuris_s0_matched"]
    assert "s0matched_vs_fixed_eval" not in deltas  # not yet declared; see record doc


def test_improver_returns_usage_for_tuple_meta_agents() -> None:
    # The meta-agent may return (content, usage) — the live caller's
    # shape; the improver accumulates tokens and records the attempt.
    def dev_runner(package: dict) -> dict:
        return {
            "decisions": {"award": False, "followup_1": True, "followup_2": True},
            "policy_errors": [],
            "final_state": {"memory_delivered": []},
            "model_calls": 3,
            "model_tokens_in": 900,
            "model_tokens_out": 300,
            "tool_ledger": {"tool_calls": 0},
        }

    def tuple_meta(prompt: str):
        return (
            json.dumps(
                {"clusters": [{"component": "E", "action": "add_card", "target": "c",
                               "card": {"body": "hint", "stage": "*", "requires_field": None},
                               "evidence": ["award"]}]}
            ),
            {"prompt_tokens": 500, "completion_tokens": 120, "finish_reason": "stop"},
        )

    improver = RecurisAdaptedImprover(meta_agent=tuple_meta, dev_runner=dev_runner, rounds=1)
    final, record = improver.improve(json.loads(json.dumps(R2B_NEUTRAL_SEED)))
    assert record["meta_tokens_in"] == 500
    assert record["meta_tokens_out"] == 120
    assert record["meta_attempts"][0]["finish_reason"] == "stop"
    assert record["dev_runs_internal"][0]["model_tokens_in"] == 900
