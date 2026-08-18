# Design critique: RSIBench-Context A2 fitness (2026-08-15)

Status: read-only scientific critique. No generator, grammar, or GPU change in this note.
Panel used as data: `artifacts/hard-baseline-gate/qwen-v3b-causal-replay-disposable-v1.json`
(SHA-256 `a753e56390365c67c9bfdf8db216dcf46bd7579d7165ed908cbb95d887f22d08`), 344 calls.

## 1. Verdict

**Valuable-with-fixes.** The protocol object is a real Datasets & Benchmarks contribution.
The current compositional profile is not a valid A2 fitness landscape, and the pre-registered
primary question cannot be asked on it. Dense can stay. Do not start A2, do not lengthen
context, do not open the KV track.

The minimum repair is a **competitive 2-hop cut with a disjoint validity rule**, not a
harder needle and not a 3-hop chain that `GraphHopsV1.TWO` cannot reach.

## 2. What was evaluated

| Object                                                       | Role                                                                                                                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-registered A2 question (`docs/a2-preregistration.md:20`) | coding researcher vs matched 5-slot search in finite `PolicySpecV1`, isolated gate, calibration, causality                                               |
| Intended venue                                               | NeurIPS Datasets & Benchmarks; protocol/benchmark primary, empirical discovery secondary                                                                 |
| Frozen reader                                                | Qwen3.6-27B, T=0, thinking off, 1 reader call, 32K source → 8K pack                                                                                      |
| Grammar                                                      | 32 curated `PolicySpecV1` configs: selector, hops 0/1/2, allocator, position reserve, order                                                              |
| Compositional generator                                      | `_compositional_item` (~L447): 3 consecutive gold chunks, 3 retired competing pairs, 1 answer decoy                                                      |
| Dense generator                                              | `_dense_item`: 1 rule + 6 scored nodes; **leave unchanged**                                                                                              |
| Difficulty contract                                          | `evaluate_difficulty`: strongest non-oracle in [0.25, 0.75], none ≥0.90, range ≥0.20, top-2 disagreement ≥0.20, gold-drop ≥0.40, CF ≥0.80, no 0/1 strata |

## 3. Strengths (keep)

1. **Locus is clean.** Researcher edits a source-to-context compiler; the policy does not
   answer; reader, decoding, prompt, labels, and single-call contract stay frozen. That is a
   separable scientific object, unlike joint KV/scheduler/policy search (already rejected in
   `.hl/failed_directions.md`).
2. **Causal instruments already pass on this panel.** Full 1.000, gold-drop 0.000,
   counterfactual following 1.000, strongest policy ×5 replay 0.75 SD=0. The failure is
   _difficulty / construct_, not evidence leakage or reader noise.
3. **Dense is still a useful profile.** Max non-oracle 0.50; gold-only/full 1.0. Do not
   retune it to “make the average look harder.”
4. **The protocol already names the right confounds:** extra researcher compute is a
   treatment not a matched efficiency comparison; gold-aware exhaustive selector is required
   because visible gold + a public 32-list is otherwise free search; open Python is a
   separate operator-invention arm; null results have pre-registered interpretations.
5. **Failed directions are being used as science.** v2 lexical saturation, v3 dense
   gold-only floor, v3b compositional grammar saturation are recorded rather than overwritten.
6. A TDD test already exists that _anticipates_ the right structural fix
   (`test_compositional_two_hop_rank_does_not_cover_the_full_gold_chain`): 5 gold chunks,
   hops=2 RANK must not cover full gold on most items, hops=0 ≤ hops=2, RANK vs
   RARE_COVERAGE disagreement. The live generator still emits 3 gold chunks, so this test
   is a specification ahead of the code, not a passed gate.

## 4. Is the research question well-posed?

**As a protocol question, yes. As an A2 estimand on the current panel, no.**

The estimand is: gate score of the visible-selected researcher policy minus gate score of
the visible-selected matched control, paired within profile, seed, reader, and budget.
That is a well-defined, falsifiable contrast. The rival table in the preregistration is
honest (search ties, visible-not-gate, poor calibration, reader floor, replay noise).

**Confounds that remain even after a topology repair:**

