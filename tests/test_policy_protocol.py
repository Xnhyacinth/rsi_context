"""Byte and sequence regression tests for the isolated policy wire contract."""

from __future__ import annotations

import io
import json
import struct
from copy import deepcopy
from typing import Any

import pytest

from rsicontext.security.policy_protocol import (
    MAX_FRAME_BYTES,
    MAX_TOOL_REQUESTS,
    OneTurnSession,
    ProtocolError,
    decode_frame,
    encode_message,
    read_frame,
)


def _message(kind: str, seq: int, body: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "seq": seq, "type": kind, "body": body}


def _stage() -> dict[str, object]:
    return _message(
        "stage_start",
        0,
        {
            "view": {
                "stage_id": "s1",
                "kind": "survey",
                "prompt_text": "Read the visible document.",
                "documents": [
                    {
                        "doc_id": "d1",
                        "title": "Visible",
                        "text": "Evidence",
                        "source_url": "",
                        "retrieved_date": "",
                        "superseded_by": None,
                    }
                ],
                "axes": {
                    "information_scale_tokens": 100,
                    "dependency_distance_stages": 1,
                    "persistence_span_resets": 0,
                    "action_dependency": "strong",
                    "environment_changes": 0,
                },
                "remaining_budget": 4,
                "receipts": [],
            },
            "state": {"notes": ["d1"]},
        },
    )


def _done(seq: int = 1) -> dict[str, object]:
    return _message(
        "turn_done",
        seq,
        {
            "decision": {
                "pack_text": "[[doc:d1]]",
                "actions": [
                    {
                        "kind": "finalize",
                        "record_id": "r1",
                        "fields": {"answer": "A"},
                        "provenance": ["d1"],
                        "precondition_refs": [],
                        "precondition_current_revision": None,
                        "precondition_revision_scope": [],
                        "precondition_scope_constraint": None,
                    }
                ],
                "memory_writes": {"notes": ["d1"]},
                "errors": [],
            },
            "state": {"notes": ["d1"]},
        },
    )


def _raw(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


def test_round_trip_and_one_stage_order() -> None:
    session = OneTurnSession()
    messages = [
        _stage(),
        _message("tool_request", 1, {"tool": "reread", "args": {"doc_id": "d1", "span": [0, 1]}}),
        _message(
            "tool_reply",
            2,
            {
                "tool": "reread",
                "result": {
                    "ok": True,
                    "answer": "Evidence",
                    "cause": "",
                    "tokens_in": 33,
                    "tokens_out": 0,
                },
            },
        ),
        _done(3),
    ]
    for message, sender in zip(messages, ("host", "worker", "host", "worker"), strict=True):
        decoded = read_frame(io.BytesIO(encode_message(message)))
        assert decoded == message
        session.accept(decoded, sender=sender)
    assert session.complete


def test_short_pipe_reads_reassemble_header_and_body() -> None:
    class ShortRead(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            return super().read(2 if size is None else min(size, 2))

    assert read_frame(ShortRead(encode_message(_stage()))) == _stage()


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        b"\x00\x00",
        struct.pack(">I", MAX_FRAME_BYTES + 1),
        _raw(b"{"),
        struct.pack(">I", 9) + b"{}",
        _raw(b"{}") + b"trailing",
    ],
)
def test_invalid_or_truncated_frame(bad: bytes) -> None:
    with pytest.raises(ProtocolError):
        decode_frame(bad)


def test_stream_truncation_and_oversize_rejected_before_read() -> None:
    with pytest.raises(ProtocolError, match="truncated frame body"):
        read_frame(io.BytesIO(struct.pack(">I", 20) + b"{}"))
    with pytest.raises(ProtocolError, match="invalid frame length"):
        read_frame(io.BytesIO(struct.pack(">I", MAX_FRAME_BYTES + 1)))


def test_encoded_frame_over_one_megabyte_rejected() -> None:
    done: dict[str, Any] = deepcopy(_done())
    done["body"]["decision"]["pack_text"] = "x" * MAX_FRAME_BYTES
    with pytest.raises(ProtocolError, match="frame exceeds"):
        encode_message(done)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"version":1,"version":1,"seq":0,"type":"stage_start","body":{}}',
        b'{"version":1,"seq":0,"type":"stage_start","body":{"state":{"x":1,"x":2}}}',
        b'{"version":1,"seq":0,"type":"turn_done","body":{"decision":{"pack_text":NaN}}}',
        b'{"version":1,"seq":0,"type":"turn_done","body":{"decision":{"pack_text":Infinity}}}',
    ],
)
def test_duplicate_keys_and_nonfinite_json_rejected(payload: bytes) -> None:
    with pytest.raises(ProtocolError):
        decode_frame(_raw(payload))


def test_exact_fields_reject_forged_material_and_extra_arguments() -> None:
    stage: dict[str, Any] = deepcopy(_stage())
    stage["body"]["view"]["gold_evidence_ids"] = ["secret"]
    with pytest.raises(ProtocolError, match="view requires exactly"):
        encode_message(stage)
    request = _message(
        "tool_request",
        1,
        {"tool": "reread", "args": {"doc_id": "d1", "span": None, "path": "/etc/passwd"}},
    )
    with pytest.raises(ProtocolError, match="tool args requires exactly"):
        encode_message(request)
    unknown = _message("tool_request", 1, {"tool": "open", "args": {"path": "/etc/passwd"}})
    with pytest.raises(ProtocolError, match="unknown tool"):
        encode_message(unknown)


