# World-level task-semantic audit of research-v2 (2026-09-20)

Status: **first-priority deliverable of the external review round 3** — the
task-semantic audit of observed worlds, executed against the actual PopQA
rows rather than summaries. Every classification below was verified by
reading the question, subject, aliases, and gold-passage text of the row in
`data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl` at HEAD
`dd8fc0b`. This document amends (does not supersede) the records it cites.

## 1. The unified result index (reconciling 17/20 and 0.333)

The two headline numbers come from **two different instruments on two
different world sets**, and they are consistent once stated precisely:

| Number | Instrument | World set | Presentation | Scoring path |
| --- | --- | --- | --- | --- |
| 17/20 pass | `scripts/difficulty_stratification.py` — one reader call per world | 20 gold-sane-v2 worlds | question + all 9 survey docs (noise[:8] + gold) in ONE prompt | immediate extraction (`difficulty_stratification.py:213-223`) |
| 3-arm tie 0.333 | `scripts/arm_comparison_v2.py` — full five-stage lifecycle | 3 dev worlds (542248, 3006731, 1652383), 4 instances each | stage-1 survey only carries the docs; stage 5 carries none | sandbox commit via `ObjectiveChecker` alias mode |

The dev-3 slice contains **2 of the pool's only 3 non-pass worlds**
(3006731, 1652383) plus one trivial pass world (542248). Per-world outcomes
under the lifecycle (4/4, 0/4, 0/4 for every arm, w2/w4 reproduced) are
**identical to the single-call probe's tiers**. Verified conclusion:

> For these worlds, the five-stage lifecycle adds no measurable difficulty
> over single-call presentation. The memory-necessity gate (no-history 1.0
> vs 0.0) comes from withholding documents at stage 5 — but when notes work,
> item difficulty is decided at stage 1 by the same span-selection and
> normalization mechanisms as the one-shot probe.

The v2 family's realized value so far is **leak closure and staged access
discipline**, not harder information integration. That is the gap the
main-task revision must close, and it is a constructor problem (make stages
2/4/5 binding), not new infrastructure.

The tie therefore licenses no claim about arms in either direction: the
slice had no mid-difficulty headroom (verified), and nothing about method
efficacy, budget, or update mechanisms is established by a tie at n=12 with
zero headroom items. The arm-comparison record's "binding constraint is
item difficulty structure" stands **for this slice only**, per this
amendment.

## 2. What `gold_sane_v2` checks, and what it cannot

`gold_sane_v2` (`lifecycle/material_v2.py:164`) requires that some gold
passage contains, after normalization, (i) an answer alias and (ii) a
subject term. Both terms are checked by **string co-occurrence**. It is a
necessary hygiene gate against the wrong-entity retrieval class, and it
works (the 4402885 defect row is rejected). It is **not** a relation check:
nothing verifies that the passage asserts the asked relation *about the
asked entity*.

The external review's four-class taxonomy is adopted verbatim as the audit
classification:

| Class | Definition | Handling |
| --- | --- | --- |
| 1. Label/scoring defect | correct evidence-side answer is missed by aliases, or gold passage does not support the label for the asked entity | fix or remove from formal pool; never a difficulty tier |
| 2. Unresolvable ambiguity | question admits multiple entities; material carries no disambiguation cue | accept answer sets, or drop; never force a hidden gold |
| 3. Resolvable association difficulty | sufficient cues exist; the reader must bind question-entity to gold-entity across distractors | valid task material |
| 4. Long-range strategy difficulty | early information choices change later action quality | the main task's target; currently absent (see §5) |

## 3. Per-world audit table (all 20 stratification worlds)

Verified from row content. "Title-bound" = gold passage title carries a
subject term; "relation" = whether the gold text *asserts the asked
relation about the asked entity*.

