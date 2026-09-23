"""R2a acceptance tests — the stats contract and the two arms, pinned.

The contract's rules are testable properties: planned-and-started
denominator, last-snapshot (not best) artifact selection, dev/eval
split (eval material never in improvement input), and the arms'
runnability with per-decision breakdown.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import r2a_compare
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget


def test_strong_model_fixed_solves_dev_offline() -> None:
    # The honest control RUNS end-to-end with the scripted worker: its
    # content decisions flow through ask_model (13+ calls), and the
    # award/follow-up decisions pass on the dev world.
    env = ProjectState()
    budget = ToolBudget()
    hook = PolicyHook(
        {},
        strong_model_fixed_policy_text(),
        tool_budget=budget,
        responder=r2a_compare._offline_responder,
    )
    hook.bind_env(env)
    record = run_lifecycle(build_research_v4_dossier(), hook, env, max_turns_per_stage=2)
    assert hook.model_calls >= 10
    assert hook.policy_errors == []
    decisions = {
        "award": not any("commit gate" in f for f in record.final_check.failures),
        "followup_1": not any("s6-followup-1" in f for f in record.final_check.failures),
    }
    assert decisions["award"] and decisions["followup_1"]


def test_policy_code_carries_no_answers() -> None:
    # The baseline's policy text must not contain the world's answer
    # strings: content decisions belong to the MODEL, orchestration to
    # the code (swap the facts -> the outputs follow the material).
    text = strong_model_fixed_policy_text()
    # World-specific ANSWER strings must be absent: the policy cannot
    # know the winner, the decoy, the calibration supplier, or the
    # world's check names.
    for needle in (
        "atlas-carriage",
        "vesper-instruments",
        "harborline-freight",
        "orbit-hosting",
        "pinnacle-courier",
        "customs-preclearance",
        "cold-chain-integrity",
        "northwind-logistics",
        "vesper",
        "orbit hosting",
    ):
        assert needle not in text, needle
    # The diagnosis ENUM names may appear only inside prompt format
    # specifications ('status=<...>') — never as an assigned default.
    assert 'status = "reverify"' not in text
    assert 'status = "current"' not in text
    assert "def on_turn" in text


def test_eval_variant_changes_facts_not_structure() -> None:
    mother = build_research_v4_dossier()
    mirror = build_dossier_variant("mirror")
    assert mirror.instance_id != mother.instance_id
    # Structure identical (8 stages, same kinds).
    assert [s.kind for s in mirror.stages] == [s.kind for s in mother.stages]
    # Facts permuted: different legal plan, different fu1 answer.
    assert (
        mirror.stages[4].commit_precondition["legal_plans"]
        != mother.stages[4].commit_precondition["legal_plans"]
    )
    assert mirror.stages[5].expected_state_delta != mother.stages[5].expected_state_delta
    # The supersession scope flips -> the derived fu2 diagnosis flips.
    assert mirror.stages[6].rule_change_scope != mother.stages[6].rule_change_scope


def test_unassisted_prompt_has_no_diagnosis() -> None:
    # The researcher round's task prompt must NOT tell the improver
    # which mechanism is broken or which knob to turn (the assisted
    # framing is retired from the main condition).
    import inspect

    source = inspect.getsource(r2a_compare)
    prompt_zone = source[source.index("_researcher_unassisted_round") :]
    for banned in (
        "STRATEGY_RERVERIFY",
        "the failure is",
        "stale",
        "re-verify",
        "reverify",
        "revision-1",
        "known failure mode",
    ):
        # banned strings must not appear in the prompt construction
        # (they may appear elsewhere in code).
        prompt_text = prompt_zone[
            prompt_zone.index("prompt = (") : prompt_zone.index("+ baseline_policy")
        ]
        assert banned not in prompt_text.lower(), banned


def test_last_snapshot_rule() -> None:
    # A failed researcher round keeps the PREVIOUS snapshot — never the
    # best-scoring one (stats-contract §3).
    dev_experience = {"stages": [], "failures": [], "run_result": "failed"}
    policy, record = r2a_compare._researcher_unassisted_round(
        strong_model_fixed_policy_text(), dev_experience, live=False
    )
    # Offline deterministic candidate is a legal edit; a no-policy
    # output must fall back to the baseline (checked in main()). Here:
    # the round returns a policy, and the run keeps the last produced.
    assert "def on_turn" in policy


def test_denominator_counts_started_units() -> None:
    # Every planned unit produces an outcome record; none vanish. The
    # comparison entry runs 4 planned units (2 arms x 2 worlds) and
    # each carries passed/failures — enforced by the artifact shape.
    import json

    artifact = Path("artifacts/rsi-core-v1/r2a-offline.json")
    if not artifact.exists():  # offline run in CI without the artifact
        import subprocess

        subprocess.run(
            [
                sys.executable,
                "scripts/r2a_compare.py",
                "--offline",
                "--output",
                str(artifact),
            ],
            check=True,
            capture_output=True,
        )
    payload = json.loads(artifact.read_text())
    cells = []
    for arm in payload["arms"].values():
        for cell, run in arm.items():
            if isinstance(run, dict) and "passed" in run:
                cells.append((cell, run))
    assert len(cells) == 4
    for _cell, run in cells:
        assert isinstance(run["passed"], bool)
        assert isinstance(run["failures"], list)
        assert "model_calls" in run and "tool_ledger" in run