| Confound                                                                     | Severity                     | Already handled?                                                                                                                 |
| ---------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Visible gold + enumerable 32-config grammar                                  | Critical                     | Named; gold-aware selector required but **not implemented**                                                                      |
| Extra internal LLM compute vs Random-5/Sequential-5                          | High                         | Named as intentional treatment; do not sell as equal-compute search                                                              |
| 5 slots in 32 classes                                                        | High                         | See §6; not enough to claim “research ability,” enough to claim feedback-use vs blind 5-slot search _if_ the landscape is graded |
| `sequential-search-5` Hamming-one on a _curated_ 32-list with illegal combos | High                         | Named in prose; **no sequential/Hamming walker exists** in `src/rsicontext/baselines/search.py` (only random + grid)             |
| One item per profile×position (Bernoulli 0/1 strata)                         | High                         | Difficulty gate then _must_ fail (`difficulty.py:103`) even for a healthy topology                                               |
| n=4 per profile, score quantum 0.25                                          | High                         | A2 visible is 40 items; the _disposable screen_ must grow before claiming the landscape is calibrated                            |
| Template/split overfitting                                                   | Medium                       | Split body grammars differ; still need sealed isolation (absent on this host)                                                    |
| Historical-best vs last-attempt                                              | Medium                       | Pre-registered; keep both                                                                                                        |
| Construct: “research” vs “pick hops=2 from gold”                             | Critical on current topology | Topology must make gold-recall ≠ reader-score                                                                                    |

**Internal inconsistency:** the difficulty contract requires strongest non-oracle in
[0.25, 0.75] _and_ no stratum at 0 or 1. With one item per stratum, any non-degenerate
policy that is sometimes right will produce 0/1 strata. That is a measurement-design bug,
not a topology bug. Repairing only the generator will not pass `evaluate_difficulty` on a
4-item panel.

## 5. Datasets & Benchmarks vs underpowered method paper

**D&B is the right venue if and only if the paper’s main object is the protocol.**

What D&B can buy:

- a three-way researcher / policy / frozen-reader boundary
- matched 5-slot search, historical-best, gold-aware, and diagnostic oracles
- replay, gold-drop, counterfactual, calibration (Brier vs uniform / always-unchanged / base rate)
- a difficulty contract that can _reject_ a task family (this screen is the existence proof)
- a generator with split-private grammars and opaque IDs

What would make it a method paper in disguise:

- leading with “a coding agent discovers a better RAG policy”
- treating `PolicySpecV1` graph expansion as the scientific result
- 2 researchers × 2 profiles × 2 seeds × 5 rounds sold as a ranking of agents (the
  preregistration already says A2 is a screen, not a ranking — keep that sentence in the
  abstract)
- iterating the generator until the preferred operator (hops=2 + edge-interleave) wins

A2 as currently powered cannot support a methods-style superiority claim. It _can_ support
a D&B claim of the form: “this protocol can detect discovery, retention, calibration
failure, and search-sufficiency on a frozen reader.” That is the paper. Empirical A2 is a
worked example. If A2 is started before the landscape is valid, the example is junk and
the protocol looks like a method that failed.

## 6. Five slots in a 32-config grammar

On the **current** compositional landscape this comparison is vacuous.

11/32 policies score 1.0 on compositional. Random-5 without replacement hits at least one
of those 11 with probability

\[
1 - \binom{21}{5}/\binom{32}{5} \approx 0.90
\]

A researcher cannot beat matched search on a space where blind 5-draw almost surely draws
a perfect policy. Top-2 aggregate policies (`v1:query_bm25:2:rank:none:edge_interleave` and
`...:source`) have **item disagreement 0**. There is no residual fitness to research.

After a graded repair, 5-in-32 is enough to show **feedback-use vs blind 5-slot search**,
not general research ability:

- If ~3/32 configs are “good” (0.5–0.75) and the rest are weak, P(Random-5 hits one) ≈ 0.41.
  Gold+reasoning can beat luck. That is a legitimate screen.
- It still cannot distinguish “scientific researcher” from “enumerate hops then read gold.”
  That distinction is the gold-aware control, which must be reported beside the primary
  estimand (already in the preregistration). If the researcher ties gold-aware and beats
  Random-5, the supported claim is _used visible gold_, not invented a policy class.
- Hamming-one sequential search is only meaningful once the 32-list neighborhood is
  defined on **behavior-class IDs**, not on illegal spec tuples. Implement that before A2;
  do not start A2 to discover that Sequential-5 is undefined.

Do not expand the grammar to 128 configs to make 5 slots look more heroic. That moves the
goalposts and turns A2 into a methods search-space paper.

