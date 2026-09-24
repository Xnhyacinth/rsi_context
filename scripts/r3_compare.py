#!/usr/bin/env python3
"""r3 — the unified A/B/C three-group comparison entry.

The r3design blueprint: normalize every arm×group run into ONE
GroupRun record, and make every consumer (improver, deltas, artifact)
consume only that record. Five cells (strong_model_fixed,
unassisted_update, non_adaptive_search, recuris_s0_matched,
recuris_adapted) on ALL THREE groups (A: single lifecycle; B/C: session
sequences), each with its own A0 baseline. Per-group deltas (Δ_update,
Δ_practical, Δ_recuris vs S0-matched) + the aggregate four-outcome as a
CONJUNCTION (improves iff every group improves and none regresses) —
never a single merged score; the groups are different tasks, not
replicates.

Governed by docs/stats-contract-v1.md. Artifact:
artifacts/rsi-core-v1/r3-comparison.json (the shared checkout path).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_b_group import (
    build_b1_reverse_sessions,
    build_b1_sessions,
)
from rsicontext.lifecycle.material_c_group import (
    build_c1_mirror_sessions,
    build_c1_sessions,
)
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.recuris_memory_policy import recuris_memory_policy_text
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.participant.recuris_real_arm import (
    R2B_NEUTRAL_SEED,
    RecurisAdaptedImprover,
    package_to_state,
)

from r2a_compare import (
    READER_ENDPOINT,
    RESEARCHER_MODEL,
    _live_responder_factory,
    _offline_responder,
    _policy_loadable,
    _researcher_unassisted_round,
    _run_arm,
)

#: The recuris arm's per-group seeds: the r3design §5 data adjustment —
#: B/C cards must be able to reach the recovery-relevant stages
#: (rule_change, session_start), which R2B_NEUTRAL_SEED's
#: invocation stages (act_verify/follow_up only) never allowed.
_R3_GROUP_SEEDS: dict[str, dict[str, object]] = {
    "A": R2B_NEUTRAL_SEED,
    "B": {
        **R2B_NEUTRAL_SEED,
        "name": "r3-b-neutral",
        "invocation": {
            **R2B_NEUTRAL_SEED["invocation"],  # type: ignore[typeddict-item]
            "invoked_on_stages": ["act_verify", "follow_up", "rule_change", "session_start"],
        },
    },
    "C": {
        **R2B_NEUTRAL_SEED,
        "name": "r3-c-neutral",
        "invocation": {
            **R2B_NEUTRAL_SEED["invocation"],  # type: ignore[typeddict-item]
            "invoked_on_stages": ["act_verify", "follow_up", "rule_change", "session_start"],
        },
    },
}

SEARCH_CANDIDATES = 3  # K — declared in advance (stats-contract §6)


def _a_worlds() -> tuple[Any, Any]:
    return build_research_v4_dossier(), build_dossier_variant("mirror")


def _b_worlds() -> tuple[list[Any], list[Any]]:
    """B's dev/eval twins: b1 (mother→mirror) vs b1-reverse
    (mirror→mother) — the full three-session triple each."""

    dev = build_b1_sessions()
    ev = build_b1_reverse_sessions()
    return list(dev), list(ev)


def _c_worlds() -> tuple[list[Any], list[Any]]:
    """C's dev/eval twins: c1 vs c1-mirror (both two-session)."""

    dev = build_c1_sessions()
    ev = build_c1_mirror_sessions()
    return list(dev), list(ev)


class GroupSpec:
    """One group's run shape and decision vocabulary."""

    def __init__(
        self,
        group_id: str,
        dev_worlds: list[Any],
        eval_worlds: list[Any],
        *,
        shape: str,
        turns: int,
        baseline_policy: str,
        dev_experience_stages: list[str],
    ) -> None:
        self.group_id = group_id
        self.dev_worlds = dev_worlds
        self.eval_worlds = eval_worlds
        self.shape = shape
        self.turns = turns
        self.baseline_policy = baseline_policy
        self.dev_experience_stages = dev_experience_stages


