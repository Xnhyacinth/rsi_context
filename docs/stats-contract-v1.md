# Statistical Contract v1 — frozen BEFORE the R2a arms run

2026-09-23. This file freezes the evaluation object, denominator,
selection rules, feedback boundary, cost accounting, and stopping rules
for R2a/R2b. The review's requirement: these are decided before any
arm produces numbers, so no result below can be shaped by peeking.
Numbers produced under this contract are dev-phase; the FORMAL scale
(sizes, budget values) is separately frozen before any paper-scale run
and is not set by which size favored any arm.

## 1. Evaluation object

- **Primary outcome**: project completion — for the dossier slice, the
  conjunction {award gate passes at s5, follow-up 1 correct, follow-up 2
  diagnosis correct}. One PROJECT = one unit; the three decisions are
  DIAGNOSED separately (per-decision pass/fail reported) but are NOT
  three independent samples.
- **Secondary outcomes** (reported, not gated): cost per project
  (model tokens, tool units, wall time), which decisions failed and
  their named failure causes.

## 2. Denominator and failure handling

- Denominator = evaluation units **planned and actually started** in
  the run manifest. Every unit ends in exactly one of: completed
  (scored), method-failed (scored as failure, cause recorded),
  infra-failed (scored ZERO per the infra-zero rule, cause recorded,
  separately counted). No unit is silently dropped; no post-hoc removal.
- Method failures (policy crash, budget exhaustion, invalid decisions)
  are system-level results — reported as failures, never re-rolled.
- Repeat draws for endpoint reliability are recorded as distinct units
  with their outcome; they are not replacements.

## 3. Snapshot and artifact selection

- The improvement arm produces candidate snapshots S1..Sk under a
  FIXED budget: rounds are fixed in advance (default 1 for R2a; the
  number is declared per run), and the FINAL snapshot is the LAST one
  produced, not the best-scoring one. No selection by dev score.
- If a round fails (endpoint/protocol), the previous snapshot stands
  (recorded as a failed round; the failure is a reported outcome).

## 4. Evaluation split

- The dossier mother world is DEV material. Evaluation uses variant
  instances whose decisive facts change (different winning supplier,
  different superseded check, different calibration answer) — generated
  from the same structure, and REPORTED as same-family transfer, never
  as independent projects.
- Nothing from evaluation instances (ids, material, outcomes, failure
  text) enters any improvement input. Structural guarantee: the
  researcher round's feedback builder consumes dev runs only.

## 5. Cost accounting (per arm, per run)

- worker model usage (platform-reported where available; word-estimate
  fallback labeled as such), researcher usage, candidate validation
  (dev-probe runs), tool units (env units — rereads/verifications/
  delegations — kept separate from model tokens), maintenance (memory
  serialization). Reported in one ledger per arm; arms are compared on
  the frontier, not a single "cheaper".

## 6. Stopping rules

- Fixed rounds; fixed evaluation manifest; fixed per-run budget. No
  arm runs until "a positive result appears". Endpoint retries obey
  the researcher retry policy (5 attempts) — after that the round
  fails and is recorded.

## 7. Reporting rules for R2a

- Four outcomes are all publishable states: improves / ties /
  regresses / strong-fixed already sufficient. The run reports which.
- Paired deltas are reported per decision (award, followup-1,
  followup-2) AND overall; uncertainty is descriptive only at this n
  (no significance claims — dev-phase, n≈1 mother world).
- Every arm's runs carry: policy text (or its digest), budget config,
  world identity + material hash, full cost ledger, policy errors.

## 8. What this contract deliberately does NOT yet fix

- Formal-scale n, cluster structure, and CIs (post-pilot, per the
  8013d6f review's three-threshold distinction).
- Cross-session (B-group) and execution-recovery (C-group) outcomes.
- A judge for open text (not needed: all R2a decisions are env-graded).
