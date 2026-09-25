# R5 policy IPC protocol slice

Status: codec and one-turn validation harness only. This branch does not run
candidate code, launch a child, forward a tool, call a provider, or change the
live isolation gate.

## Wire contract v1

Each message is UTF-8 JSON after a four-byte unsigned big-endian length.
The payload is at most 1 MiB. Writers emit sorted-key, compact JSON; readers
reject duplicate keys, non-finite numbers, malformed UTF-8/JSON, extra fields,
unknown message/tool/action names, oversized or truncated frames, and state
objects over 64 KiB measured as canonical UTF-8 JSON. Structured messages
carry `version: 1`, a zero-based consecutive `seq`, `type`, and `body`.

One stage follows this sequence:

1. Host sends `stage_start` with only the visible `StageView` fields and
   candidate-owned `state`. Documents and receipts have exact field schemas;
   evaluator-only fields cannot be serialized into this message.
2. Worker sends `tool_request` for one named operation. Its argument schema
   is exact: `ask_model(prompt)`, `reread(doc_id, span)`,
   `query_sandbox(pattern)`, `request_verification(check, subject)`, or
   `delegate(query, doc_ids)`. There is no generic method or path field.
3. Host sends a matching `tool_reply` with a typed result. Requests and
   replies alternate; at most 128 requests are allowed in this one turn.
4. Worker sends `turn_done` containing pack text, exact `Action.to_dict`
   shapes, the full updated candidate-owned state, memory writes, and errors.
   Both state and memory writes are separately bounded to 64 KiB. Returning
   full state preserves policies that mutate `turn.state` directly. Action
   kinds and precondition shapes are checked against the lifecycle `Action`
   constructor. Each memory write must appear in the full returned state.
   Completion closes the sequence.

`OneTurnSession.accept(..., sender=...)` checks host/worker roles, order,
monotone sequence numbers, and matching tool names. Tests cover round-trip,
negative framing/JSON/schema/action cases, and ordering. The limit is a
protocol ceiling, not permission to spend 128 calls: the future host broker
must apply the actual `ToolBudget` before every operation.

## Required integration before any live use

Build a jailed worker and trusted host broker. The host must construct the
visible stage projection without copying evaluator-only data, check the
candidate hash at launch and completion, enforce tool budgets before calls,
meter failures/refusals, validate action permissions against the current
environment, and bound total turns plus CPU/memory/wall time. Negative tests
must prove that candidate code cannot access host files, environment secrets,
network, process state, or evaluator objects. The existing live gate remains
closed until those checks and the end-to-end legitimate-turn comparison pass.