def _run_arm_on_group(
    spec,
    policy_text: str,
    responder,
    initial_state: dict[str, object] | None = None,
    phase: str = "dev",
) -> dict[str, object]:
    """One arm cell on one group (dispatches on the shape).

    phase selects the world set (stats-contract §4): "dev" runs the
    dev worlds (the improver's dev_runner and every candidate-gate run
    default here — experience is gained on dev only); "eval" runs the
    held-out worlds. The returned record is the SAME GroupRun contract
    either way, so build_trace_doc and run_gate run UNMODIFIED over it
    (the improver never learns what a session is).
    """

    worlds = spec.dev_worlds if phase == "dev" else spec.eval_worlds
    if spec.shape == "lifecycle":
        return _run_arm(policy_text, worlds[0], responder, initial_state=initial_state)
    from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

    budget = ToolBudget()
    registry = DocumentRegistry()
    sessions = list(worlds)
    seq = run_session_sequence(
        sessions,
        lambda state: _make_hook(policy_text, state, budget, registry, responder),
        envs=[ProjectState() for _ in sessions],
        budget=budget,
        registry=registry,
        max_turns_per_stage=spec.turns,
        decision_rules=_b_decision_rules if spec.group_id == "B" else _c_decision_rules,
    )
    return _sequence_to_group_run(seq, budget)


def _b_decision_rules(record, sessions):
    """B's six-decision vector (session-record needles)."""

    s1, s2, s3 = (record.sessions + [None, None, None])[:3]

    def _decision(key: str, session, needle: str) -> None:
        failures = session.failures if session else []
        record.decisions[key] = not any(needle in f for f in failures)

    if s1:
        _decision("s1_award", s1, "commit gate")
    if s2:
        _decision("s2_calibration", s2, "s9-followup-calibration")
        _decision("s2_currency", s2, "s10-followup-currency")
        _decision("s2_reaward_fresh", s2, "commit gate[s11-re-award]")
    if s3:
        _decision("s3_award", s3, "commit gate")
        _decision("s3_calibration", s3, "n6-followup-calibration")


def _c_decision_rules(record, sessions):
    """C's two-decision vector: per-session pass/fail."""

    record.decisions = {f"c{i + 1}_recovery": s.passed for i, s in enumerate(record.sessions)}


def _sequence_to_group_run(seq, budget) -> dict[str, object]:
    """Merge a SequenceRecord into the GroupRun contract."""

    merged_transcript: list[dict[str, object]] = []
    stage_records: list[dict[str, object]] = []
    memory_delivered: list[object] = []
    obs: list[object] = []
    policy_errors: list[str] = []
    failures: list[str] = []
    for session in seq.sessions:
        merged_transcript.extend(session.model_transcript)
        stage_records.extend(session.stage_records)
        memory_delivered.extend(session.final_memory_delivered)
        obs.extend(session.final_obs)
        policy_errors.extend(session.policy_errors)
        failures.extend(session.failures)
    cost = seq.cost()
    return {
        "instance_id": ";".join(s.instance_id for s in seq.sessions),
        "passed": all(s.passed for s in seq.sessions),
        "decisions": dict(seq.decisions),
        "failure_detail": {k: list(v) for k, v in seq.failure_detail.items()},
        "policy_errors": policy_errors[:16],
        "model_calls": cost["model_calls"],
        "model_tokens_in": cost["model_tokens_in"],
        "model_tokens_out": cost["model_tokens_out"],
        "tool_ledger": cost["tool_ledger"],
        "model_transcript": merged_transcript,
        "stage_records": stage_records,
        "final_state": {"memory_delivered": memory_delivered, "obs": obs},
    }


# --- the arm runners -------------------------------------------------------


def _make_hook(policy_text, state, budget, registry, responder):
    from rsicontext.lifecycle.policy import PolicyHook

    hook = PolicyHook(
        dict(state), policy_text, tool_budget=budget, responder=responder, registry=registry
    )
    return hook


def _run_failures(run: dict[str, object]) -> list[str]:
    """The run's failure strings, across both GroupRun spellings.

    A-group records carry `failures` (r2a's _run_arm); B/C sequence
    records carry `failure_detail` (per decision). The researcher's
    experience payload must be the union.
    """

    failures: list[str] = list(run.get("failures") or [])
    for needle_list in (run.get("failure_detail") or {}).values():
        failures.extend(needle_list)
    return failures


