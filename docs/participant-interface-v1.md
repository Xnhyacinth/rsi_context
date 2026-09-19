# Participant interface v1: registration, state, and control arms

Status: **design spec, frozen for Phase B implementation**. 2026-09-19.
Parent contract: [`benchmark-contract-v2.md`](benchmark-contract-v2.md).
Task-family spec: [`task-family-research-v1.md`](task-family-research-v1.md).

## The participant object

A registered participant is `S = (A_0, Σ, I, μ)`:

| Component | Contents | Constraints |
| --- | --- | --- |
| `A_0` initial agent system | executable strategy code (any mix of Python, config, skill text, retrieval stores, workflows) | must run under the benchmark worker; auditable; no benchmark-internal imports |
| `Σ` retainable-state specification | the declared schema of state the system may persist across items/sessions | canonical serialization; byte cap inside the resource envelope `B`; provenance fields typed when the family's provenance metrics apply |
| `I` improvement process | code or procedure that changes `A_0`/`Σ` between projects (memory evolution, code editing, architecture search — or a no-op) | its own tokens/$/wall are accounted as `C_improve`; it consumes the restricted feedback `F` only |
| `μ` serving configuration | reader/model pool selection | evidence tier T1/T2/T3 per the contract; pools fixed at registration; every call accounted |

The existing CLI researcher surface (`src/rsicontext/researcher/api.py`:
turn in → policy-tree edits + manifest out; `schemas/manifest.schema.json`
for the submission artifact) is retained as ONE adapter: it implements `I`
for the open-S arm. The generalization is that `I` no longer implies
"external CLI model editing Python files" — an in-process improvement loop
(e.g. a Recuris-style validation-gated memory updater) is equally
registrable, provided it satisfies the boundary rules below.

Boundary rules (what stays benchmark-owned): task stream and order; the
feedback `F` schema and bandwidth; hidden gate/sealed items; the resource
envelope `B`; audit and manifest formats; result definitions; the sandboxed
action environment. "External strong researcher assisting a target agent"
and "same-model self-improvement" are recorded as distinct registration
labels and never pooled.

## State contract

1. Serialization: canonical sorted-key JSON, UTF-8; `PYTHONHASHSEED=0` pinned
   in the worker environment; deterministic ordering everywhere (v1 review
   finding: unpinned hash order is a latent variance source the per-item-fresh
   design masked).
2. Byte cap: persisted state size counts against `B`, enforced at the
   serialization boundary, not by trust.
3. State resets to empty at every split boundary — visible, gate, replay, and
   sealed runs are separate sessions; gate/replay sessions contain only gate
   items.
4. The full state transcript (post-item state bytes + memory-op ledger:
   writes/reads, bytes, ops) is logged per session and auditable.
5. Leak probe (pre-registered): visible-gold canary tokens injected in a
   canary session must be absent from all gate-session state and packs.
6. State is untrusted-code-authored persistent data: re-validated (cap,
   schema, parse) at every load; the auditor treats state blobs as data, not
   code; no filesystem persistence outside the declared store.

## Implementation anchors (verified against the code, 2026-09-19)

- The campaign runner is already callback-based and duck-typed:
  `ResearcherCallback = __call__(ResearchRoundRequest) -> None`
  (`src/rsicontext/campaign/researcher.py:103-106`); the runner never invokes
  a CLI itself. The generalization point is therefore ONE layer: replace the
  `ResearcherKind = Literal["codex","claude","api"]` dispatch
  (`campaign/autonomous_dynamic.py:88,372-389`) with a formal participant
  protocol.
- Three structural gaps found for non-CLI participants: (a) the workspace is
  rematerialized from the immutable store each round (`researcher.py:642-655`)
  — no participant-owned persistent state channel, so memory evolution must
  be re-encoded into policy bytes; (b) usage accounting expects CLI
  `TokenUsage` events (`researcher/streams.py:17-29`,
  `autonomous_dynamic.py:892`); (c) integrity checks hash the researcher
  executable (`autonomous_dynamic.py:1286-1317`). All three are in the
  participant-protocol build.
- Manifest/auditor/lineage machinery is content-agnostic and survives the
  generalization; what breaks is the one-call-compiler assumption
  (`ContextPack` verbatim-span validation `policy/types.py:162-189`, single
  `Policy.assemble` worker entrypoint `eval/_policy_worker.py:26-42`) — that
  is the submission-schema-v2 work, scoped with the lifecycle runtime.
- The fresh-policy JSON protocol (duplicate-key rejection, canonical
  sort_keys; `eval/fresh_policy.py:349-414`) is the template for the
  state-in/state-out protocol; `PYTHONHASHSEED` pinning goes into
  `_WORKER_ENVIRONMENT` (`fresh_policy.py:36-41`) and `_BASE_ENVIRONMENT`
  (`researcher/process.py:118`).

## The three first arms

| Arm | `A_0` | `I` | Purpose |
| --- | --- | --- | --- |
| **fixed-strategy reference** | a frozen, reasonable baseline strategy (v1 H0-style source-order/evidence packing generalized to the stage loop) | no-op | the "is updating worth it" denominator; also carries the saturation kills |
| **experience-accumulation-only** | same frozen strategy code; `Σ` active (facts/notes accumulate across projects) | state growth only; strategy code byte-frozen | isolates experience-content gains from strategy-update gains — the external review's key decomposition |
| **open-S researcher** | current open-S seed folder | CLI researcher edits (the existing harness) | the researcher-driven strategy-update arm |

Fairness: all arms face the identical task stream, feedback bandwidth
(same `F` schema and bytes), resource envelope `B`, and split boundaries.
The experience arm and the researcher arm both persist state (the v1
"stateful fairness rule" — a control that exists gets the same state and
budget, or the comparison is invalid). Matched non-agent search arms
(stateful Random-K / Sequential-K over a stateful grammar) are deferred;
the registration interface must leave their slot implementable without
redesign.

## Reader tiers in registration

`μ` declares one pool: T1 anchor (deterministic replay rights), T2 versioned
API (per contract gates: pre/post canaries, ≥5-repeat variance floor,
version+echo recording, rejection ceiling), or T3 compatibility-only.
Cross-tier pooling in one reported comparison is forbidden; tier is a
reported column.

## Manifest extensions

The v1 manifest (candidate identity, evidence, mechanisms, cost) gains:
`participant_id`, `arm`, `state_schema` (hash of `Σ`), `improvement_cost`
(`C_improve` tokens/$/wall), `pool_tier`, and `state_transcript_ref`. All
manifest hashing and audit paths (`security/audit.py`) extend, none are
replaced.

## Qualification of a registration

Before entering a reported cell, a registration passes: (i) the auditor on
`A_0` and `I` code; (ii) a smoke lifecycle (one project end-to-end);
(iii) the state contract checks (cap, reset, transcript, canary absence);
(iv) for its tier, the reader gates. A registration that fails any gate runs
nowhere — engineering failure, not a scientific result.
