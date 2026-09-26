"""Prospective, R16-conditioned KEP arithmetic and prior-decision diagnostic.

This is development evidence about one observed failure, not a benchmark
trajectory or a fresh source-dependency test. The prompts never contain the
private legal plan or the evaluator's effective-request calculation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.analysis.k8s_fixed_reader_r16 import case_materials
from rsicontext.experiment.api import APIProfile
from rsicontext.lifecycle.material_k8s_r14 import build_k8s_resource_order_sessions

R16_TASK_SHA256 = "15520c0aedba2d471d7e85085b1d05813a366b22f401ae5b641e669468e6a36d"
R16_LATER_PROMPT_SHA256 = "f6cf02f400497f844984ba116b96cc16102bc78a75f6cc952e26871401f1bb21"
R16_AMENDMENT_SHA256 = "198bf01062a787132bab32cdb58e624cf31625434ebdd4d04b2c007629ee5431"
R16_OBSERVED_FORMULA = "formula=prefix"
R16_OBSERVED_FIRST_PLAN = "hold-at-1000m"
CASE_ORDER = (
    "legacy-with-prior",
    "rule-membership",
    "numeric-with-prior",
    "numeric-without-prior",
)
_PLAN = re.compile(r"plan=(hold-at-1000m|admit-at-1000m)")
_NUMERIC = re.compile(r"effective_cpu_m=([0-9]{1,5})\nplan=(hold-at-1000m|admit-at-1000m)")
_MEMBERSHIP = re.compile(r"a_sidecar_m=([0-9]{1,5})\nb_sidecar_m=([0-9]{1,5})")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def require_r16_observation(task_path: Path) -> dict[str, str]:
    """Bind the conditional diagnostic to the immutable observed R16 failure."""

    raw = task_path.read_bytes()
    if _sha(raw) != R16_TASK_SHA256:
        raise ValueError("R16 paid task artifact differs from the reviewed observation")
    task = json.loads(raw)
    if not isinstance(task, dict):
        raise ValueError("R16 paid task artifact is invalid")
    attempts = task.get("attempts")
    cases = task.get("cases")
    if not isinstance(attempts, list) or len(attempts) != 3 or not isinstance(cases, list):
        raise ValueError("R16 observation lacks the three authentic task calls")
    expected = (
        ("source-survey", R16_OBSERVED_FORMULA),
        ("resource-request-stage", "plan=" + R16_OBSERVED_FIRST_PLAN),
        ("resource-order-change", "plan=" + R16_OBSERVED_FIRST_PLAN),
    )
    for attempt, (stage, reply) in zip(attempts, expected, strict=True):
        if (
            not isinstance(attempt, dict)
            or attempt.get("stage") != stage
            or attempt.get("reply") != reply
            or attempt.get("status") != "ok"
            or attempt.get("finish_reason") != "stop"
            or not isinstance(attempt.get("provider_usage"), dict)
        ):
            raise ValueError("R16 task reply differs from the reviewed observation")
    if attempts[2].get("prompt_sha256") != R16_LATER_PROMPT_SHA256:
        raise ValueError("R16 later prompt differs from the reviewed observation")
    case = cases[0] if len(cases) == 1 else None
    if (
        not isinstance(case, dict)
        or case.get("case") != "full-source"
        or case.get("session_passed") != [True, False]
        or case.get("final_plan") != R16_OBSERVED_FIRST_PLAN
    ):
        raise ValueError("R16 full-source outcome differs from the reviewed failure")
    return {
        "r16_task_sha256": R16_TASK_SHA256,
        "observed_formula": R16_OBSERVED_FORMULA,
        "observed_first_plan": R16_OBSERVED_FIRST_PLAN,
        "observed_later_plan": R16_OBSERVED_FIRST_PLAN,
    }


def amendment_text(source_root: Path) -> str:
    """Take the same model-visible R16 full-source amendment, not an edited task."""

    pair = dict(case_materials(build_k8s_resource_order_sessions(source_root)))["full-source"]
    text = pair[1].stages[1].documents[0].text
    if _sha(text.encode()) != R16_AMENDMENT_SHA256:
        raise ValueError("R16 KEP amendment material differs from the reviewed bytes")
    condition = pair[1].stages[2].commit_precondition
    if not isinstance(condition, Mapping) or condition.get("legal_plans") != [
        "admit-at-1000m"
    ]:
        raise ValueError("R16 private legal-plan contract drifted")
    return text


def prompts(amendment: str) -> dict[str, str]:
    """Freeze four target calls probing rule membership, arithmetic and prior cue."""

    if _sha(amendment.encode()) != R16_AMENDMENT_SHA256:
        raise ValueError("amendment bytes differ from R16")
    common = (
        "Apply the retained resource calculation to the visible scheduling "
        "request. Use the actual init-container order and CPU requests. "
    )
    formula = "\n\nRetained formula: " + R16_OBSERVED_FORMULA
    prior = "\nPrior decision: " + R16_OBSERVED_FIRST_PLAN
    query = "\n\nOrder amendment:\n" + amendment
    legacy = (
        common
        + "Return exactly plan=hold-at-1000m or plan=admit-at-1000m, with no explanation."
        + formula
        + prior
        + query
    )
    if _sha(legacy.encode()) != R16_LATER_PROMPT_SHA256:
        raise ValueError("reconstructed R16 later prompt does not match the paid request")
    numeric = (
        common
        + "First calculate the Pod's effective CPU request in millicores using "
        "the actual order. Then choose the plan using the 1000m node capacity. "
        "Return exactly two lines: effective_cpu_m=<nonnegative integer> and "
        "plan=hold-at-1000m or plan=admit-at-1000m. No explanation."
        + formula
    )
    membership = (
        common
        + "For regular init A and regular init B separately, report the total "
        "native-sidecar CPU request counted alongside that init under the "
        "retained formula. Return exactly two lines: a_sidecar_m=<nonnegative "
        "integer> and b_sidecar_m=<nonnegative integer>. Do not compute the "
        "overall Pod effective request or choose a scheduling plan."
        + formula
    )
    return {
        CASE_ORDER[0]: legacy,
        CASE_ORDER[1]: membership + query,
        CASE_ORDER[2]: numeric + prior + query,
        CASE_ORDER[3]: numeric + query,
    }


def interpret_reply(case: str, reply: str) -> dict[str, object]:
    """Evaluator-only diagnostic: separate arithmetic from threshold mapping."""

    if case not in CASE_ORDER:
        raise ValueError("unregistered R17 diagnostic case")
    answer = reply.strip()
    if case == CASE_ORDER[0]:
        match = _PLAN.fullmatch(answer)
        return {
            "valid_format": match is not None,
            "effective_cpu_m": None,
            "plan": match.group(1) if match else None,
            "arithmetic_correct": None,
            "threshold_consistent": None,
            "legal_plan": bool(match and match.group(1) == "admit-at-1000m"),
        }
    if case == CASE_ORDER[1]:
        membership = _MEMBERSHIP.fullmatch(answer)
        a_sidecar = int(membership.group(1)) if membership else None
        b_sidecar = int(membership.group(2)) if membership else None
        return {
            "valid_format": membership is not None,
            "a_sidecar_m": a_sidecar,
            "b_sidecar_m": b_sidecar,
            "rule_membership_correct": a_sidecar == 0 and b_sidecar == 300,
            "effective_cpu_m": None,
            "plan": None,
            "arithmetic_correct": None,
            "threshold_consistent": None,
            "legal_plan": None,
        }
    match = _NUMERIC.fullmatch(answer)
    if match is None:
        return {
            "valid_format": False,
            "effective_cpu_m": None,
            "plan": None,
            "arithmetic_correct": False,
            "threshold_consistent": None,
            "legal_plan": False,
        }
    effective = int(match.group(1))
    plan = match.group(2)
    return {
        "valid_format": True,
        "effective_cpu_m": effective,
        "plan": plan,
        "arithmetic_correct": effective == 800,
        "threshold_consistent": plan
        == ("admit-at-1000m" if effective <= 1000 else "hold-at-1000m"),
        "legal_plan": plan == "admit-at-1000m",
    }


def build_registration(
    source_root: Path, task_path: Path, *, profile: APIProfile, tokenizer: ChatTokenizer
) -> dict[str, object]:
    """Record exact materials, final-chat geometry, request hashes and call cap."""

    observation = require_r16_observation(task_path)
    amendment = amendment_text(source_root)
    if profile.chat_template_enable_thinking is not False or profile.system_prompt is None:
        raise ValueError("R17 requires the pinned two-message non-thinking profile")
    items: list[dict[str, object]] = []
    total_input = 0
    for case, prompt in prompts(amendment).items():
        messages = [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": prompt},
        ]
        geometry = measure_chat_geometry(
            tokenizer,
            messages,
            enable_thinking=False,
            evidence=R16_OBSERVED_FORMULA,
            query=amendment,
        )
        tokens = geometry["rendered_input_tokens"]
        if (
            geometry["span_status"] != "unique_later_query"
            or not isinstance(tokens, int)
            or tokens + profile.max_output_tokens > profile.evaluation_max_model_len
        ):
            raise ValueError("R17 diagnostic has invalid exact chat geometry")
        total_input += tokens
        payload = {
            "max_tokens": profile.max_output_tokens,
            "messages": messages,
            "model": profile.model,
            "seed": profile.seed,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        items.append(
            {
                "case": case,
                "prompt_sha256": _sha(prompt.encode()),
                "request_sha256": _sha(_canonical(payload)),
                "local_template_geometry": geometry,
            }
        )
    return {
        "schema_version": 1,
        "scope": "r17-kep-r16-conditioned-mechanism-diagnostic",
        "interpretation": "post-hoc development diagnostic; no independent source-dependency claim",
        "r16_observation": observation,
        "amendment_sha256": R16_AMENDMENT_SHA256,
        "profile_sha256": profile.profile_hash,
        "call_order": list(CASE_ORDER),
        "target_call_cap": len(CASE_ORDER),
        "auxiliary_call_cap": 0,
        "local_input_tokens": total_input,
        "requested_output_tokens": len(CASE_ORDER) * profile.max_output_tokens,
        "local_input_plus_requested_ceiling": total_input
        + len(CASE_ORDER) * profile.max_output_tokens,
        "requests": items,
    }


__all__ = [
    "CASE_ORDER",
    "R16_TASK_SHA256",
    "amendment_text",
    "build_registration",
    "interpret_reply",
    "prompts",
    "require_r16_observation",
]
