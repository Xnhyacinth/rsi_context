"""Short-input KEP rule-projection feasibility calibration after R16/R17.

The projected material is authentic pinned source text, but supplying it
directly removes the long-source extraction step. This is development-only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.analysis.k8s_diagnostic_r17 import (
    amendment_text,
    require_r16_observation,
)
from rsicontext.analysis.k8s_diagnostic_r17 import (
    interpret_reply as interpret_r17_reply,
)
from rsicontext.experiment.api import APIProfile
from rsicontext.lifecycle.material_k8s_r14 import SOURCE_FILES, SOURCE_REVISION

R17_TASK_SHA256 = "c3ec0144de17c477e64d2aae97c2c3ec48d3ebb201e6c74c111b09b412ad84ec"
CASE_ORDER = (
    "coarse-membership",
    "coarse-numeric",
    "explicit-membership",
    "explicit-numeric",
)
_README = "keps/sig-node/753-sidecar-containers/README.md"
_RULE_SPANS = (
    (780, 794, "501730735b2c8397ddd7f19062551a0976d497a749122bcfa411f1f116191f34"),
    (835, 838, "4704a8c456cfa800a08d64e11cd7f2416ec68dd648b8ce91fe76e61fbda9b3f2"),
)
_COARSE = "formula=prefix"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def require_r17_observation(task_path: Path) -> dict[str, object]:
    """Bind calibration motivation to the observed, immutable R17 provider run."""

    raw = task_path.read_bytes()
    if _sha(raw) != R17_TASK_SHA256:
        raise ValueError("R17 paid task artifact differs from reviewed bytes")
    task = json.loads(raw)
    if not isinstance(task, dict):
        raise ValueError("R17 task artifact is invalid")
    attempts = task.get("attempts")
    cases = task.get("cases")
    expected_replies = (
        "plan=hold-at-1000m",
        "a_sidecar_m=300\nb_sidecar_m=0",
        "effective_cpu_m=1200\nplan=hold-at-1000m",
        "effective_cpu_m=1200\nplan=hold-at-1000m",
    )
    if (
        task.get("status") != "completed-diagnostic"
        or not isinstance(attempts, list)
        or len(attempts) != 4
        or not isinstance(cases, list)
        or len(cases) != 4
    ):
        raise ValueError("R17 paid diagnostic lacks its four target calls")
    for attempt, reply in zip(attempts, expected_replies, strict=True):
        if (
            not isinstance(attempt, dict)
            or attempt.get("reply") != reply
            or attempt.get("status") != "ok"
            or attempt.get("finish_reason") != "stop"
            or not isinstance(attempt.get("provider_usage"), dict)
        ):
            raise ValueError("R17 paid target reply differs from reviewed evidence")
    return {
        "r17_task_sha256": R17_TASK_SHA256,
        "observed_membership": {"a_sidecar_m": 300, "b_sidecar_m": 0},
        "observed_effective_cpu_m": 1200,
        "observed_plan": "hold-at-1000m",
    }


def projected_rule(source_root: Path) -> tuple[str, list[dict[str, object]]]:
    """Extract two exact source spans without inserting any case answer."""

    raw = (source_root / _README).read_bytes()
    if _sha(raw) != SOURCE_FILES[_README]:
        raise ValueError("R18 KEP source README differs from pinned bytes")
    lines = raw.splitlines(keepends=True)
    blocks: list[str] = []
    ledger: list[dict[str, object]] = []
    for first, last, expected in _RULE_SPANS:
        block = b"".join(lines[first - 1 : last])
        if _sha(block) != expected:
            raise ValueError(f"R18 source rule span {first}-{last} drifted")
        blocks.append(block.decode("utf-8"))
        ledger.append(
            {
                "first_line": first,
                "last_line": last,
                "raw_sha256": expected,
                "utf8_bytes": len(block),
            }
        )
    return "\n".join(blocks).rstrip(), ledger


def prompts(amendment: str, rule: str) -> dict[str, str]:
    """Use the same question and amendment under coarse versus exact source rule."""

    if not rule or "InitContainerUse(i)" not in rule:
        raise ValueError("R18 explicit material lacks the ordered-prefix equation")
    common = (
        "Apply the supplied resource rule to the visible scheduling amendment. "
        "Use the actual init-container order and CPU requests."
    )
    membership = (
        "For regular init A and regular init B separately, report the total "
        "native-sidecar CPU request counted alongside that init. Return exactly "
        "two lines: a_sidecar_m=<nonnegative integer> and "
        "b_sidecar_m=<nonnegative integer>. Do not compute the overall Pod "
        "effective request or choose a scheduling plan."
    )
    numeric = (
        "Calculate the Pod's effective CPU request in millicores, then choose "
        "the plan using the 1000m node capacity. Return exactly two lines: "
        "effective_cpu_m=<nonnegative integer> and plan=hold-at-1000m or "
        "plan=admit-at-1000m. No explanation."
    )

    def render(question: str, material: str) -> str:
        return (
            common
            + "\n\n"
            + question
            + "\n\nSupplied resource rule:\n"
            + material
            + "\n\nOrder amendment:\n"
            + amendment
        )

    return {
        CASE_ORDER[0]: render(membership, _COARSE),
        CASE_ORDER[1]: render(numeric, _COARSE),
        CASE_ORDER[2]: render(membership, rule),
        CASE_ORDER[3]: render(numeric, rule),
    }


def interpret_reply(case: str, reply: str) -> dict[str, object]:
    """Apply the R17 evaluator-only oracle to the matching R18 probe."""

    if case not in CASE_ORDER:
        raise ValueError("unregistered R18 calibration case")
    r17_case = "rule-membership" if case.endswith("membership") else "numeric-without-prior"
    return interpret_r17_reply(r17_case, reply)


def build_registration(
    source_root: Path,
    r16_task: Path,
    r17_task: Path,
    *,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
) -> dict[str, object]:
    """Freeze exact short prompts, material hashes, geometry and call envelope."""

    if profile.chat_template_enable_thinking is not False or profile.system_prompt is None:
        raise ValueError("R18 requires the frozen non-thinking two-message profile")
    r16 = require_r16_observation(r16_task)
    r17 = require_r17_observation(r17_task)
    amendment = amendment_text(source_root)
    rule, spans = projected_rule(source_root)
    material = prompts(amendment, rule)
    registered: list[dict[str, object]] = []
    total_input = 0
    for case in CASE_ORDER:
        prompt = material[case]
        messages = [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": prompt},
        ]
        evidence = _COARSE if case.startswith("coarse") else rule
        geometry = measure_chat_geometry(
            tokenizer, messages, enable_thinking=False, evidence=evidence, query=amendment
        )
        tokens = geometry["rendered_input_tokens"]
        if (
            geometry["span_status"] != "unique_later_query"
            or not isinstance(tokens, int)
            or tokens + profile.max_output_tokens > profile.evaluation_max_model_len
        ):
            raise ValueError("R18 calibration has invalid final-chat geometry")
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
        registered.append(
            {
                "case": case,
                "prompt_sha256": _sha(prompt.encode()),
                "request_sha256": _sha(_canonical(payload)),
                "local_template_geometry": geometry,
            }
        )
    return {
        "schema_version": 1,
        "scope": "r18-kep-short-input-rule-projection-calibration",
        "interpretation": "development feasibility only; no source-dependency or parent claim",
        "r16_observation": r16,
        "r17_observation": r17,
        "source_revision": SOURCE_REVISION,
        "source_readme_sha256": SOURCE_FILES[_README],
        "source_rule_spans": spans,
        "projected_rule_sha256": _sha(rule.encode()),
        "coarse_material_sha256": _sha(_COARSE.encode()),
        "amendment_sha256": _sha(amendment.encode()),
        "profile_sha256": profile.profile_hash,
        "case_order": list(CASE_ORDER),
        "target_call_cap": len(CASE_ORDER),
        "auxiliary_call_cap": 0,
        "local_input_tokens": total_input,
        "requested_output_tokens": len(CASE_ORDER) * profile.max_output_tokens,
        "local_input_plus_requested_ceiling": total_input
        + len(CASE_ORDER) * profile.max_output_tokens,
        "requests": registered,
    }


__all__ = [
    "CASE_ORDER",
    "R17_TASK_SHA256",
    "build_registration",
    "interpret_reply",
    "projected_rule",
    "prompts",
    "require_r17_observation",
]
