# A2 pre-registration: researching a frozen model's information interface

Status: implementation and difficulty calibration. No A2 paper result has been run.

## Scope and primary question

RSIBench-Context studies whether a coding researcher can improve a frozen
reader's **source-to-context compiler**. The editable object is an executable
policy that selects, allocates, orders, and verifies evidence under an 8K
`ContextPack` budget. The reader weights, decoding, prompt, evaluator, and
single-call contract remain fixed.

This is bounded component-level self-improvement, not recursive self-improvement:
the researcher does not improve its own weights, and the policy does not answer
the task. Relative to RSIBench-Data, the intervention locus changes from training
data to the inference-time information interface. Exact policy replay removes
post-training variance, making discovery and retention failures more directly
attributable to the research process.

The pre-registered A2 primary question is:

> Under five candidate evaluations in the same finite `PolicySpecV1` grammar,
> does a coding researcher discover and retain a context policy whose isolated-
> gate score exceeds the best visible-selected non-agent search control, while
> predicting item-level improvements and regressions before evaluation and
> passing evidence-causality checks?

The primary estimand is the gate score of the visible-selected researcher policy
minus the gate score of the visible-selected matched control, paired within task
profile, research seed, reader, and budget. Gate outcomes never select a round.
A2 screens for a usable signal; it is not powered to rank researchers. The
researcher, Random-5, and Sequential-search-5 receive byte-identical committed
visible `RoundFeedback`, the same H0, and exactly five candidate slots. The
researcher's additional internal LLM compute is an intentional treatment and is
reported in tokens, cost, and wall time; this is not a pure algorithm-efficiency
comparison.

Arbitrary audited Python is a separate open-program arm, not part of this
matched primary estimand. If the restricted researcher ties search but the open
researcher wins, the supported claim is representation/operator invention—not
superior search within a common policy class. A finite random search cannot be
called matched to unrestricted Python.

## Fixed factorial and accounting

`build_a2_pilot_plan` materializes the exact `2 researchers x 2 task profiles x
2 research seeds x 5 rounds` factorial. Each researcher/profile/seed cell is a
separate trajectory over 40 visible items from one task profile. Each of the 40
researcher turns has a hard 1,800-second timeout, so the aggregate researcher
wall ceiling is 72,000 seconds. Invalid, duplicate, timed-out, missing, or
over-budget submissions consume their attempt slot.

The matched primary runs in a frozen repository image with a fixed dependency
lock, prompt, tool allowlist, task bundle, and network-disabled researcher
workspace. A separately labeled open-autonomy arm may use the public internet,
but does not enter the matched estimand. Candidate policy workers and the reader
endpoint have no network in every formal arm. Candidate slots, wall time,
feedback bytes, target calls, and policy tokens are matched allocations;
researcher tokens/dollars and reader GPU/HBM/latency are accounting outcomes.

These serialized seeds control researcher/search randomness and public visible
item order only. Generator seeds for gate and sealed data are evaluator secrets,
are independently sampled per split, and never enter this plan or a researcher
workspace.

For every profile/seed pair, the controls are:

- Random-5 without replacement from the pre-registered common policy grammar;
- Sequential-search-5 under the same five candidate evaluations;
- budget-matched static H0, head-tail, lexical, and hand-hybrid references;
- evaluator-only bounded-oracle, gold-only, no-context, and unbudgeted
  full-context diagnostic instruments. Full context is not a matched 8K policy.

The restricted primary uses a benchmark-owned canonical `PolicySpecV1`
interpreter for every controller. The committed grammar contains only dataset-
agnostic choices for seed selection, rare-token graph expansion, bounded hop
depth, allocation/diversity, position reserve, evidence order, and coverage
verification. It contains no arbitrary strings, regexes, family/profile terms,
answer dictionaries, or split switches. The grammar schema, interpreter source,
canonical valid-config list and order, target tokenizer, and H0 bytes are hashed
before evaluation. Random-5 samples without replacement from that list;
Sequential-search-5 follows a fixed Hamming-one neighborhood and tie rule.
Duplicate, invalid, timed-out, or over-budget candidates consume their slot.

