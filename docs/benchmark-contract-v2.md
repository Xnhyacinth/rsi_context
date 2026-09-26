# RSIBench-Context v2 benchmark contract

Status: **normative charter for the v2 redesign — proposal frozen 2026-09-19,
implementation not yet built**. This document supersedes
[`goal-redesign-proposal-2026-09-18.md`](goal-redesign-proposal-2026-09-18.md)
as the statement of what the project is; that proposal's adversarial review
record (its §9) remains normative history. The v1
[`study-contract.md`](study-contract.md) governs every already-executed v1
record (open-S campaigns, hy3/local-reader qualifications, data
qualifications); those records are immutable and are not reinterpreted by this
document.

Design inputs: an external review of the 2026-09-18 proposal (2026-09-19),
owner decisions recorded in
[`../plans/rsibench-context-sorted-toast.md`](../plans/rsibench-context-sorted-toast.md),
and verified protocol deep-reads of the 2026 RSI/memory wave (Recuris
2608.24876; MGM 2608.07645; Dream-RSI 2609.14858; ModularRSI 2609.14857;
SoL-Pi 2609.20519; PAST-Bench 2608.04003; Evo-Memory 2511.20857; MemoryBench
2510.17281; MemoryArena 2602.16313; MemEvolve 2512.18746; AutoMem 2608.14621;
harness-evolution protocol studies 2607.12227 and 2607.14004) plus the
2026-09-19 verified benchmark-side sweep (AgentStream 2608.00155; SEA-Eval
2604.08988; StudyBench 2609.00787; Aspire 2608.31111; FinEvo-Bench
2608.06144; Live-Evo 2602.02369; RSI2 2609.06396; the
Fragility-of-Self-Improving-Agents critique 2608.18066).

## Position against the 2026 benchmark-side neighbors (verified 2026-09-19)

The naive claim "nobody evaluates improvement on task streams" is **false**
(PAST-Bench, AgentStream, SEA-Eval, FinEvo-Bench all do), and "nobody
compares improvement methods under one protocol" is false at method-paper
level (AgentStream, StudyBench). Each axis of our design is individually
occupied. The defensible position is the **conjunction**, and every neighbor
line below states what we must additionally answer to not be redundant:

| Neighbor | Occupies | We must additionally answer |
| --- | --- | --- |
| PAST-Bench (2608.04003) | retained-experience gains of fixed frameworks on fresh-session orders, with matched persistence-on/off controls and a Mechanism-Evidence Score | open the improvement object to participant-supplied arbitrary processes; long-doc evidence; matched improvement-cost accounting; replay |
| AgentStream (2608.00155) | five author-selected self-evolving methods on streams (isolated/sequential/interleaved), no-evolution baseline, order stability | make tasks information/action-coupled, not just evolution-state-coupled; retention over horizon; open submissions |
| Evo-Memory (2511.20857) | memory-content-only evolution on continuous ordered streams, 10+ modules, matched retrieval budget | permit policy/architecture/code to change; coupled lifecycles; cost-of-improvement |
| MemoryArena (2602.16313) | memory USE by fixed systems on coupled multi-session lifecycles (766 tasks, ~6.9 interdependent subtasks) | improvement across episodes, not use within a fixed system |
| MemoryBench (2510.17281) | learning from simulated user feedback during service | coupled agentic tasks with action dependencies; matched-compute controls; improvement-cost split |
| SEA-Eval (2604.08988) | stream evaluation with efficiency-evolution and interference stability, empty-memory/noise controls | non-repeating coupled tasks; open method interface; matched budgets |
| StudyBench (2609.00787) | textbook→transfer self-evolution (physics), guidance gap and compute plateau | beyond physics; cross-session state + action dependency; deployment cost |
| FinEvo-Bench (2608.06144) | longitudinal finance streams, paired non-evolving controls, in-scene skill/memory evolution split | cross-mechanism arms; multiple backbones; non-financial domains |
| Aspire (2608.31111) | outcome evaluation of evolved systems on hidden tests | visible coupled lifecycles and process-level metrics |

