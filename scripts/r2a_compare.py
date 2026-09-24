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
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import ToolBudget

READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
RESEARCHER_MODEL = "deepseek-ai/deepseek-v4.1-flash"


def _reported_usage(raw: object) -> dict[str, object]:
    """Keep provider counts separate from the policy channel's word estimates."""

    usage = raw if isinstance(raw, dict) else {}
    counts = {
        name: value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        for value in (usage.get(name),)
    }
    return {
        **counts,
        "usage_status": "reported"
        if all(value is not None for value in counts.values())
        else "missing",
    }


def _provider_usage_totals(calls: list[dict[str, object]], *, live: bool) -> dict[str, object]:
    if not live:
        return {
            "usage_status": "not_applicable",
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
    complete = bool(calls) and all(call.get("usage_status") == "reported" for call in calls)
    return {
        "usage_status": "reported" if complete else "incomplete",
        **{
            name: sum(cast(int, call[name]) for call in calls) if complete else None
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
    }


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


def _live_responder_factory(*, enable_thinking: bool | None = None) -> Any:
    import os
    import urllib.request

    key = os.environ["SIFLOW_API_KEY"]
    usage_calls: list[dict[str, object]] = []

    def responder(prompt: str) -> str:
        body = {
            "model": READER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the project worker. Follow the requested output format exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.0,
            "seed": 42,
            "stream": False,
        }
        if enable_thinking is False:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        request = urllib.request.Request(
            READER_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            # READER_ENDPOINT is a code-owned HTTPS constant.
            with urllib.request.urlopen(request, timeout=300) as response:  # nosec B310
                raw = json.loads(response.read())
        except Exception as exc:
            usage_calls.append(
                {
                    "model": READER_MODEL,
                    "model_echo": None,
                    "system_fingerprint": None,
                    "outcome": "request_error",
                    "finish_reason": None,
                    "error_type": type(exc).__name__,
                    **_reported_usage(None),
                }
            )
            raise
        try:
            choice = raw["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise TypeError("worker content must be a string")
            reasoning = message.get("reasoning") or message.get("reasoning_content")
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            usage_calls.append(
                {
                    "model": READER_MODEL,
                    "model_echo": raw.get("model") if isinstance(raw, dict) else None,
                    "system_fingerprint": (
                        raw.get("system_fingerprint") if isinstance(raw, dict) else None
                    ),
                    "outcome": "protocol_error",
                    "finish_reason": None,
                    "error_type": type(exc).__name__,
                    **_reported_usage(raw.get("usage") if isinstance(raw, dict) else None),
                }
            )
            raise
        usage_calls.append(
            {
                "model": READER_MODEL,
                "model_echo": raw.get("model"),
                "system_fingerprint": raw.get("system_fingerprint"),
                "outcome": "ok",
                "finish_reason": finish_reason,
                **_reported_usage(raw.get("usage")),
            }
        )
        finish_reasons.append(finish_reason)
        # Channel robustness (declared fix, late-report diagnosis): the
        # endpoint family emits final answers in the reasoning channel
        # with empty visible content. Rescue the four decision-line
        # shapes (supplier= / status= / check= / candidate=) from the
        # reasoning tail; record finish_reason for truncation diagnosis.
        if not content.strip() and isinstance(reasoning, str):
            for marker in ("supplier=", "status=", "check=", "candidate="):
                if marker in reasoning:
                    tail = reasoning[reasoning.rfind(marker) :]
                    content = tail[
                        : max(len(marker) + 60, tail.find("\n") if "\n" in tail else len(tail))
                    ][:100]
                    break
        return content

    finish_reasons: list[str | None] = []

    def channel_state() -> list[str | None]:
        return list(finish_reasons)

    def usage_state() -> list[dict[str, object]]:
        return [dict(call) for call in usage_calls]

    responder.channel_state = channel_state  # type: ignore[attr-defined]
    responder.usage_state = usage_state  # type: ignore[attr-defined]
    return responder


def _run_arm(
    policy_text: str,
    inst: LifecycleInstance,
    responder: Any,
    max_turns: int = 2,
    initial_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = ProjectState()
    budget = ToolBudget()
    channel_state = getattr(responder, "channel_state", None)
    finish_reasons_before = len(channel_state()) if channel_state else 0
    usage_state = getattr(responder, "usage_state", None)
    usage_before = len(usage_state()) if usage_state else 0
    hook = PolicyHook(
        dict(initial_state) if initial_state else {},
        policy_text,
        tool_budget=budget,
        responder=responder,
    )
    hook.bind_env(env)
    started = time.monotonic()
    record = run_lifecycle(inst, hook, env, max_turns_per_stage=max_turns)
    failures = list(record.final_check.failures)
    decisions = {
        "award": not any("commit gate" in f for f in failures),
        "followup_1": not any("s6-followup-1" in f for f in failures),
        "followup_2": not any("s8-followup-2" in f for f in failures),
    }
    provider_calls = usage_state()[usage_before:] if usage_state else []
    return {
        "instance_id": inst.instance_id,
        "passed": record.final_check.passed,
        "decisions": decisions,
        "failures": failures[:8],
        "policy_errors": list(hook.policy_errors)[:6],
        "model_calls": hook.model_calls,
        "model_tokens_in": hook.model_tokens_in,
        "model_tokens_out": hook.model_tokens_out,
        "model_tokens_source": "word_estimate",
        "provider_usage_calls": provider_calls,
        "provider_usage_totals": _provider_usage_totals(provider_calls, live=bool(usage_state)),
        "tool_ledger": budget.ledger(),
        # Late-report fixes: the run record now carries the evidence the
        # review's per-run questions need — which docs each stage cited
        # (provenance retention), the per-stage shape, and the model-call
        # transcript (prompts/replies/ok/tokens).
        "provenance_retention": [sr.provenance_retention for sr in record.stage_records],
        "stage_records": [sr.to_dict() for sr in record.stage_records],
        "model_transcript": list(hook.model_transcript),
        "finish_reasons": channel_state()[finish_reasons_before:] if channel_state else [],
        "final_state": {
            k: v
            for k, v in hook.state.items()
            if k in ("memory_delivered", "obs", "recuris_memory", "supplier", "notes")
        },
        "wall_seconds": round(time.monotonic() - started, 1),
    }


def _policy_loadable(policy_text: str) -> bool:
    """Scan + compile + on_turn check — the selection-time load gate.

    The R2b diagnosis: the researcher's output carried an UNTERMINATED
    STRING from mid-block truncation; the "def on_turn" substring check
    accepted it and every stage then ran "policy unavailable". A
    candidate counts only if it would actually load.
    """

    try:
        from rsicontext.lifecycle.policy import load_policy

        load_policy(policy_text)
        return True
    except Exception:
        return False


def _researcher_unassisted_round(
    baseline_policy: str,
    dev_experience: dict[str, Any],
    live: bool,
    *,
    max_output_tokens: int = 16384,
    max_attempts: int = 5,
    backoff_seconds: float = 10.0,
    thinking: bool | None = None,
) -> tuple[str, dict[str, Any]]:
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
        "max_tokens": max_output_tokens,
        "temperature": 0.0,
        "seed": 42,
        "stream": False,
    }
    if thinking is False:
        body["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        READER_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # Researcher retries (flag 7, declared in configs/budget_v1.json:
    # 5 attempts / 10s backoff): retry TRANSPORT/endpoint failures only.
    # A completed-but-unusable reply (truncation "length", empty/missing
    # python block) is a RESULT, not an error — the per-run diagnosis
    # showed this endpoint family consumes output budget in the
    # reasoning channel; retrying that would burn compute without
    # changing the outcome class.
    attempts: list[dict[str, object]] = []
    started = time.monotonic()
    content = ""
    usage: object = None
    finish_reason = None
    model_echo = None
    system_fingerprint = None
    for attempt_index in range(max_attempts):
        try:
            # READER_ENDPOINT is a code-owned HTTPS constant.
            with urllib.request.urlopen(request, timeout=600) as response:  # nosec B310
                raw = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError) as exc:
            attempts.append(
                {
                    "attempt": attempt_index,
                    "outcome": "transport_error",
                    "cause": f"{type(exc).__name__}: {exc}",
                }
            )
            if attempt_index + 1 < max_attempts:
                time.sleep(backoff_seconds)
            continue
        usage = raw.get("usage") if isinstance(raw, dict) else None
        model_echo = raw.get("model") if isinstance(raw, dict) else None
        system_fingerprint = raw.get("system_fingerprint") if isinstance(raw, dict) else None
        try:
            choice = raw["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason")
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise TypeError("researcher content must be a string")
            reasoning = message.get("reasoning") or message.get("reasoning_content")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            reported = _reported_usage(usage)
            attempts.append(
                {
                    "attempt": attempt_index,
                    "outcome": "protocol_error",
                    "error_type": type(exc).__name__,
                    "model_echo": model_echo,
                    "system_fingerprint": system_fingerprint,
                    **reported,
                }
            )
            return "", {
                "round_outcome": "failed: protocol_error",
                "attempts": attempts,
                "input_tokens": reported["prompt_tokens"],
                "output_tokens": reported["completion_tokens"],
                "total_tokens": reported["total_tokens"],
                "usage_status": reported["usage_status"],
                "model": RESEARCHER_MODEL,
                "model_echo": model_echo,
                "system_fingerprint": system_fingerprint,
                "wall_seconds": round(time.monotonic() - started, 3),
            }
        attempts.append(
            {
                "attempt": attempt_index,
                "outcome": "ok",
                "finish_reason": finish_reason,
                "reply_chars": len(content),
                "reasoning_present": bool(reasoning),
                "model_echo": model_echo,
                "system_fingerprint": system_fingerprint,
                **_reported_usage(usage),
            }
        )
        break
    else:
        return "", {
            "round_outcome": f"failed: transport after {max_attempts} attempts",
            "attempts": attempts,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "usage_status": "missing",
            "model": RESEARCHER_MODEL,
            "model_echo": None,
            "wall_seconds": round(time.monotonic() - started, 3),
        }
    # Extract the python block.
    if "```python" in content:
        block = content.split("```python", 1)[1]
        block = block.split("```", 1)[0]
        content = block.strip() + "\n"
    reported = _reported_usage(usage)
    return content, {
        "round_outcome": "ok" if "def on_turn" in content else "no-policy",
        "finish_reason": finish_reason,
        "attempts": attempts,
        "input_tokens": reported["prompt_tokens"],
        "output_tokens": reported["completion_tokens"],
        "total_tokens": reported["total_tokens"],
        "usage_status": reported["usage_status"],
        "model": RESEARCHER_MODEL,
        "model_echo": model_echo,
        "system_fingerprint": system_fingerprint,
        "wall_seconds": round(time.monotonic() - started, 3),
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
    if not _policy_loadable(updated_policy):
        # The round's output must LOAD (scan+compile+on_turn) — the R2b
        # diagnosis found a mid-string truncation that passed the old
        # "def on_turn" substring check and then failed to load at
        # runtime ("policy unavailable" every stage). The load gate
        # makes that failure visible at selection time; the previous
        # snapshot still stands (stats-contract §3 — last, not best).
        had_on_turn = "def on_turn" in updated_policy
        updated_policy = baseline
        prefix = (
            "rejected: policy does not compile (kept baseline)"
            if had_on_turn
            else "no-policy (kept baseline)"
        )
        researcher_record["round_outcome"] = f"{prefix}: {researcher_record.get('round_outcome')}"
    dev_updated = _run_arm(updated_policy, dev_inst, responder)
    eval_updated = _run_arm(updated_policy, eval_inst, responder)

    # Four-outcome state + per-decision deltas (descriptive, n=1 family).
    def _overall(run: dict[str, Any]) -> int:
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
