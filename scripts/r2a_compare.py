#!/usr/bin/env python3
"""R2a — the longitudinal comparison entry (stats-contract-v1 governed).

Arms:
  strong-model-fixed  the honest control: same worker via ask_model,
                      content decisions made by the MODEL (orchestration
                      only in policy code); NEVER updates.
  unassisted-update   starts from the SAME baseline policy text (same
                      A0), then ONE researcher round rewrites the policy
                      from dev experience ONLY — the task prompt carries
                      NO failure-mode diagnosis (unassisted; the old
                      "the failure is X, do Y" prompt is gone).

Runs both arms on the DEV dossier and on the EVAL variant (mirror), and
reports the four-outcome state (improves / ties / regresses /
fixed-sufficient) with per-decision breakdown and full cost ledgers,
per the stats contract (planned-and-started units, infra-zero, last-
snapshot rule, descriptive n).

Offline mode (--offline) uses a deterministic scripted responder (the
wiring smoke); live mode uses the Siflow worker (needs SIFLOW_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget

READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
RESEARCHER_MODEL = "deepseek-ai/deepseek-v4.1-flash"


def _offline_responder(prompt: str) -> str:
    """A deterministic scripted worker (offline wiring smoke only).

    A directive-following stand-in for the live model: when the prompt
    carries the decisive card text (the policy batches the corpus), it
    extracts the clause lines; when asked for a decision line, it scans
    the CARRIED NOTES in the prompt for the clause it needs. It has NO
    world knowledge beyond the prompt — swap the facts and its answers
    follow the text, like the live model's should.
    """

    lowered = prompt.lower()
    # Survey extraction batches: quote the exception/buried clauses.
    # Only CARD BODY lines (they carry [[doc:...]] markers) qualify —
    # the instruction lines mention the clause names too.
    if "extract only" in lowered:
        kept = []
        in_doc = False
        for line in prompt.splitlines():
            stripped = line.strip()
            if stripped.startswith("[[doc:"):
                in_doc = True
                continue
            if not stripped:
                in_doc = False
                continue
            if not in_doc:
                continue  # instruction block
            body = stripped.lower()
            if (
                "exception clause" in body
                or "buried condition" in body
                or "on paper" in body
                or "northern service hub" in body
                or "verification protocol defines" in body
            ):
                kept.append(stripped)
        return "notes: " + (" | ".join(kept) if kept else "(no clauses in this batch)")
    # Award choice: the retained notes are in the prompt.
    if "name the one supplier" in lowered:
        if "atlas carriage" in lowered and "lapsed" in lowered:
            # The decoy's disqualifier is also present: Atlas qualifies,
            # Pinnacle does not.
            return "supplier=atlas-carriage"
        if "harborline freight" in lowered and "suspended" in lowered:
            return "supplier=harborline-freight"
        if "atlas carriage" in lowered:
            return "supplier=atlas-carriage"
        if "harborline freight" in lowered:
            return "supplier=harborline-freight"
        return "supplier=unknown"
    # Constraint analysis.
    if "check=<name>" in lowered or "which verification check" in lowered:
        if "customs-preclearance" in lowered:
            return "check=customs-preclearance candidate=atlas-carriage"
        return "check=customs-preclearance candidate=atlas-carriage"
    # Calibration follow-up.
    if "which instrument supplier" in lowered:
        if "orbit hosting" in lowered:
            return "supplier=orbit-hosting"
        return "supplier=vesper-instruments"
    # Rule-change analysis.
    if "does this change invalidate" in lowered:
        if "documentation update" in lowered:
            return "invalidates=none"
        if "customs-preclearance check only" in lowered:
            return "invalidates=customs-preclearance"
        return "invalidates=cold-chain-integrity"
    # Currency diagnosis.
    if "still current" in lowered:
        if "customs-preclearance check only" in lowered:
            return "status=reverify"
        if "cold-chain-integrity check only" in lowered:
            return "status=current"
        return "status=reverify"
    return "notes: (nothing decisive in this batch)"


def _live_responder_factory():
    import os
    import urllib.request

    key = os.environ["SIFLOW_API_KEY"]

    def responder(prompt: str) -> str:
        body = {
            "model": READER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are the project worker. Follow the requested output format exactly.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.0,
            "seed": 42,
            "stream": False,
        }
        request = urllib.request.Request(
            READER_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = json.loads(response.read())
        choice = raw["choices"][0]
        finish_reasons.append(choice.get("finish_reason"))
        message = choice["message"]
        content = message.get("content") or ""
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        # Channel robustness (declared fix, late-report diagnosis): the
        # endpoint family emits final answers in the reasoning channel
        # with empty visible content. Rescue the four decision-line
        # shapes (supplier= / status= / check= / candidate=) from the
        # reasoning tail; record finish_reason for truncation diagnosis.
        if not content.strip() and isinstance(reasoning, str):
            for marker in ("supplier=", "status=", "check=", "candidate="):
                if marker in reasoning:
                    tail = reasoning[reasoning.rfind(marker) :]
                    content = tail[: max(len(marker) + 60, tail.find("\n") if "\n" in tail else len(tail))][:100]
                    break
        return content

    finish_reasons: list[str | None] = []

    def channel_state() -> list[str | None]:
        return list(finish_reasons)

    responder.channel_state = channel_state  # type: ignore[attr-defined]
    return responder


def _run_arm(policy_text: str, inst, responder, max_turns: int = 2) -> dict:
    env = ProjectState()
    budget = ToolBudget()
    hook = PolicyHook({}, policy_text, tool_budget=budget, responder=responder)
    hook.bind_env(env)
    started = time.monotonic()
    record = run_lifecycle(inst, hook, env, max_turns_per_stage=max_turns)
    failures = list(record.final_check.failures)
    decisions = {
        "award": not any("commit gate" in f for f in failures),
        "followup_1": not any("s6-followup-1" in f for f in failures),
        "followup_2": not any("s8-followup-2" in f for f in failures),
    }
    channel_state = getattr(responder, "channel_state", None)
    return {
        "instance_id": inst.instance_id,
        "passed": record.final_check.passed,
        "decisions": decisions,
        "failures": failures[:8],
        "policy_errors": list(hook.policy_errors)[:6],
        "model_calls": hook.model_calls,
        "model_tokens_in": hook.model_tokens_in,
        "model_tokens_out": hook.model_tokens_out,
        "tool_ledger": budget.ledger(),
        # Late-report fixes: the run record now carries the evidence the
        # review's per-run questions need — which docs each stage cited
        # (provenance retention), the per-stage shape, and the model-call
        # transcript (prompts/replies/ok/tokens).
        "provenance_retention": [
            sr.provenance_retention for sr in record.stage_records
        ],
        "stage_records": [sr.to_dict() for sr in record.stage_records],
        "model_transcript": list(hook.model_transcript),
        "finish_reasons": channel_state() if channel_state else [],
        "wall_seconds": round(time.monotonic() - started, 1),
    }


def _researcher_unassisted_round(
    baseline_policy: str, dev_experience: dict, live: bool
) -> tuple[str, dict]:
    """One researcher round: rewrite the policy from EXPERIENCE ONLY.

    Unassisted (stats-contract §4 + review): the task prompt names the
    interface and the dev run's observable facts (stage kinds, receipt
    causes, decision outcomes) — NO failure-mode diagnosis, no hint of
    which knob matters.
    """

    if not live:
        # Offline: the deterministic 'researcher' applies a generic
        # robustness edit ( batching size + a wider extraction prompt)
        # — an arbitrary-but-legal candidate, not an oracle answer.
        edited = baseline_policy.replace("BATCH_DOCS = 6", "BATCH_DOCS = 4")
        return edited, {
            "round_outcome": "ok (offline deterministic candidate)",
            "input_tokens": 0,
            "output_tokens": 0,
            "wall_seconds": 0.0,
        }

    import os
    import urllib.request

    prompt = (
        "You maintain the strategy file of a project agent. The agent "
        "runs multi-stage supplier-selection projects: it reads a large "
        "corpus, keeps notes, requests verifications from the "
        "environment, commits an award, and answers follow-up requests "
        "after rule changes. Below is (1) the CURRENT strategy file and "
        "(2) the record of one development run — what happened at each "
        "stage, what the environment answered, and which decisions "
        "passed or failed. Improve the strategy file. You may change "
        "anything in the file; it must still define on_turn(turn) with "
        "the same interface (turn.ask_model, turn.actions.*, "
        "turn.view.documents, turn.state). Reply with ONLY the new file "
        "content in a ```python code block.\n\n"
        "=== CURRENT STRATEGY ===\n```python\n"
        + baseline_policy
        + "\n```\n\n=== DEVELOPMENT RUN ===\n"
        + json.dumps(dev_experience, indent=1)
    )
    body = {
        "model": RESEARCHER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are the strategy maintenance engineer.",
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
    with urllib.request.urlopen(request, timeout=600) as response:
        raw = json.loads(response.read())
    content = raw["choices"][0]["message"].get("content") or ""
    usage = raw.get("usage", {})
    # Extract the python block.
    if "```python" in content:
        block = content.split("```python", 1)[1]
        block = block.split("```", 1)[0]
        content = block.strip() + "\n"
    return content, {
        "round_outcome": "ok" if "def on_turn" in content else "no-policy",
        "input_tokens": int(usage.get("prompt_tokens", 0)),
        "output_tokens": int(usage.get("completion_tokens", 0)),
        "wall_seconds": 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/r2a-comparison.json"),
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

    # DEV world (dev material; the update round's only input source).
    dev_inst = build_research_v4_dossier()
    # EVAL variant (same-family transfer; never enters improvement input).
    eval_inst = build_dossier_variant("mirror")

    # Arm 1: strong model-fixed (never updates).
    dev_fixed = _run_arm(baseline, dev_inst, responder)
    eval_fixed = _run_arm(baseline, eval_inst, responder)

    # Arm 2: unassisted update — S0 = the SAME baseline (same A0),
    # one round from dev experience only.
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
    updated_policy, researcher_record = _researcher_unassisted_round(baseline, dev_experience, live)
    if "def on_turn" not in updated_policy:
        # Round produced no usable policy: the PREVIOUS snapshot stands
        # (stats-contract §3 — last snapshot, not best).
        updated_policy = baseline
        researcher_record["round_outcome"] = "no-policy (kept baseline): " + str(
            researcher_record.get("round_outcome")
        )
    dev_updated = _run_arm(updated_policy, dev_inst, responder)
    eval_updated = _run_arm(updated_policy, eval_inst, responder)

    # Four-outcome state + per-decision deltas (descriptive, n=1 family).
    def _overall(run: dict) -> int:
        return int(run["passed"])

    delta_dev = _overall(dev_updated) - _overall(dev_fixed)
    delta_eval = _overall(eval_updated) - _overall(eval_fixed)
    if delta_eval > 0:
        outcome = "improves"
    elif delta_eval == 0 and delta_dev >= 0:
        outcome = "ties" if not dev_fixed["passed"] else "fixed-sufficient"
    else:
        outcome = "regresses"

    payload = {
        "mode": "offline" if args.offline else "live",
        "contract": "docs/stats-contract-v1.md",
        "arms": {
            "strong_model_fixed": {
                "dev": dev_fixed,
                "eval_mirror": eval_fixed,
            },
            "unassisted_update": {
                "researcher_record": researcher_record,
                "policy_head": updated_policy[:300],
                "dev": dev_updated,
                "eval_mirror": eval_updated,
            },
        },
        "deltas": {
            "dev": delta_dev,
            "eval_mirror": delta_eval,
            "per_decision_dev": {
                k: dev_updated["decisions"][k] - dev_fixed["decisions"][k]
                for k in dev_fixed["decisions"]
            },
            "per_decision_eval": {
                k: eval_updated["decisions"][k] - eval_fixed["decisions"][k]
                for k in eval_fixed["decisions"]
            },
        },
        "four_outcome": outcome,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(json.dumps(payload["deltas"], indent=1))
    print("four_outcome:", outcome)
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