def _dev_experience(spec, baseline_run: dict[str, object]) -> dict[str, object]:
    """The unassisted/search arms' dev-experience payload (per group)."""

    return {
        "stages": spec.dev_experience_stages,
        "decisions": dict(baseline_run.get("decisions") or {}),
        "failures": _run_failures(baseline_run),
        "receipt_causes_sample": [
            "environment verification verdicts (pass/fail)",
            "protocol revision notices",
        ],
        "run_result": "passed" if baseline_run.get("passed") else "failed",
    }


def _four_outcome(delta_eval: int, delta_dev: int, fixed_passed: bool) -> str:
    """r2a's semantics, applied per group (stats-contract §5):

    improves if eval gained; fixed-sufficient if the fixed system
    already passed (nothing to gain — a publishable ties class);
    otherwise ties; regresses if eval lost.
    """

    if delta_eval > 0:
        return "improves"
    if delta_eval < 0:
        return "regresses"
    if fixed_passed:
        return "fixed-sufficient"
    if delta_dev < 0:
        return "regresses"
    return "ties"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/r3-comparison.json"),
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

    a_dev, a_eval = _a_worlds()
    b_dev, b_eval = _b_worlds()
    c_dev, c_eval = _c_worlds()

    specs = {
        "A": GroupSpec(
            "A",
            [a_dev],
            [a_eval],
            shape="lifecycle",
            turns=2,
            baseline_policy=strong_model_fixed_policy_text(),
            dev_experience_stages=[
                "survey",
                "constraint_injection",
                "act_verify",
                "follow_up x2",
            ],
        ),
        "B": GroupSpec(
            "B",
            b_dev,
            b_eval,
            shape="sequence",
            turns=2,
            baseline_policy=group_b_basline_policy_text(),
            dev_experience_stages=[
                "survey + award (session 1)",
                "resume + rule change + follow-ups (session 2)",
                "new project (session 3)",
            ],
        ),
        "C": GroupSpec(
            "C",
            c_dev,
            c_eval,
            shape="sequence",
            turns=3,
            baseline_policy=group_c_baseline_policy_text(),
            dev_experience_stages=[
                "survey + probe + fail receipt + switch (session 1)",
                "mutation + re-verify + re-award (session 2)",
            ],
        ),
    }

    groups_payload: dict[str, dict[str, object]] = {}
    for group_id, spec in specs.items():
        # Arm 1: the group baseline (never updated).
        dev_base = _run_arm_on_group(spec, spec.baseline_policy, responder)
        eval_base = _run_arm_on_group(spec, spec.baseline_policy, responder, phase="eval")

        # Arm 2: unassisted update (one round from dev experience).
        dev_experience = _dev_experience(spec, dev_base)
        updated_policy, update_record = _researcher_unassisted_round(
            spec.baseline_policy, dev_experience, live
        )
        if not _policy_loadable(updated_policy):
            updated_policy = spec.baseline_policy
            update_record["round_outcome"] = "rejected: policy does not compile (kept baseline)"
        dev_update = _run_arm_on_group(spec, updated_policy, responder)
        eval_update = _run_arm_on_group(spec, updated_policy, responder, phase="eval")

        # The declared selection rule picks the first usable candidate
        # (loadable, zero dev policy errors) — its POLICY TEXT is the
        # arm's delivery. If none qualify, the baseline stands (recorded).
        candidates: list[dict[str, object]] = []
        candidate_texts: list[str] = []
        for candidate_index in range(SEARCH_CANDIDATES):
            policy, record = _researcher_unassisted_round(
                spec.baseline_policy, dev_experience, live
            )
            usable = _policy_loadable(policy)
            if usable:
                dev_run = _run_arm_on_group(spec, policy, responder)
                usable = not dev_run.get("policy_errors")
                record = dict(
                    record,
                    policy_head=policy[:200],
                    dev_policy_errors=len(dev_run.get("policy_errors") or []),
                )
            else:
                dev_run = None
            candidates.append({"usable": usable, "record": record})
            if usable:
                candidate_texts.append(policy)
        selected_text = candidate_texts[0] if candidate_texts else spec.baseline_policy
        eval_search = _run_arm_on_group(spec, selected_text, responder, phase="eval")

        # Arm 4+5: recuris S0-matched + adapted.
        seed = _R3_GROUP_SEEDS[group_id]
        dev_s0 = _run_arm_on_group(
            spec,
            recuris_memory_policy_text(),
            responder,
            initial_state=package_to_state(dict(seed)),
        )
        eval_s0 = _run_arm_on_group(
            spec,
            recuris_memory_policy_text(),
            responder,
            initial_state=package_to_state(dict(seed)),
            phase="eval",
        )

        def dev_runner(package: dict) -> dict:
            return _run_arm_on_group(
                spec,
                recuris_memory_policy_text(),
                responder,
                initial_state=package_to_state(package),
            )

        improver = RecurisAdaptedImprover(
            meta_agent=_r3_meta_agent(live), dev_runner=dev_runner, rounds=2
        )
        final_package, improver_record = improver.improve(json.loads(json.dumps(dict(seed))))
        eval_recuris = _run_arm_on_group(
            spec,
            recuris_memory_policy_text(),
            responder,
            initial_state=package_to_state(final_package),
            phase="eval",
        )

        def _score(run: dict) -> int:
            return int(run.get("passed") is True)

        deltas = {
            "update_vs_baseline": _score(eval_update) - _score(eval_base),
            "search_vs_baseline": _score(eval_search) - _score(eval_base),
            "recuris_vs_s0matched": _score(eval_recuris) - _score(eval_s0),
        }
        groups_payload[group_id] = {
            "shape": spec.shape,
            "arms": {
                "baseline": {"dev": dev_base, "eval": eval_base},
                "unassisted_update": {
                    "researcher_record": update_record,
                    "dev": dev_update,
                    "eval": eval_update,
                },
                "non_adaptive_search": {
                    "candidates": candidates,
                    "eval": eval_search,
                },
                "recuris_s0_matched": {"dev": dev_s0, "eval": eval_s0},
                "recuris_adapted": {
                    "improver_record": improver_record,
                    "final_package": final_package,
                    "eval": eval_recuris,
                },
            },
            "deltas": deltas,
            "four_outcome": _four_outcome(
                deltas["update_vs_baseline"],
                _score(dev_update) - _score(dev_base),
                _score(eval_base) == 1,
            ),
        }

    # The aggregate: CONJUNCTION over the groups — improves iff every
    # group improves; regresses if any regresses; fixed-sufficient iff
    # every group is fixed-sufficient (the fixed system already passed
    # everywhere — nothing to gain); otherwise ties. Reported alongside
    # the per-group states (primary).
    outcomes = [g["four_outcome"] for g in groups_payload.values()]
    if all(o == "improves" for o in outcomes):
        aggregate = "improves"
    elif any(o == "regresses" for o in outcomes):
        aggregate = "regresses"
    elif all(o == "fixed-sufficient" for o in outcomes):
        aggregate = "fixed-sufficient"
    else:
        aggregate = "ties"

    payload = {
        "mode": "offline" if args.offline else "live",
        "contract": "docs/stats-contract-v1.md",
        "search_candidates_declared": SEARCH_CANDIDATES,
        "groups": groups_payload,
        "aggregate_four_outcome": aggregate,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    summary = {
        gid: {
            "deltas": g["deltas"],
            "four_outcome": g["four_outcome"],
        }
        for gid, g in groups_payload.items()
    }
    print(json.dumps({"aggregate": aggregate, "groups": summary}, indent=1))
    print(f"artifact: {args.output}")
    return 0


def _r3_meta_agent(live: bool):
    if live:

        def meta_agent(prompt: str):
            import os
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
                    with urllib.request.urlopen(request, timeout=600) as response:
                        raw = json.loads(response.read())
                    break
                except Exception:
                    if _attempt == 4:
                        raise
                    time.sleep(10.0)
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

        return meta_agent

    def offline_stub(prompt: str):
        import re

        failed = re.findall(r'"([a-z0-9_]+)": false', prompt)
        target = failed[0] if failed else "award"
        return json.dumps(
            {
                "clusters": [
                    {
                        "component": "E",
                        "action": "add_card",
                        "target": f"repair-{target}",
                        "card": {
                            "body": "re-read the decisive clause and pin the answer's id form before deciding",
                            "stage": "act_verify",
                            "requires_field": None,
                        },
                        "evidence": [target],
                    }
                ]
            }
        )

    return offline_stub


if __name__ == "__main__":
    raise SystemExit(main())
