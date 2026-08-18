"""Frozen OpenAI-compatible reader used with a separately managed vLLM server."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from rsicontext.policy import ContextPack

from .core import ReaderOutput

if TYPE_CHECKING:
    from rsicontext.experiment import APIProfile, RunSpec
    from rsicontext.registry import RegistryEntry, ServingProfile

Transport = Callable[[urllib.request.Request, float], bytes]
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
_MAX_RESPONSE_BYTES = 1024 * 1024
_SYSTEM_PROMPT = (
    "Answer the question using only the supplied evidence. "
    "If the evidence is insufficient, return INSUFFICIENT. Return only the answer."
)


class ReaderProtocolError(RuntimeError):
    """The frozen endpoint returned an invalid or unsuccessful response."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        raise ReaderProtocolError("reader redirects are forbidden")


def _urlopen_transport(request: urllib.request.Request, timeout: float) -> bytes:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RejectRedirects(),
    )
    try:
        with opener.open(request, timeout=timeout) as response:  # nosec B310
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
            if not isinstance(payload, bytes):
                raise ReaderProtocolError("reader transport returned a non-bytes payload")
            if len(payload) > _MAX_RESPONSE_BYTES:
                raise ReaderProtocolError("reader response exceeds the 1 MiB size limit")
            return payload
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReaderProtocolError(f"reader request failed: {exc}") from exc


@dataclass(frozen=True, slots=True)
class OpenAICompatibleReader:
    """Minimal, fail-closed chat-completions client with frozen decoding fields."""

    endpoint: str
    model: str
    max_tokens: int
    max_model_len: int | None = None
    seed: int = 42
    stream: bool = False
    chat_template_enable_thinking: bool | None = None
    require_response_model: bool = False
    timeout_seconds: float = 30.0
    allowed_hosts: tuple[str, ...] = _LOCAL_HOSTS
    api_key: str | None = field(default=None, repr=False, compare=False)
    transport: Transport = field(default=_urlopen_transport, repr=False, compare=False)

    @classmethod
    def from_run_spec(
        cls,
        *,
        endpoint: str,
        run_spec: RunSpec,
        serving_profile: ServingProfile,
        registry_model: RegistryEntry,
        reader_profile: APIProfile,
        timeout_seconds: float = 30.0,
        api_key: str | None = None,
        transport: Transport = _urlopen_transport,
    ) -> Self:
        """Build a reader whose registered serving stack cannot drift from the run."""

        from rsicontext.registry import validate_run_binding

        validate_run_binding(run_spec, serving_profile, registry_model, reader_profile)

        reader = cls(
            endpoint=endpoint,
            model=run_spec.model.model_id,
            max_tokens=run_spec.budget.output_tokens,
            max_model_len=run_spec.model.max_model_len,
            seed=run_spec.seed,
            stream=True,
            chat_template_enable_thinking=run_spec.chat_template_enable_thinking,
            require_response_model=True,
            timeout_seconds=timeout_seconds,
            allowed_hosts=(reader_profile.allowed_host,),
            api_key=api_key,
            transport=transport,
        )
        if reader.timeout_seconds > run_spec.budget.wall_time_seconds:
            raise ValueError("reader timeout exceeds the run wall-time budget")
        return reader

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str):
            raise TypeError("reader endpoint must be a string")
        parsed = urllib.parse.urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("reader endpoint must be an absolute HTTP(S) URL")
        if parsed.hostname not in self.allowed_hosts:
            raise ValueError(f"reader endpoint host is not allowlisted: {parsed.hostname}")
        if parsed.hostname not in _LOCAL_HOSTS and parsed.scheme != "https":
            raise ValueError("remote reader endpoints must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("reader endpoint must not contain embedded credentials")
        if parsed.query:
            raise ValueError("reader endpoint must not contain a query string")
        if parsed.fragment:
            raise ValueError("reader endpoint must not contain a fragment")
        if not parsed.path.endswith("/chat/completions"):
            raise ValueError("reader endpoint must target /chat/completions")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("reader model must be non-empty")
        if not isinstance(self.max_tokens, int) or isinstance(self.max_tokens, bool):
            raise TypeError("reader max_tokens must be an integer")
        if self.max_tokens <= 0:
            raise ValueError("reader max_tokens must be positive")
        if self.max_model_len is not None and (
            not isinstance(self.max_model_len, int) or isinstance(self.max_model_len, bool)
        ):
            raise TypeError("reader max_model_len must be an integer or null")
        if self.max_model_len is not None and self.max_model_len <= 0:
            raise ValueError("reader max_model_len must be positive")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise TypeError("reader seed must be an integer")
        if self.seed < 0:
            raise ValueError("reader seed must be non-negative")
        if not isinstance(self.stream, bool):
            raise TypeError("reader stream must be a boolean")
        if self.chat_template_enable_thinking is not None and not isinstance(
            self.chat_template_enable_thinking, bool
        ):
            raise TypeError("chat-template thinking switch must be a boolean or null")
        if not isinstance(self.require_response_model, bool):
            raise TypeError("reader require_response_model must be a boolean")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("reader timeout_seconds must be finite and positive")
        if not isinstance(self.allowed_hosts, tuple):
            raise TypeError("allowed_hosts must be an immutable tuple")
        if not self.allowed_hosts or any(
            not isinstance(host, str) or not host for host in self.allowed_hosts
        ):
            raise ValueError("allowed_hosts must contain non-empty host names")
        if self.api_key is not None and (not isinstance(self.api_key, str) or not self.api_key):
            raise TypeError("api_key must be a non-empty string or null")
        if not callable(self.transport):
            raise TypeError("reader transport must be callable")

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        payload = {
            "max_tokens": self.max_tokens,
            "messages": [
                {"content": _SYSTEM_PROMPT, "role": "system"},
                {"content": _user_prompt(query, context), "role": "user"},
            ],
            "model": self.model,
            "seed": self.seed,
            "stream": self.stream,
            "temperature": 0.0,
        }
        if self.stream:
            payload["stream_options"] = {"include_usage": True}
        if self.chat_template_enable_thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": self.chat_template_enable_thinking
            }
        headers = {"Content-Type": "application/json"}
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
            headers=headers,
            method="POST",
        )
        raw = self.transport(request, self.timeout_seconds)
        output = (
            _parse_stream_output(raw, self.model, self.require_response_model)
            if self.stream
            else _parse_output(raw, self.model, self.require_response_model)
        )
        if output.output_tokens > self.max_tokens:
            raise ReaderProtocolError("reader reported usage above the output token limit")
        if (
            self.max_model_len is not None
            and output.input_tokens + output.output_tokens > self.max_model_len
        ):
            raise ReaderProtocolError("reader reported usage above the model length")
        return output


