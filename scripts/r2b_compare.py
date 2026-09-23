#!/usr/bin/env python3
"""R2b — three-arm comparison: strong-fixed, unassisted-update,
non-adaptive strategy search (the `stateful_control` slot's first real
implementation).

The search arm (stats-contract-v1 §7 + review §5.2): K candidate
policies proposed INDEPENDENTLY from the SAME unassisted prompt (each
call sees only the baseline + dev experience — never a previous
candidate's output: no cross-candidate feedback adaptation); selection
by the DECLARED rule: among candidates whose dev run completes without
policy errors, pick the first in proposal order (deterministic, not
dev-score-based, not eval-based). Compute accounting: the search arm
bears ALL candidate dev runs + all proposals (reported alongside).

Both deltas reported:
  Δ_update    = J(S_k) - J(strong fixed)          [same A0 lineage]
  Δ_practical = J(search arm) - J(strong fixed)   [full-system view]

Offline mode uses the deterministic scripted worker/responder chain
(wiring); live mode uses Siflow (needs SIFLOW_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget

from r2a_compare import (
    READER_ENDPOINT,
    RESEARCHER_MODEL,
    _live_responder_factory,
    _offline_responder,
    _researcher_unassisted_round,
    _run_arm,
)

SEARCH_CANDIDATES = 3  # K — declared in advance (stats-contract §6)


def _search_candidate_rounds(baseline, dev_experience, live: bool):
    """K INDEPENDENT proposals: identical prompt, no cross-candidate
    state (each call re-derives from baseline + experience only)."""

    rounds = []
    for candidate_index in range(SEARCH_CANDIDATES):
        policy, record = _researcher_unassisted_round(baseline, dev_experience, live)
        record = dict(record, candidate_index=candidate_index)
        rounds.append((policy, record))
        # NOTE: `policy` is deliberately NOT fed into the next round —
        # non-adaptive means each proposal is drawn fresh.
    return rounds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/r2b-comparison.json"),
    )
    args = parser.parse_args()
    started = time.monotonic()
    live = not args.offline
    if live:
        import os

        if not os.environ.get("SIFLOW_API_KEY"):
            print("live mode needs SIFLOW_API_KEY", file=sys.stderr)
            return 2

    responder = _live_responder_factory() if live else _offline_responder
    baseline = strong_model_fixed_policy_text()

    dev_inst = build_research_v4_dossier()
    eval_inst = build_dossier_variant("mirror")

    # Arm 1: strong model-fixed.
    dev_fixed = _run_arm(baseline, dev_inst, responder)
    eval_fixed = _run_arm(baseline, eval_inst, responder)

    # Dev experience for the improvement-style arms (identical input).
    dev_experience = {
        "stages": [
            {"stage": "survey", "outcome": "notes built", "model_calls": 4},
            {"stage": "constraint_injection", "outcome": dev_fixed["decisions"]},
            {"stage": "act_verify", "outcome": dev_fixed["decisions"]},
            {"stage": "follow_up x2", "outcome": dev_fixed["decisions"]},
        ],
        "failures": dev_fixed["failures"],
        "receipt_causes_sample": [
            "environment verification verdicts (pass/fail)",
            "protocol revision notices",
        ],
        "run_result": "passed" if dev_fixed["passed"] else "failed",
    }

    # Arm 2: unassisted update (one round — same as R2a).
    updated_policy, update_record = _researcher_unassisted_round(baseline, dev_experience, live)
    if "def on_turn" not in updated_policy:
        updated_policy = baseline
        update_record["round_outcome"] = "no-policy (kept baseline)"
    dev_update = _run_arm(updated_policy, dev_inst, responder)
    eval_update = _run_arm(updated_policy, eval_inst, responder)

    # Arm 3: non-adaptive strategy search.
    candidate_rounds = _search_candidate_rounds(baseline, dev_experience, live)
    candidates = []
    for policy, record in candidate_rounds:
        if "def on_turn" not in policy:
            candidates.append({"usable": False, "record": record, "dev_run": None})
            continue
        dev_run = _run_arm(policy, dev_inst, responder)
        candidates.append(
            {
                "usable": True,
                "record": record,
                "policy_head": policy[:200],
                "dev_run": dev_run,
            }
        )
    # DECLARED selection rule (fixed before running): first usable
    # candidate in proposal order with zero policy errors on dev; if
    # none qualify, the baseline stands (recorded).
    selected = None
    for candidate in candidates:
        if candidate["usable"] and candidate["dev_run"]["policy_errors"] == []:
            selected = candidate
            break
    if selected is None:
        search_policy = baseline
        selection_note = "no usable zero-error candidate; baseline stands"
    else:
        search_policy = None  # resolved below from the candidate head only
        selection_note = (
            f"candidate #{selected['record']['candidate_index']} selected (declared rule)"
        )
    # The search arm's POLICY is the selected candidate's — but we only
    # kept its head; re-run selection from the kept rounds.
    if selected is not None:
        idx = selected["record"]["candidate_index"]
        search_policy, _ = candidate_rounds[idx]
    eval_search = _run_arm(search_policy, eval_inst, responder)

    def _score(run: dict) -> int:
        return int(run["passed"])

    delta_update = _score(eval_update) - _score(eval_fixed)
    delta_practical = _score(eval_search) - _score(eval_fixed)
    if delta_update > 0:
        outcome_update = "improves"
    elif delta_update == 0:
        outcome_update = "ties"
    else:
        outcome_update = "regresses"

    payload = {
        "mode": "offline" if args.offline else "live",
        "contract": "docs/stats-contract-v1.md",
        "search_candidates_declared": SEARCH_CANDIDATES,
        "arms": {
            "strong_model_fixed": {"dev": dev_fixed, "eval_mirror": eval_fixed},
            "unassisted_update": {
                "researcher_record": update_record,
                "dev": dev_update,
                "eval_mirror": eval_update,
            },
            "non_adaptive_search": {
                "selection_note": selection_note,
                "candidates": [{k: v for k, v in c.items() if k != "dev_run"} for c in candidates],
                "dev": selected["dev_run"] if selected else dev_fixed,
                "eval_mirror": eval_search,
            },
        },
        "deltas": {
            "update_vs_fixed_eval": delta_update,
            "search_vs_fixed_eval": delta_practical,
            "per_decision_update": {
                k: eval_update["decisions"][k] - eval_fixed["decisions"][k]
                for k in eval_fixed["decisions"]
            },
            "per_decision_search": {
                k: eval_search["decisions"][k] - eval_fixed["decisions"][k]
                for k in eval_fixed["decisions"]
            },
        },
        "four_outcome_update": outcome_update,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(json.dumps(payload["deltas"], indent=1))
    print("update outcome:", outcome_update)
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