Because the researcher sees visible gold evidence, the non-agent references
must also include an exhaustive gold-aware `PolicySpecV1` selector that scores
every profile-local behavior class by evidence recall without target-reader
calls. Random-5 and Sequential-search-5 alone cannot isolate feedback use: a
researcher could otherwise enumerate the public grammar offline and look
stronger merely by exploiting free gold information. The gold-aware selector
is reported separately from five-call matched search and participates in the
strongest-control comparison.

The implemented V1 registry currently contains 32 curated configurations. The
behavior-class audit is performed separately within each A2 task profile: on
the repaired disposable panel with the pinned Qwen tokenizer, compositional has
32 classes and dense has 22. Both exceed the pre-registered minimum of 20.
Random/sequential controllers must sample or traverse these profile-local class
IDs without wasting slots on duplicates. This is a structural policy-space
qualification, not a reader-score or researcher result; all 32 policies still
require the real-reader saturation screen below.

That full 32-policy screen has now run on a disposable visible seed. Eleven
policies score 1.0 on compositional, violating the non-oracle 0.90 ceiling;
dense has a healthy maximum of 0.50. Gold-drop decrease, counterfactual
following, and exact replay are 1.0, 1.0, and zero observed standard deviation,
respectively, but the strongest two policies have zero item disagreement. The
current compositional profile is therefore rejected as A2 fitness even though
its causal and replay instruments pass.

The generator replacement (Repair A) keeps five gold statements `{A,B,C,R,M}`
but does not lengthen the hop grammar. Gold A/B/C occupy distinct source thirds.
Two competing two-hop terminals are string-isomorphic to gold B/C and carry no
local `retired`/`not live` status cue. Registrar and cycle-authority statements
are not distance-2 neighbors of A, and satellite pairs force `|N₂(A)| > 16` on
32K sources. Structural tests require hops=0/1 RANK to miss gold C, hops=2 RANK
to recover C on a proper subset of items, RANK vs RARE_COVERAGE disagreement,
and hops=0 MMR not always packing C. Dense is unchanged. The Repair A Qwen
screen (736 calls, seed `hard-repair-a-visible-causal-disposable-v1`)
unsaturated the grammar (max compositional 0.375) but failed gold-only 0.85 and
bounded-oracle 0.80. Repair B changes only the query/output contract, not
topology, hops, or the 32-config grammar. Do not add hops=3 or expand the
grammar to unsaturate the panel. Every landscape reports accuracy together with
pack tokens, reader tokens, and wall seconds (LongLLMLingua efficiency axes).

The matched-controller surface is now implemented in the harness: Hamming-one
sequential search, exhaustive gold-aware recall without a reader call,
byte-identical `RoundFeedback`, pre-dispatch `SpendLedger` caps (including
`$0` local-only runs), restricted V1 workspaces that may contain only
`spec_v1_key.txt`, invalid submissions consuming attempt slots, and an A2
launcher that refuses qualification-only plans. This is not A2 execution.

Each arm uses H0-inclusive visible historical-best to select one artifact after
all five rounds, breaking score ties by lower actual reader input and then
earlier attempt. Random and sequential each select on visible; the single
"best matched control" is then selected between them using visible score and a
fixed controller-priority tie break. Only precommitted selected artifacts are
evaluated once on gate. Random and sequential each contribute one visible-
selected artifact to gate for secondary controller-specific reporting; which
one is the primary "best matched control" is committed from visible scores
before either gate result is revealed. This is why the call projection includes
both control artifacts while the primary estimand uses only one. Gate feedback
therefore never enters candidate generation or model selection. Each researcher
trajectory's exact peak and last artifacts, plus the selected matched control
per profile/seed, receive five **additional** exact-byte replays. With 40 items
per split, the nominal successful-matrix projection is 10,720 target-reader
calls. It excludes retries, partial failures, difficulty calibration, causal
audits, tokenizer preflight, and sealed transfer; it is neither a worst-case
ceiling nor spend authorization. A runtime ledger must debit before dispatch,
and a dollar/GPU-hour/wall-time cap and retry allowance must be filled before
execution. The plan also fixes 40 researcher turns and 1,600 pre-evaluation
probability triples.

