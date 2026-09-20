# First S0→S1 trajectory on research-v3 (2026-09-21)

Status: **trajectory record** — review round 4 deliverable 5. Script:
`scripts/trajectory_v3.py`; artifacts:
`artifacts/trajectory-v3/offline-dryrun.json` (fake reader, wiring
verification) and `artifacts/trajectory-v3/live-20260921.json` (siflow
Qwen3.6-27B T2, 2035 s, 10 reader calls on dev sessions + branch runs
through the same reader; reference executor is reader-free). Wiring
pinned by `tests/test_trajectory_wiring.py` (offline subprocess
end-to-end).

## What ran (three participant kinds — not a method competition)

1. **Reference executor** (scripted legal path): final check PASSED,
   committed plan `aurora`. Task solvability confirmed — not a
   capability result.
2. **Fixed arm** (memory-operational, strategy frozen, real reader):
   dev session over the v3 world, snapshot F0 frozen from it. Its
   commits use a revision-1 replica-lag verification — the DESIGNED
   weakness (no scope-aware re-verification after the rule change).
3. **DS arm**: dev session → S0 frozen; ONE improvement round (strategy
   edit + state update, as the DS researcher emits: `agent_files_changed`
   + `state_update`); S1 frozen with the edit (scope-aware invalidation:
   `STRATEGY_RERVERIFY = True` + the two learning notes).

Each snapshot then entered the SAME three evaluation branches
(continuation / new-world / regression, 2 variants each) through the
frozen-snapshot carry — legitimate carry, branch isolation, no
write-back (the snapshot.py machinery from deliverable 2).

## Results (identical offline and live)

| Snapshot | Continuation | New-world | Regression | Failure mode |
| --- | --- | --- | --- | --- |
| fixed F0 | refused ×2 | refused ×2 | refused ×2 | `stale protocol revision 1 (in rule-change scope)` — the designed stale-conclusion failure, now observable at the action boundary |
| ds S0 | refused ×2 | refused ×2 | refused ×2 | same signature (before the improvement the arm shares the weakness) |
| ds S1 | ran ×2 | ran ×2 | ran ×2 | the scope-aware strategy re-verifies; commits pass |

**The loop is closed and explainable**: the modification demonstrably
changes behavior (S0→S1 branch contrast), legitimate learning
(state + code) carries into every branch identically, evaluation
branches are independent, and the difference between arms is a named
mechanism (scope-aware invalidation vs. stale revision-1 evidence) —
not a score delta to interpret post hoc.

## What this record does NOT claim

- **Not a capability/improvement claim.** The improvement round here is
  harness-authored (a scripted strategy edit standing in for the DS
  researcher's own edit); it demonstrates the measurement loop
  end-to-end. The REAL DS round (researcher-model-generated edit, with
  its reliability gates and cost accounting) is the next trajectory —
  same script, `strategy_text` produced by the researcher, not by us.
- The fixed arm's 0-for-branches is by construction (its commit carries
  revision-1 evidence against the v3 world's precondition); it is the
  designed failure class 2, not a measured weakness of the reader.
- n=1 world, 2 variants per branch: screens, not powered tests; the
  variants are ONE parent world (task card) and are never counted as
  independent samples.
- The live reader call count (10 across dev sessions; branch hooks
  share the reader) is a fraction of one arm-comparison run: this
  trajectory is cheap by design and repeatable.

## Cost (two-column, from the artifact)

- C_improve (this trajectory): 1 improvement round, 0 researcher-model
  tokens (scripted stand-in), seconds of harness time.
- C_deploy (dev sessions + branches): 10 reader calls, 1,816 input +
  7,728 output tokens on the dev sessions (branch session calls are
  carried in the branch records), 2,035 s wall.

## Next (unchanged from the review's order)

Deliverable 6 (structural stratification, gold-position jitter at the
final-visible-material layer, external-method fidelity check) — and the
real-DS trajectory on this same script. No claim escalation until a
researcher-authored S1 runs the same loop.
