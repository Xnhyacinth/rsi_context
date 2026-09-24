"""DeepSeek API researcher arm: an in-process improvement process over HTTP.

Contract status: implements participant-interface-v1.md §arms — the open-S
CLI arm's in-process sibling. Where ``OpenSClIResearcherImprover`` bridges a
campaign callback, this arm asks a remote reasoning model (the registered
researcher, e.g. ``deepseek-ai/deepseek-v4.1-flash`` on a versioned API) to
propose agent-file edits from the restricted feedback, then applies them.

Roles stay separated per the owner's assignment: the researcher model
proposes; the reader model (a different profile) is invoked only by the
benchmark during evaluation. Credentials resolve from the environment at
call time — never stored on this object, never serialized.

Reliability (the 1/4 arm record, docs/arm-comparison-v2-first-20260920.md):
transient reasoning-channel failures — empty replies, output-budget
truncation, transport errors — retry under a bounded ``RetryPolicy``;
deterministic protocol failures (malformed JSON, unsafe paths) never
retry, and every attempt lands in a per-improver attempt log with its
token counts.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final

from rsicontext.participant.registration import (
    ImprovementRoundInput,
    ImprovementRoundOutput,
    ParticipantError,
)
from rsicontext.participant.usage import UsageReport

_ALLOWED_TOP = re.compile(r"\A[A-Za-z0-9_][A-Za-z0-9_./-]*\.(py|json|md|txt|yaml|yml|toml)\Z")
_SYSTEM_PROMPT = (
    "You are a coding researcher improving an agent strategy system. You "
    "receive the current agent files and restricted feedback from the last "
    "benchmark round. Reply with ONLY a JSON object of the form "
    '{"changes": {"<relative/path>": "<new full file content>", ...}}. '
    "Only include files you changed. Paths must be relative and safe. "
    "Never touch benchmark-owned files."
)
_RETRYABLE_OUTCOMES: Final = frozenset({"empty_content", "truncated", "transport_error"})


def _reported_tokens(usage: object, key: str) -> int:
    """Best-effort token count from a possibly-malformed usage block.

    A failed attempt still cost money when the endpoint reported tokens;
    a usage block that never arrived or is malformed contributes zero.
    """

    value = usage.get(key) if isinstance(usage, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


class APIResearcherError(RuntimeError):
    """Raised when the researcher endpoint fails protocol validation."""


class APIResearcherRetryableError(APIResearcherError):
    """A transient researcher failure that a bounded retry may fix.

    Deterministic protocol failures stay plain ``APIResearcherError``:
    replaying the same request (temperature 0, fixed seed) would fail
    identically. The token counts of the failed attempt ride along so the
    round's usage accounting can still charge it — a failed attempt's
    tokens cost money.
    """

    outcome: ClassVar[str]

    def __init__(self, message: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class APIResearcherEmptyError(APIResearcherRetryableError):
    """Reply content empty, even after the reasoning-tail fallback."""

    outcome = "empty_content"


class APIResearcherTruncatedError(APIResearcherRetryableError):
    """Reply cut off by the output-token budget (finish_reason == "length")."""

    outcome = "truncated"


class APIResearcherTransportError(APIResearcherRetryableError):
    """Endpoint unreachable: URLError or timeout before any payload arrived."""

    outcome = "transport_error"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry for transient researcher failures.

    ``retry_on`` carries failure classes by name ("empty_content",
    "truncated", "transport_error"); deterministic protocol failures are
    never listed, so they pass through on the first attempt. Validation
    guards against retry classes outside that taxonomy.
    """

    max_attempts: int = 3
    backoff_seconds: float = 5.0
    retry_on: tuple[str, ...] = ("empty_content", "truncated", "transport_error")

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise ParticipantError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ParticipantError("max_attempts must be at least 1")
        if (
            isinstance(self.backoff_seconds, bool)
            or not isinstance(self.backoff_seconds, (int, float))
            or not math.isfinite(float(self.backoff_seconds))
            or float(self.backoff_seconds) < 0
        ):
            raise ParticipantError("backoff_seconds must be finite and non-negative")
        if not isinstance(self.retry_on, tuple) or any(
            not isinstance(name, str) for name in self.retry_on
        ):
            raise ParticipantError("retry_on must be a tuple of failure-class names")
        unknown = [name for name in self.retry_on if name not in _RETRYABLE_OUTCOMES]
        if unknown:
            raise ParticipantError(
                "retry_on names unknown failure classes: " + ", ".join(sorted(unknown))
            )


