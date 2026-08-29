# RSIBench-Context execution roadmap

Status: planning and qualification. This document operationalizes the normative
[`study-contract.md`](study-contract.md) and
[`a2-preregistration.md`](a2-preregistration.md); it does not replace either.
All expected effects below are hypotheses, not results.

## What the project is testing

The scientific treatment is a frozen coding researcher given bounded feedback
and five opportunities to edit a source-to-context policy. The outcome is not
whether that researcher can answer a long-context question. It is whether the
policy artifact it authors causes a frozen reader to outperform policies found
by matched non-agent search on evaluator-isolated items, while predicting and
retaining its effects.

This makes the project analogous to RSIBench-Data at a different intervention
locus:

| Element             | RSIBench-Data                                        | RSIBench-Context                                             |
| ------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| Editable artifact   | training data/config                                 | inference-time context policy H                              |
| Frozen causal stack | training/evaluation recipe around each data proposal | reader, decode, prompt, evaluator, policy interpreter        |
| Main uncertainty    | discovery mixed with training variance               | policy discovery above measured replay/runtime variance      |
| Research question   | can a researcher improve post-training data?         | can a researcher improve the reader's information interface? |

The intended paper is therefore a benchmark/protocol and empirical study. It
does not claim strict RSI, a new compressor, a new evolution operator, or
long-context state of the art. A method contribution is deferred until a
reproducible failure mode survives historical-best and matched controls.

## Recuris: borrow, adapt, and keep separate

| Recuris mechanism                           | RSIBench-Context use                                                        | Boundary                                                  |
| ------------------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------- |
| invariant machine versus evolving memory    | checksum frozen reader/evaluator versus editable H                          | strengthens the existing isolation contract               |
| component-scoped patch                      | manifest names changed H components and predicted flips/cost                | researcher still edits only `policy/`                     |
| mechanism fingerprint                       | evaluator records actual selection/order/verification/abstention activation | attribution instrument, not fitness                       |
| held-out arithmetic gate and regression cap | paired item bootstrap and anchor-regression analysis                        | hidden gate remains one-shot and gives no search feedback |
| file-based cross-round memory               | benchmark-owned committed feedback and artifact ledger                      | no hidden chat history as an uncontrolled resource        |
| evolving working state/checkers             | baseline in offline/live long-horizon transfer                              | excluded from static A2 genotype                          |

Recuris's task plugins, oracle knowledge, retries, model judges, four-round
schedule, and simulation budget are not copied into the primary experiment.
They define a different task and noise model.

## Claim-to-evidence matrix

| Claim                       | Comparison                                                                                       | Required evidence                                                               | Main falsifier                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| autonomous policy discovery | best researcher H versus H0 and first valid H                                                    | paired visible and gate effects above replay floor                              | gain is no larger than replay/runtime drift                            |
| researcher advantage        | visible-selected researcher versus visible-selected strongest matched control                    | paired isolated-gate difference and item bootstrap CI                           | Random-5, Sequential-5, or gold-aware selector ties/wins               |
| retention/reliability       | last versus peak versus historical-best                                                          | post-peak regression rate and selection regret, clustered by trajectory         | historical-best is misreported as monotonic improvement                |
| predictive self-knowledge   | submitted flip probabilities versus observed parent-relative outcomes                            | multiclass Brier primary; log loss/ECE/PR secondary                             | uniform or always-unchanged is as good                                 |
| evidence-grounded mechanism | policy gain plus gold-drop/keep, counterfactual, parametric deletion, and activation fingerprint | causal score changes and actual policy-component activation                     | answer survives evidence deletion or claimed component never activates |
| transfer                    | frozen selected H on new length/template/domain/reader/horizon                                   | no further search; paired transfer effects and task requalification             | gain disappears outside visible construction                           |
| efficiency                  | researcher/policy versus matched control                                                         | accuracy per reader token, target call, wall time, and reported dollar/GPU cost | gain is only from more target calls or an unmatched budget             |

## Execution matrix

| Stage      | Purpose                                                        |                                    Scale |                                    Reader calls | Launch condition                      | Output                                           |
| ---------- | -------------------------------------------------------------- | ---------------------------------------: | ----------------------------------------------: | ------------------------------------- | ------------------------------------------------ |
| T0-offline | choose a real causal multi-hop source                          |                       3 dataset families |                                               0 | licenses/revisions reviewed           | qualification comparison and one selected source |
| T0-reader  | validate task floor, ceiling, causality, disagreement, noise   | 16-item screen then 40-item confirmation |                           derived before launch | pinned adapter and tokenizer          | signed difficulty report; pass or reject         |
| A2         | detect whether the benchmark has a researcher signal           |                   2R × 2P × 2S × 5 slots | 10,720 nominal, excluding qualification/retries | both profiles + isolation + caps pass | complete micro-pilot ledger and analysis         |
| A3         | estimate discovery, regression, calibration, and heterogeneity |                  4R × 4P × 4S × 10 slots |                TBD from A2 throughput and power | A2 go criteria pass                   | paper-scale benchmark results                    |
| A3-L       | test information-allocation transfer                           |             32K/128K/256K, fixed 8K pack |                                             TBD | frozen A3 policies                    | length/position/topology transfer curves         |
| A4         | test offline horizon transfer                                  |                           LongMemEval-V2 |               TBD from official scorer protocol | official evaluation integrated        | frozen-policy memory comparison                  |
| A5         | external validity in a live agent                              |            one preregistered task family |                    task-specific, retry matched | A4 and live preflight pass            | paired policy-on/off study                       |

The A2 call count is a nominal projection, not spend authorization. A3 and
transfer calls remain TBD until A2 produces measured throughput and variance.

## Task roles and qualification

