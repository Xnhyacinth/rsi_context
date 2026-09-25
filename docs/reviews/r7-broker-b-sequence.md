# R7 brokered B sequence: offline execution check

Status: **development integration only; live gate remains closed**. This
slice connects the R6 trusted pipe broker to the real
`run_session_sequence` boundary. It uses trusted test threads as fake
children and makes no model API or GPU call.

## Defect and change

Before this change, the sequence runner called `bind_env` only when a
hook provided it. `BrokeredPolicyHook` had no such method, so its
`ToolSurface` could verify against a placeholder `ProjectState` while
`run_lifecycle` installed the evaluator oracle in a different one. A
two-session test with otherwise legal actions reproduced **FAIL/FAIL**
where the actual project should have produced **PASS/PASS**.

The broker now accepts one explicit pre-turn binding of the runner's
`ProjectState`, shared `ToolBudget`, and shared `DocumentRegistry`.
Rebinding to different resources or binding after a stage starts
raises a named error. The sequence runner gives the broker those exact
objects before any stage and closes each hook after its session. The
broker may own a worker handle; `close()` attempts both pipe closes
and the child close even if one cleanup step fails. Protocol and
trusted-runner errors also close the worker and keep the original cause.

## Evidence

The test world has two actual sessions and one shared project state.
The first session requests an environment verification through the
broker's tool RPC, queries its own sandbox at ledgered cost to discover
the issued evidence ID, then finalizes `migration_commit`. The fake
worker does not guess the host budget's internal ID. The second worker
starts with only the prior `carry`, rereads a document revealed in the
first session using the shared registry, obtains a second verification,
and finalizes `renewal`. The shared budget records both checks, both
sandbox queries, and the reread. The first worker's non-carry `work`
value is absent in session 2.
Both session workers and all host pipe descriptors close on success.

| Controlled path | Session 1 | Session 2 | Mechanism |
| --- | --- | --- | --- |
| Legal PASS receipt | PASS | PASS | First verification is environment-issued and precedes its finalization. |
| First verification FAIL | FAIL | FAIL | Forced first finalization does not supply a prior PASS. |
| Late first verification | FAIL | FAIL | Second-session repair cannot satisfy the session-entry prior gate. |
| Forged first verification | FAIL | FAIL | A participant record with `performed_by=environment` lacks an environment-issued ID. |

Malformed protocol input and a trusted runner exception each leave the
child reaped and both host pipe descriptors closed. The direct broker
test also proves resource rebinding is refused after the first turn.
The focused regression command is:

```bash
RSICONTEXT_OTEL_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0 \
uv run --no-sync pytest -q --cov=rsicontext.lifecycle.brokered_policy \
  --cov=rsicontext.lifecycle.session_sequence --cov-branch --cov-fail-under=0 \
  tests/test_brokered_policy.py tests/test_brokered_sequence.py \
  tests/test_b_group_sessions.py tests/test_c_group.py \
  tests/test_otel_long_b.py tests/test_otel_long_b_v2.py \
  tests/test_k8s_parent.py tests/test_group_baselines.py
```

This exercises a trusted fake child, not the jailed candidate process.
The launcher still must attest the runtime and policy bytes, and
synchronous model/delegate callbacks need bounded cancellation and
provider usage before paid live execution.
