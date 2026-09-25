"""Versioned, bounded wire format for one isolated lifecycle policy turn.

This module validates bytes and message order only. It neither starts a worker
nor authorizes a tool call; the future host broker must validate visibility,
budget, and action semantics again before executing a request.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Mapping
from io import BufferedIOBase
from typing import cast

from rsicontext.lifecycle.env import Action

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 1_048_576
MAX_STATE_BYTES = 65_536
MAX_TOOL_REQUESTS = 128
_TOOLS = frozenset({"ask_model", "reread", "query_sandbox", "request_verification", "delegate"})
_ACTIONS = frozenset({"create_record", "update_record", "finalize", "request_verification"})
_STAGE_KINDS = frozenset(
    {
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
        "follow_up",
        "session_start",
        "session_end",
    }
)


class ProtocolError(ValueError):
    """Malformed or out-of-order policy IPC input."""


def _object(value: object, keys: set[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProtocolError(f"{name} requires exactly {sorted(keys)}")
    return value


def _string(value: object, name: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ProtocolError(f"{name} must be a {'possibly empty ' if empty else ''}string")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolError(f"{name} must be a non-negative integer")
    return value


def _strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ProtocolError(f"{name} must be a list")
    return [_string(item, name) for item in value]


def _json_tree(value: object, *, depth: int = 0) -> None:
    if depth > 32:
        raise ProtocolError("JSON nesting exceeds 32 levels")
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolError("non-finite JSON number")
        return
    if isinstance(value, list):
        for item in value:
            _json_tree(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError("JSON object keys must be strings")
            _json_tree(item, depth=depth + 1)
        return
    raise ProtocolError(f"unsupported JSON value: {type(value).__name__}")


def _canonical(value: object) -> bytes:
    _json_tree(value)
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid JSON payload") from exc


def _state(value: object, name: str) -> None:
    if not isinstance(value, dict):
        raise ProtocolError(f"{name} must be an object")
    if len(_canonical(value)) > MAX_STATE_BYTES:
        raise ProtocolError(f"{name} exceeds {MAX_STATE_BYTES} canonical bytes")


def _stage_view(value: object) -> None:
    view = _object(
        value,
        {"stage_id", "kind", "prompt_text", "documents", "axes", "remaining_budget", "receipts"},
        "view",
    )
    _string(view["stage_id"], "stage_id")
    if _string(view["kind"], "stage kind") not in _STAGE_KINDS:
        raise ProtocolError("unknown stage kind")
    _string(view["prompt_text"], "prompt_text", empty=True)
    _integer(view["remaining_budget"], "remaining_budget")
    axes = _object(
        view["axes"],
        {
            "information_scale_tokens",
            "dependency_distance_stages",
            "persistence_span_resets",
            "action_dependency",
            "environment_changes",
        },
        "axes",
    )
    for key in (
        "information_scale_tokens",
        "dependency_distance_stages",
        "persistence_span_resets",
        "environment_changes",
    ):
        _integer(axes[key], key)
    if axes["action_dependency"] not in ("weak", "strong"):
        raise ProtocolError("invalid action_dependency")
    if not isinstance(view["documents"], list) or not isinstance(view["receipts"], list):
        raise ProtocolError("documents and receipts must be lists")
    for doc in view["documents"]:
        item = _object(
            doc,
            {"doc_id", "title", "text", "source_url", "retrieved_date", "superseded_by"},
            "document",
        )
        _string(item["doc_id"], "doc_id")
        _string(item["title"], "title")
        for key in ("text", "source_url", "retrieved_date"):
            _string(item[key], key, empty=True)
        if item["superseded_by"] is not None:
            _string(item["superseded_by"], "superseded_by")
    for receipt in view["receipts"]:
        item = _object(
            receipt,
            {
                "action_kind",
                "record_id",
                "applied",
                "cause",
                "check",
                "subject",
                "verdict",
                "protocol_revision",
            },
            "receipt",
        )
        for key in ("action_kind", "record_id", "cause", "check", "subject", "verdict"):
            _string(item[key], key, empty=True)
        if type(item["applied"]) is not bool:
            raise ProtocolError("receipt applied must be boolean")
        _integer(item["protocol_revision"], "protocol_revision")


def _tool_request(value: object) -> str:
    item = _object(value, {"tool", "args"}, "tool request")
    tool = _string(item["tool"], "tool")
    if tool not in _TOOLS:
        raise ProtocolError("unknown tool")
    shapes = {
        "ask_model": {"prompt"},
        "reread": {"doc_id", "span"},
        "query_sandbox": {"pattern"},
        "request_verification": {"check", "subject"},
        "delegate": {"query", "doc_ids"},
    }
    args = _object(item["args"], shapes[tool], "tool args")
    for key, arg in args.items():
        if key == "doc_ids":
            _strings(arg, key)
        elif key == "span":
            if arg is not None:
                if not isinstance(arg, list) or len(arg) != 2:
                    raise ProtocolError("span must be null or [start, length]")
                for part in arg:
                    _integer(part, "span element")
        else:
            _string(arg, key)
    return tool


def _action(value: object) -> None:
    item = _object(
        value,
        {
            "kind",
            "record_id",
            "fields",
            "provenance",
            "precondition_refs",
            "precondition_current_revision",
            "precondition_revision_scope",
            "precondition_scope_constraint",
        },
        "action",
    )
    kind = _string(item["kind"], "action kind")
    if kind not in _ACTIONS:
        raise ProtocolError("unknown action kind")
    _string(item["record_id"], "record_id")
    _state(item["fields"], "action fields")
    provenance = _strings(item["provenance"], "provenance")
    refs = _strings(item["precondition_refs"], "precondition_refs")
    scope = _strings(item["precondition_revision_scope"], "precondition_revision_scope")
    revision = item["precondition_current_revision"]
    if revision is not None:
        _integer(revision, "precondition_current_revision")
    constraint = item["precondition_scope_constraint"]
    if constraint is not None:
        checked = _object(constraint, {"domain", "requires_check"}, "precondition_scope_constraint")
        _string(checked["domain"], "domain")
        required = checked["requires_check"]
        if isinstance(required, str):
            _string(required, "requires_check")
        elif isinstance(required, list) and required:
            _strings(required, "requires_check")
        else:
            raise ProtocolError("requires_check must be a nonempty string or string list")
    try:
        Action(
            kind=kind,  # type: ignore[arg-type]
            record_id=str(item["record_id"]),
            fields=item["fields"],  # type: ignore[arg-type]
            provenance=tuple(provenance),
            precondition_refs=tuple(refs),
            precondition_current_revision=revision,  # type: ignore[arg-type]
            precondition_revision_scope=tuple(scope),
            precondition_scope_constraint=constraint,  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"invalid action: {exc}") from exc


def validate_message(value: object) -> dict[str, object]:
    """Validate one complete wire message, including nested exact schemas."""

    message = _object(value, {"version", "seq", "type", "body"}, "message")
    if type(message["version"]) is not int or message["version"] != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    _integer(message["seq"], "seq")
    kind = _string(message["type"], "message type")
    if kind == "stage_start":
        body = _object(message["body"], {"view", "state"}, "stage_start")
        _stage_view(body["view"])
        _state(body["state"], "state")
    elif kind == "tool_request":
        _tool_request(message["body"])
    elif kind == "tool_reply":
        body = _object(message["body"], {"tool", "result"}, "tool_reply")
        if _string(body["tool"], "tool") not in _TOOLS:
            raise ProtocolError("unknown tool reply")
        result = _object(
            body["result"], {"ok", "answer", "cause", "tokens_in", "tokens_out"}, "tool result"
        )
        if type(result["ok"]) is not bool:
            raise ProtocolError("tool result ok must be boolean")
        _string(result["answer"], "answer", empty=True)
        _string(result["cause"], "cause", empty=True)
        _integer(result["tokens_in"], "tokens_in")
        _integer(result["tokens_out"], "tokens_out")
    elif kind == "turn_done":
        body = _object(message["body"], {"decision", "state"}, "turn_done")
        decision = _object(
            body["decision"], {"pack_text", "actions", "memory_writes", "errors"}, "decision"
        )
        _string(decision["pack_text"], "pack_text", empty=True)
        if not isinstance(decision["actions"], list):
            raise ProtocolError("actions must be a list")
        for action in decision["actions"]:
            _action(action)
        _state(decision["memory_writes"], "memory_writes")
        _strings(decision["errors"], "errors")
        _state(body["state"], "state")
        writes = cast(dict[str, object], decision["memory_writes"])
        state = cast(dict[str, object], body["state"])
        if any(state.get(key) != value for key, value in writes.items()):
            raise ProtocolError("memory_writes must appear in final state")
    else:
        raise ProtocolError("unknown message type")
    _canonical(message)
    return message


def encode_message(message: Mapping[str, object]) -> bytes:
    """Encode one canonical JSON frame with a 4-byte big-endian length."""

    payload = _canonical(validate_message(dict(message)))
    if len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds 1 MiB")
    return struct.pack(">I", len(payload)) + payload


def _reject_constant(value: str) -> None:
    raise ProtocolError(f"non-finite JSON number: {value}")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_frame(frame: bytes) -> dict[str, object]:
    """Decode one complete length-prefixed frame; reject trailing bytes."""

    if len(frame) < 4:
        raise ProtocolError("truncated frame header")
    size = struct.unpack(">I", frame[:4])[0]
    if size == 0 or size > MAX_FRAME_BYTES:
        raise ProtocolError("invalid frame length")
    if len(frame) != size + 4:
        raise ProtocolError("truncated frame or trailing bytes")
    try:
        payload = json.loads(
            frame[4:].decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except ProtocolError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProtocolError("invalid JSON frame") from exc
    return validate_message(payload)


def read_frame(stream: BufferedIOBase) -> dict[str, object]:
    """Read a single frame from a bounded binary pipe."""

    def read_exact(size: int, label: str) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = stream.read(size - len(data))
            if not chunk:
                raise ProtocolError(f"truncated frame {label}")
            data.extend(chunk)
        return bytes(data)

    header = read_exact(4, "header")
    size = struct.unpack(">I", header)[0]
    if size == 0 or size > MAX_FRAME_BYTES:
        raise ProtocolError("invalid frame length")
    return decode_frame(header + read_exact(size, "body"))


class OneTurnSession:
    """Enforce stage, alternating request/reply, done, and monotone seq."""

    def __init__(self) -> None:
        self._next_seq = 0
        self._phase = "start"
        self._pending_tool: str | None = None
        self._tool_requests = 0

    def accept(self, message: Mapping[str, object], *, sender: str) -> None:
        checked = validate_message(dict(message))
        if checked["seq"] != self._next_seq:
            raise ProtocolError("wrong message sequence")
        kind = checked["type"]
        if self._phase == "start":
            if kind != "stage_start" or sender != "host":
                raise ProtocolError("host stage_start required first")
            self._phase = "worker"
        elif self._phase == "worker":
            if sender != "worker":
                raise ProtocolError("worker message required")
            if kind == "tool_request":
                if self._tool_requests >= MAX_TOOL_REQUESTS:
                    raise ProtocolError("tool request limit exceeded")
                self._tool_requests += 1
                request = _object(checked["body"], {"tool", "args"}, "tool request")
                self._pending_tool = str(request["tool"])
                self._phase = "host"
            elif kind == "turn_done":
                self._phase = "done"
            else:
                raise ProtocolError("worker must request a tool or finish")
        elif self._phase == "host":
            if sender != "host" or kind != "tool_reply":
                raise ProtocolError("matching tool reply required")
            reply = _object(checked["body"], {"tool", "result"}, "tool reply")
            if reply["tool"] != self._pending_tool:
                raise ProtocolError("matching tool reply required")
            self._pending_tool = None
            self._phase = "worker"
        else:
            raise ProtocolError("turn already complete")
        self._next_seq += 1

    @property
    def complete(self) -> bool:
        return self._phase == "done"