The two A2 profiles must expose different policy decisions:

1. **Real long-document routing.** HELMET PopQA k1000 is the current candidate:
   approximately 111K source tokens must be reduced to an 8K pack. It must
   remain non-saturated across the canonical grammar and must not be described
   as official HELMET performance until the official scorer is used.
2. **Causal multi-hop/global reasoning.** Select one of MuSiQue, HotpotQA
   distractor, or 2Wiki only after an offline comparison of supporting facts,
   licenses/revisions, answer deletion, counterfactual validity, source length,
   position control, and leakage risk. The final construction must require all
   supporting facts and contain target-tokenized distractors.

Synthetic topology tasks and 8K NIAH remain instruments for policy activation,
noise, position, and null calibration. They cannot be the main evidence that a
researcher improves real long-context capability.

Every task must pass the exact preregistered oracle, saturation, disagreement,
causal, stratum, and replay thresholds before researcher search begins. A longer
document is useful only when it changes evidence allocation, dependency, or
interference—not because the token counter is larger.

## Baseline families

| Family                | Baselines                                                                             | What it rules out                                                       |
| --------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| static policy         | H0, head, tail/head-tail, lexical/BM25, hand hybrid, full context when it fits        | trivial truncation/retrieval gains                                      |
| matched finite search | Random-5, Sequential Hamming-one-5                                                    | researcher gains caused by five lucky evaluations                       |
| visible-gold control  | exhaustive gold-aware `PolicySpecV1` selector                                         | free exploitation of visible supporting facts                           |
| adapted optimizers    | GEPA/ACE-style controller in the same grammar and target-call budget                  | advantage over established prompt/context optimization                  |
| evaluator instruments | no context, gold only, bounded oracle, gold drop, counterfactual, parametric deletion | reader floor, parametric shortcuts, and non-causal gains                |
| long-horizon          | full trace, last-k, random, lexical/hybrid, state-grounded working state              | gains attributable to generic recency/retrieval or Recuris-style memory |

Restricted and open-program arms must never be pooled. Winning in the restricted
arm is evidence about search/reasoning in a common hypothesis class; winning
only in the open arm is evidence about operator invention.

## Analysis plan

- Use paired item effects for within-cell score comparisons. Bootstrap items for
  task effects and cluster aggregate uncertainty by trajectory and item; never
  treat exact replays as independent samples.
- Report last, peak, and historical-best together. Compute post-peak regression
  only for trajectories with valid attempts after their peak.
- Score every pre-evaluation manifest relative to its actual parent artifact.
  Multiclass Brier is primary; calibration claims require aggregation beyond a
  single 40-item round.
- Record a policy activation fingerprint that compares parent and candidate
  packs at the component and item levels. A claimed mechanism is unsupported
  when the relevant behavior never changes, even if aggregate score moves.
- Report input/output tokens and target calls for every run. Latency, dollars,
  GPU-seconds, peak HBM, KV state, prefix-cache state, and scheduler settings are
  accounting metadata only when directly observable. Missing API-side metrics
  remain `unobservable`.
- Analyze researcher effects separately from reader effects. `hy3-ioa` can
  replace a coding-researcher treatment under a frozen API contract; replacing
  the target reader changes the benchmark block and requires fresh difficulty,
  replay, and endpoint-attestation gates.

## Expected patterns and how to interpret them

| Hypothesis              | Expected direction                                                | If observed                                             | If not observed                                                   |
| ----------------------- | ----------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| H1 discovery            | best researcher H > H0/first valid beyond replay                  | coding agents can locate useful policy changes          | no autonomous discovery in this policy/task budget                |
| H2 researcher advantage | researcher > strongest matched control on gate                    | feedback use/reasoning adds value inside common grammar | grammar is enumerable enough that coding research is unnecessary  |
| H3 retention gap        | last < peak on a nonzero fraction; historical-best reduces regret | discovery and retention are distinct                    | deterministic policy search may be more stable than data-side RSI |
| H4 calibration gap      | calibration improves more slowly than score                       | discovery without reliable scientific self-knowledge    | manifests may be useful stop/gate signals                         |
| H5 length transfer      | positive effect partly survives 128K/256K                         | learned allocation principle generalizes                | visible topology/length overfit                                   |
| H6 horizon transfer     | frozen H beats retrieval/recency baselines offline                | some static context principles transfer to memory       | online state evolution is a distinct capability                   |

These directions guide falsification and power planning; they are not promises.
A matched-search tie, failed transfer, or disappearance of regression above a
near-zero noise floor remains a useful benchmark result if the corresponding
confidence intervals are informative.

## Go/no-go ledger

| Gate                          | Current status           | Required next evidence                                                         |
| ----------------------------- | ------------------------ | ------------------------------------------------------------------------------ |
| three-way API/policy boundary | implemented and tested   | re-attest in formal image                                                      |
| real routing profile          | promising, not frozen    | complete PopQA qualification                                                   |
| causal multi-hop profile      | blocked                  | offline dataset selection + pinned adapter + reader qualification              |
| replay floor                  | local qualification only | repeat on both final profiles and formal endpoint                              |
| spend caps                    | blocked                  | signed host/provider `SpendCaps`                                               |
| physical gate isolation       | blocked                  | evaluator process/container/mount/network attestation and negative access test |
| runtime identity              | partial                  | endpoint/model-response and all code/data/runtime hashes                       |
| A2                            | not launched             | every gate above passes                                                        |
| A3/A3-L/A4/A5                 | conditional              | preceding stage analysis frozen                                                |

The immediate implementation unit is deliberately narrow: produce the offline
multi-hop dataset qualification artifact, select one candidate, and only then
add a reviewed registry entry and adapter. No researcher or gate evaluation is
authorized by this roadmap alone.
