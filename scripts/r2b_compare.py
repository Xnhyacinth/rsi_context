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
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from r2a_compare import (
    READER_ENDPOINT,
    RESEARCHER_MODEL,
    _live_responder_factory,
    _offline_responder,
    _policy_loadable,
    _researcher_unassisted_round,
    _run_arm,
)

from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.recuris_memory_policy import recuris_memory_policy_text
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.participant.recuris_real_arm import (
    R2B_NEUTRAL_SEED,
    RecurisAdaptedImprover,
    package_to_state,
)
from rsicontext.security.isolated_policy import (
    PolicyIsolationUnavailable,
    require_isolated_policy_executor,
)

SEARCH_CANDIDATES = 3  # K — declared in advance (stats-contract §6)


def _search_candidate_rounds(
    baseline: str, dev_experience: dict[str, object], live: bool
) -> list[tuple[str, dict[str, object]]]:
    """K INDEPENDENT proposals: identical prompt, no cross-candidate
    state (each call re-derives from baseline + experience only)."""

    rounds: list[tuple[str, dict[str, object]]] = []
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
        try:
            require_isolated_policy_executor()
        except PolicyIsolationUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2
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
    # The LOAD gate (liveprep's material finding, ported from r2a): the
    # R2b live failure mode was a mid-string truncation that passed the
    # "def on_turn" substring check and then failed to load at runtime
    # ("policy unavailable" every stage). Without this gate, Δ_update
    # measures the researcher's 16K truncation instead of the update.
    if not _policy_loadable(updated_policy):
        had_on_turn = "def on_turn" in updated_policy
        updated_policy = baseline
        prefix = (
            "rejected: policy does not compile (kept baseline)"
            if had_on_turn
            else "no-policy (kept baseline)"
        )
        update_record["round_outcome"] = f"{prefix}: {update_record.get('round_outcome')}"
    dev_update = _run_arm(updated_policy, dev_inst, responder)
    eval_update = _run_arm(updated_policy, eval_inst, responder)

    # Arm 3: non-adaptive strategy search.
    candidate_rounds = _search_candidate_rounds(baseline, dev_experience, live)
    candidates: list[dict[str, object]] = []
    selected_index: int | None = None
    selected_run: dict[str, object] | None = None
    for index, (policy, record) in enumerate(candidate_rounds):
        if not _policy_loadable(policy):
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
        if selected_index is None and dev_run["policy_errors"] == []:
            selected_index = index
            selected_run = dev_run
    # DECLARED selection rule (fixed before running): first usable
    # candidate in proposal order with zero policy errors on dev; if
    # none qualify, the baseline stands (recorded).
    if selected_index is None:
        search_policy = baseline
        selection_note = "no usable zero-error candidate; baseline stands"
    else:
        search_policy, _ = candidate_rounds[selected_index]
        selection_note = f"candidate #{selected_index} selected (declared rule)"
    eval_search = _run_arm(search_policy, eval_inst, responder)

    # Arm 4: recuris_adapted (the REAL Recuris loop) + its S0-MATCHED
    # control cell. The control: the SAME frozen memory-aware policy
    # with the NEUTRAL package, never updated — Δ_update_recuris =
    # J(S_k) - J(S0-matched) isolates MEMORY EVOLUTION (the policy form
    # is constant), exactly the confound the spec names.
    import json as _json

    recuris_policy = recuris_memory_policy_text()
    dev_s0_matched = _run_arm(
        recuris_policy,
        dev_inst,
        responder,
        initial_state=package_to_state(R2B_NEUTRAL_SEED),
    )
    eval_s0_matched = _run_arm(
        recuris_policy,
        eval_inst,
        responder,
        initial_state=package_to_state(R2B_NEUTRAL_SEED),
    )

    def recuris_dev_runner(package: dict[str, object]) -> dict[str, object]:
        return _run_arm(
            recuris_policy,
            dev_inst,
            responder,
            initial_state=package_to_state(package),
        )

    if live:

        def recuris_meta_agent(prompt: str) -> str | tuple[str, Mapping[str, object]]:
            # The live Meta-Agent: the researcher model over the package +
            # trace prompt. Robustness per the wiring audit (contract §6):
            # TRANSPORT-only retries (5 attempts / 10s backoff — a
            # completed-but-unusable reply is a RESULT, never retried);
            # finish_reason captured; usage returned for the improver's
            # cost ledger; the reasoning channel is rescued for plan JSON.
            import os
            import time as _time
            import urllib.error
            import urllib.request

            body = {
                "model": RESEARCHER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are the memory-maintenance engineer.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 16384,
                "temperature": 0.0,
                "seed": 42,
                "stream": False,
            }
            request = urllib.request.Request(
                READER_ENDPOINT,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            for _attempt in range(5):
                try:
                    # READER_ENDPOINT is the fixed HTTPS URL from r2a_compare.
                    with urllib.request.urlopen(request, timeout=600) as response:  # nosec B310
                        raw = json.loads(response.read())
                    break
                except (urllib.error.URLError, TimeoutError):
                    if _attempt == 4:
                        raise
                    _time.sleep(10.0)
            choice = raw["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning") or message.get("reasoning_content")
            if not content.strip() and isinstance(reasoning, str) and '"clusters"' in reasoning:
                start = reasoning.find("{")
                end = reasoning.rfind("}")
                if start != -1 and end > start:
                    content = reasoning[start : end + 1]
            usage = dict(raw.get("usage") or {})
            usage["finish_reason"] = choice.get("finish_reason")
            return content, usage
    else:

        def recuris_meta_agent(prompt: str) -> str | tuple[str, Mapping[str, object]]:
            # Offline deterministic stub: proposes a placeholder card for
            # the FIRST failed decision cited in the trace (evidence
            # cites a real failure; the body is a placeholder — passes
            # the validator by construction).
            import re

            failed = re.findall(r'"(award|followup_1|followup_2)": false', prompt)
            target = failed[0] if failed else "award"
            return json.dumps(
                {
                    "clusters": [
                        {
                            "component": "E",
                            "action": "add_card",
                            "target": f"repair-{target}",
                            "card": {
                                "body": (
                                    "re-read the decisive clause and pin the "
                                    "answer's id form before deciding"
                                ),
                                "stage": "act_verify",
                                "requires_field": None,
                            },
                            "evidence": [target],
                        }
                    ]
                }
            )

    improver = RecurisAdaptedImprover(
        meta_agent=recuris_meta_agent, dev_runner=recuris_dev_runner, rounds=2
    )
    final_package, recuris_record = improver.improve(_json.loads(_json.dumps(R2B_NEUTRAL_SEED)))
    eval_recuris = _run_arm(
        recuris_policy,
        eval_inst,
        responder,
        initial_state=package_to_state(final_package),
    )
    # The dev-side numbers come from the improver's OWN final incumbent
    # run (the last internal dev run — deterministic offline, and live
    # it is the exact run the gate accepted), not a redundant re-run
    # that would silently inflate the arm's dev-run column.
    dev_recuris = recuris_record["final_incumbent_run"]

    def _score(run: dict[str, object]) -> int:
        passed = run["passed"]
        if not isinstance(passed, bool):
            raise TypeError("arm run must report a boolean passed field")
        return int(passed)

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
                "dev": selected_run if selected_run is not None else dev_fixed,
                "eval_mirror": eval_search,
            },
            "recuris_s0_matched": {
                "dev": dev_s0_matched,
                "eval_mirror": eval_s0_matched,
            },
            "recuris_adapted": {
                "improver_record": recuris_record,
                "final_package": final_package,
                "dev": dev_recuris,
                "eval_mirror": eval_recuris,
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
            "recuris_update_vs_s0matched_eval": _score(eval_recuris) - _score(eval_s0_matched),
            "per_decision_recuris_update": {
                k: eval_recuris["decisions"][k] - eval_s0_matched["decisions"][k]
                for k in eval_s0_matched["decisions"]
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