## Difficulty contract

The old four-item panel remains an infrastructure qualification only. The
formal A2 task identities are not yet frozen. They must fill two pre-registered
roles: (1) realistic long-document evidence routing and (2) causally annotated
multi-hop or global reasoning. At least one profile must come from a real public
long-document distribution; synthetic profiles may provide causal instruments
but cannot be the sole paper headline. The currently promising routing cell is
HELMET PopQA k1000 (approximately 111K source tokens to an 8K pack). The second
role remains blocked until a MuSiQue/HotpotQA/2Wiki-style supporting-fact task
with target-tokenized distractors passes the same oracle, saturation, position,
and causal gates. Exact profile IDs, revisions, and fingerprints freeze before
the first A2 researcher turn.

The rejected synthetic calibration candidate used a target-tokenized 32K source
with an 8K policy budget and two profiles:

1. compositional retrieval with five gold statements, isomorphic competing
   two-hop terminals, and a bushy distance-2 neighborhood. The v3b three-link
   unique-ID chain is rejected: it is isomorphic to `GraphHopsV1.TWO` and
   saturates 11/32 policies. The v3c retired-chain repair is also rejected:
   local status cues kept competitors out of the two-hop cut, and hops=0 MMR
   could still pack the gold terminal;
2. dense global authority comparison requiring a rule and six distributed
   candidate records in the presence of wrong-cycle and wrong-seal decoys.
   Dense is unchanged from the v3b repair.

Temporal stale/future/authority resolution and supported abstention are held as
additional diagnostic profiles for A3 or transfer. All profiles support
head/middle/tail/distributed evidence. Opaque policy-facing IDs contain no split,
topology, answer, or gold markers. Gate/sealed seeds are independent evaluator
secrets and are never derived from a visible seed.

The v3 generator now builds directly against an evaluator-owned target tokenizer
and uses structurally different Ledger, CARD, and Dispatch grammars for visible,
gate, and sealed splits. Hidden splits require independent evaluator-secret
seeds. These are implementation properties, not a passed scientific gate:
independence still depends on the secret resolver and physical evaluator
boundary, and real-reader qualification remains mandatory.

Primary-profile decoy bodies now also differ by split: visible uses ledger
narrative, gate uses key-value rejection records, and sealed uses withdrawn or
review narrative. Tests reject wrapper-only distinctions by checking
characteristic nongold body signatures. This is a generator property, not a
confidentiality or hidden-transfer result.

The first v3 disposable Qwen qualification generated 32,730--32,750 actual
tokens for a 32,768 target. It removed compositional lexical saturation, but the
dense profile scored zero even under gold-only and bounded-oracle evidence.
A v3b replacement then achieved 1.0 under gold-only, bounded-oracle, and full
context, with fixed-policy scores from 0.25 to 0.50 overall and no-context 0.
The strongest two fixed policies disagree on 3/8 items. This repairs the
reader/task floor and clears the disposable disagreement threshold but does not
make A2 eligible: the larger-sample stratum, gold-drop, counterfactual, replay,
controller-runner, and physical-isolation gates remain pending.

Before any researcher run, a disposable calibration seed—not a formal A2
seed—must satisfy both primary profiles:

- gold-only accuracy at least 0.85 and bounded-oracle accuracy at least 0.80;
- no-context accuracy at most `max(chance + 0.05, 0.10)`;
- strongest non-oracle fixed policy in `[0.25, 0.75]`, with none at or above 0.90;
- fixed-policy range at least 0.20 and the two strongest policies disagree on
  at least 20% of items;