## 7. Why compositional saturated: evidence chain vs `GraphHopsV1.TWO`

This is not “long context is easy.” Two independent mechanisms, both of which the
32-policy screen measured, make the profile an identity function of operators the grammar
already contains.

### 7.1 Intended chain (what the generator plants)

Visible gold, three chunks, consecutive under HEAD/MIDDLE/TAIL:

1. `The live route for {subject} at cycle {cycle} enters junction {junction}.`
2. `Binding {junction} forwards to folio {folio} with seal {authority}.`
3. `Payload {folio} resolves to {answer}.`

Query names `{subject}` and `{cycle}` only. Answer lives only in chunk 3.

Competing “retired” pairs share `{subject}` but use different junction/folio/value IDs and
are **lexically marked** (`retired`, `not live`, `status=retired_edge`). An answer-shaped
decoy quotes `{answer}` for another subject.

### 7.2 What `GraphHopsV1` actually builds (`spec_v1.py` `_ranked_candidates`)

- Tokens split on non-alnum, so `jx-cc0e4c366079` is `jx` + `cc0e4c366079`.
- Rare IDs: opaque hex with **document frequency ≤ 2**.
- Edges exist only when a rare ID has **exactly two owners**.
- Seeds: query opaque IDs with df ≤ `isqrt(n_chunks)` (8 at 64 chunks), not df≤2.

On the disposable seed (whitespace reconstruction of the same ID topology):

- Subject hex df=5 (gold A + 3 first-decoys + answer decoy). **Not rare, so not an edge.**
- Junction hex df=2 → edge A—B.
- Folio hex df=2 → edge B—C.
- Answer hex df=2 → edge C—answer_decoy (hops=2 does _not_ expand from C, distance already 2).
- Exact-2 edges in the whole 64-chunk artifact: **6**, of which **2 are the gold path**.

The competing chains are **disconnected from the seed in the rare-ID graph**. They compete
only in BM25 (shared subject). Graph expansion never has to choose among live terminals.

Measured gold recall on the real Qwen-tokenized panel:

| Operator                | Compositional gold recall | Compositional accuracy |
| ----------------------- | ------------------------: | ---------------------: |
| hops=0 RANK             |                     0.333 |                  0.000 |
| hops=1 RANK             |                     0.667 |                  0.000 |
| hops=2 RANK (any order) |                     1.000 |                  1.000 |
| hops=0/1/2 MMR          |                     1.000 |                  1.000 |
| hops=2 RARE_COVERAGE    |                     1.000 |                  1.000 |
| lexical                 |                     0.333 |                  0.000 |
| head / head-tail        |             0.333 / 0.667 |          0.250 / 0.500 |

The hop ladder for **RANK** is exactly the intended 1/3, 2/3, 3/3 coverage. Accuracy is 0
until the answer chunk is present, then 1. There is no partial-credit reasoning and no
need for allocation or order once hops=2 lands C. All five hops=2 configs score 1.0.
That is 5 of the 11 saturating policies.

### 7.3 Second saturator: MMR vs cyclic filler (5+1 of the 11)

All five hops=0 MMR configs, plus hops=1 MMR, also score compositional 1.0 with gold
recall 1.0. RANK at the same hop depths does not.

Mechanism: `_padded_text` cycles 87 filler words. Near-duplicate distractors have Jaccard
≈0.73–0.80 with the seed. Gold B/C use a _different sentence template_, so they keep
novelty ≈0.25 while remaining filler clones collapse to novelty ≈0.05 once a few
high-BM25 decoys are taken. MMR therefore promotes gold B (hops=0 rank **63 of 64**) and
gold C (rank **62**) into the 16-chunk pack. This is not multi-hop retrieval. It is
**novelty against homogeneous padding**.

Dense shares `_padded_text`. Do not “fix MMR” by changing filler globally. Diversify
_compositional_ nongold bodies instead (see §8).

### 7.4 Why competing chains do not compete

1. They are off the rare-ID graph (subject df>2, no shared junction/folio with gold).
2. They advertise `retired` / `not live` on the chunk itself. Once the gold path is in the
   pack, the reader does not need a non-local rule. Local wording selects the terminal.
3. Gold A, B, C are consecutive for HEAD/MIDDLE/TAIL, so positional policies that hit the
   block get an unambiguous live path.

Position therefore disappears for every hops=2 policy: head/middle/tail/distributed all
score 1.0. Strongest-policy disagreement is 0 because both winners are hops=2 RANK and
the four compositional items plus the same two dense items flip together.

