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
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

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


class APIResearcherError(RuntimeError):
    """Raised when the researcher endpoint fails protocol validation."""


@dataclass(frozen=True, slots=True)
class APIResearcherConfig:
    """Endpoint/model description for the researcher; secrets stay in env."""

    endpoint: str
    model: str
    api_key_env: str = "SIFLOW_API_KEY"
    timeout_seconds: float = 600.0
    max_output_tokens: int = 16384

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.startswith("https://"):
            raise ParticipantError("researcher endpoint must be an HTTPS URL")
        if not self.endpoint.endswith("/chat/completions"):
            raise ParticipantError("researcher endpoint must target /chat/completions")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ParticipantError("researcher model must be non-empty")


@dataclass(frozen=True, slots=True)
class APIResearcherImprover:
    """One registered arm: a remote reasoning model as the improvement process."""

    config: APIResearcherConfig
    round_budget_notes: tuple[str, ...] = ()
    _usage: list[UsageReport] = field(default_factory=list, repr=False, compare=False)

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        import os

        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise ParticipantError(
                f"missing researcher credential environment variable: {self.config.api_key_env}"
            )
        prompt = self._build_prompt(round_input)
        started = time.perf_counter()
        content, input_tokens, output_tokens = self._request(prompt, api_key)
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

    # --- internals --------------------------------------------------------

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

    def _request(self, prompt: str, api_key: str) -> tuple[str, int, int]:
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
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise APIResearcherError(f"researcher endpoint unreachable: {exc}") from exc
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
        if not isinstance(content, str) or not content.strip():
            # Reasoning researchers can emit the final output only inside the
            # reasoning channel: fall back to its tail (the last JSON object
            # the model formed before finishing).
            reasoning = message.get("reasoning") or message.get("reasoning_content")
            if isinstance(reasoning, str) and "{" in reasoning:
                tail = reasoning[reasoning.rfind('{"changes"') :].strip()
                if tail.startswith("{") and "}" in tail:
                    content = tail[: tail.rfind("}") + 1]
        if not isinstance(content, str) or not content.strip():
            raise APIResearcherError("researcher response content is empty")
        usage = raw.get("usage") if isinstance(raw, dict) else None
        if not isinstance(usage, dict):
            raise APIResearcherError("researcher response must report token usage")
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")
        if not isinstance(in_tokens, int) or not isinstance(out_tokens, int):
            raise APIResearcherError("researcher usage must carry prompt/completion tokens")
        if finish_reason == "length":
            raise APIResearcherError("researcher reply was truncated by the output-token budget")
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
    "APIResearcherError",
    "APIResearcherImprover",
]