@dataclass(frozen=True, slots=True)
class APIResearcherConfig:
    """Endpoint/model description for the researcher; secrets stay in env."""

    endpoint: str
    model: str
    api_key_env: str = "SIFLOW_API_KEY"
    timeout_seconds: float = 600.0
    max_output_tokens: int = 16384
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.startswith("https://"):
            raise ParticipantError("researcher endpoint must be an HTTPS URL")
        if not self.endpoint.endswith("/chat/completions"):
            raise ParticipantError("researcher endpoint must target /chat/completions")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ParticipantError("researcher model must be non-empty")
        if not isinstance(self.retry, RetryPolicy):
            raise ParticipantError("retry must be a RetryPolicy")


@dataclass(frozen=True, slots=True)
class APIResearcherImprover:
    """One registered arm: a remote reasoning model as the improvement process."""

    config: APIResearcherConfig
    round_budget_notes: tuple[str, ...] = ()
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False, compare=False)
    _usage: list[UsageReport] = field(default_factory=list, repr=False, compare=False)
    _attempt_log: list[dict[str, object]] = field(default_factory=list, repr=False, compare=False)

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        import os

        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise ParticipantError(
                f"missing researcher credential environment variable: {self.config.api_key_env}"
            )
        prompt = self._build_prompt(round_input)
        started = time.perf_counter()
        content, input_tokens, output_tokens = self._request_with_retry(prompt, api_key)
        elapsed = time.perf_counter() - started
        usage = UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            wall_seconds=elapsed,
            dollar_estimate=None,
        )
        self._usage.append(usage)
        changes = self._parse_changes(content)
        return ImprovementRoundOutput(
            agent_files_changed=changes,
            state_update=None,
            usage=usage,
        )

    def usage_reports(self) -> tuple[UsageReport, ...]:
        """Accumulated per-round usage (the C_improve column source)."""

        return tuple(self._usage)

    def attempts(self) -> tuple[dict[str, object], ...]:
        """Every researcher request attempt, in order, across all rounds.

        One record per attempt: ``{"attempt": int, "outcome": str,
        "input_tokens": int, "output_tokens": int}`` — the improver-side
        reliability record behind the arm's 1/4 operational history.
        """

        return tuple(self._attempt_log)

    # --- internals --------------------------------------------------------

    def _request_with_retry(self, prompt: str, api_key: str) -> tuple[str, int, int]:
        """Bounded retry loop around one HTTP request.

        Usage from every attempt — failed ones included — sums into the
        returned totals; wall time is the caller's concern (it wraps this
        whole loop). When the final attempt still fails transiently, its
        exception propagates so the round is recorded as failed, not
        silently absorbed.
        """

        policy = self.config.retry
        total_input = 0
        total_output = 0
        for index in range(policy.max_attempts):
            if index:
                self.sleep(policy.backoff_seconds)
            try:
                content, in_tokens, out_tokens = self._request_once(prompt, api_key)
            except APIResearcherRetryableError as exc:
                total_input += exc.input_tokens
                total_output += exc.output_tokens
                self._attempt_log.append(
                    {
                        "attempt": index + 1,
                        "outcome": exc.outcome,
                        "input_tokens": exc.input_tokens,
                        "output_tokens": exc.output_tokens,
                    }
                )
                if index == policy.max_attempts - 1 or exc.outcome not in policy.retry_on:
                    raise
                continue
            total_input += in_tokens
            total_output += out_tokens
            self._attempt_log.append(
                {
                    "attempt": index + 1,
                    "outcome": "ok",
                    "input_tokens": in_tokens,
                    "output_tokens": out_tokens,
                }
            )
            return content, total_input, total_output
        raise AssertionError("unreachable: retry loop must return or raise")

    def _build_prompt(self, round_input: ImprovementRoundInput) -> str:
        files: dict[str, str] = {}
        for path in sorted(round_input.current_agent_dir.rglob("*")):
            if path.is_file():
                relative = path.relative_to(round_input.current_agent_dir).as_posix()
                if _ALLOWED_TOP.fullmatch(relative):
                    files[relative] = path.read_text(encoding="utf-8")
        payload = {
            "round_index": round_input.round_index,
            "remaining_slots": round_input.remaining_slots,
            "task": round_input.task_text,
            "restricted_feedback": round_input.restricted_feedback_bytes.decode(
                "utf-8", errors="replace"
            ),
            "agent_files": files,
            "notes": list(self.round_budget_notes),
        }
        return json.dumps(payload, indent=1, sort_keys=True)

    def _request_once(self, prompt: str, api_key: str) -> tuple[str, int, int]:
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.config.max_output_tokens,
            "temperature": 0.0,
            "seed": 42,
            "stream": False,
        }
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            # APIResearcherConfig rejects non-HTTPS endpoints at construction.
            with urllib.request.urlopen(  # nosec B310
                request, timeout=self.config.timeout_seconds
            ) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise APIResearcherTransportError(f"researcher endpoint unreachable: {exc}") from exc
        try:
            raw: Any = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise APIResearcherError("researcher response is not valid JSON") from exc
        choices = raw.get("choices") if isinstance(raw, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise APIResearcherError("researcher response must contain one choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        finish_reason = choices[0].get("finish_reason")
        usage = raw.get("usage") if isinstance(raw, dict) else None
        if not isinstance(content, str) or not content.strip():
            # Reasoning researchers can emit the final output only inside the
            # reasoning channel: fall back to its tail (the last JSON object
            # the model formed before finishing).
            reasoning = (
                (message.get("reasoning") or message.get("reasoning_content"))
                if isinstance(message, dict)
                else None
            )
            if isinstance(reasoning, str) and "{" in reasoning:
                tail = reasoning[reasoning.rfind('{"changes"') :].strip()
                if tail.startswith("{") and "}" in tail:
                    content = tail[: tail.rfind("}") + 1]
        if not isinstance(content, str) or not content.strip():
            raise APIResearcherEmptyError(
                "researcher response content is empty",
                input_tokens=_reported_tokens(usage, "prompt_tokens"),
                output_tokens=_reported_tokens(usage, "completion_tokens"),
            )
        if not isinstance(usage, dict):
            raise APIResearcherError("researcher response must report token usage")
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")
        if not isinstance(in_tokens, int) or not isinstance(out_tokens, int):
            raise APIResearcherError("researcher usage must carry prompt/completion tokens")
        if finish_reason == "length":
            raise APIResearcherTruncatedError(
                "researcher reply was truncated by the output-token budget",
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
        return content, in_tokens, out_tokens

    def _parse_changes(self, content: str) -> dict[str, str]:
        text = content.strip()
        # Strip markdown code fences the reasoning researcher tends to add.
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1 and text.rstrip().endswith("```"):
                text = text[first_newline + 1 : text.rstrip().rfind("```")].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise APIResearcherError("researcher reply contains no JSON object")
        try:
            parsed: Any = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise APIResearcherError("researcher reply JSON is malformed") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("changes"), dict):
            raise APIResearcherError('researcher reply must be {"changes": {...}}')
        changes: dict[str, str] = {}
        for relative, file_content in parsed["changes"].items():
            if not isinstance(relative, str) or not isinstance(file_content, str):
                raise APIResearcherError("changes entries must be string-to-string")
            if _ALLOWED_TOP.fullmatch(relative) is None or relative.startswith(".."):
                raise APIResearcherError(f"unsafe researcher file path: {relative!r}")
            changes[relative] = file_content
        return changes


__all__ = [
    "APIResearcherConfig",
    "APIResearcherEmptyError",
    "APIResearcherError",
    "APIResearcherImprover",
    "APIResearcherRetryableError",
    "APIResearcherTransportError",
    "APIResearcherTruncatedError",
    "RetryPolicy",
]