def _user_prompt(query: str, context: ContextPack) -> str:
    texts = {span.chunk_id: span.text for span in context.spans}
    texts.update({note.note_id: note.text for note in context.notes})
    evidence = "\n\n".join(f"[{item_id}]\n{texts[item_id]}" for item_id in context.ordering)
    return f"Question:\n{query}\n\nEvidence:\n{evidence}"


def _parse_output(
    payload: bytes,
    expected_model: str,
    require_response_model: bool,
) -> ReaderOutput:
    try:
        raw: object = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReaderProtocolError("reader response is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ReaderProtocolError("reader response root must be an object")
    response_id, response_model = _response_identity(raw, expected_model, require_response_model)
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ReaderProtocolError("reader response must contain at least one choice")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ReaderProtocolError("reader choice must contain string message content")
    content = message.get("content")
    if not isinstance(content, str):
        raise ReaderProtocolError("reader choice must contain string message content")
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        raise ReaderProtocolError("reader response must contain token usage")
    input_tokens = _usage_tokens(usage.get("prompt_tokens"), "prompt_tokens")
    output_tokens = _usage_tokens(usage.get("completion_tokens"), "completion_tokens")
    return ReaderOutput(
        content.strip(),
        input_tokens,
        output_tokens,
        response_id=response_id,
        response_model=response_model,
    )


def _parse_stream_output(
    payload: bytes,
    expected_model: str,
    require_response_model: bool,
) -> ReaderOutput:
    try:
        text = payload.decode()
    except UnicodeDecodeError as exc:
        raise ReaderProtocolError("reader stream is not valid UTF-8") from exc
    content_parts: list[str] = []
    usage: tuple[int, int] | None = None
    response_id: str | None = None
    response_model: str | None = None
    done = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if done:
            raise ReaderProtocolError("reader stream contains data after [DONE]")
        if not line.startswith("data:"):
            raise ReaderProtocolError("reader stream contains a non-data SSE event")
        event = line.removeprefix("data:").lstrip()
        if event == "[DONE]":
            done = True
            continue
        try:
            raw: object = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ReaderProtocolError("reader stream event is not valid JSON") from exc
        if not isinstance(raw, dict):
            raise ReaderProtocolError("reader stream event must be an object")
        chunk_id, chunk_model = _response_identity(raw, expected_model, require_response_model)
        if response_id is not None and chunk_id != response_id:
            raise ReaderProtocolError("reader stream response id changed between events")
        if response_model is not None and chunk_model != response_model:
            raise ReaderProtocolError("reader stream model changed between events")
        response_id = chunk_id or response_id
        response_model = chunk_model or response_model
        choices = raw.get("choices")
        if not isinstance(choices, list):
            raise ReaderProtocolError("reader stream choices must be a list")
        if choices:
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ReaderProtocolError("reader stream choice must be an object")
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                raise ReaderProtocolError("reader stream choice must contain a delta object")
            part = delta.get("content", "")
            if not isinstance(part, str):
                raise ReaderProtocolError("reader stream delta content must be a string")
            content_parts.append(part)
        raw_usage = raw.get("usage")
        if raw_usage is not None:
            if usage is not None or not isinstance(raw_usage, dict):
                raise ReaderProtocolError("reader stream must contain exactly one usage object")
            usage = (
                _usage_tokens(raw_usage.get("prompt_tokens"), "prompt_tokens"),
                _usage_tokens(raw_usage.get("completion_tokens"), "completion_tokens"),
            )
    if not done:
        raise ReaderProtocolError("reader stream is missing the [DONE] marker")
    if usage is None:
        raise ReaderProtocolError("reader stream is missing token usage")
    return ReaderOutput(
        "".join(content_parts).strip(),
        usage[0],
        usage[1],
        response_id=response_id,
        response_model=response_model,
    )


def _response_identity(
    raw: dict[str, object],
    expected_model: str,
    require_response_model: bool,
) -> tuple[str | None, str | None]:
    response_id = raw.get("id")
    if response_id is not None and (not isinstance(response_id, str) or not response_id):
        raise ReaderProtocolError("reader response id must be a non-empty string")
    response_model = raw.get("model")
    if response_model is not None and (not isinstance(response_model, str) or not response_model):
        raise ReaderProtocolError("reader response model must be a non-empty string")
    if require_response_model and response_model != expected_model:
        raise ReaderProtocolError("reader response model does not match the requested model")
    return response_id, response_model


def _usage_tokens(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReaderProtocolError(f"reader usage.{field_name} must be a non-negative integer")
    return value
