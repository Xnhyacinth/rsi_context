# RSIBench-Context study contract

Status: **normative project charter; no paper-scale A2 result has been run**.
The historical fixed-8K executable is launch-invalid after the elastic-envelope
revision. A new executable instance must be reconciled with and frozen in
[`a2-preregistration.md`](a2-preregistration.md), then re-hashed before
evaluation.

## Research question and claim boundary

The project asks:

> Under a fixed reader, evaluator, feedback interface, and resource envelope,
> can a general coding researcher autonomously discover, predict, retain, and
> transfer a better source-to-context compiler than matched non-agent search?

This is a benchmark of **bounded externalized self-improvement at the context
policy locus**. It is not strict recursive self-improvement of the researcher:
the researcher model, reader weights, and outer loop do not change. It is also
not another context-compression method or a long-context leaderboard entry.

Let `R` be the frozen researcher system, `H_k` the editable context policy,
`M0` the frozen reader, `E` the frozen evaluator, and `F_k` the permitted
feedback after round `k`. The benchmark loop is:

`H_(k+1) = R(H_k, F_k; B)`, followed by `F_(k+1) = E(M0(H_(k+1)(x)))`, under
the fixed resource envelope `B`. `B` constrains maximum rendered context,
per-candidate batch input tokens, derived trajectory input tokens, calls, wall
time, and retries; it does not force every policy or item to consume the same
number of context tokens.

We use the following terms only when their conditions are met:

| Term                     | Required evidence                                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| iterative search         | at least two valid or invalid attempt slots are consumed                                                                    |
| autonomous discovery     | a researcher-authored `H` beats H0 and the first valid attempt beyond replay noise                                          |
| researcher advantage     | the visible-selected `H` beats the visible-selected matched control on the isolated gate                                    |
| retained improvement     | last-attempt and historical-best are both reported; the accepted policy passes anchor-task regression criteria              |
| transferable improvement | the frozen selected `H` improves a new length, template, domain, reader, or offline trajectory split without further search |
| strict RSI               | **not claimed**; neither researcher weights nor the outer improvement procedure self-modify                                 |

The paper remains valuable if researchers fail. A matched-search tie identifies
that the policy class is too simple to require a coding researcher. A visible
gain that fails gate transfer identifies overfitting. Historical-best removing
the gap identifies selection rather than discovery as the bottleneck. Replay
noise matching round changes invalidates the causal claim and stops the study.

## Relationship to the closest systems

The design deliberately combines experimental disciplines that prior work uses
at different intervention loci:

