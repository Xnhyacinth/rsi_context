# Task family research-v1: sustained research and evidence synthesis

Status: **design spec, frozen for Phase B implementation**. 2026-09-19.
Parent contract: [`benchmark-contract-v2.md`](benchmark-contract-v2.md).
Sister spec: [`participant-interface-v1.md`](participant-interface-v1.md).

## Purpose

The first coupled task lifecycle family. Its job is to make the v2 question
answerable: **do early information-handling choices alter later action
quality, with delayed error exposure** — and can an improvement process learn
to handle that better than fixed or experience-only baselines?

## Task structure

One task instance = one **evidence project** in five stages. Material is drawn
from wired real corpora (HELMET PopQA k1000 KILT passages; MuSiQue multi-hop
support chains; LongMemEval-V2 trajectory histories where a procedural or
errors-gotchas structure fits). Real documents are embedded as the project's
document base; the coupling events are benchmark-authored and deterministic.

| Stage | The agent must | Coupling mechanism |
| --- | --- | --- |
| 1. Survey | read a long document set, build its own working index/notes | its notes are its only carry-forward (no re-read of full corpus without cost accounting) |
| 2. Constraint injection | a NEW user constraint arrives that references stage-1 evidence (e.g. a scope rule, an exclusion, a validity window) | the constraint is only checkable against what the agent retained; a lossy stage-1 compression makes stage 2 wrong silently |
| 3. Delegated verification | a bounded sub-agent (participant-configured) verifies candidate answers against source passages; the principal only sees the sub-agent's return | the return's information quality (finding, source, applicability condition) is what the principal can act on |
| 4. Rule change | one document is superseded (a policy/version event); prior conclusions may become invalid | detection of the invalidation depends on whether the agent kept provenance, not just conclusions |
| 5. Act and verify | the agent commits a final answer artifact through a checkable write action in a sandboxed project state; the evaluator verifies actual end state, not the stated one | "reported done" ≠ "state is correct"; the check is objective and deterministic |

Each stage's output feeds the next; between stages the context window may
reset (persistence through `Σ`, not through the prompt). A run's score is the
final action correctness plus per-stage evidence-provenance checks (see
Metrics).

## The five natural failure classes (design targets)

The family is constructed so these occur, at measurable rates, for plausible
strategies:

1. **Compression loss of a later-needed exception** — stage-2 constraint
   references an exception that a summary policy dropped.
2. **Stale retained preference/fact applied after supersession** — stage-4
   rule change invalidates a retained conclusion that lacked provenance.
3. **Delegation without provenance** — stage-3 sub-agent return lacking
   source/applicability fields leads the principal to a wrong commit.
4. **Plan built on outdated project state** — the agent's own earlier write
   is not consulted after the rule change.
5. **Declared success with objective state mismatch** — final action claims
   completion while the sandbox state check fails.

These are the mechanisms the v2 contract's §motivation predicts; the family
must demonstrate (in a qualification run) that a naive fixed strategy fails
each class at a non-trivial rate, and that the failure is **causally
traceable to an information-handling choice** (checked by gold-drop and
provenance-drop counterfactuals on the instrumented stages).

## Instance material and construction

- Document base: real passages from `data/helmet-data/…/kilt/popqa_test_1000_k1000_dep6.jsonl`
  (1000 scored contexts per question, `has_answer` flags for gold evidence)
  and MuSiQue support chains (`data/musique-answerable-data-qualification/…`).
- Constraint/rule-change events: benchmark-authored, deterministic, and
  **causally anchored** to specific gold evidence spans (the constraint text
  is generated so that its satisfaction is checkable against those spans
  only) — never free-form invention, to avoid repeating the v1 synthetic-panel
  treadmill.
- Procedural/gotcha structures: adapted from LongMemEval-V2
  `procedure`/`errors-gotchas` question patterns over its trajectory
  histories where they fit stages 2/4.
- Sandbox write step: a minimal deterministic project-state store (create/
  update records with typed fields), evaluated by objective state comparison —
  no general tool execution in v1 of this family.

Construction rules: every instance is complete-evidence solvable (all five
stages derivable from the supplied material), position-balanced (gold
evidence position distribution controlled), and non-saturated (difficulty
kills below). The per-neighbor differential table (§Neighbors) is part of the
family's qualification, not an afterthought.