### 7.5 What this is _not_

- Not a 32K length failure (full context 1.0; gold-only 1.0).
- Not reader inability (gold-drop 0, CF 1.0).
- Not hops=2 “too weak.” Hops=2 is a **perfect decoder of this generator’s unique df=2
  path of length 2**, which is exactly `GraphHopsV1.TWO`.

## 8. Topology repairs (2–3) and the one to implement

Constraint recap: strongest non-oracle <0.90, ideally [0.25, 0.75]; several policies with
dynamic range; top-2 disagreement ≥0.20; gold-only/full near 1; gold-drop large;
counterfactual follows; dense unchanged; dataset-agnostic policy; hops=0 fail, hops=1
partial, hops=2 better but not perfect unless allocation/order also right; competing
chains + cross-region multi-hop + dense distractors; no answer dictionaries in policy.

### Repair A — Competitive 2-hop cut + disjoint rule (RECOMMENDED)

**Gold chunks: 5** (matches the already-written test).

| Gold          | Region                                   | Content                                                                                                 | Graph role                   |
| ------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------- |
| A (seed)      | varies with `EvidencePosition`           | `{subject}` at cycle K **names three junctions** J, J′, J″ without a local winner                       | dist 0                       |
| B             | a _different_ third of the source from A | J → folio F with seal AUTH                                                                              | dist 1                       |
| C             | the remaining third                      | F → `{answer}`                                                                                          | dist 2                       |
| R (rule)      | not adjacent to A/B/C                    | non-local predicate: the live continuation is the junction whose seal equals the cycle-K registrar AUTH | **not** a df=2 neighbor of A |
| M (registrar) | fourth locus (offset from R)             | AUTH is the registrar for cycle K; active folio set includes F                                          | **not** a df=2 neighbor of A |

**Competing chains (not gold):** two full A-linked paths J′→F′→WRONG and J″→F″→WRONG2,
same templates as gold B/C (no `retired` / `not live` / `withdrawn` cue). Validity is
only recoverable from R+M.

**Bushy distractors (replace generic `_distractors` slots, compositional only):** ≥8
satellite chunks that share a df=2 ID with A or B but do not continue a terminal. Target
**|N₂(A)| > 16** (the 8K / 512 = 16 chunk budget) so hops=2 RANK cannot ingest the whole
cut.

**Position:** never place A,B,C as a consecutive block. `EvidencePosition` moves **A**
(head/middle/tail/distributed); B and C stay in other bands. That is cross-region
multi-hop while preserving a position factor for truncation policies.

**Why this hits every required inequality:**

- hops=0 RANK: seed A ± BM25. No C. Accuracy ~0.
- hops=1 RANK: A + B/B′/B″ + A-satellites. No C. Accuracy ~0 (“partial” = intermediate
  recall, not a free point).
- hops=2 RANK: A + all dist-1 + a **prefix** of dist-2. May include C, C′, C″; usually
  misses R and M. Reader sees multiple terminals and no registrar → accuracy in the
  middle band, not 1.0.
- hops=2 RARE_COVERAGE / MMR: different leftover slots (uncovered rare IDs vs novelty) →
  item disagreement with RANK, including on dense-untouched compositional items.
- Order (source / relevance / edge-interleave): when two terminals are in the pack,
  Qwen’s T=0 copy preference can flip. That is the cheapest disagreement ≥0.20.
- Gold-only / full: R+M+A+B+C present, one live terminal. Keep the rule as easy as v3b
  dense (“matching seal, ignore others”) so Qwen can still score ≥0.85 complete-evidence.
- Gold-drop: remove those five; competing terminals and answer decoys remain → large drop.
- MMR hops=0: many equal-template competitors/satellites, so gold B/C are no longer the
  unique novel documents against cyclic filler.
- Policy stays ID-agnostic: still BM25 + rare-hex graph + coverage/MMR/order.

**Do not** lengthen the gold _path_ to 3 hops. `GraphHopsV1.TWO` would then be unable to
reach the answer, the restricted A2 arm would be vacuous, and the temptation would be to
change the grammar (out of scope).

### Repair B — 3-hop path, grammar-unreachable terminal (REJECT)

Four path chunks, hops=2 never sees the answer. Forces either grammar expansion or
reliance on MMR/filler accidents. Makes PolicySpecV1 the wrong hypothesis class. Reject.

