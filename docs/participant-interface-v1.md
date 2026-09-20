# Participant interface v1: registration, state, and control arms

Status: **design spec; §State contract and §Arms amended 2026-09-20 by the
external review (root-cause report
[`root-cause-24-of-24-20260920.md`](root-cause-24-of-24-20260920.md))**.
The 2026-09-19 freeze governs already-executed records; the amendments
below govern everything after.
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

## State contract (amended 2026-09-20)

The 2026-09-19 clause 3 ("state resets to empty at every split boundary")
is **replaced**. Blanket state-clearing made retained learning impossible
and treated code-carried and memory-carried learning unequally. The
amended contract distinguishes three state kinds and a snapshot boundary:

| State kind | Examples | Boundary treatment |
| --- | --- | --- |
| **Working state** (current project) | current plan, completed steps, project-specific constraints | retained within one project; new independent projects initialize per task setting |
| **Learned persistent knowledge** | skills, historical experience, memory architecture, tool rules, legitimately observed facts | carried by the **frozen learning snapshot** into every allowed evaluation branch — equally for code, config, skill text, and memory stores |
| **Evaluation-branch temporary state** | gate-run scratch, sealed-task caches | confined to its branch; never written back to the development process, the snapshot, or another branch |

Amended clauses:

1. Serialization: unchanged (canonical sorted-key JSON, UTF-8,
   `PYTHONHASHSEED=0`, deterministic ordering).
2. Byte cap: unchanged in force, but **all persistence channels count** —
   declared state store, code files, memory packages, indexes, and any
   other durable bytes the system writes. The cap applies to the sum; a
   representation change may not move bytes out of accounting.
3. **Frozen learning snapshot**: the development trajectory produces
   `S_k`; evaluation branches (gate / replay / sealed / transfer) each
   start independently from `S_k`. Branches cannot write back to it or to
   each other. What a participant legitimately learned (facts, skills,
   code) is IN the snapshot; what an evaluation branch generated is OUT.
4. Transcript and memory-op ledger: unchanged (auditable per session).
5. Leak probe: unchanged (visible-gold canaries absent from gate state
   and packs — this remains the direct anti-leakage instrument, now
   alongside rather than instead of snapshot isolation).
6. Untrusted-data re-validation: unchanged.
7. **Content rule (replaces "method-experience-only", which is
   withdrawn)**: participants may retain ALL information legitimately
   acquired within their authorized observations (their own runs, their
   restricted feedback, their actions' results) and its derivations. The
   boundary is information SOURCE, TIME, and SCOPE — never the textual
   shape ("fact" vs "method"). Forbidden: hidden evaluation data, labels,
   `has_answer`-style flags, future material, other branches' state.
   "Method-experience-only" may appear only as a labeled analysis
   condition, never as the default contract.
8. **Ownership vs runtime freeze**: `S` is participant-owned, but a
   registration freezes at submission — `A_0`'s original is preserved;
   the model pool `μ` is registered once and runtime selection is
   pool-internal; whether `I` may modify itself is a declared property of
   the registration; all durable channels enter accounting.

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

## The arms (amended 2026-09-20)

The fixed arm is **redefined**: "no updating" must not mean "no memory".
A fixed strategy that cannot take notes or recall facts is not a baseline
for improvement — it is a handicapped system, and comparisons against it
measure the handicap (root-cause report, cause 4).

| Arm | `A_0` | `I` | Working state | Purpose |
| --- | --- | --- | --- | --- |
| **fixed-strategy reference** | frozen, reasonable strategy code | no-op | **fully operational** (read/write/recall within the project, per the state contract's working-state row) | "is updating worth it" — the denominator, WITH normal memory |
| **experience-accumulation-only** | same frozen strategy code | persistent-knowledge growth only; strategy code byte-frozen | operational; learned knowledge accumulates across projects within the snapshot discipline | isolates experience-content gains |
| **open-S researcher** | current open-S seed folder | CLI researcher edits | operational | researcher-driven strategy updates |
| **recuris-style (fidelity arm)** | memory package (E/W/ρ/C) | component-scoped, validation-gated memory evolution | operational | proves the interface admits external methods with core mechanisms preserved |
| **stateful control (slot)** | stateful grammar | matched random/sequential search | operational | deferred; must stay expressible |

Fairness: all arms face the identical task stream, feedback bandwidth
(same `F` schema and bytes), resource envelope `B`, identical reader
prompt shape (channel parity is a precondition — the root-cause report's
finding), and the same snapshot/branch rules. Matched non-agent search
arms are deferred; the slot stays implementable without redesign.

## Continuation vs migration (reported separately, amended 2026-09-20)

Two task relations are distinct measurements and are never pooled:

- **Continuation** (same world/user/project): past facts SHOULD help;
  measures state maintenance, update correctness, and use.
- **Migration** (new world, new entities, preserved dependency structure):
  measures whether the way of working transfers.

A high continuation score with low migration score is a reportable
pattern, not a failure to be averaged away. Anti-caching for migration is
structural (new worlds with new facts), not content-based filtering of
participant state.

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
(iii) the state contract checks (cap, snapshot isolation, transcript,
canary absence); (iv) for its tier, the reader gates. A registration that
fails any gate runs nowhere — engineering failure, not a scientific
result.

## Open-comparison vs mechanism-attribution (amended 2026-09-20)

The main comparison evaluates **whole systems** and reports initial
capability, post-experience capability, retention/migration, and full
cost — not deltas alone (a deliberately weak `A_0` can buy a large
"improvement"). Mechanism attribution (experience content vs strategy
update vs extra compute) is claimed ONLY within interface-compatible
analysis subsets where the 对照 arms exist; no promise is made to
decompose arbitrary black-box participants into additive contributions.
A method's win over a memory-operational fixed baseline is the honest
denominator; "improvement beats memory-less" is not a finding.
