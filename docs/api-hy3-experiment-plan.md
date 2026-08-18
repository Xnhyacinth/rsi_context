# Tencent `hy3-ioa` API track

## Decision

`hy3-ioa` is usable as a high-capability **API replication reader** for the
semantic `single_reader` track. It does not replace the pinned Qwen reader as
the sole paper backbone.

The distinction is scientific rather than cosmetic:

- the endpoint returns the requested model alias but no provider checkpoint or
  immutable revision;
- the service requires SSE streaming and may change behind the alias;
- evaluator-side KV, prefix-cache, GPU-second, HBM, tokenizer, batching, and
  scheduler controls are unavailable;
- private sealed documents must not be sent to the remote service without a
  separate data-governance decision.

The paper therefore uses two reader classes:

1. `M_open`: pinned Qwen checkpoint plus frozen vLLM stack; reproducibility and
   sealed claims anchor here.
2. `M_api`: `hy3-ioa`; high-capability replication, public transfer, and cheap
   pilot discovery after the gates below pass.

Do not pool their scores into one leaderboard. Report backbone interaction and
API limitations directly.

Tencent's public TokenHub documentation currently lists `hy3`, not the
`hy3-ioa` Copilot alias, with a 256K context window and OpenAI-compatible Chat
Completions. Those public specifications are not assumed to apply to this
endpoint. See:

- <https://cloud.tencent.com/document/product/1823/130051>
- <https://cloud.tencent.com/document/product/1823/130932>

## Core invariant

The experiment still changes only context policy `H`:

```text
researcher R -> policy/*.py + manifest.json
frozen evaluator -> H(document or trajectory, query, budget) -> ContextPack
frozen hy3-ioa reader -> answer -> fixed metric
```

The researcher does not answer benchmark questions. `H` cannot modify the API
endpoint, model alias, system prompt, temperature, seed, output cap, scorer, or
labels. The API is never used for evaluator judging in exact-match profiles.

Using `hy3-ioa` as both researcher and reader is a separate factorial variable,
not the default: researcher capability and reader capability must remain
identifiable.

## Completed protocol canary

The credential-free record is stored under ignored experiment artifacts at
`artifacts/api-canary/hy3-ioa-20260814-canary-02.json`.

| Field             | Observed value |
| ----------------- | -------------: |
| Repetitions       |              5 |
| Exact answers     |    5/5 `amber` |
| Returned model    |  5/5 `hy3-ioa` |
| Prompt tokens     |   65 every run |
| Completion tokens |    2 every run |
| Mean latency      |        1.817 s |
| Median latency    |        1.804 s |
| Latency range     |  1.563–2.057 s |
| Provider revision |    unavailable |

This passes connectivity and short-request stability only. It is not a model
quality result and does not establish long-context replay noise.

## Claim–evidence matrix

| Claim                                            | Required evidence                              | Workload                     | Baselines                                               | Primary metrics                                | Status  |
| ------------------------------------------------ | ---------------------------------------------- | ---------------------------- | ------------------------------------------------------- | ---------------------------------------------- | ------- |
| Research agents discover better context policies | matched-budget trajectories                    | RULER/HELMET/private visible | H0, hand hybrid, grid/random, GEPA/MCE adapters         | discovery gain, paired score delta, cost       | planned |
| Improvements survive continued research          | all post-peak rounds and fixed-artifact replay | same trajectories            | last, historical-best, gate selector                    | final-below-peak rate, regret, noise ratio     | planned |
| Gains come from evidence handling                | evaluator-only causal panels                   | multi-hop distractors        | full, gold-only/drop, no-context, counterfactual        | EM/F1 and causal score drop/recovery           | planned |
| Gains transfer across readers                    | freeze `H*`, change only reader                | public transfer              | Qwen `M_open`, `hy3-ioa` `M_api`                        | paired backbone interaction and CI             | planned |
| The same locus transfers to long horizon         | freeze/adapt only trajectory context policy    | LongMemEval-V2 offline       | full trace, last-k, lexical, hybrid, memory/compression | answer accuracy, state recall, stale rejection | planned |

No unknown result is implied by this table.

## Staged execution queue and stop rules

### A0 — API protocol and replay gate

Run short exact canaries before and after every campaign. Record profile hash,
requested/returned model, response IDs, usage, latency, temperature, seed, and
the missing provider revision.