The conjunction we occupy: **open participant-supplied improvement processes ×
genuinely coupled lifecycles (task N+1 unsolvable without state/evidence from
N) × acquisition/retention/transfer metrics × improvement-vs-deployment cost
split with compute-matched controls × replay/order-randomization**. FinEvo-Bench
and AgentStream are the nearest neighbors to differentiate against in the
paper; the Fragility critique (2608.18066) supplies a hard design constraint:
multi-seed, shuffled-order protocols are mandatory, not optional.

## Project question and type

The project asks:

> Under fixed model serving, information permissions, and resource
> constraints, can different self-improvement methods — through continuous
> task experience — improve an agent's information acquisition, context
> organization, memory maintenance, planning-execution, and
> verification-recovery strategies? Do those improvements persist and
> transfer to unseen task streams, and at what long-run net cost
> `C_total(N) = C_improve + N·C_deploy`? How much of the gain comes from
> experience content, from strategy updates, and from extra compute?

This is a **benchmark and analytical study**, not a method or harness
contribution. The litmus test: if our own default improvement procedure were
deleted and Recuris-style memory evolution, MGM-style code editing,
AutoMem-style architecture search, and fixed strategies entered as
participants, the paper's value must still stand. Execution infrastructure
(runner, isolation, accounting) is a necessary facility, never the claim.

Terms are gated exactly as in the v1 contract, plus these v2 gates (the
Recuris TTA lesson is the standing example: 51/87 frozen-memory retries vs
53/87 adapted retries at p=0.774 — an attempt-budget headline must never be
reported as a learning headline):

| Term | Required evidence |
| --- | --- |
| open benchmark | at least one external improvement method runs as a registered participant before submission |
| coupled task lifecycle | early information-handling choices demonstrably alter later available information and action quality, with delayed error exposure |
| improvement (per arm) | post-period performance exceeds the arm's own noise floor on unseen items, with CI |
| retained improvement | improvement survives periods where the improving mechanism is disabled, measured on unseen items |
| transferred improvement | improvement survives a task family whose surface features change while dependency structure is preserved |
| net-beneficial improvement | `C_improve + N·C_deploy` beats the fixed-strategy reference at its `N·C_deploy` for the deployment horizon N reported |
| meta-improvement ("the improver improves") | **out of scope**; the improvement process itself is a participant-supplied constant within a study, and any claim about it requires a separate, pre-registered design |

## What this is not

- Not a strict-RSI claim, and not a definition of RSI: frozen weights are an
  attribution setting of the main track (open to closed-model compatibility),
  not a boundary that defines self-improvement.
- Not a context-compression method, a memory architecture, or a general agent
  framework. Component novelty is not claimed anywhere.
- Not a "true-RSI detector". The protocol identifies the incremental
  contributions of five distinct effects — extra compute, feedback-conditioned
  generation, better selection, retention, transfer — against explicitly named
  controls, and the conditions under which each holds.
- Not a guarantee that null results are publishable. Qualification failures
  and blocked runs are engineering records; only a null measured under a
  qualified, fair, powered-enough cell is a scientific result.

## The measured object

The unit of evaluation is an **improvement process operating on a stateful
agent system**:

`S = (A_0, Σ, I, μ)` — initial agent system `A_0`, retainable-state
specification `Σ`, improvement process `I`, model serving configuration `μ`.

The behavior contract of the agent system at time t is generalized beyond the
v1 ContextPack compiler: `H_k: (o_t, z_t, g_t, b_t) → (model calls, tool
actions, memory ops, delegations, stop; z_{t+1})` — from observation, state,
goal/progress, and remaining budget to the next action and updated state.
Static single-call context packing (the v1 locus) survives as an in-task
diagnostic subtask, not as the project's central abstraction.

Three time scales are measured separately and never conflated:

| Scale | What the system does | Capability observed |
| --- | --- | --- |
| within-task | read, retrieve, act, maintain working state | long-context comprehension, evidence integration, long-dependency execution |
| across sessions/tasks | persist facts, update preferences, accumulate experience, resume | persistent memory, state updating, experience reuse |
| across improvement generations | revise memory algorithms, prompts, tool wrappers, control policy | strategy improvement, retention, migration |

Freezing applies to what is **outside** the measured system: hidden
evaluation, permission boundaries, task order, resource accounting, audit
records, and result definitions. What is inside `S` — how to learn, what to
keep, in what representation — is the participant's choice.

