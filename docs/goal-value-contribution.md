# Project goal, value, and contribution (2026-09-23, post-R2b-wiring)

Evidence-level discipline throughout (the reviews' demand): every claim
is labeled [implemented+pinned] (code + tests), [implemented, evidence
pending] (code exists; no run yet licenses it), or [design only].
Where evidence lives: file/test/run is named. This document replaces
`docs/paper-contribution.md`'s v1-lineage claims as the project's
current statement (that file is superseded normative history).

## 1. Goal (one paragraph)

This project studies **system-level strategy improvement of stateful,
model-driven agents on long-horizon information work**: whether an
agent's policy for reading, remembering, verifying, and acting can
improve from its own project experience — through an honest
measurement environment whose evidence, costs, and feedback boundaries
cannot be gamed by the participant — and whether such improvement is
retained on unseen projects, at what resource cost. It is a benchmark +
analytic study, not a method: the deliverables are the task family, the
measurement protocol, and the comparative findings (including negative
ones) about when improvement beats a competent fixed system, matched
search, or simply more deployment compute.

## 2. Value / contribution claims (honest, three)

### C1 — A measurement environment where evidence is real by
construction, not by participant honesty

**Claim**: verifications are environment-issued and subject-bound
(participants request, never write, verdicts); rule changes advance a
PER-CHECK revision clock so "unaffected" and "superseded" evidence are
distinguished the way the world's rules say; commits are graded at
their TIME POINT (later rule changes cannot retroactively fail a
legitimate commit); follow-up answers are DERIVED from the sandbox
(different legal histories yield different correct answers); crashes
score zero; budgets are enforced before execution and billed uniformly
across call syntaxes.

**Why the neighbors don't cover it**: the surveyed self-improvement
benchmarks (Evo-Memory, AgentStream, MGM, Dream-RSI) evaluate OUTCOMES
of evolving systems; none of them pin the evidence-validity layer
(who may assert a verification, per-check staleness semantics,
time-point grading) as part of the benchmark contract. Rethinking pins
evaluation PROTOCOL (budgets/holdouts) but takes task harnesses as
given. Our claim is about the MEASUREMENT LAYER, complementary to both.

**Evidence**: [implemented+pinned] — env.py (Receipt/submit/
check_revisions), runner.py (time-point gate, follow-up derivation,
infra-zero), tests: test_review_e7ec000_deliverable_a (16),
test_phase1_entry (8), test_world_v4_dossier (13 incl. removal
simulations), test_rsi_core_receipts/policy (17). Live run behaved per
contract (failures scored, no re-rolls).

### C2 — A longitudinal main-task slice where the three "long" axes
are STRUCTURED and their load-bearing is AUDITABLE

**Claim**: the dossier task (8 stages, follow-ups AFTER a commit, two
rule changes with different scopes) requires decisions 4+ stages from
their single-source evidence across a commit; the load-bearing ledger
states decision ← proposition ← evidence-path, with removal
simulations showing what information is actually lost (and that env
verification is a parallel legal path — text is not the only route);
irrelevant perturbation (bulk growth) provably does not change the
legal answers.

**Why the neighbors don't cover it**: Evo-Memory/AgentStream streams
are sequences of SEPARATE tasks (state carries; tasks are
self-contained); MemoryArena has interdependence but is an external
environment we would consume, not one with an auditable
proposition-level ledger; no surveyed work ships a removal-simulation
ledger as task documentation.

**Evidence**: [implemented+pinned as STRUCTURE] —
material_v4_dossier.py + task card + tests. [NOT claimed]: that the
axes' full DIFFICULTY is validated for real models — the R2a live run
showed the current worker fails selection (honest negative), and bulk
filler is name-filterable (a robustness diagnostic, not selection
pressure). The task card separates structure from evidence level.

### C3 — The honest-comparison protocol for improvement claims on
this environment

**Claim**: a pre-run frozen statistical contract (planned-and-started
denominator, infra-zero, last-snapshot artifact rule — no dev-score
selection, dev/eval split with structural feedback isolation,
four-outcome reporting where "the fixed system suffices" is a
publishable result) plus an arms apparatus whose control is
model-driven (content decisions through the metered model channel;
policy code carries no answers — pinned) and whose update arm is
provably unassisted (prompt carries no diagnosis — pinned), with the
non-adaptive search arm (stateful_control's first real implementation)
reporting both Δ_update and Δ_practical.

**Why the neighbors don't cover it**: Rethinking contributes the
matched-feedback/compute discipline (we adopt it — attributed);
AgentStream the no-evolution control delta (adopted — attributed);
what is ours is the COMPOSITION with C1/C2: the controls run inside an
environment where evidence validity and time-point semantics are
pinned, on tasks with an auditable ledger, under a contract that also
governs the improvement arms' failure handling (the live no-policy
round kept the baseline per contract §3, recorded).

**Evidence**: [implemented+pinned for the protocol] —
stats-contract-v1.md + test_r2a_arms (6) + test_r2b (5). [evidence
pending for findings]: exactly ONE live two-arm run exists (ties —
transcribed in docs/r2a-record.md); R2b's three-arm comparison is
wired, offline-verified, live run pending.

## 3. What we explicitly do NOT claim

- No novelty for "experience reuse across task streams" (Evo-Memory),
  "streaming evaluation of evolving agents" (AgentStream), "cross-
  session memory-action interdependence" (MemoryArena — a candidate
  external validation surface), "scaffold lineage evolution" (MGM),
  "exploration-policy improvement with replay scoring" (Dream-RSI),
  or "evaluation controls for harness evolution" (Rethinking).
