"""Bounded, development-only fixed-reader screen for the PostgreSQL pair.

The policy is benchmark-owned and fixed. The provider is called only through
the strict profile reader; this module does not execute researcher updates.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from rsicontext.analysis.postgresql_model_screen import _change_source, without_decisive_span
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, build_profile_reader
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.postgresql_model_fixed import postgresql_model_fixed_policy_text
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

MAX_TRAJECTORIES = 8
MAX_WORKER_ATTEMPTS = 16
Preflight = Callable[[str], dict[str, object]]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    # OpenAICompatibleReader.complete uses json.dumps' default ASCII escaping.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _finish_reason(raw: bytes) -> str:
    """Read the terminal SSE reason without assuming a provider-specific delta."""

    reasons: list[str] = []
    for line in raw.decode("utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        event = line.removeprefix("data:").strip()
        if event == "[DONE]":
            break
        body = json.loads(event)
        if not isinstance(body, dict):
            raise ValueError("SSE event must be an object")
        choices = body.get("choices")
        if not isinstance(choices, list):
            raise ValueError("SSE choices must be a list")
        for choice in choices:
            if not isinstance(choice, dict):
                raise ValueError("SSE choice must be an object")
            reason = choice.get("finish_reason")
            if reason is not None:
                if not isinstance(reason, str) or not reason:
                    raise ValueError("invalid finish reason")
                reasons.append(reason)
    if len(reasons) != 1:
        raise ValueError("SSE must report exactly one finish reason")
    return reasons[0]


class _AbortAfterFailure(RuntimeError):
    pass


@dataclass
class _Worker:
    profile: APIProfile
    endpoint: ResolvedAPIEndpoint
    preflight: Preflight
    transport: Transport
    attempts: list[dict[str, object]] = field(default_factory=list)
    preflight_failures: list[dict[str, str]] = field(default_factory=list)
    failed: bool = False

    def __call__(self, prompt: str) -> str:
        if self.failed:
            raise _AbortAfterFailure("previous worker request failed")
        if len(self.attempts) >= MAX_WORKER_ATTEMPTS:
            self.failed = True
            raise _AbortAfterFailure("worker request cap reached")
        try:
            geometry = self.preflight(prompt)
        except Exception as exc:
            self.failed = True
            self.preflight_failures.append(
                {
                    "prompt_sha256": _sha(prompt.encode("utf-8")),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            raise
        if not isinstance(geometry, dict) or geometry.get("prompt_sha256") != _sha(
            prompt.encode("utf-8")
        ):
            self.failed = True
            self.preflight_failures.append(
                {
                    "prompt_sha256": _sha(prompt.encode("utf-8")),
                    "error": "prompt geometry is missing or mismatched",
                }
            )
            raise ValueError("prompt geometry is missing or mismatched")
        attempt: dict[str, object] = {
            "index": len(self.attempts),
            "stage": geometry.get("stage"),
            "prompt_sha256": geometry["prompt_sha256"],
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "preflight_geometry": geometry,
            "status": "attempted",
            "provider_usage": None,
        }
        self.attempts.append(attempt)
        observed: list[tuple[bytes, bytes]] = []

        def capture(request: urllib.request.Request, timeout: float) -> bytes:
            if not isinstance(request.data, bytes):
                raise ValueError("reader request has no body")
            body = json.loads(request.data)
            if not isinstance(body, dict) or body.get("messages") != [
                {"role": "system", "content": self.profile.system_prompt},
                {"role": "user", "content": prompt},
            ]:
                raise ValueError("reader messages differ from preflight")
            if (
                body.get("model") != self.profile.model
                or body.get("chat_template_kwargs") != {"enable_thinking": False}
                or body.get("max_tokens") != self.profile.max_output_tokens
                or body.get("stream_options") != {"include_usage": True}
            ):
                raise ValueError("reader request fields differ from frozen profile")
            if geometry.get("request_sha256") != _sha(_canonical(body)):
                raise ValueError("reader request hash differs from geometry preflight")
            attempt["request_sha256"] = _sha(request.data)
            attempt["endpoint_sha256"] = _sha(request.full_url.encode("utf-8"))
            raw = self.transport(request, timeout)
            observed.append((request.data, raw))
            attempt["response_sha256"] = _sha(raw)
            attempt["finish_reason"] = _finish_reason(raw)
            return raw

        try:
            reader = build_profile_reader(self.profile, self.endpoint, transport=capture)
            output = reader.complete(prompt)
            attempt["provider_usage"] = {
                "input_tokens": output.input_tokens,
                "output_tokens": output.output_tokens,
            }
            attempt["response_id"] = output.response_id
            attempt["response_model"] = output.response_model
            if len(observed) != 1 or attempt.get("finish_reason") != "stop":
                raise ValueError("worker response did not stop normally")
            local = geometry.get("local_template_geometry")
            if not isinstance(local, Mapping):
                raise ValueError("preflight lacks local chat geometry")
            local_count = local.get("rendered_input_tokens")
            if not isinstance(local_count, int) or local_count != output.input_tokens:
                raise ValueError(
                    f"provider prompt tokens {output.input_tokens} differ from local {local_count}"
                )
            attempt.update(
                status="ok",
                reply_sha256=_sha(output.answer.encode("utf-8")),
                reply=output.answer,
            )
            return output.answer
        except Exception as exc:
            self.failed = True
            attempt["status"] = "failed"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            raise


class _NoRereadRegistry(DocumentRegistry):
    def get(self, doc_id: str) -> Any:
        if doc_id == "upstream-create-subscription":
            return None
        return super().get(doc_id)


def _case_specs(
    older: tuple[LifecycleInstance, LifecycleInstance],
    newer: tuple[LifecycleInstance, LifecycleInstance],
) -> tuple[tuple[str, tuple[LifecycleInstance, LifecycleInstance], bool, bool], ...]:
    older_source = older[0].stages[0].documents[0].text
    newer_source = newer[0].stages[0].documents[0].text
    older_notice = older[0].stages[0].documents[1].text
    newer_notice = newer[0].stages[0].documents[1].text
    return (
        ("full-16", older, False, False),
        ("full-17", newer, False, False),
        (
            "withheld-16",
            _change_source(
                older,
                "[[doc:upstream-create-subscription]] withheld",
                "[[doc:upstream-notice]] withheld",
            ),
            False,
            False,
        ),
        (
            "withheld-17",
            _change_source(
                newer,
                "[[doc:upstream-create-subscription]] withheld",
                "[[doc:upstream-notice]] withheld",
            ),
            False,
            False,
        ),
        ("swapped-16", _change_source(older, newer_source, newer_notice), False, False),
        ("swapped-17", _change_source(newer, older_source, older_notice), False, False),
        (
            "decisive-span-removed-17",
            _change_source(newer, without_decisive_span(newer_source), None),
            False,
            False,
        ),
        ("empty-carry-no-reread-17", newer, True, True),
    )


def run_development_pilot(
    older: tuple[LifecycleInstance, LifecycleInstance],
    newer: tuple[LifecycleInstance, LifecycleInstance],
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    preflight: Preflight,
    transport: Transport,
) -> dict[str, object]:
    """Run eight predeclared interventions, stopping on the first bad call."""

    if profile.chat_template_enable_thinking is not False or not profile.system_prompt:
        raise ValueError("pilot requires explicit non-thinking worker profile")
    worker = _Worker(profile, endpoint, preflight, transport)
    specs = _case_specs(older, newer)
    if len(specs) != MAX_TRAJECTORIES:
        raise AssertionError("development pilot trajectory count changed")
    cases: list[dict[str, object]] = []
    task_failed = False
    for name, sessions, clear_carry, no_reread in specs:
        first, second = sessions
        env = ProjectState()
        budget = ToolBudget(max_calls=16)
        registry = _NoRereadRegistry() if no_reread else DocumentRegistry()
        factory_count = 0

        def factory(
            state: dict[str, object],
            *,
            clear: bool = clear_carry,
            case_budget: ToolBudget = budget,
            case_registry: DocumentRegistry = registry,
        ) -> PolicyHook:
            nonlocal factory_count
            factory_count += 1
            if factory_count == 2 and clear:
                state["carry"] = {}
            return PolicyHook(
                state,
                postgresql_model_fixed_policy_text(),
                tool_budget=case_budget,
                registry=case_registry,
                responder=worker,
            )

        start = len(worker.attempts)
        record = run_session_sequence(
            [first, second],
            factory,
            envs=[env, env],
            budget=budget,
            registry=registry,
            max_turns_per_stage=3,
        )
        cases.append(
            {
                "case": name,
                "session_passed": [s.passed for s in record.sessions],
                "session_failures": [s.failures for s in record.sessions],
                "persist_ok": [s.persist_ok for s in record.sessions],
                "final_plan": env.records.get("native_capability_decision", {}).get("plan"),
                "material_sha256": _sha(first.stages[0].documents[0].text.encode()),
                "notice_sha256": _sha(first.stages[0].documents[1].text.encode()),
                "worker_attempt_indexes": list(range(start, len(worker.attempts))),
                "policy_transcript": [
                    entry for session in record.sessions for entry in session.model_transcript
                ],
                "action_kinds": [action.kind for action in env.transcript],
            }
        )
        if worker.failed:
            break
        if name in ("full-16", "full-17") and not all(s.passed for s in record.sessions):
            task_failed = True
            break
    return {
        "schema_version": 1,
        "scope": "postgresql_adaptive_fixed_reader_development_only",
        "status": (
            "stopped-on-worker-failure"
            if worker.failed
            else "stopped-on-full-task-failure"
            if task_failed
            else "completed-development-screen"
        ),
        "profile_id": profile.id,
        "profile_sha256": profile.profile_hash,
        "policy_sha256": _sha(postgresql_model_fixed_policy_text().encode()),
        "trajectory_cap": MAX_TRAJECTORIES,
        "worker_attempt_cap": MAX_WORKER_ATTEMPTS,
        "worker_attempt_count": len(worker.attempts),
        "provider_usage_total": {
            "input_tokens": sum(
                int(usage["input_tokens"])
                for attempt in worker.attempts
                if isinstance((usage := attempt.get("provider_usage")), dict)
            ),
            "output_tokens": sum(
                int(usage["output_tokens"])
                for attempt in worker.attempts
                if isinstance((usage := attempt.get("provider_usage")), dict)
            ),
            "unknown_usage_attempts": sum(
                attempt.get("provider_usage") is None for attempt in worker.attempts
            ),
        },
        "attempts": worker.attempts,
        "preflight_failures": worker.preflight_failures,
        "cases": cases,
    }


__all__ = ["MAX_TRAJECTORIES", "MAX_WORKER_ATTEMPTS", "run_development_pilot"]