def test_state_limit_is_canonical_utf8_bytes() -> None:
    stage: dict[str, Any] = deepcopy(_stage())
    stage["body"]["state"] = {"a": "é" * 33_000}
    with pytest.raises(ProtocolError, match="state exceeds"):
        encode_message(stage)
    done: dict[str, Any] = deepcopy(_done())
    done["body"]["decision"]["memory_writes"] = {"a": "x" * 65_536}
    with pytest.raises(ProtocolError, match="memory_writes exceeds"):
        encode_message(done)
    done = deepcopy(_done())
    done["body"]["state"] = {"a": "x" * 65_536}
    with pytest.raises(ProtocolError, match="state exceeds"):
        encode_message(done)
    done = deepcopy(_done())
    done["body"]["state"] = {"notes": ["other"]}
    with pytest.raises(ProtocolError, match="memory_writes must appear"):
        encode_message(done)


def test_forged_action_and_invalid_action_shapes_rejected() -> None:
    for change in ({"method": "delete"}, {"kind": "delete_record"}):
        done: dict[str, Any] = deepcopy(_done())
        done["body"]["decision"]["actions"][0].update(change)
        with pytest.raises(ProtocolError):
            encode_message(done)
    done = deepcopy(_done())
    done["body"]["decision"]["actions"][0]["provenance"] = []
    with pytest.raises(ProtocolError, match="invalid action"):
        encode_message(done)
    done = deepcopy(_done())
    action = done["body"]["decision"]["actions"][0]
    action["kind"] = "request_verification"
    action["fields"] = {"check": "x", "subject": "y", "verdict": "pass"}
    with pytest.raises(ProtocolError, match="invalid action"):
        encode_message(done)


def test_wrong_sequence_order_and_reply_tool_rejected() -> None:
    session = OneTurnSession()
    with pytest.raises(ProtocolError, match="host stage_start required"):
        session.accept(_done(0), sender="worker")
    with pytest.raises(ProtocolError, match="host stage_start required"):
        session.accept(_stage(), sender="worker")
    session.accept(_stage(), sender="host")
    with pytest.raises(ProtocolError, match="wrong message sequence"):
        session.accept(_done(2), sender="worker")
    session.accept(
        _message("tool_request", 1, {"tool": "ask_model", "args": {"prompt": "Why?"}}),
        sender="worker",
    )
    with pytest.raises(ProtocolError, match="matching tool reply"):
        session.accept(
            _message(
                "tool_reply",
                2,
                {
                    "tool": "reread",
                    "result": {
                        "ok": False,
                        "answer": "",
                        "cause": "refused",
                        "tokens_in": 0,
                        "tokens_out": 0,
                    },
                },
            ),
            sender="host",
        )
    with pytest.raises(ProtocolError, match="matching tool reply"):
        session.accept(_done(2), sender="worker")


def test_completed_turn_and_request_limit_rejected() -> None:
    session = OneTurnSession()
    session.accept(_stage(), sender="host")
    result: dict[str, object] = {
        "tool": "ask_model",
        "result": {"ok": False, "answer": "", "cause": "refused", "tokens_in": 0, "tokens_out": 0},
    }
    for index in range(MAX_TOOL_REQUESTS):
        session.accept(
            _message("tool_request", 1 + 2 * index, {"tool": "ask_model", "args": {"prompt": "x"}}),
            sender="worker",
        )
        session.accept(_message("tool_reply", 2 + 2 * index, result), sender="host")
    with pytest.raises(ProtocolError, match="tool request limit"):
        session.accept(
            _message(
                "tool_request",
                1 + 2 * MAX_TOOL_REQUESTS,
                {"tool": "ask_model", "args": {"prompt": "x"}},
            ),
            sender="worker",
        )
    session.accept(_done(1 + 2 * MAX_TOOL_REQUESTS), sender="worker")
    with pytest.raises(ProtocolError, match="turn already complete"):
        session.accept(_done(2 + 2 * MAX_TOOL_REQUESTS), sender="worker")


def test_rejects_noncanonical_python_values_and_unknown_fields() -> None:
    bad: dict[str, Any] = deepcopy(_stage())
    bad["body"]["state"] = {"n": float("nan")}
    with pytest.raises(ProtocolError, match="non-finite"):
        encode_message(bad)
    bad = deepcopy(_stage())
    bad["extra"] = 1
    with pytest.raises(ProtocolError, match="message requires exactly"):
        encode_message(bad)
    bad = json.loads(json.dumps(_done()))
    bad["body"]["decision"]["actions"][0]["fields"] = {"a": object()}
    with pytest.raises(ProtocolError, match="unsupported JSON"):
        encode_message(bad)


def test_malformed_type_fails_as_protocol_error() -> None:
    stage: dict[str, Any] = deepcopy(_stage())
    stage["body"]["view"]["kind"] = ["survey"]
    with pytest.raises(ProtocolError):
        encode_message(stage)
    reply = _message(
        "tool_reply",
        2,
        {
            "tool": ["reread"],
            "result": {"ok": True, "answer": "x", "cause": "", "tokens_in": 1, "tokens_out": 0},
        },
    )
    with pytest.raises(ProtocolError):
        encode_message(reply)
