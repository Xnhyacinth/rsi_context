# Researcher draw distributions across seeds (2026-09-22)

Status: **the pooled draw record** — 9 independent authoring draws
(3 seeds × 3 draws, the SAME S₀ + same-feedback protocol per seed),
live DS v4.1-flash. Seeds 1/2 ran with the strengthened retry gate
(5 attempts / 10 s backoff, `abd6cb8`); seed 0 is the pre-gate matrix-3
run, kept in the pool with that provenance noted.

## Pooled results

| Seed | Draws (outcome → score) | Floor SD |
| --- | --- | --- |
| 0 (pre-gate) | empty → 1/6 · ok → 6/6 · empty → 1/6 | 0.48 |
| 1 (gated) | ok → 6/6 · ok → 6/6 · ok → 6/6 | 0.00 |
| 2 (gated) | empty → 1/6 · ok → 6/6 · ok → 6/6 | 0.48 |

**Pooled: 9 draws, 6 ok (67%), 3 empty-reply failures (33%).** Every
successful draw scored 6/6 — when the round completes, the researcher's
world-generic strategy passes every cell (its strategies consistently
refuse hardcoding; the successful files across seeds and draws all set
STRATEGY_RERVERIFY and leave WORLD_PROFILES/PLAN_PREFERENCE empty).
The failing draws score 1/6 (the no-change baseline). **No partial
draw in this pool** — the outcome distribution is bimodal: complete
success or endpoint failure.

## What the pool establishes

1. **The representativeness rule has numbers**: a single researcher
   draw is a coin weighted ~2:1 toward success at this endpoint —
   single-run researcher claims remain unrepresentative; any report
   must carry the draw distribution (matrix 3's rule, now quantified).
2. **The retry gate's effect is visible but not conclusive**: seed 1
   (gated) drew 3/3 clean; seed 2 (gated) still lost one draw to a
   persistent empty (5 attempts exhausted — the failure's attempt log
   shows the retry loop ran; the endpoint state outlasted the gate).
   The gate recovers transient states, not persistent ones — as
   designed. n=3 per seed cannot attribute the seed-1 cleanliness to
   the gate; it is recorded as consistent-with, not caused-by.
3. **Successful authoring is stable**: across 6 successful draws (3
   seeds), every strategy converged on the same world-generic policy
   and scored 6/6 — genuine authoring variance (a completing draw that
   still fails) has not yet been observed; the variance observed so
   far is entirely the endpoint-reliability component. The floor's
   de-conflation is therefore load-bearing: after the attempt-log fix
   (`e539699` follow-up), every failure record carries
   `usage.attempts` so empty-failures are separable from strategy
   variance by inspection, not inference.

## Post-run fix (applied, untested live)

While reading the s2 failure record this round exposed that the
failure path dropped the improver's attempt log (empty `attempts` on
failed draws). Fixed: `_researcher_round` wraps failures in
`ResearcherRoundFailure` with the attempt log attached; both the main
round record and every author draw now carry `usage.attempts` on
success AND failure. Committed post-run — the next live run will
exercise it.

## Not claimed

Effect estimates at n=9 (CI-less counts); the gate's causal effect
(needs paired gated/ungated draws, not 3+3); strategy variance (the
pool's variance is so far all endpoint-reliability — the authoring
component remains to be observed once reliability is controlled).
