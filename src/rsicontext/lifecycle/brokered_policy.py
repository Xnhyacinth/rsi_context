"""Trusted parent-side broker for one stage at a time over preopened pipes.

The broker never imports or executes candidate policy bytes. A separate
launcher must supply a jailed, audited, long-lived worker and owns process
lifetime; this hook owns only its two pipe descriptors and closes them on a
fatal protocol or transport error.
"""

from __future__ import annotations

import hashlib
import math
import os
import select
import struct
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from rsicontext.lifecycle.env import Action, ActionKind, ProjectState
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget, ToolReceipt, ToolSurface
from rsicontext.security.policy_protocol import (
    MAX_FRAME_BYTES,
    OneTurnSession,
    ProtocolError,
    decode_frame,
    encode_message,
)


class BrokerError(RuntimeError):
    """A fatal policy pipe, deadline, or protocol failure."""


@dataclass(frozen=True, slots=True)
class MeteredModelReply:
    """Adapter result; usage provenance is separate from budget charges."""

    ok: bool
    content: str = ""
    cause: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    usage_source: Literal["provider", "estimated", "unknown"] = "unknown"

    def __post_init__(self) -> None:
        if (
            type(self.ok) is not bool
            or not isinstance(self.content, str)
            or not isinstance(self.cause, str)
        ):
            raise TypeError("model reply requires boolean status and string content/cause")
        for name, value in (("tokens_in", self.tokens_in), ("tokens_out", self.tokens_out)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.usage_source not in ("provider", "estimated", "unknown"):
            raise ValueError("invalid usage_source")


def _visible_stage(stage: StageView) -> dict[str, object]:
    """Project the participant view by explicit allowlist, never dataclass __dict__."""

    return {
        "stage_id": stage.stage_id,
        "kind": stage.kind,
        "prompt_text": stage.prompt_text,
        "documents": [doc.to_dict() for doc in stage.documents],
        "axes": stage.axes.to_dict(),
        "remaining_budget": stage.remaining_budget,
        "receipts": [receipt.to_dict() for receipt in stage.receipts],
    }


def _read_exact(fd: int, count: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BrokerError("policy turn deadline exceeded while reading")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise BrokerError("policy turn deadline exceeded while reading")
        try:
            chunk = os.read(fd, count - len(data))
        except BlockingIOError:
            continue
        if not chunk:
            raise BrokerError("policy worker closed pipe before completing frame")
        data.extend(chunk)
    return bytes(data)


def _read_message(fd: int, deadline: float) -> dict[str, object]:
    header = _read_exact(fd, 4, deadline)
    length = struct.unpack(">I", header)[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("invalid policy frame length")
    return decode_frame(header + _read_exact(fd, length, deadline))


def _write_message(fd: int, message: Mapping[str, object], deadline: float) -> None:
    frame = encode_message(message)
    sent = 0
    while sent < len(frame):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BrokerError("policy turn deadline exceeded while writing")
        _, ready, _ = select.select([], [fd], [], remaining)
        if not ready:
            raise BrokerError("policy turn deadline exceeded while writing")
        try:
            written = os.write(fd, frame[sent:])
        except BlockingIOError:
            continue
        if written <= 0:
            raise BrokerError("policy worker pipe made no write progress")
        sent += written


def _action_from_wire(value: object) -> Action:
    # The codec already checked the exact field set and Action constructor.
    # Reconstruct in the trusted process instead of accepting worker objects.
    item = cast(dict[str, object], value)
    return Action(
        kind=cast(ActionKind, item["kind"]),
        record_id=cast(str, item["record_id"]),
        fields=cast(dict[str, object], item["fields"]),
        provenance=tuple(cast(list[str], item["provenance"])),
        precondition_refs=tuple(cast(list[str], item["precondition_refs"])),
        precondition_current_revision=cast(int | None, item["precondition_current_revision"]),
        precondition_revision_scope=tuple(cast(list[str], item["precondition_revision_scope"])),
        precondition_scope_constraint=cast(
            dict[str, object] | None, item["precondition_scope_constraint"]
        ),
    )


class BrokeredPolicyHook:
    """Stage hook over one long-lived worker; each stage resets wire seq to 0."""

    def __init__(
        self,
        *,
        read_fd: int,
        write_fd: int,
        state: dict[str, Any],
        tool_budget: ToolBudget,
        env: ProjectState,
        timeout_seconds: float,
        registry: DocumentRegistry | None = None,
        responder: Callable[[str], MeteredModelReply] | None = None,
        delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if read_fd == write_fd:
            raise ValueError("read_fd and write_fd must be separate pipe descriptors")
        os.set_blocking(read_fd, False)
        os.set_blocking(write_fd, False)
        self._read_fd = read_fd
        self._write_fd = write_fd
        self._closed = False
        self._turn_lock = threading.Lock()
        self.state = state
        self.tool_budget = tool_budget
        self.env = env
        self.timeout_seconds = timeout_seconds
        self.registry = registry if registry is not None else DocumentRegistry()
        self.responder = responder
        self.delegate_runner = delegate_runner
        self.model_calls = 0
        self.model_tokens_in = 0
        self.model_tokens_out = 0
        self.provider_tokens_in = 0
        self.provider_tokens_out = 0
        self.model_transcript: list[dict[str, object]] = []
        self.policy_errors: list[str] = []

    def close(self) -> None:
        """Poison the hook and close owned descriptors, idempotently."""

        if self._closed:
            return
        self._closed = True
        for fd in (self._read_fd, self._write_fd):
            os.close(fd)

    def _model(self, prompt: str, stage: StageView) -> dict[str, object]:
        budget = self.tool_budget
        charged_in = 0
        if self.responder is None:
            budget.charge(0, 0)
            reply = MeteredModelReply(ok=False, cause="no model channel installed")
        elif not prompt.strip():
            budget.charge(0, 0)
            reply = MeteredModelReply(ok=False, cause="ask_model requires a non-empty prompt")
        elif (refusal := budget.enforce("ask_model")) is not None:
            budget.charge(0, 0)
            reply = MeteredModelReply(ok=False, cause=refusal)
        else:
            estimated_in = max(1, len(prompt.split()))
            if (refusal := budget.enforce_input("ask_model", estimated_in)) is not None:
                budget.charge(0, 0)
                reply = MeteredModelReply(ok=False, cause=refusal)
            else:
                budget.charge(0, 0)
                self.model_calls += 1
                try:
                    reply = self.responder(prompt)
                    if not isinstance(reply, MeteredModelReply):
                        raise TypeError("responder must return MeteredModelReply")
                except Exception as exc:
                    reply = MeteredModelReply(
                        ok=False,
                        cause=f"model call failed: {type(exc).__name__}: {exc}",
                        tokens_in=estimated_in,
                        usage_source="unknown",
                    )
                charged_in = max(estimated_in, reply.tokens_in)
                budget.charge_input(charged_in)
                budget.charge_output(reply.tokens_out)
                self.model_tokens_in += charged_in
                self.model_tokens_out += reply.tokens_out
                if reply.usage_source == "provider":
                    self.provider_tokens_in += reply.tokens_in
                    self.provider_tokens_out += reply.tokens_out
                self.model_transcript.append(
                    {
                        "stage_kind": stage.kind,
                        "stage_id": stage.stage_id,
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
                        "prompt_head": prompt[:2000],
                        "ok": reply.ok,
                        "reply_head": reply.content[:2000] if reply.ok else "",
                        "cause": reply.cause,
                        "tokens_in": charged_in,
                        "tokens_out": reply.tokens_out,
                        "adapter_tokens_in": reply.tokens_in,
                        "usage_source": reply.usage_source,
                    }
                )
        receipt = ToolReceipt(
            tool="ask_model",
            ok=reply.ok,
            answer=reply.content,
            cause=reply.cause,
            tokens_in=charged_in,
            tokens_out=reply.tokens_out,
        )
        budget.receipts.append(receipt)
        return {
            "ok": reply.ok,
            "answer": reply.content,
            "cause": reply.cause,
            "tokens_in": charged_in,
            "tokens_out": reply.tokens_out,
        }

    def _tool(
        self, body: dict[str, object], surface: ToolSurface, stage: StageView
    ) -> dict[str, object]:
        name = cast(str, body["tool"])
        args = cast(dict[str, object], body["args"])
        if name == "ask_model":
            return self._model(cast(str, args["prompt"]), stage)
        if name == "reread":
            span = cast(list[int] | None, args["span"])
            receipt = surface.reread(
                cast(str, args["doc_id"]), None if span is None else (span[0], span[1])
            )
        elif name == "query_sandbox":
            receipt = surface.query_sandbox(cast(str, args["pattern"]))
        elif name == "request_verification":
            receipt = surface.request_verification(
                cast(str, args["check"]), cast(str, args["subject"])
            )
        elif name == "delegate":
            receipt = surface.delegate(cast(str, args["query"]), cast(list[str], args["doc_ids"]))
        else:
            raise ProtocolError("unknown tool after validation")
        return {
            "ok": receipt.ok,
            "answer": receipt.answer,
            "cause": receipt.cause,
            "tokens_in": receipt.tokens_in,
            "tokens_out": receipt.tokens_out,
        }

    def on_stage(self, stage: StageView) -> StageResponse:
        """Process exactly one stage; a fatal error closes both pipe ends."""

        if not self._turn_lock.acquire(blocking=False):
            raise BrokerError("policy broker already has an active turn")
        try:
            return self._run_stage(stage)
        finally:
            self._turn_lock.release()

    def _run_stage(self, stage: StageView) -> StageResponse:
        if self._closed:
            raise BrokerError("policy broker is closed after a fatal error")
        deadline = time.monotonic() + self.timeout_seconds
        session = OneTurnSession()
        try:
            surface = ToolSurface(
                documents=stage.documents,
                env=self.env,
                budget=self.tool_budget,
                registry=self.registry,
                delegate_runner=self.delegate_runner,
            )
            start = {
                "version": 1,
                "seq": 0,
                "type": "stage_start",
                "body": {"view": _visible_stage(stage), "state": self.state},
            }
            session.accept(start, sender="host")
            _write_message(self._write_fd, start, deadline)
            while not session.complete:
                message = _read_message(self._read_fd, deadline)
                if time.monotonic() >= deadline:
                    raise BrokerError("policy turn deadline exceeded after frame read")
                session.accept(message, sender="worker")
                if message["type"] == "tool_request":
                    body = cast(dict[str, object], message["body"])
                    name = cast(str, body["tool"])
                    result = self._tool(body, surface, stage)
                    if time.monotonic() >= deadline:
                        raise BrokerError("policy turn deadline exceeded during tool call")
                    reply = {
                        "version": 1,
                        "seq": cast(int, message["seq"]) + 1,
                        "type": "tool_reply",
                        "body": {"tool": name, "result": result},
                    }
                    session.accept(reply, sender="host")
                    _write_message(self._write_fd, reply, deadline)
                    continue
                if message["type"] != "turn_done":
                    raise ProtocolError("unexpected worker message")
                body = cast(dict[str, object], message["body"])
                decision = cast(dict[str, object], body["decision"])
                actions = tuple(
                    _action_from_wire(item) for item in cast(list[object], decision["actions"])
                )
                admitted: list[Action] = []
                for action in actions:
                    if action.kind == "request_verification":
                        refusal = self.tool_budget.enforce("request_verification (action)")
                        if refusal is not None:
                            self.tool_budget.charge(0, 0)
                            self.policy_errors.append(f"action dropped: {refusal}")
                            continue
                        self.tool_budget.charge_verification()
                    admitted.append(action)
                final_state = cast(dict[str, Any], body["state"])
                self.state.clear()
                self.state.update(final_state)
                self.policy_errors.extend(cast(list[str], decision["errors"]))
                return StageResponse(
                    pack_text=cast(str, decision["pack_text"]),
                    actions=tuple(admitted),
                )
            raise ProtocolError("worker turn ended without decision")
        except Exception as exc:
            self.policy_errors.append(f"broker failed: {type(exc).__name__}: {exc}")
            self.close()
            raise BrokerError(f"policy broker failed: {exc}") from exc