| World | Question (subj) | Gold title | Title-bound | Relation support | Class | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| 542248 | occupation, Tadhg Dall Ó hUiginn | same | yes | stated directly ("was an Irish poet") | 3 (easy) | keep (regression surface) |
| 6112233, 3538090, 5035834, 6392317, 3731527, 3727461, 2734115, 1948707, 510782, 984804, 6391380 | entity-page questions, title-bound | same | yes | stated directly or near-directly | 3 (easy) | keep |
| 5919594 | genre, The Cross | Cross (disambiguation) | yes | **stated for the exact work** ("The Cross" (2009 film), a documentary film) among 5+ same-name rows | 3 (genuine) | **keep — the pool's one true class-3 world** |
| 1650366 | country, Randfontein | List of cities and towns in Gauteng | no | "South Africa" appears in the gold text; relation inferable from province list | 3 (weak) | keep, monitor |
| 2004556 | sport, Rotherham County F.C. | Rotherham United F.C. | yes (successor club) | any club page states football | 3 (easy) | keep |
| 2120061 | occupation, Darrell Hammond | Mark Z. Danielewski | **no** | Darrell Hammond named as "SNL alum" among "different actors"; occupation relation **inferential, not stated** | 3, masked | reclassify: passes today via parametric recall (famous entity), not evidence binding — candidate for the mid tier **only after** the label is pinned to evidence-side wording |
| 3026511 | father of Krishna | Mahabharata | **no** | **defect**: gold text is Jain cosmology where "Vasudeva" is a *class name in a triad with Krishna*, not a father assertion; the alias hit is co-occurrence luck | **1** | **remove from formal pool** (kept as a gold-sane regression fixture) |
| 1652383 | genre, Holiday (Green Day song) | Scuba Dice | **no** | **defect at relation level**: genre phrase ("power pop, punk, punk pop") describes the *covering band*, not the asked song; label "punk rock" is the Green Day original's genre | 1/2 hybrid | **decide before any use as "target tier"** (see §4) |
| 6271105 | sport, Dragons (rugby union) | Ballarat | **no** | **entity mismatch**: gold describes the *Ballarat Dragons rugby league* club (a different team, different country, different code); the asked subject is the Welsh rugby-union Dragons; the hit is saved only by the broad alias "rugby" | 1/2 hybrid | decide (see §4) |
| 3006731 | genre, Killjoy (2000 film) | Killjoy Goes to Hell | yes | **entity mismatch beneath the "normalization" label**: gold is the 2012 *sequel* ("comedy horror film"), asked entity is the 2000 original; "comedy horror" is faithful to the evidence, the alias set belongs to a different film | 1 + residual normalization | decide (see §4) |

Headline finding: **at least 6 of 20 worlds carry question-entity ≠
gold-entity at the relation level, and one of them (3026511) sits in the
"pass" tier** — the co-occurrence gate cannot see any of them. The
stratification record's proposed "mid-difficulty tier" (question-entity ≠
gold-subject at work level) is precisely the relation-mismatch set, i.e.
**the planned sampler would have deliberately manufactured more class-1/2
items**. The tier-stratified sampler (40% span-selection / 40% pass / 20%
normalization) is **withdrawn as a main-pool plan**; the review's
structural-stratification replacement is adopted (§6).

## 4. The three decision cases (owner calls, not silent fixes)

**1652383 Holiday.** Two defensible task semantics: (a) "genre of the
Green Day song" — then the Scuba Dice passage does not support the label
and the world is class-1 until a song-side gold passage exists; (b) "genre
of the rendition the project surveyed" — then the correct answer set is
the band's own phrasing ("power pop, punk, punk pop" / "punk"), the
current aliases are wrong, and the reader's dominant-distractor failures
('romantic comedy', 'bubblegum pop') become genuine class-3 difficulty.
Recommendation: (b) with evidence-side answer sets; only then does this
world earn "mid-difficulty" status.

**6271105 Dragons.** Same structure: label entity (Welsh RU side) vs
evidence entity (Ballarat RL club). Either pin the label to the evidence
entity (answer set then includes "rugby league" — and note the current
alias "rugby" already containment-hits it, which is why the world "works"
today) or drop the world. As constructed it measures alias breadth, not
evidence binding.

