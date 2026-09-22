# New-semantics live smoke — 2026-09-22

Reviewer of `8013d6f` asked for exactly one thing before the main-benchmark
phase: a live smoke to confirm the model wiring survived the env-verification
fix, explicitly NOT another endpoint-retry study. This is that smoke.

Artifact: `artifacts/trajectory-v3/live-smoke-post-fix-20260922.json`
(run: `--researcher --rounds 1 --seed 0`, exit 0, 47.2 min wall,
Siflow key from the workspace local-env).

## Wiring confirmed

- **Reader (Qwen3.6-27B @ Siflow)**: live five-stage sessions on the dev
  world; per-cell hook ledgers recorded (e.g. S1 new-world cells: 5 calls,
  2.7K/4.1K in, 9.5K/9.3K out). Replies drove plan/check extraction.
- **Researcher (deepseek-v4.1-flash @ Siflow)**: round outcome `ok`, 1
  attempt (no retry), 682 in / 905 out tokens, 41 s.

## Result shape (one draw, one seed — calibration-grade, not a claim)

| Cell | S0 (no strategy) | S1 (researcher strategy) | F0 (fixed) |
| --- | --- | --- | --- |
| continuation ×2 | fail (stale evidence) | **pass** | fail |
| new_world ×2 (orinoco, zephyr) | 1 fail / 1 pass | **pass** | 1 fail / 1 pass |
| regression ×2 | fail (stale evidence) | **pass** | fail |

The S1 passes rest on env-issued evidence: the strategy's re-requests were
re-executed by the environment under the current protocol revision — no
self-labeled `protocol_revision: 2` records exist. Every cell records its
world identity + material sha256; zephyr's hash reflects the corrected
constraint text, so the fingerprint did its job. No strategy errors.

## What the researcher actually wrote (notable)

It chose a WORLD-GENERIC policy over lookup tables — and said why:
`WORLD_PROFILES` and `PLAN_PREFERENCE` were left empty *deliberately*
because per-world names "do not exist on unseen worlds and would silently
degrade to no policy at all". STRATEGY_RERVERIFY=True is the whole policy.

## Honest caveats

- One draw, one seed; the S0→S1 gap here is calibration evidence, and the
  stub still documents the flag (assisted-improvement framing, per the
  review's §2.3 — the task prompt names the failure mode).
- S0/F0's zephyr pass is the non-scoped-first-candidate shape (the world's
  own semantics, not a fluke), and the fixed arm's failures are the
  designed control.
- Endpoint reliability (empty-content draws) did not recur in this single
  round; nothing about that distribution should be re-inferred from n=1.

Status: wiring under the new semantics is confirmed; the live path is
usable for the deliverable-2/3 work (real acting loop, strong fixed
baseline, unprompted improvement).