- No claim that any improvement has been measured: the first live
  comparison result is TIES, and the worker currently fails the task
  — reported as the result.
- No claim of model generality (one worker family), scale (one mother
  world + one variant), cross-session recovery (B-group unbuilt), or
  execution-recovery dependence (C-group unbuilt).
- No weight-training loop anywhere (improvement surface is the
  carried policy artifact; consistent with the whole field).

## 4. Mechanism inventory → claim support

| Mechanism | Where | Supports |
| --- | --- | --- |
| Env-issued, subject-bound verification + per-check revisions + time-point grading | env.py, runner.py | C1 |
| Receipts / act-observe loop / multi-turn intra-stage recovery | env.py, runner.py | C1 (behavioral honesty) |
| Metered tools + ask_model channel + uniform billing + budget enforcement | tools.py, policy.py | C1 (cost honesty), C3 (matched compute) |
| Load-bearing ledger + removal simulations + derived follow-up grading | material_v4_dossier.py, runner.py | C2 |
| Stats contract + last-snapshot rule + dev/eval split | stats-contract-v1.md, r2a/r2b entries | C3 |
| Model-call audit transcript (R2b) | policy.py | C3 (diagnosability: which material was read, which reply changed action) |
| Non-adaptive search arm | r2b_compare.py | C3 (Δ attribution) |

## 5. Path from current evidence to the claims

| Step | Licenses |
| --- | --- |
| R2b live (three arms, audit transcript on) | first real Δ_update / Δ_practical numbers; failure attribution via transcript |
| Worker-2 family (the live negative motivates it) | non-Qwen generality of any finding |
| B-group: session boundary + state recovery on the same corpus | long-memory claim beyond stage-crossing |
| C-group: action results change future paths | long-horizon dependence claim beyond sequence grading |
| Formal-scale freeze + independent projects (per stats-contract §8) | any benchmark-level statement |

## 5b. Open flags (from the 2026-09-23 independent audits)

1. The R2a live artifact is unrecoverable (see §6) — the committed
   record doc is its sole surviving evidence.
2. `docs/paper-contribution.md` is the old compression-era direction
   and contradicts the current charter — read as superseded history.
3. The long-context axis is NOT validated difficulty (name-filterable
   filler = robustness diagnostic; the task card says so).
4. The matrix 1–3 S0→S1 "improvements" are calibration-profile
   evidence only (a one-boolean reachable difference); never cite them
   as strategy-improvement results.
5. STATE-2026-09-22.md predates RSI-core-v1; read its observations
   through flag 4.
6. Literature verification debt: all neighbor reads are arXiv-level;
   PUBLICATION STATUS NOT VERIFIED (an arXiv read does not establish
   the absence of peer review — LongMemEval and HELMET have ICLR
   2025 records; several RSI-neighbor details are abstract-level;
   spec Part 4 carries provenance). FACTUAL CORRECTION (2026-09-24
   review): gpt-5.4 DOES exist (OpenAI announced it 2026-03-05) —
   the earlier "does not exist" claim came from reading only the
   deprecations page and is withdrawn in
   docs/worker2-research-20260923.md; "model exists", "account
   access", "aggregator offers it", and "deprecated" are four
   distinct questions.
7. Researcher retry policy: implemented (transport-only, 5 attempts,
   per-attempt records — commit 4b11f18); the r2b load gate is also
   ported (both call sites). Remaining gap: the live meta-agent
   closure duplicates the transport skeleton rather than factoring it
   with the unassisted round (cosmetic).

## 6. Postmortem notes (recorded honestly)

- The R2a live artifact was written inside a removed worktree
  (artifacts are gitignored); its numbers survive only in
  docs/r2a-record.md. Root cause: run in a worktree, default output
  path relative. Fix applied: run outputs now write to the shared
  checkout path; record docs carry the transcription duty.
- CORRECTION to the R2b mirror reading (late-report diagnosis,
  2026-09-23): the mirror variant's s5 award gate was DEFECTIVE — its
  plan_requirements still keyed the mother world's winner, so the
  variant's own winner faced NO evidence requirement (the gate's
  requirement lookup returns None for unlisted plans). The R2b live
  "award passes on mirror" was therefore partially confounded: a
  correct naming fix AND a weakened gate both contributed. The
  constructor is fixed (requirements now derive from the variant
  spec; pinned); the recorded R2b numbers stand as measured, with this
  annotation. Future runs grade the mirror at equal strength.
- The R2a record's initial researcher-failure theory (file-size
  exceeds cap) failed arithmetic and is corrected in r2a-record.md —
  the output was reasoning-dominated (endpoint-family behavior, per
  the canaries); finish_reason + replies are recorded from R2b on.
- rsi-core-spec-v1.md's "zero tool calls" demo line was stale after
  R1.1's unified billing (~28 charged verification actions on the
  calibration pool); corrected in place with a note.
