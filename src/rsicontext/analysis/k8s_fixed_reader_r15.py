"""Offline, bounded fixed-reader screen for the KEP-753 resource-order card.

The same runner can accept a fake SSE transport for contract tests. No live
transport is wired here; the R15 CLI refuses paid execution until preregistration
and provider canaries are frozen by the integration owner.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.analysis.otel_siflow_pilot import _Worker
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.k8s_model_fixed_r15 import k8s_model_fixed_policy_text
from rsicontext.lifecycle.material_k8s_r14 import SOURCE_FILES, build_k8s_resource_order_sessions
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance, canonical_instance_json
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

PROFILE_ID = "siflow-qwen3.6-27b-r15-bc-dev-2048"
PROFILE_SHA256 = "b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69"
WORLD_SHA256 = (
    "4565339a3636212ede2dd7fd3ef9e4f4d961e613c939a0f6c2a6010e3e96042a",
    "542cae04f4b34a356bf321771bc988590bb238dd49afad7250c69cd57100a99e",
)
CASE_ORDER = ("full-source", "source-free", "both-order-rules-neutralized")
MAX_TRAJECTORIES = 3
MAX_WORKER_ATTEMPTS = 9
_MARKER = "[[doc:kep753-resource-source]]\n"
_WITHHELD = _MARKER + "[SOURCE WITHHELD: no KEP rule supplied]"
_README = "keps/sig-node/753-sidecar-containers/README.md"
# Complete LF-terminated line blocks: first formula and its explanation, then
# the later equivalent calculation. Everything outside these blocks stays exact.
_RULE_SPANS = (
    (780, 794, "501730735b2c8397ddd7f19062551a0976d497a749122bcfa411f1f116191f34"),
    (835, 848, "8cf06b1272661b01402a79e3c74eff995c018074f2f237e3b76bfc7ca38fdf42"),
)


@dataclass(frozen=True, slots=True)
class SyntheticTransport:
    """Explicit offline transport capability; never resolve a live endpoint."""

    handler: Transport

    def __call__(self, request: urllib.request.Request, timeout: float) -> bytes:
        return self.handler(request, timeout)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def neutralize_both_order_rules(source_text: str) -> tuple[str, dict[str, object]]:
    """Remove both explicit ordered-prefix rule blocks from one pinned README.

    Exact byte slices outside the two registered blocks are unchanged. The
    retained simpler upper-bound formula remains as an alternative source cue.
    """

    if not source_text.startswith(_MARKER):
        raise ValueError("KEP source marker is missing")
    raw = source_text[len(_MARKER) :].encode("utf-8")
    if _sha(raw) != SOURCE_FILES[_README]:
        raise ValueError("intervention requires the complete pinned KEP README")
    lines = raw.splitlines(keepends=True)
    edits: list[tuple[int, int, bytes, bytes]] = []
    for start_line, end_line, expected in _RULE_SPANS:
        start = sum(len(line) for line in lines[: start_line - 1])
        end = sum(len(line) for line in lines[:end_line])
        before = raw[start:end]
        if _sha(before) != expected:
            raise ValueError(f"KEP ordered-rule span {start_line}-{end_line} drifted")
        replacement = (
            b"[Ordered-prefix calculation withheld for this diagnostic arm.]\n"
            + b"\n" * (before.count(b"\n") - 1)
        )
        edits.append((start, end, before, replacement))
    changed = raw
    for start, end, _before, replacement in reversed(edits):
        changed = changed[:start] + replacement + changed[end:]
    source_cursor = changed_cursor = 0
    for start, end, _before, replacement in edits:
        untouched = raw[source_cursor:start]
        if changed[changed_cursor : changed_cursor + len(untouched)] != untouched:
            raise ValueError("intervention altered bytes outside the rule spans")
        source_cursor = end
        changed_cursor += len(untouched) + len(replacement)
    if changed[changed_cursor:] != raw[source_cursor:]:
        raise ValueError("intervention altered the source suffix")
    if any(
        phrase in changed
        for phrase in (
            b"before the first sidecar containers",
            b"sidecar containers with index < i",
            b"sidecar resource usage needs to be summed",
        )
    ):
        raise ValueError("ordered-prefix rule still appears after intervention")
    ledger = {
        "original_raw_sha256": _sha(raw),
        "intervened_raw_sha256": _sha(changed),
        "spans": [
            {
                "start_line": _RULE_SPANS[index][0],
                "end_line": _RULE_SPANS[index][1],
                "start_byte": start,
                "end_byte": end,
                "original_sha256": _sha(before),
                "replacement_sha256": _sha(replacement),
            }
            for index, (start, end, before, replacement) in enumerate(edits)
        ],
        "untouched_bytes_exact": True,
    }
    return _MARKER + changed.decode("utf-8"), ledger


def _source_variant(
    sessions: tuple[LifecycleInstance, LifecycleInstance], text: str
) -> tuple[LifecycleInstance, LifecycleInstance]:
    first, second = sessions
    survey = first.stages[0]
    changed = replace(survey.documents[0], text=text)
    return replace(first, stages=(replace(survey, documents=(changed,)), *first.stages[1:])), second


def case_materials(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
) -> tuple[tuple[str, tuple[LifecycleInstance, LifecycleInstance]], ...]:
    original = sessions[0].stages[0].documents[0].text
    neutralized, _ledger = neutralize_both_order_rules(original)
    return (
        (CASE_ORDER[0], sessions),
        (CASE_ORDER[1], _source_variant(sessions, _WITHHELD)),
        (CASE_ORDER[2], _source_variant(sessions, neutralized)),
    )


def _verify_base_world(sessions: tuple[LifecycleInstance, LifecycleInstance]) -> None:
    actual = tuple(_sha(canonical_instance_json(world).encode()) for world in sessions)
    if actual != WORLD_SHA256:
        raise ValueError("R15 KEP canonical evaluator world differs from preregistered bytes")


def measure_k8s_worker_prompt(
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    prompt: str,
    *,
    approved_source_hashes: frozenset[str],
) -> dict[str, object]:
    """Measure the exact two-message final chat and refuse unregistered source."""

    if (
        profile.id != PROFILE_ID
        or profile.profile_hash != PROFILE_SHA256
        or profile.chat_template_enable_thinking is not False
    ):
        raise ValueError("R15 KEP screen requires the frozen non-thinking profile")
    if not profile.system_prompt:
        raise ValueError("profile lacks frozen system prompt")
    stage: str
    source_sha256: str | None = None
    if _MARKER in prompt:
        stage = "source-survey"
        source = prompt[prompt.index(_MARKER) :]
        source_sha256 = _sha(source.encode())
        if source_sha256 not in approved_source_hashes or prompt.count(_MARKER) != 1:
            raise ValueError("survey source differs from registered material")
        evidence = source
        query = None
    elif "Project request:\n" in prompt:
        stage = "resource-request-stage"
        evidence = prompt.split("Retained formula: ", 1)[1].split("\n", 1)[0]
        query = prompt.split("Project request:\n", 1)[1]
    elif "Order amendment:\n" in prompt:
        stage = "resource-order-change"
        evidence = prompt.split("Retained formula: ", 1)[1].split("\n", 1)[0]
        query = prompt.split("Order amendment:\n", 1)[1]
    else:
        raise ValueError("unregistered R15 KEP worker prompt")
    messages = [
        {"role": "system", "content": profile.system_prompt},
        {"role": "user", "content": prompt},
    ]
    geometry = measure_chat_geometry(
        tokenizer, messages, enable_thinking=False, evidence=evidence, query=query
    )
    if stage != "source-survey" and geometry["span_status"] != "unique_later_query":
        raise ValueError("later request or retained formula has no unique chat span")
    tokens = geometry["rendered_input_tokens"]
    if (
        not isinstance(tokens, int)
        or tokens + profile.max_output_tokens > profile.evaluation_max_model_len
    ):
        raise ValueError("rendered chat exceeds registered model limit")
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
    return {
        "stage": stage,
        "prompt_sha256": _sha(prompt.encode()),
        "request_sha256": _sha(_canonical(payload)),
        "source_material_sha256": source_sha256,
        "profile_sha256": profile.profile_hash,
        "local_template_geometry": geometry,
        "provider_template_parity": "unverified",
    }


def enumerate_allowed_prompt_geometry(
    source_root: Path, *, profile: APIProfile, tokenizer: ChatTokenizer
) -> list[dict[str, object]]:
    """Dry-run every allowed formula/first-plan continuation without a provider."""

    sessions = build_k8s_resource_order_sessions(source_root)
    _verify_base_world(sessions)
    cases = case_materials(sessions)
    neutralized, _ledger = neutralize_both_order_rules(sessions[0].stages[0].documents[0].text)
    approved = frozenset(
        _sha(text.encode())
        for text in (sessions[0].stages[0].documents[0].text, _WITHHELD, neutralized)
    )
    prompts: dict[str, set[str]] = {}
    for case_name, pair in cases:
        for formula in ("formula=prefix", "formula=conservative", "formula=unknown"):
            for first_plan in ("plan=hold-at-1000m", "plan=admit-at-1000m"):
                env = ProjectState()
                budget = ToolBudget(max_calls=8)
                registry = DocumentRegistry()
                observed: list[str] = []

                def scripted(
                    prompt: str,
                    *,
                    seen: list[str] = observed,
                    answer_formula: str = formula,
                    answer_plan: str = first_plan,
                ) -> str:
                    seen.append(prompt)
                    if _MARKER in prompt:
                        return answer_formula
                    if "Project request:\n" in prompt:
                        return answer_plan
                    if "Order amendment:\n" in prompt:
                        return "plan=hold-at-1000m"
                    raise ValueError("unexpected synthetic R15 worker prompt")

                def factory(
                    state: dict[str, object],
                    *,
                    case_budget: ToolBudget = budget,
                    case_registry: DocumentRegistry = registry,
                    responder: Callable[[str], str] = scripted,
                ) -> PolicyHook:
                    return PolicyHook(
                        state,
                        k8s_model_fixed_policy_text(),
                        tool_budget=case_budget,
                        registry=case_registry,
                        responder=responder,
                    )

                run_session_sequence(
                    list(pair),
                    factory,
                    envs=[env, env],
                    budget=budget,
                    registry=registry,
                    max_turns_per_stage=3,
                )
                if len(observed) != 3:
                    raise ValueError(
                        f"synthetic prompt enumeration missed a worker call: "
                        f"{case_name}, {formula}, {first_plan}, {len(observed)}"
                    )
                for prompt in observed:
                    prompts.setdefault(prompt, set()).add(case_name)
    if len(prompts) != 12:
        raise ValueError(f"expected 12 exact prompt variants, observed {len(prompts)}")
    output: list[dict[str, object]] = []
    for prompt, owners in prompts.items():
        geometry = measure_k8s_worker_prompt(
            tokenizer, profile, prompt, approved_source_hashes=approved
        )
        geometry["cases"] = sorted(owners)
        output.append(geometry)
    return sorted(output, key=lambda item: (str(item["stage"]), str(item["prompt_sha256"])))


def make_synthetic_transport(tokenizer: ChatTokenizer, profile: APIProfile) -> SyntheticTransport:
    """Return a local scripted SSE transport for dry-run contract checks only."""

    count = 0

    def transport(request: urllib.request.Request, _timeout: float) -> bytes:
        nonlocal count
        if not isinstance(request.data, bytes):
            raise ValueError("synthetic request has no JSON body")
        body = json.loads(request.data)
        if not isinstance(body, dict) or body.get("model") != profile.model:
            raise ValueError("synthetic request model differs from profile")
        messages = body.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or messages[0] != {"role": "system", "content": profile.system_prompt}
            or not isinstance(messages[1], dict)
            or not isinstance(messages[1].get("content"), str)
        ):
            raise ValueError("synthetic request messages differ from profile")
        prompt = messages[1]["content"]
        if _MARKER in prompt:
            if "[SOURCE WITHHELD" in prompt:
                answer = "formula=unknown"
            elif "[Ordered-prefix calculation withheld" in prompt:
                answer = "formula=conservative"
            else:
                answer = "formula=prefix"
        elif "Project request:\n" in prompt:
            answer = "plan=hold-at-1000m"
        elif "Order amendment:\n" in prompt:
            answer = (
                "plan=admit-at-1000m"
                if "Retained formula: formula=prefix" in prompt
                else "plan=hold-at-1000m"
            )
        else:
            raise ValueError("synthetic transport received an unknown prompt")
        count += 1
        input_geometry = measure_chat_geometry(tokenizer, messages, enable_thinking=False)
        input_tokens = input_geometry["rendered_input_tokens"]
        output_tokens = len(
            tokenizer(answer, add_special_tokens=False, return_offsets_mapping=True)["input_ids"]
        )
        if not isinstance(input_tokens, int) or output_tokens < 1:
            raise ValueError("synthetic tokenizer failed to count the request")
        identity = {"id": f"offline-kep-{count}", "model": profile.model}
        content = {
            **identity,
            "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
        }
        usage = {
            **identity,
            "choices": [],
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
        }
        return (
            "data: "
            + json.dumps(content)
            + "\n\n"
            + "data: "
            + json.dumps(usage)
            + "\n\n"
            + "data: [DONE]\n\n"
        ).encode()

    return SyntheticTransport(transport)


def require_paid_gate() -> None:
    """Fail closed until parent preregistration and provider canaries are frozen."""

    raise RuntimeError(
        "R15 KEP paid execution is closed: parent preregistration and canary pending"
    )


def run_offline_screen(
    source_root: Path,
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    tokenizer: ChatTokenizer,
    transport: SyntheticTransport,
    geometry_registry: list[dict[str, object]],
) -> dict[str, object]:
    """Exercise three cases only when every request matches frozen geometry."""

    if profile.profile_hash != PROFILE_SHA256:
        raise ValueError("R15 KEP shared profile hash changed")
    if type(transport) is not SyntheticTransport:
        raise TypeError("offline screen requires an explicit synthetic transport")
    if len(geometry_registry) != 12:
        raise ValueError("R15 KEP geometry registry must contain 12 prompt variants")
    registered: dict[str, dict[str, object]] = {}
    for item in geometry_registry:
        digest = item.get("prompt_sha256")
        if (
            not isinstance(digest, str)
            or digest in registered
            or item.get("profile_sha256") != PROFILE_SHA256
            or not isinstance(item.get("request_sha256"), str)
            or not isinstance(item.get("cases"), list)
        ):
            raise ValueError("invalid or duplicate R15 KEP geometry registration")
        registered[digest] = item
    sessions = build_k8s_resource_order_sessions(source_root)
    _verify_base_world(sessions)
    cases = case_materials(sessions)
    original = sessions[0].stages[0].documents[0].text
    neutralized, intervention = neutralize_both_order_rules(original)
    approved = frozenset(_sha(text.encode()) for text in (original, _WITHHELD, neutralized))
    current_case = ""
    case_attempt_index = 0
    stage_order = ("source-survey", "resource-request-stage", "resource-order-change")

    def preflight(prompt: str) -> dict[str, object]:
        nonlocal case_attempt_index
        measured = measure_k8s_worker_prompt(
            tokenizer, profile, prompt, approved_source_hashes=approved
        )
        expected = registered.get(str(measured["prompt_sha256"]))
        owners = expected.get("cases") if expected is not None else None
        if (
            expected is None
            or not isinstance(owners, list)
            or current_case not in owners
            or case_attempt_index >= len(stage_order)
            or measured["stage"] != stage_order[case_attempt_index]
            or any(
                measured[field] != expected.get(field)
                for field in (
                    "prompt_sha256",
                    "request_sha256",
                    "profile_sha256",
                    "source_material_sha256",
                    "local_template_geometry",
                )
            )
        ):
            raise ValueError("actual R15 KEP prompt differs from frozen case geometry")
        case_attempt_index += 1
        return measured

    # Reuse the existing strict per-attempt SSE/usage/finish accounting. The
    # transport is injected and this entrypoint never resolves credentials.
    worker = _Worker(profile, endpoint, preflight, transport)
    records: list[dict[str, object]] = []
    cap_refusals = 0
    full_failed = False
    for name, pair in cases:
        current_case = name
        case_attempt_index = 0
        env = ProjectState()
        budget = ToolBudget(max_calls=8)
        registry = DocumentRegistry()
        start = len(worker.attempts)

        def capped_worker(prompt: str) -> str:
            nonlocal cap_refusals
            if len(worker.attempts) >= MAX_WORKER_ATTEMPTS:
                cap_refusals += 1
                raise RuntimeError("R15 KEP worker attempt cap reached before dispatch")
            return worker(prompt)

        def factory(
            state: dict[str, object],
            *,
            case_budget: ToolBudget = budget,
            case_registry: DocumentRegistry = registry,
            responder: Callable[[str], str] = capped_worker,
        ) -> PolicyHook:
            return PolicyHook(
                state,
                k8s_model_fixed_policy_text(),
                tool_budget=case_budget,
                registry=case_registry,
                responder=responder,
            )

        run = run_session_sequence(
            list(pair),
            factory,
            envs=[env, env],
            budget=budget,
            registry=registry,
            max_turns_per_stage=3,
        )
        records.append(
            {
                "case": name,
                "session_passed": [session.passed for session in run.sessions],
                "session_failures": [session.failures for session in run.sessions],
                "policy_errors": [session.policy_errors for session in run.sessions],
                "model_calls": [session.model_calls for session in run.sessions],
                "carry_bytes": [session.carry_bytes for session in run.sessions],
                "final_plan": env.records.get("resource_reassessment", {}).get("plan"),
                "source_material_sha256": _sha(pair[0].stages[0].documents[0].text.encode()),
                "world_sha256": [_sha(canonical_instance_json(world).encode()) for world in pair],
                "worker_attempt_indexes": list(range(start, len(worker.attempts))),
                "receipts": {
                    key: {
                        "subject": env.records[key].get("subject"),
                        "verdict": env.records[key].get("verdict"),
                        "protocol_revision": env.records[key].get("protocol_revision"),
                    }
                    for key in ("first-review", "later-review")
                    if key in env.records
                },
            }
        )
        if name == "full-source" and not all(session.passed for session in run.sessions):
            full_failed = True
        if worker.failed or cap_refusals or full_failed:
            break
    synthetic_usage_total = {
        "input_tokens": sum(
            int(usage["input_tokens"])
            for item in worker.attempts
            if isinstance((usage := item.get("provider_usage")), Mapping)
        ),
        "output_tokens": sum(
            int(usage["output_tokens"])
            for item in worker.attempts
            if isinstance((usage := item.get("provider_usage")), Mapping)
        ),
        "unknown_usage_attempts": sum(
            item.get("provider_usage") is None for item in worker.attempts
        ),
    }
    for item in worker.attempts:
        item["synthetic_usage"] = item.pop("provider_usage", None)
        item["response_provenance"] = "synthetic_sse"
    return {
        "schema_version": 1,
        "scope": "kep753_b_longitudinal_fixed_reader_offline_development_only",
        "live_ready": False,
        "usage_provenance": "synthetic_sse_transport_only",
        "status": (
            "stopped-on-worker-failure"
            if worker.failed
            else "stopped-on-attempt-cap"
            if cap_refusals
            else "stopped-on-full-task-failure"
            if full_failed
            else "completed-offline-screen"
        ),
        "registered_case_order": CASE_ORDER,
        "trajectory_cap": MAX_TRAJECTORIES,
        "worker_attempt_cap": MAX_WORKER_ATTEMPTS,
        "worker_attempt_count": len(worker.attempts),
        "attempt_cap_refusals": cap_refusals,
        "preflight_failures": worker.preflight_failures,
        "profile_id": profile.id,
        "profile_sha256": profile.profile_hash,
        "geometry_registry_sha256": _sha(_canonical(geometry_registry)),
        "policy_sha256": _sha(k8s_model_fixed_policy_text().encode()),
        "source_file_sha256": SOURCE_FILES[_README],
        "base_world_sha256": WORLD_SHA256,
        "source_intervention": intervention,
        "provider_usage_total": None,
        "synthetic_usage_total": synthetic_usage_total,
        "attempts": worker.attempts,
        "cases": records,
    }


__all__ = [
    "CASE_ORDER",
    "MAX_TRAJECTORIES",
    "MAX_WORKER_ATTEMPTS",
    "PROFILE_ID",
    "PROFILE_SHA256",
    "WORLD_SHA256",
    "SyntheticTransport",
    "case_materials",
    "enumerate_allowed_prompt_geometry",
    "make_synthetic_transport",
    "measure_k8s_worker_prompt",
    "neutralize_both_order_rules",
    "require_paid_gate",
    "run_offline_screen",
]
