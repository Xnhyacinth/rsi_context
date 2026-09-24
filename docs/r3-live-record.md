# The r3 live first run (2026-09-24, r3-live.json)

The first LIVE run of the unified A/B/C entry (five arms × three
groups, each with its own A0 baseline and its held-out eval twin).
Artifact: `artifacts/rsi-core-v1/r3-live.json` (shared checkout;
13,319 s wall). Governed by docs/stats-contract-v1.md; transcribed
here because the artifact path is gitignored.

**Provenance note (matters):** this is the first run in which the
dev/eval structural split was actually enforced — the pre-run code
review found `_run_arm_on_group` ignoring the phase (every eval cell
re-ran the dev worlds); that run was killed before any artifact was
written and the fix landed first (fd7b46b, pinned by tests). Every
eval cell below ran its group's twin: A = the mirror, B = the full
b1-reverse triple, C = the c1-mirror pair.

## Headline: aggregate four_outcome = **ties** (A: fixed-sufficient)

| Group | Arm | dev (project / decisions) | eval (project / decisions) |
| --- | --- | --- | --- |
| A (lifecycle) | baseline | 0/1 (2/3: award ✗, fu1 ✓, fu2 ✗) | **1/1 (3/3)** |
| A | unassisted_update (truncated, baseline kept) | 0/1 (2/3) | 1/1 (3/3) |
| A | non_adaptive_search (cand 1 selected) | 0/1 (2/3) | 0/1 (1/3: award ✗, fu1 ✗) |
| A | recuris_s0_matched | 0/1 (2/3) | 1/1 (3/3) |
| A | recuris_adapted (round-1 ACCEPTED) | 0/1 (2/3 dev, see improver) | 0/1 (2/3: fu2 ✗) |
| B (sequence) | baseline | 0/1 (3/6) | 0/1 (3/6) |
| B | unassisted_update (truncated, baseline kept) | 0/1 (3/6) | 0/1 (3/6) |
| B | non_adaptive_search (no usable candidate; baseline stands) | — | 0/1 (3/6) |
| B | recuris_s0_matched | 0/1 (3/6) | 0/1 (2/6: s2_calib ✗) |
| B | recuris_adapted (both rounds rejected/bounced) | 0/1 (3/6) | 0/1 (2/6) |
| C (sequence) | baseline | 0/1 (1/2) | 0/1 (0/2) |
| C | unassisted_update (truncated, baseline kept) | 0/1 (1/2) | 0/1 (0/2) |
| C | non_adaptive_search (cand 1 selected) | 0/1 (1/2) | 0/1 (1/2: c2_recovery ✓) |
| C | recuris_s0_matched | 0/1 (1/2) | 0/1 (0/2) |
| C | recuris_adapted (both rounds rejected) | 0/1 (1/2) | 0/1 (0/2) |

Deltas (project-level): Δ_update = 0 everywhere; Δ_search = −1 on A,
0 on B/C; Δ_recuris = −1 on A, 0 on B/C. Aggregate conjunction:
A fixed-sufficient (the baseline already passes the mirror), B ties,
C ties → **ties**.

## The three group stories

**A — fixed-sufficient, and two genuine regressions.** The baseline
passes the mirror 3/3 (dev fails the award and fu2 — the mirror is
easier than the mother here). Two arms lost ground on the held-out
world:
- `non_adaptive_search`: the selected candidate (compiled, zero dev
  policy errors) regressed award AND fu1 — the failure strings show
  worker-reply parsing debris: the committed plan parsed as
  `'none`.*'` and the fu1 supplier as `'nor'` (a truncated
  'northern…'?). Same failure family as R2b's backtick bleed: the
  rewritten policy's reply-parsing is fragile, and the load gate
  (compile + on_turn) cannot see it — only a dev-run failure would
  have, and the candidate's dev decisions were not worse than the
  baseline's (both 2/3). A candidate gate that diffs dev decisions
  vs baseline would select on dev score — the contract forbids it;
  the fragility is reported, not screened.
- `recuris_adapted`: the run's centerpiece — see below.

