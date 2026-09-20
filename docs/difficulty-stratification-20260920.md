# Pool widening, difficulty stratification, and failure-mode quantification (2026-09-20)

Status: tasks #28 + #29 from docs/arm-comparison-v2-first-20260920.md
§Consequences. Script: `scripts/difficulty_stratification.py`; artifact:
`artifacts/qualification/difficulty-stratification-20260920.json` (20
gold-sane-v2 worlds, one reader probe each, Qwen3.6-27B @ siflow T2).

## Tier distribution (20-world pool)

| Tier | Count | Meaning |
| --- | --- | --- |
| pass | 17 | reader extracts an alias from the survey — memory adds nothing |
| span_selection | 2 | reader answers from a non-gold passage (the mid-difficulty tier where notes/retrieval CAN change outcomes) |
| normalization | 1 | right span, alias-set mismatch — scoring/item problem, not memory |

**The pool is 85% easy.** With only 2 mid-difficulty worlds per 20, an
arm comparison needs a much larger pool or a deliberate sampler to find
items where improvement mechanisms can matter.

**[Superseded 2026-09-21 by docs/world-audit-20260920.md and
docs/legacy-seal-20260921.md: (i) 6/20 worlds carry relation-level
question-entity ≠ gold-entity mismatches, including 3026511 in the pass
tier — "pass" here certifies extraction, not label validity; (ii) the
"span_selection" tier as defined (question-entity ≠ gold-subject) is the
relation-mismatch set, so the tier-stratified sampler proposed below
(§Consequences 1) is WITHDRAWN — structural stratification replaces it;
(ii) the three decision worlds are withdrawn from the formal pool.]**

## Structural signals measured per world (and their limits)

- `first_gold_rank` is **constant at 9** (gold appended after the 8-doc
  noise slice) — position never varies, so it cannot stratify; future
  constructors should jitter gold position (position balance was a v1
  contract rule the v2 slicing quietly dropped).
- `ambiguous_noise_docs` (subject-term mentions in noise) and
  `gold_token_share` do NOT separate pass from fail cleanly (pass worlds
  span ambiguity 0-8 and share 0.078-0.284; the 3 fails sit inside both
  ranges).

## Failure-mode mechanism (per-item, task #29's deliverable)

The three non-pass worlds decompose into two distinct mechanisms:

1. **Question-entity ≠ gold-subject at the WORK level (2 worlds)** —
   1652383 "What genre is Holiday?": the question asks about a SONG; the
   gold passage describes the BAND that covered it ("power pop, punk,
   punk pop"); 8 noise docs are films named "Holiday". 6271105 "What
   sport does Dragons play?": gold describes "The Ballarat Dragons" under
   the title "Ballarat". The reader must (a) reject same-name distractors
   and (b) accept an indirect subject relation — genuine
   **span-selection difficulty where better notes/strategy can change
   the outcome**. This IS the target tier.
2. **Alias-normalization gap (1 world)** — 3006731 "What genre is
   Killjoy?": gold literally says "comedy horror film", aliases are
   "horror film"/"horror movie"; the reader's evidence-faithful
   extraction ("comedy horror") is *correct behavior* met by a scoring
   gap. This tier carries no memory signal until the scoring semantics
   decide whether qualifier-stripped matches count (a deliberate
   scoring-policy decision, not a bug).

## Consequences

1. **Sampler change (constructor work)**: to build comparisons with
   enough mid-difficulty items, the pool loader needs a
   `--tier-stratified` mode: probe worlds cheaply (one call each, this
   script's method), then compose dev pools with a target tier mix
   (e.g. 40% span-selection / 40% pass / 20% normalization). The
   20-world probe costs ~20 reader calls — cheap enough to run at
   pool-construction time.
2. **Gold-position jitter**: re-add position balance to the v2 slicing
   (gold rank currently constant at 9).
3. **Scoring policy decision (owner call)**: does qualifier-stripped
   matching ("comedy horror" vs "horror film") count? Options: (a)
   strict alias containment (current — normalization worlds are noise),
   (b) add qualifier-tolerant scoring as a SECOND reported metric, (c)
   exclude normalization-gap worlds from improvement measurement and
   report them separately as a reader-normalization lens. Recommended:
   (c) now, (b) as an analysis column later.
4. The mid-difficulty definition is now operational: **question-entity ≠
   gold-subject at the work level, gold present, aliases present in
   gold** — constructible as a deliberate pool criterion (subject-term
   NOT in gold title, question entity name ≠ gold subject name, while
   gold_sane_v2 still holds via body text).
