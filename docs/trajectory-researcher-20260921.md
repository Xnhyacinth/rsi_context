# First researcher-authored S0→S1 trajectory (2026-09-21)

Status: **trajectory record — the first S1 whose strategy was written by
the researcher model** (review round 4 deliverable 5's completion;
`docs/trajectory-v3-20260921.md` was the harness-authored rehearsal).
Script: `scripts/trajectory_v3.py --researcher`; artifact:
`artifacts/trajectory-v3/researcher-live-20260921.json` (live, siflow
Qwen3.6-27B reader + deepseek-ai/deepseek-v4.1-flash researcher; 3271.6 s;
researcher round: 682 input / 1357 output tokens, 6.3 s wall — the full
C_improve of the improvement, now a real model's cost).

## The loop (identical harness to the rehearsal)

Dev session (live reader) → S₀ frozen → **S₀ dev-branch probe over the
three branch kinds collects the gate's named failure messages as
restricted feedback** → one researcher round: the DS model receives the
task + the stub's interface contract + the failure feedback and rewrites
`strategy.py` → **the researcher's file is S₁'s carried code, whatever
it says** → S₀/S₁/fixed-F₀ each enter continuation / new-world
(variant worlds orinoco/parana) / regression branches.

## Results

| Snapshot | Continuation | New-world (variants) | Regression | strategy_errors |
| --- | --- | --- | --- | --- |
| fixed F₀ | fail ×2 | fail ×2 | fail ×2 | — |
| ds S₀ | fail ×2 | fail ×2 | fail ×2 | none |
| ds S₁ (researcher-authored) | **pass ×2** | **pass ×2** | **pass ×2** | none |

Reference executor: pass (aurora). The failure signature on F₀/S₀ is the
named stale-protocol-revision gate failure; S₁'s cells pass with
`strategy_errors == []` — clean, not crash-fallback.

## What the researcher actually did (the interesting part)

The DS round (round_outcome "ok", 1.4k output tokens) produced a
strategy that:
- diagnosed the mechanism from the feedback alone: "verification
  evidence is keyed to a protocol revision, and every rule change bumps
  that revision… no matter which world, plan, domain or check name is
  involved";
- set `STRATEGY_RERVERIFY = True` (the world-generic fix);
- **explicitly declined the two hardcoding traps**: it left
  `WORLD_PROFILES` empty ("per-world entries would have to name specific
  plans/domains/checks, which cannot generalise to unseen worlds; the
  default is the safe superset") and `PLAN_PREFERENCE` empty ("plan
  names differ per world"), with reasoning written into the file;
- documented its own policy and non-decisions in the docstring.

The S₁ that passes on BOTH the main and the variant surfaces is
therefore the researcher's world-generic policy choice, not plan-name
lookup — the transfer surface did its job, and this time the
improvement was authored by the model under test, not by us.

## What this record does and does NOT claim

- **It does not claim a capability result.** n=1 researcher, n=1 round,
  one task family, three worlds, one reader/researcher pair; the
  improvement surface here was designed to be findable (the stub
  documents the interface; the feedback names the failure). It is a
  CLOSED, EXPLAINED LOOP: the edit verifiably entered the pipeline,
  legitimate carry brought it to every branch, branches ran
  independently, the cost is two-columned, and the outcome is
  attributable to a named mechanism.
- The fixed-arm experience control (F₀ through the same dev stream)
  still fails all branches: "experience alone" (notes, no strategy
  update) did not repair the weakness; the strategy EDIT did. That is
  the contrast the S₀-vs-S₁ design isolates — but at n=1 it is a
  demonstration of the measurement, not an effect estimate.
- The researcher's token cost (682 in / 1357 out) is now a real
  C_improve datapoint: two orders of magnitude below the deployment
  cost of the trajectory's reader calls — the cost split the benchmark
  exists to make visible.

## Replication status

Single run, no seeds, no repetition battery — a screen, not a test. The
replay/variance machinery (T2 gates) was not invoked for this
trajectory; per the contract, statistical claims need the replication
matrix, which remains future work.