**B — ties at the project level, with decision-level structure.**
The b1-reverse eval twin bites: baseline 3/6 on eval (loses
s2_currency, s2_reaward_fresh, s3_award — the fresh mother-project
trap) vs 3/6 on dev (loses s1_award, s2_reaward_fresh,
s3_calibration). The recuris arms additionally lose s2_calibration
on eval (2/6) — the frozen recuris policy is weaker than the B
baseline on the reverse twin's session 2. All three researcher
candidates failed (two no-policy, one round-ok but failed the load
gate) → the baseline stood, honestly recorded.

**C — ties, with the run's only decision-level gain.** The baseline
fails BOTH mirror sessions (c1_recovery ✗: harborline fails on the
mirror, the baseline's switch logic doesn't transfer; c2_recovery ✗).
The search candidate uniquely recovered c2_recovery (1/2 on eval —
the mutation/re-award session) while still failing c1. Δ_search = 0
at the project level, +1 at the decision level — reported both.

## The researcher truncation (all three groups)

Every unassisted-update round (1 per group for the update arm + 3 per
group for search candidates) hit the 16,384-token output cap with
`finish_reason=length`: A in 1,969; B in 3,035; C in 3,228 tokens
in. Truncated policies fail the load gate → the baseline stands
(`rejected: policy does not compile`). This is the endpoint's
reasoning-heavy family behavior (per the r2a canaries and the r2a
record's correction — reasoning burns the cap before the policy
emerges), not a transport error: per the frozen contract, retries
are transport-only, so no re-roll. Consequence: Δ_update measures
"no change" in all three groups — an honest outcome, but one that
leaves the live unassisted arm unexercised. The R2b live run's
researcher round DID complete (15,176 out tokens) — the r3 prompts
are longer (the failure-union payload), which plausibly pushed
reasoning past the cap. A max_tokens raise or a reasoning-split is a
config change for the NEXT declared run, not a re-run of this one.

## The recuris mechanism — FIRST live exercise

A's round-1 plan was ACCEPTED: an E-component card
(`precommit_consistency_check`, body: "Before…") passed strict repair
(no dev regression, fu2 0→1 on dev, fingerprint fired). The final
incumbent's dev run: award ✗, fu1 ✓, fu2 ✓ — the patch genuinely
repaired the dev failure it targeted. On the eval mirror it
REGRESSED fu2 (1→0, answered 'reverify' where 'current' is correct):
the mirror's rule change (cold-chain) does not supersede the customs
evidence the award cites, while the mother's does. **The same
disposition — "be more careful about currency" — is a repair on dev
and a regression on the held-out twin: a textbook repair-vs-transfer
data point**, now measured live.

B: round-1 rejected (tie-or-worse, 2 vs 2); round-2 BOUNCED on menu
conformance — the meta-agent proposed `('RHO', 'add_card')`, not in
the validator's component/action menu (meta tokens for the plan were
billed; the patch was never applied). C: both rounds rejected
(tie-or-worse). Meta spend: A 6,414 in / 14,061 out; B 11,438 /
24,067; C 7,092 / 15,243 (2 attempts each).

Open follow-up (recorded, not acted on): the B/C seeds open
`rule_change`/`session_start` invocation stages, but the menu of
patchable components may not cover what the meta-agent wants there —
the bounce is correct validator behavior; whether the menu is too
narrow is a design question for the next round.

## Cost and audit surface

Eval-cell model calls / tokens-in / tokens-out: A 13 / 2,457 / 121
(fixed-shaped arms), A search 15 / 2,044 / 35; B 33 / 5,860 / 398
(baseline-shaped), B recuris 27 / 3,770 / 220; C 18 / 3,571 / 203,
C recuris 15 / 2,041 / 172. Zero policy_errors in every eval cell.
Per-call audit transcript and per-decision failure detail are in the
artifact. (B's `failure_detail` blocks are empty — r3's
`_b_decision_rules` records decisions but not the per-decision
failure strings; the M2 panel's rule set populates them. A one-line
port, noted for the next round.)

## Contract discipline (this run)

- Planned-and-started denominator; every started cell reported; no
  cell re-run or dropped. The run stands as measured.
- Dual denominators throughout: project 0/1 AND decision counts
  (never merged).
- The dev/eval split is REAL in this run (pinned by the fd7b46b
  tests; the pre-fix conflation was killed before any artifact
  existed).
- Four-outcome reporting: A's fixed-sufficient is a publishable
  class, not a failure of the run.