Pass only if:

- every request returns `model=hy3-ioa`, one usage object, and `[DONE]`;
- exact answer and usage are stable in at least five repeats;
- no endpoint/profile field changed between pre/post records.

Any alias or usage drift invalidates the campaign batch rather than becoming
research noise.

### A1 — length and position gate

Use public synthetic evidence at 8K, 32K, and 128K, with the answer at the
front, middle, and tail. Repeat every fixed artifact three times. Run single
needle plus a dense aggregation item so retrieval saturation is visible.

Pass a length into RSI only when:

- request success is 100%;
- replay standard deviation is below 20% of the smallest meaningful policy
  difference;
- H0 and full-context are neither both saturated nor both at floor;
- endpoint-reported prompt plus completion tokens stay under the registered
  evaluation cap.

Do not infer `hy3-ioa` limits from the public `hy3` model card.

### A2 — micro RSI pilot

Start with 2 researchers × 2 evidence profiles × 2 research seeds × 5 rounds.
Use 40 visible and 40 gate items per profile. This is at most 1,600 visible
target calls before replay/gate accounting; record the exact realized count.

Required baselines under the same evaluator-call budget:

- head-tail truncation and lexical/BM25;
- frozen hand-written hybrid;
- finite random/grid search over the same policy surface;
- full context where it fits;
- historical-best as a selection rule, not a researcher.

Promote to the main matrix only if at least one non-saturated profile has a
between-round signal larger than replay noise and API quota/cost is auditable.

### A3 — main long-context matrix

Use the pre-registered 4 researchers × 4 evidence profiles × 4 seeds × 10-round
matrix. Keep item panels, round count, feedback, and selection rules identical
between `M_open` and `M_api`. Report API and open-reader results separately.

Primary profiles:

- RULER controlled length/needle and dense aggregation;
- HELMET exact-RAG/multi-hop;
- private counterfactual multi-hop visible/gate families;
- saturated 8K null zone for calibrated stopping.

One-pass public transfer and the isolated private sealed evaluation happen only
after policies and analysis are frozen. The remote API does not receive the
private sealed set unless explicitly approved.

### A4 — long-horizon bridge

Use LongMemEval-V2 as an offline trajectory corpus. The immutable history is the
source artifact; `H` may only select, compress through evaluator-owned
transforms, order, retain, or abstain under 32K/64K/128K budgets. The frozen
reader answers once.

Measure:

- answer accuracy and answer-bearing-state recall;
- stale-state rejection and premise abstention;
- old/new-state swap, supporting-state drop/keep, failure-only, and random
  trajectory controls;
- target input/output tokens, latency, API calls, and researcher cost;
- the same discovery, retention, calibration, selection-regret, and replay-noise
  metrics as the static track.

Only after freezing `H*`, run a small paired `H on/off` live MemoryArena-style
test with fixed host agent, tools, environment snapshot, seeds, and max steps.
Live success is external validity and never feeds back into policy search.
Terminal-Bench, OSWorld, and similar tasks remain later validation because they
confound context policy with planning, tools, recovery, and environment noise.

## Analysis and record contract

Every campaign directory must contain:

```text
run_spec.json                 # datasets, split, policy/profile hashes, budgets
api_canary.before.json        # no credentials
rounds/<round>/policy/        # immutable candidate source
rounds/<round>/manifest.json  # predicted improve/regress/unchanged
rounds/<round>/result.json    # per-item score/flip/usage/latency
selection.json                # last/dev-best/gate/oracle-hidden indices
replay.json                   # fixed-artifact repetitions and noise
causal.json                   # evaluator-only audit results
api_canary.after.json
analysis.json                 # CIs, regret, calibration, cost-normalized gain
```

Never record API keys, hidden questions, hidden labels, or item-level gate/sealed
scores. A provider/model/profile change starts a new experimental block; it is
not silently appended as another seed.

## Interpretation boundaries

- Better RULER/HELMET scores establish long-input context-policy improvement,
  not general long-horizon agency.
- Better LongMemEval-V2 results establish transfer to bounded context over
  historical trajectories, not online planning improvement.
- Only the frozen paired live test supports a limited external-validity claim
  about long-horizon task performance.
- If historical-best closes the gap, random search matches researchers, or no
  regression exceeds replay noise, those are valid benchmark findings rather
  than reasons to change the endpoint post hoc.