## Task lifecycles

The benchmark's core instrument is a **coupled task lifecycle**: long-document
evidence, cross-session persistent state, and action dependencies arranged so
that early information choices change later information and action quality,
and errors surface late. Task families (first: sustained research and evidence
synthesis; later: long-term collaboration/transactional work, multi-stage
project work, adaptive exploration and delegation) are specified in
[`task-family-research-v1.md`](task-family-research-v1.md).

Every instance carries five description axes as metadata, never as a single
difficulty score: information scale, dependency distance, persistence span,
action dependency, environment change. Static long-QA items are diagnostics
and are labeled as such; they never masquerade as long-horizon tasks.

Task-identity rules from the v1 contract remain binding per family:
complete-evidence solvability, position balance, and causal dependence on
gold evidence. The numerical difficulty kills in the earlier v1 contract are
retired by [`rsi-core-spec-v1.md`](rsi-core-spec-v1.md); legal saturation is
reported rather than hidden.

## Participants and controls

Participant registration and the first control arms are specified in
[`participant-interface-v1.md`](participant-interface-v1.md). The arms for
the first phase are: the **fixed-strategy reference** (no update — the
benchmark for "is updating worth it"), the **experience-accumulation-only
arm** (state content grows, strategy frozen — isolates experience content
from strategy updates), and the **open-S CLI researcher arm** (current
harness). Matched non-agent search controls are designed-in (same state, same
budget, if stateful) but deferred beyond the first phase. "External strong
researcher assisting a target agent" and "same-model self-improvement" are
separately labeled, never pooled.

## Reader evidence tiers

Readers (and any model pool an `S` may schedule) are classified by evidence
assurance, not by open/closed identity:

| Tier | Definition | Carries |
| --- | --- | --- |
| T1 anchor | pinnable weights and serving (e.g. Qwen3.6-27B @ `1b559cf…`, vLLM 0.25.1, serving-profile hash, thinking flag, tokenizer manifest) | mechanism reproduction and debugging; all deterministic replay |
| T2 versioned API | any transport, open or closed, under a pinned version string + access window + protocol | main statistical conclusions for that window, subject to the gates below |
| T3 compatibility-only | cannot account usage | compatibility runs only; excluded from efficiency comparisons |

T2 gates (the exact failures the hy3 record documented): pre/post-campaign
canaries on answer form, usage, and returned-model echo, any drift invalidating
the whole batch; a same-policy in-batch score-variance floor from ≥ 5 repeats
that reported deltas must exceed; version + date + echo recorded per artifact;
and a pre-registered in-batch variance ceiling above which the reader is
rejected for that block. Model pools are fixed per registration and every
call is accounted; "smarter routing" may not silently substitute a stronger
model.

## Protocol semantics (v2 corrections)

- **Order and seeds are controlled inputs, not nuisances**: multi-seed and
  shuffled-task-order protocols are mandatory (the Fragility-of-Self-Improving-
  Agents critique, 2608.18066, shows run-to-run variance and task order can
  dominate reported self-improvement gains).
- **Selection-blind is a feedback-visibility arm**, not a proxy for non-agent
  search. Controls are named for what they are.
- **Replay is dual-purpose and both are required**: deterministic replay of
  program + state + ledger (reproduction), and fresh-request replay (variance
  estimation). Neither substitutes for the other; archived outputs never
  stand in for the real behavior of a changed input policy.
- **Noise floors are calibrated, not absolute**: measurement uncertainty,
  minimum practical value, service drift, and system error are separated;
  sufficient independent repeats may resolve mean differences below a single
  run's standard deviation.
- **Cost is two-column**: `C_improve` (the improvement loop's own tokens,
  dollars, wall time — which the 2026 wave under-reports) and `C_deploy`
  (per-task service cost), reported per deployment horizon N.
- **Trajectory metrics beyond final score**: acquisition, retention, transfer,
  deployment cost — each a table cell with a clustered CI; no abstract-only
  headline numbers.