## Description axes (per-instance metadata)

Five axes recorded as metadata on every instance, reported in distributions,
never collapsed into one score:

| Axis | Operationalization in this family |
| --- | --- |
| information scale | tokens of document base |
| dependency distance | stage span between an information item's availability and its use (1–4 stages) |
| persistence span | number of context resets between retention and use |
| action dependency | whether the final state check depends on stage-1/2 choices (always true here by construction; strength varies) |
| environment change | whether a stage-4 supersession exists and how many prior conclusions it invalidates |

## Metrics

- Primary: final-state correctness (objective sandbox check).
- Secondary: per-stage provenance retention (did the acting context cite
  evidence that exists in the gold-support set), stale-fact application rate,
  delegation-return completeness (finding/source/condition present), declared-
  vs-actual match.
- Effect decomposition per the v2 contract: five effect classes against the
  three arms.
- Cost: `C_improve` (improvement-loop tokens/$/wall) and `C_deploy` (per
  project), reported at horizons N.

## Qualification gates (pre-registered)

1. A fixed H0 strategy fails each of the five failure classes at rates in
   [0.1, 0.6] (non-trivial, not saturated) on a qualification panel.
2. No single strategy reaches ≥ 0.90 overall (saturation kill).
3. Top-two strategy disagreement ≥ 20% on-screen (discrimination kill).
4. Gold-drop counterfactual: removing gold evidence drops final-state
   correctness materially (causal dependence kill).
5. Provenance-drop counterfactual: stripping provenance fields from retained
   state increases failure classes 2/3 (mechanism validity kill).
6. Two-instance-cluster-aware power note: the family's items must not share
   a dominant hidden factor (the LongMemEval two-artifact lesson); document
   bases are sampled independently per instance.

## Neighbors: what this family must additionally answer

Task-structure borrowings, verified 2026-09-19: MemoryArena's coupled
multi-session structure (766 tasks, ~6.9 interdependent subtasks, later
sessions underspecified without earlier state) is the closest existing
lifecycle shape — but it measures memory USE by fixed systems; PAST-Bench's
fresh-session orders (Cold/Learn/Evaluation/Control) and
Mechanism-Evidence-Score (does the gain follow the save→retrieve→update
pathway) are adopted as reported instruments; AgentStream's
isolated/sequential/interleaved stream conditions and 3-seed order stability
become our order-control conditions. OpenAI's harness-engineering post
supplies the knowledge-structure patterns agents must rediscover (short
index over structured docs; plans as versioned artifacts; mechanical
verification of knowledge); Anthropic's two posts supply the capability
chain (acquire → organize → retain → plan/execute → verify/recover) the
stages operationalize; Managed-Agents "Dreams" (dedup/stale-replace/insight
extraction into a separate output store, never evaluated) is the
productization of exactly the consolidation question our stage-4 metrics
decompose.

| Neighbor | What its setting already shows | This family must additionally answer |
| --- | --- | --- |
| Evo-Memory (2511.20857) | memory-content reuse on sequential streams | whether OPEN strategy updates (not just memory content) improve coupled lifecycles, and at what improvement cost |
| MemoryBench (2510.17281) | learning from user feedback in service tasks | fair comparison of improvement methods + action dependency with objective end-state checks |
| MemoryArena (2602.16313) | fixed systems using memory across interdependent sessions | whether systems IMPROVE their handling, not just their recall |
| Recuris (2608.24876) | memory-control evolution with validation gates (coding/τ² domains) | the same question on evidence-synthesis lifecycles, with improvement-cost reporting and non-Recuris participants |
| PAST-Bench (2608.04003) | retained-experience pathway evidence | action coupling + rule supersession + open method family |
| AgentStream (2608.00155) | five author-selected methods on evolution-state-coupled streams | information/action coupling, retention over horizon, open submissions |
| FinEvo-Bench (2608.06144) | longitudinal finance streams with paired non-evolving controls | cross-mechanism arms, non-financial domains, multi-backbone |

## Scale for the pilot cell (Phase C)

One family, 8–16 visible instances + 8 gate instances, three arms
(fixed / experience-accumulation-only / open-S researcher), T1 anchor reader,
5-replay on selected artifacts, full manifest archiving. Reader time is
minutes; wall time is dominated by participant turns — the v1 cost model
carries over.
