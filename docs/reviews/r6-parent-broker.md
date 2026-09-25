# R6 parent broker, offline slice

`BrokeredPolicyHook` owns two preopened pipe descriptors to a long-lived
worker. It does not launch a child or import candidate policy bytes. Each
`on_stage` starts a fresh protocol sequence at zero on the same pipes, sends
only the explicit visible `StageView` projection plus candidate-owned state,
and accepts a complete `turn_done` before the next stage. Tool requests are
validated by the R5 codec and routed in the parent through `ToolSurface`,
`ToolBudget`, or the injected model responder. The parent reconstructs typed
actions, gates verification actions against the same budget, and stores the
bounded full state. A framing, sequence, pipe, or monotonic deadline error
closes the descriptors and poisons the hook. Unexpected trusted callback
exceptions take the same path and remain chained as the cause of `BrokerError`.
This includes document-registry reveal failures before `stage_start` is sent.

Offline fake-pipe tests cover two stages on one worker, visible projection,
reread equivalence, action conversion, verification-action caps, overbudget
model refusal before dispatch, provider-tagged versus unknown usage, malformed
sequence, and a silent worker timeout. These tests execute only trusted test
callbacks. No Siflow/GPU call was made.

`MeteredModelReply.usage_source` labels numbers supplied by the adapter:
`provider`, `estimated`, or `unknown`. The broker's budget charges at least a
local input estimate for each dispatched call, including failures with unknown
usage. `provider_tokens_in/out` count only values explicitly tagged provider;
that tag is an adapter assertion, not independent proof of a provider bill.
The wire reply exposes budget counts, while the parent transcript records the
adapter input count and source separately. No live usage claim follows from
the offline fake adapter.

This is not yet a live executor. The launcher must supply and attest the OS
jail, audited policy digest, runtime hash, process limits, and worker lifecycle.
The synchronous responder/delegate calls also require their own deadlines:
the broker notices an overrun after such a call returns but cannot interrupt
one that never returns. Existing `ToolSurface.delegate` accepts text only and
uses a local word estimate, so actual auxiliary-provider usage is unavailable;
disable it or add a usage-bearing adapter before live accounting. The live
gate remains closed.
