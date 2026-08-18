"""Normalize Codex JSONL and Claude stream-json without executing either CLI."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Literal


class StreamFormatError(ValueError):
    """Raised for malformed or unexpectedly shaped researcher output."""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Common token and cost fields emitted by researcher CLIs."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float | None = None

    @property
    def total_input_tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.cache_creation_input_tokens


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    """Provider-neutral event while preserving the original JSON object."""

    source: Literal["codex", "claude"]
    kind: str
    text: str | None = None
    session_id: str | None = None
    tool_name: str | None = None
    usage: TokenUsage | None = None
    payload: Mapping[str, object] = field(default_factory=dict)


def normalize_codex_jsonl(lines: Iterable[str]) -> Iterator[NormalizedEvent]:
    """Normalize events from ``codex exec --json``."""

    for line_number, line in enumerate(lines, start=1):
        raw = _decode_line(line, line_number=line_number, source="Codex")
        if raw is None:
            continue
        event_type = _string(raw.get("type"))
        if event_type == "thread.started":
            yield NormalizedEvent(
                "codex", "session", session_id=_string(raw.get("thread_id")), payload=raw
            )
        elif event_type in {"turn.completed", "turn.failed"}:
            yield NormalizedEvent(
                "codex",
                "complete" if event_type == "turn.completed" else "error",
                text=_string(raw.get("error")),
                usage=_parse_usage(raw.get("usage"), required=event_type == "turn.completed"),
                payload=raw,
            )
        elif event_type in {"item.completed", "item.updated", "item.started"}:
            yield _normalize_codex_item(raw)
        elif event_type == "error":
            yield NormalizedEvent("codex", "error", text=_string(raw.get("message")), payload=raw)
        else:
            yield NormalizedEvent("codex", "unknown", payload=raw)


def normalize_claude_stream_json(lines: Iterable[str]) -> Iterator[NormalizedEvent]:
    """Normalize events from ``claude --output-format stream-json``."""

    for line_number, line in enumerate(lines, start=1):
        raw = _decode_line(line, line_number=line_number, source="Claude")
        if raw is None:
            continue
        event_type = _string(raw.get("type"))
        if event_type == "system" and raw.get("subtype") == "init":
            yield NormalizedEvent(
                "claude", "session", session_id=_string(raw.get("session_id")), payload=raw
            )
        elif event_type in {"assistant", "user"}:
            message = _mapping(raw.get("message"))
            content = message.get("content") if message is not None else raw.get("content")
            yield from _normalize_claude_content(content, raw=raw, role=event_type)
        elif event_type == "stream_event":
            yield _normalize_claude_delta(raw)
        elif event_type == "result":
            is_error = bool(raw.get("is_error", False)) or raw.get("subtype") not in {
                None,
                "success",
            }
            yield NormalizedEvent(
                "claude",
                "error" if is_error else "complete",
                text=_string(raw.get("result")) or _string(raw.get("error")),
                session_id=_string(raw.get("session_id")),
                usage=_parse_usage(
                    raw.get("usage"),
                    cost=raw.get("total_cost_usd"),
                    required=not is_error,
                ),
                payload=raw,
            )
        else:
            yield NormalizedEvent("claude", "unknown", payload=raw)


def _decode_line(line: str, *, line_number: int, source: str) -> dict[str, object] | None:
    stripped = line.strip()
    if not stripped:
        return None
    if len(stripped) > 16 * 1024 * 1024:
        raise StreamFormatError(f"{source} line {line_number} exceeds the 16 MiB limit")
    try:
        raw: object = json.loads(
            stripped,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise StreamFormatError(f"{source} line {line_number} is not valid JSON") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise StreamFormatError(f"{source} line {line_number} must contain a JSON object")
    return raw


def _normalize_codex_item(raw: dict[str, object]) -> NormalizedEvent:
    item = _mapping(raw.get("item"))
    if item is None:
        return NormalizedEvent("codex", "unknown", payload=raw)
    item_type = _string(item.get("type"))
    if item_type == "agent_message":
        return NormalizedEvent("codex", "message", text=_string(item.get("text")), payload=raw)
    if item_type == "reasoning":
        return NormalizedEvent("codex", "reasoning", text=_string(item.get("text")), payload=raw)
    if item_type in {"command_execution", "mcp_tool_call", "web_search", "file_change"}:
        status = _string(item.get("status"))
        kind = "tool_result" if status in {"completed", "failed"} else "tool_call"
        return NormalizedEvent(
            "codex",
            kind,
            text=_string(item.get("aggregated_output")) or _string(item.get("result")),
            tool_name=_string(item.get("name")) or item_type,
            payload=raw,
        )
    return NormalizedEvent("codex", "unknown", payload=raw)


def _normalize_claude_content(
    value: object, *, raw: dict[str, object], role: str
) -> Iterator[NormalizedEvent]:
    if isinstance(value, str):
        yield NormalizedEvent("claude", "message", text=value, payload=raw)
        return
    if not isinstance(value, list):
        yield NormalizedEvent("claude", "unknown", payload=raw)
        return
    for block_value in value:
        block = _mapping(block_value)
        if block is None:
            yield NormalizedEvent("claude", "unknown", payload=raw)
            continue
        block_type = _string(block.get("type"))
        if block_type == "text":
            yield NormalizedEvent("claude", "message", text=_string(block.get("text")), payload=raw)
        elif block_type == "thinking":
            yield NormalizedEvent(
                "claude", "reasoning", text=_string(block.get("thinking")), payload=raw
            )
        elif block_type == "tool_use":
            yield NormalizedEvent(
                "claude", "tool_call", tool_name=_string(block.get("name")), payload=raw
            )
        elif block_type == "tool_result" or role == "user":
            yield NormalizedEvent(
                "claude",
                "tool_result",
                text=_content_text(block.get("content")),
                payload=raw,
            )
        else:
            yield NormalizedEvent("claude", "unknown", payload=raw)


def _normalize_claude_delta(raw: dict[str, object]) -> NormalizedEvent:
    event = _mapping(raw.get("event"))
    if event is None:
        return NormalizedEvent("claude", "unknown", payload=raw)
    if event.get("type") == "content_block_delta":
        delta = _mapping(event.get("delta"))
        if delta is not None and delta.get("type") == "text_delta":
            return NormalizedEvent(
                "claude", "message_delta", text=_string(delta.get("text")), payload=raw
            )
    return NormalizedEvent("claude", "unknown", payload=raw)


def _parse_usage(
    value: object, *, cost: object = None, required: bool = False
) -> TokenUsage | None:
    if value is None and cost is None:
        if required:
            raise StreamFormatError("successful researcher result must report usage")
        return None
    usage = _mapping(value)
    if usage is None:
        raise StreamFormatError("usage must be an object when usage or cost is reported")
    return TokenUsage(
        input_tokens=_required_nonnegative_int(usage.get("input_tokens"), "input_tokens"),
        output_tokens=_required_nonnegative_int(usage.get("output_tokens"), "output_tokens"),
        cached_input_tokens=_required_nonnegative_int(
            usage.get("cached_input_tokens", usage.get("cache_read_input_tokens", 0)),
            "cached_input_tokens",
        ),
        cache_creation_input_tokens=_required_nonnegative_int(
            usage.get("cache_creation_input_tokens", 0),
            "cache_creation_input_tokens",
        ),
        cost_usd=_optional_nonnegative_float(cost, "cost_usd"),
    )


def _mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        return None
    return dict(value)


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _required_nonnegative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StreamFormatError(f"{field_name} must be a non-negative integer")
    return value


def _optional_nonnegative_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise StreamFormatError(f"{field_name} must be a finite non-negative number")
    return float(value)


def _content_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [
            text
            for item in value
            if (block := _mapping(item)) is not None
            and (text := _string(block.get("text"))) is not None
        ]
        return "".join(parts) or None
    return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StreamFormatError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise StreamFormatError(f"non-finite JSON number: {value}")
