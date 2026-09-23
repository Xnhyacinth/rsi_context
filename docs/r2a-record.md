# R2a record — the first two-arm longitudinal comparison

Governed by `docs/stats-contract-v1.md` (frozen BEFORE the arms ran).
Arms: strong-model-fixed (the honest control — same worker via
ask_model, content decisions by the MODEL, policy code orchestrates
only) vs unassisted-update (same A0 = the same baseline policy text;
ONE researcher round rewriting it from dev experience only — the task
prompt carries no failure-mode diagnosis).

## Runs

- Offline (deterministic scripted worker; wiring smoke):
  `artifacts/rsi-core-v1/r2a-offline.json` — both arms 3/3 on dev,
  2/3 on the mirror eval variant (the scripted worker's currency
  diagnosis misses the variant's flipped semantics — an offline-sim
  limitation, not a policy property); four_outcome=fixed-sufficient.
- Live (Qwen3.6-27B worker + deepseek-v4.1-flash researcher, Siflow):
  results transcribed below. NOTE: the raw live artifact was written
  inside a worktree that was removed after merge (artifacts are
  gitignored); the results below are the surviving record — all
  numbers in this table came from the artifact. Future runs MUST write
  artifacts to the shared checkout path (the entries now default
  there).

## Live results (2026-09-23, Qwen3.6-27B + deepseek-v4.1-flash @ Siflow)

four_outcome: **ties** (0 deltas everywhere; both arms identical
because the researcher round produced no usable policy — see below).

| Arm | Cell | passed | decisions | model_calls | wall |
| --- | --- | --- | --- | --- | --- |
| strong_model_fixed | dev | false | award/fu1/fu2 all fail | 13 | 169s |
| strong_model_fixed | eval_mirror | false | fu2 passes only | 15 | 227s |
| unassisted_update | dev | false | identical to fixed (baseline kept) | 13 | 169s |
| unassisted_update | eval_mirror | false | fu2 passes only | 15 | 228s |

Honest findings (both are MEASURED properties, not wiring bugs):

1. **The real worker does not solve the dossier (yet)**: the award
   fails with plan 'Harborline' not in the legal set — the model's
   survey extraction + constraint analysis did not surface the winning
   qualification (13 calls, zero policy errors, wrong decision
   correctly scored). This is the honest control behaving honestly:
   the task's difficulty is REAL for this worker. Notably fu2 (the
   currency diagnosis) PASSES on the variant — the model can diagnose
   evidence currency even when selection failed.
2. **The researcher round hit the output cap**: output_tokens=16384
   (the cap) with no extractable python block -> per contract §3 the
   previous snapshot stands, recorded as no-policy. A real
   unassisted-round failure mode for this researcher model at this
   budget: the full policy file (~200 lines) plus reasoning exceeds
   16K output. Candidate fixes for the NEXT run (not this one — the
   contract forbids re-running until a desired result): a shorter
   baseline policy to rewrite, a diff-format reply, or a larger output
   cap declared up front in the budget pack.

This run licenses: the measurement works end-to-end with real models,
the honest control is honest (its failures are its own), the
unassisted round's failure handling follows the contract. It licenses
NO improvement claim — and reports exactly that.

## What this run does and does not license

- It exercises the FULL longitudinal pipeline with real models: batched
  survey reading, retained notes, env-issued verification, a commit
  graded at its time point, follow-ups after rule changes, and an
  unassisted improvement round.
- It licenses NO general claim: one mother world, one variant, n=1
  family, dev-phase. The outcome states are calibration-grade evidence
  that the MEASUREMENT works end to end with real models.
- The honest control's content decisions provably flow through the
  model (no-answers test pinned); the update round's prompt provably
  carries no diagnosis (no-diagnosis test pinned).

## R2b (next)

Non-adaptive strategy search (the stateful_control slot's first real
implementation: independent candidates, no cross-candidate feedback)
and the REAL Recuris adaptation (Meta-Agent proposing from legal
traces, memory actually entering the worker's context, dev-task
validation) — in parallel, per the review's order.