- gold-drop decreases accuracy by at least 0.40 and counterfactual
  answer-following is at least 0.80;
- no hop/load/position stratum is entirely correct or entirely wrong;
- replay standard deviation is below 20% of the median meaningful policy delta.

Failure means changing or replacing the failed profile before the seed is
frozen. Adding context length or meaningless filler is not a repair for
saturation or floor effects.

## Manifest calibration

Before every evaluation, the candidate manifest must cover all 40 visible items
with `P(improve)`, `P(unchanged)`, and `P(regress)` relative to the actual parent
artifact. Multiclass Brier score is primary; log loss, ECE, and improve/regress
precision-recall are secondary. Comparators are uniform, always-unchanged, and
a leave-one-trajectory-out empirical base rate. Aggregate intervals cluster by
trajectory and item; a single round's ECE is descriptive only.

All primary controllers receive the same serialized `RoundFeedback` bytes and
hash for a round: visible item order, parent predictions and scores, visible gold
evidence, and the token/cost ledger. A controller may ignore fields but may not
receive an expanded view. This separates discovering a good policy from
understanding its effect. The existing four-item qualification already
illustrates the distinction: a large
visible gain coexisted with poor calibration, but its sample is too small for a
scientific conclusion.

## Rival hypotheses and interpretable outcomes

| Result                                                       | Supported interpretation                                                             | Not supported                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| Researcher wins isolated gate, passes drop/keep and transfer | coding agents use feedback better than matched search within the same policy grammar | general intelligence improvement or long-context SOTA |
| Random/sequential search ties or wins                        | the chosen policy class does not require an expensive coding researcher              | that all context research is useless                  |
| Visible improves but gate does not                           | template/seed overfitting or repeated-evaluation exploitation                        | transferable discovery                                |
| Historical-best removes most last-attempt regret             | selection/stopping is the main retention bottleneck                                  | monotonic researcher improvement                      |
| Gain is stable but manifest calibration is poor              | discovery without reliable scientific self-knowledge                                 | mechanism understanding                               |
| Gold-only/bounded oracle are low                             | reader reasoning, not policy search, is the binding bottleneck                       | policy failure                                        |
| Replay noise matches round changes                           | endpoint/runtime drift or nondeterminism prevents causal attribution                 | research-process regression                           |

Comparison with RSIBench-Data remains a locus-level hypothesis unless the same
researcher snapshots and matched feedback/evaluation budgets are run across both
benchmarks. Descriptive comparison to its reported regression rate is not a
causal cross-benchmark result.

The open-program arm has a different interpretation. A hidden-template and
metamorphic transfer gain can support that a coding researcher invented a useful
operator outside `PolicySpecV1`; it cannot support matched-search superiority.
Visible gains that disappear under bijective identifier renaming, paraphrase,
or decoy-template inversion are generator exploitation, not transferable
context-policy research.

## A2 to A3 and transfer gates

A3 does not start unless all eight A2 trajectories fill five attempt slots,
systematic invalid rate is at most 10%, every call has a cost ledger, retry is
below 1%, both task profiles pass the difficulty and causal gates, claimed
effects exceed replay noise, and gate evaluation has a formal runtime and
physical-isolation attestation. A practical discovery screen is a gate advantage
of at least 0.05 over the strongest matched control in one profile with the same
direction on both seeds, or another pre-registered retention/calibration signal.

A3 begins at 32K. Selected frozen policies then transfer to 128K/256K while
holding the 8K policy budget fixed and varying one axis at a time: topology,
position, distractor type, or length. Every longer cell must pass exact pinned-
tokenizer rendered-prompt accounting, output reserve, request-success, OOM/
truncation, replay, and oracle gates.

LongMemEval-V2 follows only as offline frozen-policy transfer against full trace,
last-k, lexical/hybrid, and random-trajectory baselines. Live long-horizon tests
are last, paired policy-on/off external-validity experiments with a frozen host
agent and no feedback into the research loop.