**3006731 Killjoy.** The "normalization gap" ("comedy horror" vs "horror
film") is real but sits **on top of** a sequel-vs-original entity
mismatch. Decide the entity first; the qualifier-scoring question (option
(b) in the stratification record) is secondary and stays a reported-second
metric.

## 5. Implementation findings beyond the review

1. **Cross-world learning is structurally unmeasurable in the current arm
   harness.** `arm_comparison_v2.py:232` resets state to `{}` at every
   world boundary for every arm; the `__carry__` mechanism for the
   ds-researcher arm is dead code (the hook never writes `__carry__`, so
   the lookup always returns `{}`). The frozen-learning-snapshot contract
   (benchmark-contract-v2 §Protocol semantics: learned material carries
   EQUALLY into every branch; the boundary is source/time/scope) is
   **not implemented** — the harness enforces the blunter
   wipe-everything rule the review §六.1 warned about: "重置后好了" proved
   the reset changes outcomes, not that wiping is the right boundary. The
   contract's rule remains the spec; the implementation must grow a
   legitimate carry channel (method/strategy notes that are not per-item
   answer strings) with the leak probe as the guard.
2. **The fact-following gate's "closed" wording overstates.** The
   lifecycle fact-swap probe (`dependency_probes.py:961`) runs the swap
   with `_OracleStatefulHook` (a perfect-reader simulation,
   `dependency_probes.py:519`): its 1.0 follow rate proves the
   runner+materials+checker transmit an edited stage-1 fact to the
   committed answer **under an oracle participant**. It measures plumbing,
   not participant memory behavior; no real participant's fact-following
   has been measured. The gate's status is corrected from "closed" to
   "closed under an oracle participant" in the probe record; the
   reader-level 0.125 stays a reader-extraction lens. This is exactly the
   overstatement class the external review targeted.
3. **`first_gold_rank` constant at 9 is a v1-contract regression**,
   already recorded; position jitter belongs to the constructor revision
   (balance in the **final visible material**, not the raw ctxs index).
4. **The five designed failure classes are not yet constructible.**
   task-family-research-v1's classes (compression loss of an exception;
   stale preference after supersession; delegation without provenance;
   plan on outdated state; declared-vs-actual mismatch) all require stages
   2/4 to carry **binding** constraints and the sandbox to have
   multi-action state. Today stage 2's constraint is satisfiable by
   remembering a title, stage 4's "supersession" marks a noise document
   nothing relied on, and the only sandbox action is the final answer
   commit — `axes.action_dependency="strong"` is nominal. This is the
   concrete gap between the v1 spec (still the design of record) and the
   v2 implementation, and it is exactly the review's "阶段性信息访问约束
   的检索—记忆—回答任务" vs "信息—状态—行动依赖" distinction.

## 6. Amended execution order (review round 3 accepted)

The review's re-prioritization is adopted, mapped to existing surfaces:

1. ~~Task-semantic audit~~ — **done, this document**. Owner decisions
   requested on the three cases in §4; 3026511 removed from the formal
   pool; the 40/40/20 outcome-tiered sampler withdrawn.
2. **Main-task prototype** = make the existing five stages binding
   (constructor work, no new infrastructure): stage-2 constraint that
   references evidence *content* an agent must have retained (not just a
   title); stage-4 supersession that actually invalidates a prior
   conclusion the agent could hold; multi-record sandbox state where an
   early write is a precondition for a later one. Qualification bar: the
   five failure classes become constructible and the no-history /
   fact-swap / longdoc gates rerun on the revised material.
3. **Structural stratification** (task attributes: evidence dispersion,
   dependency span, update count, action chain length) + gold-position
   jitter; outcome tiers become calibration information only, never pool
   composition. Pass-tier worlds stay in the pool as the
   regression-observation surface per the contract's 2026-09-20
   amendment.
4. **One complete improvement trajectory**: strong fixed memory-operational
   arm + one improvement method + its control, from a shared S0, snapshots
   S0→S1, evaluated on unseen worlds. A tie or a regression is a
   reportable outcome; no signal-chasing.
5. Replication/transfer last (LongMemEval-V2 as frozen-policy transfer
   face; world-clustered statistics).

The review's own closing standard is adopted as the next round's success
criterion: the round's deliverable is *knowing what the result means
whichever way it lands*, not a positive delta.

## Disposition

This audit strengthens rather than overturns the standing records: the
family's qualification gates, the tie record, and the stratification
measurement all stand as measurements. What changes: the fact-following
gate wording (§5.2), one world removed from the formal pool, the
outcome-tiered sampler withdrawn, and the next-step order above replaces
the sampler-first plan in `difficulty-stratification-20260920.md` §
Consequences 1 and `arm-comparison-v2-first-20260920.md` § Consequences 1.
