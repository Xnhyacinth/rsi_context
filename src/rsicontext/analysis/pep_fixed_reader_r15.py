"""Offline registration and bounded model screen for the R15 PEP card.

The screen reuses the strict fixed-reader capture from the OTel development
pilot. Only benchmark-owned policy text is executed; candidate policy code is
never loaded here. Provider use is possible only through an injected transport.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.analysis.otel_siflow_pilot import _Worker
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_pep_r14 import SourceVariant, build_pep_license_sessions
from rsicontext.lifecycle.pep_model_fixed_r15 import pep_model_fixed_r15_text
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance, canonical_instance_json
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

Arm = Literal["full", "identity-only", "source-free"]
MAX_TRAJECTORIES = 6
MAX_WORKER_ATTEMPTS = 12
CASE_ORDER = (
    "full-pep621",
    "full-pep639",
    "identity-only-pep621",
    "identity-only-pep639",
    "source-free-pep621",
    "source-free-pep639",
)
PROFILE_ID = "siflow-qwen3.6-27b-r15-bc-dev-2048"
_SYSTEM = (
    "You are the project worker. Follow the requested output format exactly. "
    "For questions, return only the answer phrase."
)
_S1_QUERY = (
    "Question: For the archival fixture's MIT declaration, which [project].license "
    "form does this historical source prefer without deprecation? Return exactly "
    "form=license-table, form=license-string, or form=unknown if the source gives no rule."
)
_S2_QUERY = (
    "Question: Choose the archival fixture plan using the retained finding and request. "
    "If the finding is unknown, use only what you can justify. Return exactly "
    "plan=license-table or plan=license-string."
)
_FORM_REPLIES = ("form=license-table", "form=license-string", "form=unknown")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _profile_payload(profile: APIProfile, prompt: str) -> dict[str, object]:
    if (
        profile.id != PROFILE_ID
        or profile.provider != "Siflow"
        or profile.allowed_host != "api.siflow.cn"
        or profile.model != "Qwen/Qwen3.6-27B"
        or profile.protocol != "chat-completions-sse"
        or profile.evaluation_max_model_len != 262144
        or profile.max_output_tokens != 2048
        or profile.seed != 42
        or profile.temperature != 0.0
        or profile.chat_template_enable_thinking is not False
        or profile.system_prompt != _SYSTEM
    ):
        raise ValueError("PEP worker profile differs from shared R15 Qwen profile")
    return {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": profile.max_output_tokens,
        "messages": [
            {"content": _SYSTEM, "role": "system"},
            {"content": prompt, "role": "user"},
        ],
        "model": profile.model,
        "seed": profile.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
    }


@dataclass(frozen=True, slots=True)
class PepCase:
    name: str
    variant: SourceVariant
    arm: Arm
    sessions: tuple[LifecycleInstance, LifecycleInstance]

    @property
    def source(self) -> str:
        return self.sessions[0].stages[0].documents[0].text

    @property
    def source_url(self) -> str:
        return self.sessions[0].stages[0].documents[0].source_url

    @property
    def request(self) -> str:
        return self.sessions[1].stages[1].documents[0].text

    @property
    def world_sha256(self) -> list[str]:
        return [_sha(canonical_instance_json(session).encode()) for session in self.sessions]


def build_pep_cases(source_root: Path) -> tuple[PepCase, ...]:
    """Register authentic and constructed arms without changing private oracles."""

    cases: list[PepCase] = []
    arms: tuple[Arm, ...] = ("full", "identity-only", "source-free")
    variants: tuple[tuple[SourceVariant, str], ...] = (("pep621", "621"), ("pep639", "639"))
    for arm in arms:
        for variant, number in variants:
            first, second = build_pep_license_sessions(source_root, variant=variant)
            survey = first.stages[0]
            source = survey.documents[0]
            if arm == "identity-only":
                if f"PEP: {number}" not in source.text:
                    raise ValueError("PEP source header lacks registered identity")
                source = replace(
                    source,
                    text=(
                        "[[doc:historical-license-source]] "
                        "Pinned historical license metadata proposal\n"
                        f"PEP: {number}\n[all substantive rule text withheld]"
                    ),
                )
            elif arm == "source-free":
                source = replace(
                    source,
                    title="Source withheld",
                    text="[[doc:historical-license-source]] [source withheld]",
                    source_url="benchmark:withheld",
                )
            if arm != "full":
                first = replace(
                    first, stages=(replace(survey, documents=(source,)), *first.stages[1:])
                )
            cases.append(PepCase(f"{arm}-{variant}", variant, arm, (first, second)))
    if tuple(case.name for case in cases) != CASE_ORDER:
        raise AssertionError("PEP case order changed")
    if cases[4].source != cases[5].source or cases[4].source_url != cases[5].source_url:
        raise ValueError("source-free cases leak version identity")
    return tuple(cases)


def _run_case(
    case: PepCase,
    responder: Callable[[str], str],
) -> tuple[dict[str, object], ProjectState]:
    env = ProjectState()
    budget = ToolBudget(max_calls=8)
    registry = DocumentRegistry()

    def factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(
            state,
            pep_model_fixed_r15_text(),
            tool_budget=budget,
            registry=registry,
            responder=responder,
        )

    record = run_session_sequence(
        list(case.sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
    )
    final_plan = env.records.get("license_format_decision", {}).get("plan")
    gate = case.sessions[1].stages[2].commit_precondition
    legal = gate.get("legal_plans") if isinstance(gate, Mapping) else None
    return (
        {
            "case": case.name,
            "arm": case.arm,
            "variant": case.variant,
            "session_passed": [session.passed for session in record.sessions],
            "session_failures": [session.failures for session in record.sessions],
            "policy_errors": [session.policy_errors for session in record.sessions],
            "persist_ok": [session.persist_ok for session in record.sessions],
            "carry_bytes": [session.carry_bytes for session in record.sessions],
            "model_calls": [session.model_calls for session in record.sessions],
            "final_plan": final_plan,
            "later_plan_legal": (
                isinstance(final_plan, str)
                and isinstance(legal, (list, tuple))
                and final_plan in legal
            ),
            "source_visible_sha256": _sha(case.source.encode()),
            "source_url_sha256": _sha(case.source_url.encode()),
            "request_sha256": _sha(case.request.encode()),
            "world_sha256": case.world_sha256,
            "policy_transcript": [
                entry for session in record.sessions for entry in session.model_transcript
            ],
            "action_kinds": [action.kind for action in env.transcript],
            "receipts": {
                key: {
                    "check": env.records[key].get("check"),
                    "subject": env.records[key].get("subject"),
                    "verdict": env.records[key].get("verdict"),
                    "protocol_revision": env.records[key].get("protocol_revision"),
                }
                for key in ("review-receipt", "license-receipt")
                if key in env.records
            },
        },
        env,
    )


def _geometry(
    tokenizer: ChatTokenizer, profile: APIProfile, case: PepCase, prompt: str, stage: str
) -> dict[str, object]:
    payload = _profile_payload(profile, prompt)
    messages = payload["messages"]
    if not isinstance(messages, list):
        raise TypeError("profile messages must be a list")
    if stage == "source-survey":
        evidence, query = case.source, _S1_QUERY
        if case.source not in prompt or case.source_url not in prompt:
            raise ValueError("survey request lacks registered source material")
    elif stage == "archive-request":
        evidence, query = case.request, _S2_QUERY
        if case.request not in prompt or case.source in prompt:
            raise ValueError("resumed request material boundary changed")
    else:
        raise ValueError(f"unexpected model stage: {stage}")
    local = measure_chat_geometry(
        tokenizer, messages, enable_thinking=False, evidence=evidence, query=query
    )
    if local.get("span_status") != "unique_later_query":
        raise ValueError("PEP evidence and later question are not uniquely located")
    count = local.get("rendered_input_tokens")
    if (
        not isinstance(count, int)
        or count + profile.max_output_tokens > profile.evaluation_max_model_len
    ):
        raise ValueError("PEP worker request exceeds frozen model context")
    return {
        "stage": stage,
        "prompt_sha256": _sha(prompt.encode()),
        "prompt_utf8_bytes": len(prompt.encode()),
        "request_sha256": _sha(_canonical(payload)),
        "evidence_sha256": _sha(evidence.encode()),
        "query_sha256": _sha(query.encode()),
        "local_template_geometry": local,
    }


def build_geometry_report(
    tokenizer: ChatTokenizer, profile: APIProfile, cases: tuple[PepCase, ...]
) -> dict[str, object]:
    """Measure every valid S1 branch without dispatching a provider call."""

    _profile_payload(profile, "geometry preflight")
    if tuple(case.name for case in cases) != CASE_ORDER:
        raise ValueError("PEP case registration changed")
    registered: dict[str, dict[str, object]] = {}
    case_reports: list[dict[str, object]] = []
    worst_case_total = 0

    def fake_responder(bucket: list[str], finding: str) -> Callable[[str], str]:
        def fake(prompt: str) -> str:
            bucket.append(prompt)
            if prompt.startswith("Historical source URL: "):
                return finding
            return "plan=license-table"

        return fake

    for case in cases:
        branches: list[dict[str, object]] = []
        branch_input_totals: list[int] = []
        for finding in _FORM_REPLIES:
            prompts: list[str] = []
            _run_case(case, fake_responder(prompts, finding))
            if len(prompts) != 2:
                raise ValueError("PEP fixed policy must make two calls per valid response branch")
            calls = [
                _geometry(tokenizer, profile, case, prompts[0], "source-survey"),
                _geometry(tokenizer, profile, case, prompts[1], "archive-request"),
            ]
            for call in calls:
                key = str(call["prompt_sha256"])
                prior = registered.setdefault(key, call)
                if prior != call:
                    raise ValueError("registered PEP prompt has conflicting geometry")
            counts: list[int] = []
            for call in calls:
                local = call.get("local_template_geometry")
                count = local.get("rendered_input_tokens") if isinstance(local, Mapping) else None
                if not isinstance(count, int):
                    raise ValueError("PEP local geometry lacks rendered token count")
                counts.append(count)
            branch_input_totals.append(sum(counts))
            branches.append({"source_finding": finding, "calls": calls})
        case_worst = max(branch_input_totals)
        worst_case_total += case_worst
        case_reports.append(
            {
                "case": case.name,
                "variant": case.variant,
                "arm": case.arm,
                "source_visible_sha256": _sha(case.source.encode()),
                "source_url_sha256": _sha(case.source_url.encode()),
                "request_sha256": _sha(case.request.encode()),
                "world_sha256": case.world_sha256,
                "local_worst_case_input_tokens": case_worst,
                "branches": branches,
            }
        )
    return {
        "schema_version": 1,
        "scope": "pep621_639_three_arm_fixed_policy_local_geometry_only",
        "profile_id": profile.id,
        "profile_sha256": profile.profile_hash,
        "policy_sha256": _sha(pep_model_fixed_r15_text().encode()),
        "registered_case_order": CASE_ORDER,
        "trajectory_cap": MAX_TRAJECTORIES,
        "worker_attempt_cap": MAX_WORKER_ATTEMPTS,
        "local_worst_case_total_input_tokens": worst_case_total,
        "profile_max_total_output_tokens": MAX_WORKER_ATTEMPTS * profile.max_output_tokens,
        "cases": case_reports,
        "registered_requests": registered,
        "limitations": (
            "Exact for pinned local Qwen template and enumerated valid S1 replies; "
            "provider parity and model behavior require separate tests."
        ),
    }


def run_pep_screen(
    cases: tuple[PepCase, ...],
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    geometry_report: Mapping[str, object],
    transport: Transport,
) -> dict[str, object]:
    """Run pre-registered cases, stopping before any unregistered paid call."""

    _profile_payload(profile, "screen preflight")
    if tuple(case.name for case in cases) != CASE_ORDER:
        raise ValueError("PEP case registration changed")
    registered_order = geometry_report.get("registered_case_order")
    if (
        geometry_report.get("profile_id") != profile.id
        or geometry_report.get("profile_sha256") != profile.profile_hash
        or geometry_report.get("policy_sha256") != _sha(pep_model_fixed_r15_text().encode())
        or not isinstance(registered_order, (list, tuple))
        or tuple(registered_order) != CASE_ORDER
        or geometry_report.get("worker_attempt_cap") != MAX_WORKER_ATTEMPTS
    ):
        raise ValueError("PEP geometry report differs from frozen screen inputs")
    registered = geometry_report.get("registered_requests")
    if not isinstance(registered, Mapping):
        raise ValueError("PEP geometry report lacks registered requests")
    case_index = 0
    case_start = 0

    def preflight(prompt: str) -> dict[str, object]:
        if len(worker.attempts) >= MAX_WORKER_ATTEMPTS:
            raise ValueError("PEP global worker attempt cap reached")
        attempt_in_case = len(worker.attempts) - case_start
        if attempt_in_case >= 2:
            raise ValueError("PEP per-case worker attempt cap reached")
        digest = _sha(prompt.encode())
        expected = registered.get(digest)
        if not isinstance(expected, dict) or expected.get("prompt_sha256") != digest:
            raise ValueError("PEP worker prompt is not preregistered")
        permitted = geometry_report.get("cases")
        if not isinstance(permitted, list) or case_index >= len(permitted):
            raise ValueError("PEP case is not registered")
        case_record = permitted[case_index]
        if not isinstance(case_record, dict) or case_record.get("case") != cases[case_index].name:
            raise ValueError("PEP case identity differs from geometry")
        if case_record.get("world_sha256") != cases[case_index].world_sha256:
            raise ValueError("PEP world bytes differ from geometry")
        branches = case_record.get("branches")
        if not isinstance(branches, list):
            raise ValueError("PEP case lacks registered response branches")
        allowed: set[str] = set()
        for branch in branches:
            if not isinstance(branch, dict):
                raise ValueError("PEP response branch is malformed")
            calls = branch.get("calls")
            if not isinstance(calls, list) or len(calls) != 2:
                raise ValueError("PEP response branch lacks two requests")
            call = calls[attempt_in_case]
            if not isinstance(call, dict) or not isinstance(call.get("prompt_sha256"), str):
                raise ValueError("PEP response branch request is malformed")
            allowed.add(call["prompt_sha256"])
        stage = ("source-survey", "archive-request")[attempt_in_case]
        if digest not in allowed or expected.get("stage") != stage:
            raise ValueError("PEP request is registered under a different case or stage")
        return expected

    worker = _Worker(profile, endpoint, preflight, transport)
    outcomes: list[dict[str, object]] = []
    status = "completed-development-screen"
    for case in cases:
        case_index = len(outcomes)
        case_start = len(worker.attempts)
        outcome, _env = _run_case(case, worker)
        outcome["worker_attempt_indexes"] = list(range(case_start, len(worker.attempts)))
        outcomes.append(outcome)
        if worker.failed:
            status = "stopped-on-worker-failure"
            break
        if case.arm == "full" and outcome["session_passed"] != [True, True]:
            status = "stopped-on-full-task-failure"
            break
    usages = [attempt.get("provider_usage") for attempt in worker.attempts]
    return {
        "schema_version": 1,
        "scope": "pep_adaptive_fixed_reader_development_only",
        "status": status,
        "profile_id": profile.id,
        "profile_sha256": profile.profile_hash,
        "policy_sha256": _sha(pep_model_fixed_r15_text().encode()),
        "geometry_report_sha256": _sha(_canonical(geometry_report)),
        "registered_case_order": CASE_ORDER,
        "trajectory_cap": MAX_TRAJECTORIES,
        "worker_attempt_cap": MAX_WORKER_ATTEMPTS,
        "worker_attempt_count": len(worker.attempts),
        "provider_usage_total": {
            "input_tokens": sum(
                int(usage["input_tokens"]) for usage in usages if isinstance(usage, dict)
            ),
            "output_tokens": sum(
                int(usage["output_tokens"]) for usage in usages if isinstance(usage, dict)
            ),
            "unknown_usage_attempts": sum(usage is None for usage in usages),
        },
        "attempts": worker.attempts,
        "preflight_failures": worker.preflight_failures,
        "cases": outcomes,
    }


__all__ = [
    "CASE_ORDER",
    "MAX_TRAJECTORIES",
    "MAX_WORKER_ATTEMPTS",
    "PepCase",
    "build_geometry_report",
    "build_pep_cases",
    "run_pep_screen",
]
