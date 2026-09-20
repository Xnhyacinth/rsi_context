# First meaningful arm comparison on research-v2 (2026-09-20)

Status: **first real comparison record** on the family qualified by
docs/probe-gates-v2-20260920.md. Four runs (artifacts/arm-comparison-v2/
first-, fourworlds-, fourworlds-w2-, fourworlds-w3-, fourworlds-w4-*.json);
the stable configuration (world-boundary state reset + DS strategy wired
into the extraction pipeline) is the w2/w4 pair. 3 dev worlds × 4
instances = 12 items per arm; reader Qwen3.6-27B @ siflow T2; ~38 min/run.

## Results (stable, reproduced across w2/w4)

| Arm | Alias hit rate | Per world (3006731 / 1652383 / 542248) |
| --- | --- | --- |
| fixed (memory-operational) | 4/12 = 0.333 | 0/4 · 0/4 · 4/4 |
| experience (within-world persistence) | 4/12 = 0.333 | 0/4 · 0/4 · 4/4 |
| ds-researcher (strategy wired back) | 4/12 = 0.333 | 0/0 · 0/4 · 4/4 |

**All three arms tie at 0.333.** No arm improves over the fixed reference
on this slice. Per-item answers are nearly identical across arms; the DS
researcher's extraction edit changed exactly 2 answers (both
"Thinking Process:" → "comedy horror" on the Killjoy world — the
meta-phrase stripping genuinely works) without changing any hit.

## What the failure structure says (per-world, per-item)

The three worlds split cleanly by difficulty mechanism:

- **world 542248 (poet): 4/4 everywhere.** Unambiguous entity; the gold
  passage dominates; every arm extracts "Irish poet" (alias-contained).
- **world 3006731 (Killjoy): 0/4 everywhere.** "Comedy horror film" in
  gold vs aliases ("horror film", "ho..." family) — answers like "comedy
  horror" are *evidence-faithful extractions* that miss the alias set
  (normalization gap at the item level; alias_hit_v2 is containment-
  based and "comedy horror" does not contain "horror film").
- **world 1652383 (Holiday): 0/4 everywhere.** Ambiguous entity: 8 of 9
  survey documents are about films named "Holiday"; the single gold
  passage (Scuba Dice, "power pop, punk, punk pop") is a needle the
  reader must prefer over dominant distractors. Reader answers
  "romantic comedy" / "bubblegum pop" — wrong-span selection, not
  extraction failure.

## Findings (honest, mechanism-level)

1. **No arm shows improvement on this slice** — the fixed
   memory-operational reference ties every improvement arm. On THIS
   evidence, neither experience accumulation (within-world) nor a DS
   strategy edit moves the needle. A tie is a reportable result, not a
   failure to hide: with only one arm's worth of difficulty variance
   across worlds (either the item is easy for all or hard for all),
   there is no headroom for any improvement mechanism to show.
2. **The binding constraint is item difficulty structure, not memory or
   strategy**: 542248 is trivially solvable by any pipeline; 3006731 and
   1652383 fail at reader-level evidence selection/normalization that
   no extraction strategy can repair (you cannot fix choosing the wrong
   span after the fact). The family's dynamic range currently collapses
   into "all-solve" vs "all-fail" per item — exactly the pattern the
   difficulty-contract kills (top-two disagreement) are designed to
   catch at panel level.
3. **The world-boundary discipline is validated as a measurement**: the
   first run (no boundary reset) showed experience 0/12 < fixed 4/12
   because stale cross-world notes ("comedy horror" carried into the
   poet world) actively poisoned answers — a real, mechanism-identified
   failure of naive persistence that the boundary rule eliminates.
   Continuation vs migration separation is not paperwork; it changes
   outcomes.
4. **The DS-researcher wiring defect is now actually fixed and
   verified**: the strategy file demonstrably enters the extraction
   pipeline (2 answers changed). The three historical occurrences of
   the "wired in name only" defect (n=16 panel, round 1, round 3
   conditional) are closed: the strategy is applied whenever present on
   disk.
5. **DS researcher reliability is a real operational cost**: of four DS
   rounds, one timed out, two hit empty/truncated replies (reasoning
   budget), one succeeded. Researcher-tier reliability gates (the T2
   machinery applied to the improver side) are a needed addition before
   any multi-round improvement trajectory.

## Consequences (next actions, in order)

1. **Item pool widening with difficulty stratification**: the dev world
   pool must be large enough to hold items between the "all-solve /
   all-fail" poles (evidence-selection difficulty that memory CAN
   move: e.g. gold present but non-dominant, answer derivable from
   combining stage-1 evidence with the stage-4 rule). The current
   3-world slice cannot show improvement because it has no items where
   better memory/notes change the outcome.
2. **Reader-side span-selection is the measured bottleneck**: quantify
   per-item whether the failure is span selection (wrong passage
   chosen) vs normalization (right span, alias mismatch) — the fix
   differs (item construction vs scoring).
3. Researcher-side reliability gates (retry/backoff on the improver
   endpoint) before multi-round trajectories.
4. Fact-following probe (lifecycle path) remains open from the gate
   record.

## Disposition

Recorded as the first honest comparison: a three-way tie at 0.333 with
mechanism-level attribution of why (item difficulty structure), the
world-boundary discipline validated, the DS wiring defect genuinely
closed, and the path forward determined by measurement rather than by
preference. No improvement claim is made or implied.