### Repair C — Answer = aggregate of several 2-hop leaves (REJECT for compositional)

Collides with dense (global compare). Would blur the two-profile design. Reject as the
compositional repair; dense already owns this skill.

## 9. Over-fitting the generator to `PolicySpecV1`

This is the main scientific risk of Repair A if tests are written as “hops=2 RANK must
score 0.50.”

**Symptoms of a puzzle:**

- unique df=2 bridges planted _because_ the interpreter uses df≤2 and exact-2 edges
- a rule chunk whose only purpose is to be the leftover that RARE_COVERAGE greedily takes
- filler/templates adjusted until MMR no longer wins, rather than because documents should
  be heterogeneous
- stopping criterion = “32-policy GPU screen now sits in [0.25, 0.75]”

**Mitigations (do these in tests, not in a score loop):**

1. Encode **document** invariants first (path length, competing terminals, rule disjoint
   from the seed graph, |N₂| vs budget, cross-region span, no local status cue). See §10.
2. Use PolicySpecV1 only as a _probe_ of those invariants (hops=0 misses answer ID;
   hops=1 misses answer ID; hops=2 neighborhood contains ≥2 terminals; RANK vs coverage
   packs differ). Do not assert reader accuracy in unit tests.
3. Keep the rule a general context skill (“apply a globally stated seal/cycle filter”),
   the same family as dense’s qualification rule, not an operator-shaped Easter egg.
4. Freeze topology tests before any GPU rescreen. One disposable Qwen screen after tests
   pass; if it misses the band, **stop and rethink**, do not gradient-descend the
   generator against the 32 scores.
5. Do not add family terms, regexes, or answer dictionaries to policy. If a repair only
   works by banning `retired` in the _policy_, the task is still a lexical giveaway.

The existing test `two_hop_rank_does_not_cover_the_full_gold_chain` is useful but is
already slightly puzzle-shaped (it asserts 5 gold and RANK/coverage disagreement). Keep
it as a _consequence_ test; add the document-level tests below as the actual specification.

## 10. Testable structural invariants (BEFORE any GPU rescreen)

Lock these on the generator with the pinned tokenizer **or** a word-count stand-in that
preserves ID topology; do not rescreen until they pass. Dense tests must still pass
unchanged (`test_dense_query_specifies_aggregation_and_exact_output_contract`, 7 gold,
6 node IDs).

**Document topology**

1. Compositional gold cardinality is 5: `{A,B,C,R,M}`.
2. Cross-region: `max(gold_index) - min(gold_index) ≥ (2/3) * (n_chunks - 1)` on every
   compositional item, including HEAD/MIDDLE/TAIL (no consecutive 3-block).
3. A, B, C occupy three distinct position thirds.
4. Query contains the subject ID and cycle, not the answer, junction, folio, or AUTH.
5. Answer ID occurs in C and in ≥1 off-path decoy, never in the query.
6. ≥2 nongold terminals (distinct `vl-` IDs) are 2-hop reachable from A on the rare-ID
   graph (exact-2 edges, same definition as the interpreter).
7. R and M share **no** df=2 identifier with A (rule is non-local).
8. Competing B/C templates are string-isomorphic to gold B/C up to IDs; they must not
   contain `retired`, `not live`, `inactive`, `withdrawn`, `superseded` as a local cue.
9. |N₂(A)| (nodes with graph distance ≤ 2 from the BM25 seed of the subject hex) > 16.
10. Opaque IDs only; no split/profile/position/gold/answer-marker leakage (existing test).

**PolicySpecV1 probes (consequences, not score targets)**

11. hops=0 RANK: answer chunk recall = 0 on all compositional items; gold-A recall = 1.
12. hops=1 RANK: answer chunk recall = 0; gold-B recall ≥ 1 on a majority of items.
13. hops=2 RANK: answer-chunk recall ∈ (0, 1) **across the 4+ item panel** (not 0/0/0/0
    and not 1/1/1/1); full 5-gold coverage on ≤ half the items (existing test).
14. hops=2 RANK vs hops=2 RARE_COVERAGE selected span sets differ on ≥20% of items.
15. hops=0 MMR answer-chunk recall < 1.0 (kills the filler-novelty oracle).
16. LexicalPolicy still fails complete gold coverage on a majority (existing test).
17. Dense gold count, query contract, and decoy structure unchanged; dense tests unmodified.

**Calibration-panel size (difficulty contract, not topology)**

