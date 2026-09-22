# e7ec000 external review — verification of claims and deliverable A

Review pinned at `e7ec000`; executed verification on 2026-09-22. Each of
the review's blocking claims was checked against the code and, where the
review itself said "static derivation, needs execution", reproduced with
probes before fixing.

## Claim-by-claim verification

| Review claim | Verdict | Evidence (pre-fix) |
| --- | --- | --- |
| Re-verification is a version-label rewrite (revision=2, no env execution) | CONFIRMED | `trajectory_v3.py` `_commit_actions`: `revision = 2 if rereverify else 1` on a plain `create_record` |
| Self-declared `status="final"` passes without finalize | CONFIRMED by execution | Probe P1: bare-create ember (legal plan, no refs) → PASS |
| Garbage provenance passes | CONFIRMED by execution | Probe P2: finalize citing `totally-fake-ref` → PASS |
| Self-filled verification records count as evidence | CONFIRMED by execution | Probe P3 (also the live "success path" itself) → PASS |
| `new_world` feedback enters the improvement loop | CONFIRMED | `_dev_feedback_bytes` iterates all three branches incl. `new_world` over the eval pool |
| World rotation never actually wired | CONFIRMED by artifact | All matrix3 artifacts (seeds 0/1/2): failures name only kestrel (orinoco) + unknown (zephyr); no quill/atlas |
| Author-draw failure path drops `exc.attempts` | CONFIRMED | matrix3-researcher-s0 artifacts: failed draws carry `attempts: []` |
| zephyr post-1990 clause has no evaluator counterpart | CONFIRMED in data | `play-the-game` (Queen, 1980) in `legal_plans`; constraint demands post-1990 |
| Snapshot dicts mutable in place, digest never rechecked | CONFIRMED by execution | Probe P5: `snapshot.memory['notes'].append(...)` leaves digest stale, branches still serve |
| `_pass_fraction` silently drops crashed cells | CONFIRMED by execution | Probe P7: crashed + passing cell → 1.0 |
| zephyr task card internally inconsistent on pop music | CONFIRMED | Card line 36 (permitted set w/o pop music) vs line 61 (pop music in permitted) |

## The fix (branch `worktree-review-e7ec000-fixes`, commit 21a0eae)

The environment now owns verification truth:

1. **`request_verification` action kind** — participants may only REQUEST
   (check, subject); the env writes the record (verdict, current
   protocol revision, `performed_by: environment`). Uncovered requests
   become named `verdict: "unverifiable"` records, never crashes, never
   fabricated passes. Rule changes advance the env's protocol clock
   (`StageSpec.rule_change_effect`) before the stage's actions apply.
2. **The commit gate** requires env-issued, subject-bound, passing
   evidence for `plan_requirements`; genuine env finalization
   (`finalized_record_ids`); and existent provenance.
3. **STRATEGY_RERVERIFY is now a real behavior**: the fixed arm requests
   verifications early (evidence ages with the clock); the strategy
   re-requests after the rule change (env re-executes at the current
   revision). The commit-time fallback is the deferred-verification
   baseline, deduped on (check, subject) so the fixed arm cannot
   accidentally re-verify.
4. **Feedback isolation**: dev probes run a dev unseen pool (authored
   variants / main world), disjoint from the held-out Option-2
   evaluation pool.
5. **Rotation + provenance**: `unseen_rotation` is wired to the seed at
   every evaluation call site; every branch record carries the world
   instance id + material sha256 + hook token/call ledgers.
6. **Author-draw failures** copy `exc.attempts`.
7. **zephyr**: the unimplemented post-1990 clause is removed (task and
   evaluator now agree; the card's own pop-music inconsistency should
   be fixed at the card next).
8. **Snapshots**: `run_evaluation_branch` recomputes the digest and
   refuses in-place-tampered carry.

## Verification of the fix

- 15 new tests pin the attack paths red-then-green
  (`tests/test_review_e7ec000_deliverable_a.py`).
- Full suite: **995 passed / 0 failed** (1 deselected is a pre-existing
  worktree-path artifact, passing on the main checkout; live-API smoke
  skipped — no key in this environment).
- Probes: P1/P2/P3/P9 FAIL (fixed), P8 honest path PASS; main world
  reference PASS, fixed FAIL by design, scripted PASS; offline
  trajectory closes end-to-end.

## What this fix does NOT cover (the review's larger point)

This is deliverable A only — evidence truthfulness, feedback isolation,
reproducibility. The review's structural findings (five stages are five
readings, not an acting loop; Option-2 material is ~900 whitespace words
not long-context; `6/6` is not six independent worlds; continuation/
regression re-run the main world; the evaluator runs participant code
in-process without isolation) remain open and are the next phase's
decision. The matrix3/STATE/researcher-draws documents describe
rotation that the artifacts show never happened — treat those numbers
as calibration records, per the review's recommendation.