- **State-boundary contract (amended 2026-09-20)**: evaluation branches
  (gate / replay / sealed / transfer) start independently from a **frozen
  learning snapshot** `S_k` — what the participant legitimately learned
  (code, skills, memory, observed facts) carries EQUALLY into every
  branch; branch-generated state is confined to its branch and never
  written back. Gate and replay sessions contain only gate items; the
  full state transcript is logged and auditable; the pre-registered leak
  probe (visible-gold canaries absent from gate state and packs) remains
  the direct anti-leakage instrument. The boundary is information SOURCE,
  TIME, and SCOPE — never the textual shape of what is remembered (the
  withdrawn "method-experience-only" rule is documented in
  `root-cause-24-of-24-20260920.md`). All persistence channels (state
  store, code, memory packages, indexes) count against the byte cap.
- **Engineering failures are not negative results**. A qualification-gate
  failure says the instrument was not ready; only a null under a qualified
  cell answers a scientific question.
- **Continuously-updating systems report the online cost formula**: the
  two-column `C_improve + N·C_deploy` model covers the offline one-shot
  case; a system that keeps updating while serving reports the per-task
  decomposition `C_total(N) = C_initial_improve + Σ_t (C_serve,t +
  C_update,t + C_maintain,t)`, where maintain is memory
  consolidation/compaction (state hygiene that changes no strategy), summed
  per token, wall, and dollar component.
- **Replay and re-run are separate evidence kinds**: deterministic replay
  over recorded outputs is evidence of execution and ledger reproducibility
  only; performance variance estimates come exclusively from fresh-request
  re-runs; canary health checks are evidence of neither — they gate the
  batch, not the claim.
- **Stage-level scores are not independent samples**: stages within one
  instance share that instance's history, and instances within one world
  share the world's trajectory; CIs and order-effect tests therefore cluster
  at the world/trajectory level, and repeated model calls estimate call
  variance, not task diversity.
- **Budget documentation lives in one place**: reader budgets in
  [`configs/api_profiles.json`](../configs/api_profiles.json)
  (`max_output_tokens` per profile) and improver budgets in the participant
  spec's arms section
  ([`participant-interface-v1.md`](participant-interface-v1.md)); the 16k
  improver output cap is the registered value; any other budget seen in
  artifacts is historical.

## Honesty constraints carried from the v1 review

- "Designed to exceed" published protocols, never "exceeds", with the
  executed/unrun split explicit.
- Adjacent institutional measurement demand (OpenAI Preparedness v2 threshold;
  Anthropic R&D Automation Index; METR's RSI-tracking funding) is background,
  not a novelty argument.
- No "first" claims: closest neighbors (Recuris, Evo-Memory, MemoryBench,
  MemoryArena, MemEvolve/AutoMem, PAST-Bench, ModularRSI, SoL-Pi, MGM,
  Dream-RSI, EvoArena) are treated as competitors and co-designers of the
  differential questions; the per-neighbor "must additionally answer" table
  is part of the task-family spec.
- The frozen-weights setting is reported as an attribution choice; weight-level
  self-improvement (SPELL-style, MetaRSI's model operators) is adjacent work,
  not out-of-scope ignorables.
- **Difficulty gates are development instruments, not permanent rules**
  (2026-09-20 review): a legitimately strong method reaching a high score is
  a result, not a task failure; tasks are calibrated on capability coverage
  and solvability, never iterated until a method ranking appears. Panels
  used to revise tasks become development material and cannot later serve
  as unseen gates. Easy, solvable tasks are retained deliberately as the
  regression-observation surface ("did improving break old abilities").
- **Continuation vs migration are separately reported**; "not updating" is
  never conflated with "not remembering" (the fixed arm is
  memory-operational); open main comparison reports whole systems (initial
  capability, post-experience, retention, migration, full cost), and
  mechanism attribution is claimed only within interface-compatible
  analysis subsets.

## Execution phases

Phase A (this document + task-family and participant-interface specs),
Phase B (lifecycle runtime, participant adapters, session-state machine with
the state-boundary contract, two-column cost ledger, contract-level tests),
Phase C (first complete end-to-end cell on the T1 anchor: three arms, replay,
hidden gate items — the project's first real trajectory), Phase D (task
families 2–3, T2 closed-API readers past their gates, the replication matrix,
retention/transfer battery), Phase E (paper assembly, benchmark/datasets
track). Container isolation procurement runs in parallel from Phase A; hidden
evaluation requires it before any sealed claim.