18. Disposable screen must use **≥2 items per profile×position** (preferably 3) or the
    stratum clause in `evaluate_difficulty` cannot pass even for a healthy task. n=4 with
    one item per position is a guaranteed 0/1 stratum failure.

Do not put reader exact-match targets in unit tests. Reader scores are the GPU screen.

## 11. What should NOT be done next

1. **Start A2.** Landscape rejected; Sequential-5 and gold-aware selector are not even
   executable; host cannot attest sealed isolation.
2. **128K / 256K / LongMemEval as a cover-up.** Failed direction already: lengthening a
   saturated topology does not unsaturate it. A3 explicitly starts at 32K after A2.
3. **KV / HBM / scheduler / prefix-cache track** mixed into the semantic estimand.
4. **Change dense** to compensate for compositional saturation.
5. **Expand or retune `PolicySpecV1`** (add hops=3, fill axes, dataset terms) so that the
   old 3-chunk path is “hard again.” That is a methods paper and an overfit.
6. **Change global filler** to break MMR; it mutates dense.
7. **Drop the gold-aware control** or claim 5-in-32 shows general research ability.
8. **Reinterpret difficulty thresholds** after the next screen (`regressions.md`).
9. **Pool compositional+dense into one “overall 0.75”** as evidence that A2 can start.
   The contract is per profile. Compositional 1.0 is a stop.
10. **One more 3-static-baseline GPU run.** The 32-policy screen is the unit; after
    generator tests pass, rerun the _full_ grammar once.

## 12. Kill conditions for the project

Stop or narrow (do not silently retarget) if any of the following hold after one honest
topology repair and one full 32-policy disposable screen:

1. Gold-only or bounded-oracle < 0.85 on compositional (reader/task floor; policy search
   cannot fix it — v3 dense lesson).
2. Any non-oracle `PolicySpecV1` config ≥ 0.90 on compositional (still saturated).
3. hops=0 RANK or hops=0 MMR still recovers the answer on most items (still a padding or
   lexical puzzle).
4. hops=2 RANK remains 1.0 _and_ RANK vs coverage vs order still have zero item
   disagreement (competition not in the 2-hop cut).
5. No config exceeds ~0.25 (task not in the grammar’s span). Restricted A2 is then empty;
   only the open-Python arm could be meaningful, which is a different paper.
6. Passing the screen requires editing `PolicySpecV1` or planting operator-shaped cues.
7. Matched Random-5 / gold-aware always match the researcher and the authors pivot to an
   agent-superiority methods claim anyway.
8. Sealed isolation never becomes available and hidden transfer is still claimed.
9. Replay SD is no longer ≪ policy deltas (attribution dies).
10. The generator is iterated through many GPU screens until a favorite operator wins
    (Texas sharpshooter on the 32-list).

A clean kill is still a D&B-useful outcome: “this protocol rejected its own task family.”
An unclean continuation (128K, A2-on-saturated, KV) is not.

## 13. Claim–evidence matrix (this screen)

| Claim                                                 | Evidence                                                                | Status               |
| ----------------------------------------------------- | ----------------------------------------------------------------------- | -------------------- |
| Reader can solve compositional from complete evidence | gold-only 1.0, full 1.0                                                 | Pass                 |
| Evidence is necessary                                 | gold-drop 0.0                                                           | Pass                 |
| Reader follows rewritten answers                      | CF 1.0                                                                  | Pass                 |
| Endpoint is deterministic enough                      | replay 0.75 SD=0                                                        | Pass                 |
| Strongest non-oracle in [0.25, 0.75]                  | 11 policies at 1.0 compositional; aggregate strongest 0.75 from 1.0+0.5 | Fail (per profile)   |
| Top-2 disagreement ≥0.20                              | 0.0                                                                     | Fail                 |
| Strata not 0/1                                        | n=1 per cell                                                            | Fail by construction |
| hops=2 is a graded operator                           | hops=2 RANK/MMR/coverage all 1.0                                        | Fail                 |
| Competing retired chain stresses the graph            | competing paths off rare-ID graph; local “retired” cue                  | Fail (design)        |
| 5-slot researcher vs search is askable                | 11/32 at 1.0 ⇒ Random-5 hit rate ≈0.90                                  | Fail                 |
| Dense still useful                                    | max 0.50, oracle 1.0                                                    | Pass — do not touch  |
| A2 may start                                          | preregistration + this matrix                                           | **No**               |