| Work                                               | Editable object                                                 | Fixed budget or gate                                                                         | What RSIBench-Context adds                                                                                             |
| -------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| [PostTrainBench](https://arxiv.org/abs/2603.08640) | full post-training pipeline                                     | 10 hours on one H100 per run; held-out evaluation                                            | isolates one information-interface locus instead of granting control over training and infrastructure                  |
| [RSIBench-Data](https://arxiv.org/abs/2607.25886)  | training data and whitelisted config                            | shared training/evaluation, nominal 16 hours and $500 per run                                | removes checkpoint-training variance and tests context-policy discovery and retention                                  |
| [Recuris](https://arxiv.org/abs/2608.24876)        | experiential/working memory, invocation, checkers               | fixed model and outer improver; held-out admission gate                                      | compares multiple general researchers against matched search and measures replay noise, manifests, and sealed transfer |
| Scientist's Last Exam (protocol cousin)            | scientific `solution.py` under a hidden domain verifier         | frozen executable oracle; open-loop saturation admission; score/validity-only next-round feedback | same isolation grammar at a different locus: long-context compiler `H` plus frozen reader, not a scientific simulator |
| RSIBench-Context                                   | `H`: select, expand, allocate, order, compress, verify, abstain | fixed reader/evaluator, candidate slots, per-turn timeout, target-call budget, isolated gate | the benchmark and discovery-reliability analysis are the contribution                                                  |

Recuris closes the broad claim that external memory-control evolution for
long-horizon agents is new. Its state-grounded invocation, structured traces,
component-scoped patches, and validation gate are reference mechanisms and
baselines. Our remaining novelty is the **researcher benchmark**: can different
general coding agents discover policies under a shared hypothesis space and
budget, can they predict their effects, and can they retain the gains above a
measured noise floor?

## Frozen, editable, and evaluator-only surfaces

| Surface            | Contract                                                                                                                                            |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| researcher `R`     | model snapshot/alias, scaffold version, reasoning effort, prompt, tools, network mode, turn timeout, and start state are frozen within a trajectory |
| policy `H`         | only top-level `policy/*.py`; restricted primary submissions select a canonical `PolicySpecV1`; the open-S harness track (`docs/open-s-harness.md`) starts from a byte-identical `seeds/open_s_v1/` folder and may invent operators, still under one target-reader call |
| submission         | audited policy plus `manifest.json`; duplicate, invalid, timed-out, or missing submissions consume a slot                                           |
| reader `M0`        | weights/revision, tokenizer, chat template, thinking mode, prompt builder, decode, output cap, serving profile, and one-call contract are frozen    |
| evaluator `E`      | splits, labels, official metric, policy interpreter, promotion rule, causal instruments, and statistical analysis are frozen                        |
| visible split      | item failures, scores, costs, and gold evidence may be returned as committed `RoundFeedback` bytes                                                  |
| gate/sealed splits | questions, labels, seeds, item scores, and fingerprints remain evaluator-only and never generate a new candidate                                    |

The policy may transform supplied evidence but may not answer the question,
call the reader, access the network, change serving, or score itself. In the
`single_reader` track, every item permits exactly one target-model call.
Evidence sufficiency checks must be deterministic policy operations. Adaptive
reread and auxiliary-model calls belong to a separately budgeted future track.
Semantic policies and KV/cache/scheduler optimization never share a leaderboard.

## Researcher environment and resource contract

The primary benchmark uses a frozen repository image, dependency lock, task
description, visible data snapshot, and tool allowlist. Scored runs have no
researcher internet access; a separately labeled open-autonomy arm may browse
public sources, but cannot enter the matched primary estimand. The policy worker
and reader endpoint have no internet access in all formal runs.

Two types of resource are separated:

1. **Matched resource envelope** determines the scientific treatment: candidate
   slots, visible items, feedback bytes, per-turn wall timeout, maximum rendered
   context, per-candidate batch input cap, derived trajectory input cap, target
   calls, and retry policy. These upper bounds are identical across researchers
   and matched controls. Actual context use may differ and is part of the policy
   outcome. Unused tokens do not carry across candidate slots.
2. **Accounting measurements** describe implementation cost: researcher tokens
   and dollars, reader input/output tokens, latency, GPU-seconds, peak HBM, KV
   capacity, prefix-cache state, and scheduler settings. They are recorded when
   observable but are not semantic-policy fitness variables.

Hard context limits use a frozen target tokenizer over the final rendered chat
request, including system prompt, query, chunk wrappers, separators, and chat
template. Each item also reserves the fixed maximum output allowance when
checking the endpoint context window. Provider-reported input tokens are
post-call cost and drift observations; they never enforce a pre-dispatch cap.

`pack-8K` and `pack-32K` name historical context-payload instruments.
`rendered-mean-8K` and `rendered-mean-32K` name elastic batch envelopes over the
complete input request. For a rendered mean tier `T`, `C_split = n × T` counts
input tokens only; output reserve enters only the per-item endpoint-window check.
The two token units are never compared as if interchangeable.

The historical fixed-8K allocation was executable and hashed by
`build_a2_pilot_plan`; the table records the revised fields that must replace it:

| Quantity                                 |                                                                   A2 value |
| ---------------------------------------- | -------------------------------------------------------------------------: |
| researchers × profiles × research seeds  |                                               `2 × 2 × 2` = 8 trajectories |
| candidate slots per trajectory           |                                                                          5 |
| hard researcher timeout per slot         |                                                              1,800 seconds |
| aggregate researcher wall ceiling        |                                             72,000 seconds across 40 turns |
| visible and gate items per profile/split |                                                                         40 |
| policy pack                              |    elastic per item up to qualified `Lmax`; batch cap frozen before launch |
| target calls, nominal full matrix        | historical fixed-8K projection 10,720; invalid until elastic re-projection |
| gate evaluations                         |                                              once per visible-selected arm |
| fixed-policy replay                      |                                5 repetitions in A2; 3 for key A3 artifacts |

The 20-hour aggregate ceiling is not a promise of equal API dollars: provider
pricing and token accounting differ. Dollar cost and researcher tokens are
reported as outcomes. A provider without auditable usage can run only in a
replication block. Before A2 launch, a host-specific `SpendCaps` artifact must
also freeze reader-token, GPU-second, total-wall, dollar, and retry caps; missing
or unobservable fields are explicit, never estimated. A2 remains blocked until
that artifact, task qualification, and formal isolation all pass.

The A3 starting matrix is `4 researchers × 4 profiles × 4 seeds × 10 slots`:
64 trajectories and 640 researcher turns. It is conditional, not automatic.
Its per-turn timeout remains 1,800 seconds, giving a five-hour maximum per
trajectory. Exact target-call and infrastructure caps are derived and frozen
from the qualified A2 throughput before A3; they are not chosen after outcomes.

## Task ladder

Length alone is not difficulty. Every fitness profile must be complete-evidence
solvable, non-parametric, non-saturated over the actual policy grammar, position
balanced, and causally dependent on its gold evidence.

| Phase | Purpose                                              | Tasks and status                                                                                                                                 | Search allowed?                     |
| ----- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------- |
| A0/T0 | harness, noise, causal, and difficulty qualification | 8K single-needle null; synthetic topology instruments; current hard-panel attempts are retained failures                                         | no researcher claim                 |
| A1    | realistic visible qualification                      | HELMET PopQA k1000, approximately 111K source tokens; fixed 8K cells remain noise and policy-sensitivity instruments                             | visible only                        |
| A2    | micro researcher screen                              | two elastic-context roles: real long-document evidence routing and causal multi-hop/global reasoning; exact `Lmax` and batch cap freeze after T0 | 2×2×2×5                             |
| A3    | paper-scale discovery/reliability                    | four qualified evidence profiles spanning sparse multi-hop, dense/global aggregation, retrieval under distractors, and verification/abstention   | 4×4×4×10                            |
| A3-L  | length and budget transfer                           | 32K/128K/256K source; report both fixed-budget instruments and frozen elastic `H`; vary one source or budget axis at a time                      | no new search first                 |
| A4    | offline trajectory transfer                          | official LongMemEval-V2 scoring plus full trace, last-k, lexical/hybrid, random, and state-grounded memory baselines                             | frozen `H`                          |
| A5    | live external validity                               | one preregistered tau²/SkillFlow-style task family with frozen host agent, matched retry budget, policy on/off                                   | no feedback into the benchmark loop |

Synthetic tasks are instruments, not the paper headline. RULER NIAH remains a
noise/saturation control. LongBench-v2 is a once-only public transfer set, not a
sealed split. The causal multi-hop profile should use auditable supporting facts
from MuSiQue, HotpotQA, or 2Wiki with target-tokenized distractors; it is not
eligible until answer deletion, gold-drop, gold-only, and counterfactual tests
pass. Dataset licenses and immutable revisions must enter `configs/registry.json`
before download or reporting.

The static-document track is primary because exact replay and one reader call
make the discovery–reliability gap identifiable. The long-horizon track is
mandatory for external validity but secondary: Recuris already demonstrates a
specific online memory-evolution method, and live environment variance and
retry effects make it a weaker place to identify researcher discovery.

## Baselines and fair comparisons

Every primary profile reports:

- H0, head, tail/head-tail, lexical/BM25, hand-written hybrid, and full context
  when it fits the endpoint and per-candidate batch envelope;
- elastic H0 requests the source up to `Lmax` with uniform item priorities; the
  evaluator's frozen batch allocator makes the request envelope-feasible, then
  H0 uses full source when its assigned payload fits and lexical selection
  otherwise; fixed-8K lexical remains a diagnostic rather than the primary H0;
- `pack-8K`/`pack-32K` policy instruments, maximum-use controls, and elastic
  policies that choose item-level length, including no-compression and
  near-full-context behavior when affordable;
- Random-5 and sequential Hamming-one search under the exact canonical grammar,
  H0, five slots, and byte-identical feedback;
- gold-aware exhaustive recall as a strong visible-gold non-agent control;
- GEPA/ACE-style optimization only after adapting it to the same policy
  representation and target-call budget;
- evaluator-only no-context, gold-only, bounded-oracle, gold-drop,
  counterfactual, and parametric-deletion instruments;
- Recuris-style state-grounded invocation and verified working state in the
  long-horizon block, with retries held constant.

The restricted and open-program arms answer different questions. A restricted
win shows better search/reasoning inside a matched policy class. An open-program
win that survives metamorphic and hidden-template transfer shows useful operator
invention. Their scores are never pooled.

## Outcomes and decision gates

The primary A2 estimand is paired isolated-gate score of the visible-selected
researcher policy minus the visible-selected matched control. The report also
contains:

- discovery over H0 and first valid attempt;
- last attempt, peak, historical-best, post-peak regression, and selection regret;
- manifest Brier score, log loss, ECE, and improve/regress precision-recall;
- accuracy or task success, pack/reader tokens, calls, latency, GPU-seconds,
  dollars, and cost per correct item;
- performance at the common hard envelope and the accuracy--actual-token Pareto
  frontier; lower token use is not rewarded inside the primary score unless a
  separately preregistered constrained-cost estimand says so;
- causal gold-drop/keep, counterfactual following, and parametric-answer deletion;
- transfer by length, position, topology, template, domain, reader, and horizon.

Fixed-budget instruments do not enter the primary elastic matched estimand. For
every selected elastic `H`, the evaluator additionally reports the same
selector/order logic with only its budget rule clamped to 8K and 32K, plus a
static baseline matched to the elastic policy's realized token consumption.
Each fixed-budget cell has its own envelope and interpretation.

The token-matched static baseline is mechanical: it freezes the lexical selector
and evidence order, then reuses the selected elastic `H`'s precommitted per-item
quota schedule. The evaluator never selects among multiple static baselines
after seeing gate outcomes.

Evidence-causality checks report two effects. The controlled direct effect
freezes the selected artifact's per-item quotas and schedule before gold
drop/keep. The total effect permits the frozen policy to reallocate after the
intervention. Neither silently substitutes for the other.

A2 does not launch unless both profiles pass the pre-registered difficulty and
causal thresholds, replay standard deviation is below 20% of the median
meaningful policy delta, all runtime identities and spend caps are committed,
and the scored policy worker has formal physical-isolation attestation. A3 does
not launch unless all eight A2 trajectories consume five slots, invalid rate is
at most 10%, retries are below 1%, cost accounting is complete, and at least one
pre-registered researcher-vs-control, retention, or calibration signal exceeds
the noise floor in the same direction across both seeds.

Historical-best is always reported but is not called self-improvement by itself.
It can preserve a submitted artifact without making the research trajectory
progressive. Gate outcomes never select a candidate, and sealed evaluation is
run once after every policy, researcher configuration, analysis script, and
claim threshold is frozen.

## Paper contribution and falsifiable branches

The intended venue is a benchmark/datasets track. The two contribution classes
are:

1. an auditable benchmark for context-policy research with isolated roles,
   matched policy/search budgets, replay noise, causal evidence instruments,
   predictive manifests, and sealed transfer; and
2. an empirical map of discovery, reliability, calibration, efficiency, and
   static-to-horizon transfer across coding researchers.

The project does not claim a new evolution operator, the first evolving context
or memory system, long-context SOTA, or strict RSI. A new method is justified
only after the benchmark reveals a reproducible bottleneck not repaired by
historical-best—for example calibrated stop/gate/rollback or verified reread—and
belongs in a subsequent method study.

Current evidence supports only that context-policy changes can move a frozen
reader beyond the locally measured replay floor on a tiny visible panel. It does
not yet establish researcher advantage, sealed transfer, a population-level
regression rate, official HELMET/LongMemEval performance, or long-horizon gain.

## Pre-launch revision — 2026-08-31

No A2 trajectory had run when this contract was revised. The original A2 used a
fixed 8,192-token cap for every policy. That design is retained only for matched
causal and replay instruments. The primary A2 now uses a matched elastic resource
envelope so that policy code can choose item-level length, compression, ordering,
and unused capacity while actual consumption is recorded.

This revision invalidates the current executable A2 hash. A2 remains blocked
until `PolicySpecV1`, matched Random/Sequential controls, contracts, call
projections, difficulty landscapes, and tests implement the elastic envelope;
the exact endpoint-qualified `Lmax`, per-candidate batch cap, and derived
trajectory cap must then be frozen and re-hashed before any researcher sees
scores. Each candidate must declare all item-level requested lengths before its
first reader call; the evaluator rejects the whole candidate if their sum
exceeds the batch cap.

The revision occurred after qualification-only fixed-8K observations, including
the Phase 13b PopQA contrast, but before formal A2 task identities, panels,
researchers, or the elastic envelope were frozen. Those observations cannot
select the formal envelope or count as confirmatory A2 evidence. Formal panels
must be independent and exclude the prior qualification items.

`Lmax` is the largest of the predeclared 32K/64K/128K rendered-input canaries
that passes request acceptance, reserve, truncation, and replay checks, capped by
the reader's registered limit. The mean batch tier is the largest of 8K or 32K
whose worst-case projected A2 input and dollar cost fit the host `SpendCaps`;
reader task scores do not enter either selection. For a split with `n` items,
`C_split = n × mean_batch_tier`. Every attempted canary/tier and the deterministic
selection outcome is retained, even when the study stops.

Before dispatch, each item supplies a desired rendered length and a positive,
dataset-agnostic priority. A frozen order-invariant weighted water-filling rule
subtracts fixed request overhead, allocates the remaining batch payload subject
to desired lengths and `Lmax`, and breaks exact ties by the item's public-input
digest. H0 and maximum-use controls use uniform priority. Allocation uses no
labels, scores, item order, or mutable policy state.

Fixed-8K replay is only an anchor. Every selected elastic artifact, maximum-use
control, and primary rendered-length stratum receives its own exact-byte replay
before its score can support discovery or retention.
