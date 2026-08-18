# Preliminary RSI-Context qualification results — 2026-08-14

## Scope

These are visible-split qualification results, not sealed benchmark results.
They cover prescribed-policy controls, one remote-API researcher trajectory,
and one completed local-reader researcher trajectory. They use only two items
per dynamic profile (four items total), one researcher, and one seed. They do
not establish an agent advantage or authorize the main matrix.

Two frozen-reader blocks were exercised:

- Tencent Copilot `hy3-ioa`, temperature 0, seed 42, strict SSE and
  returned-model/usage validation. The provider exposes no immutable revision.
- Qwen3.6-27B revision
  `1b559cf7215ebe67ff10758e14f6293ba883223b`, served by vLLM 0.25.1 with
  temperature 0, seed 42, and thinking disabled for scored runs.

The local Qwen block is the current reproducibility anchor. All researcher runs
below remain `qualification_only=true`, `split=visible`, and
`formal_sealed_isolation=false`.

The two blocks are not a matched-reader comparison. The remote dynamic gate
used a task output cap of 16 tokens, followed by a 128-token confirmation, and
the provider profile cannot explicitly toggle thinking
(`chat_template_enable_thinking=null`). The scored local gate used a 512-token
cap and explicitly set `chat_template_enable_thinking=false`; its earlier
thinking-enabled preflight is reported separately as invalid.

## Are KV and inference-system variables RSI targets?

Not in the primary semantic track.

| Variable                             | Role in semantic RSI v1   | Optimized by researcher? | How reported                                        |
| ------------------------------------ | ------------------------- | ------------------------ | --------------------------------------------------- |
| selected/compressed/ordered evidence | primary policy `H`        | yes                      | score, evidence recall, tokens, flips               |
| KV eviction/allocation               | separate systems track    | no                       | EvolKV/KVPress-style appendix if run                |
| HBM capacity                         | feasibility constraint    | no                       | fixed profile and peak HBM on local reader          |
| GPU-seconds                          | cost denominator          | no                       | measured on local reader                            |
| prefix cache                         | possible confound         | no                       | disabled in golden runs; cold/warm appendix         |
| scheduler/batching                   | reproducibility variable  | no                       | frozen and recorded in runtime manifest             |
| API internals                        | unobserved provider state | no                       | token usage, calls, latency, alias/revision warning |

Jointly optimizing semantic `H`, KV, batching, and scheduler would make the
source of an improvement unidentifiable. The semantic and systems leaderboards
therefore remain separate.

## A0 — short protocol replay

Record:
`artifacts/api-canary/hy3-ioa-20260814-canary-02.json`

- 5/5 exact answers;
- 5/5 returned model aliases equal `hy3-ioa`;
- prompt/completion usage stable at 65/2 tokens;
- answer, model, and usage stable;
- mean latency 1.817 s;
- provider revision unavailable.

Conclusion: the endpoint and strict SSE adapter pass a short compatibility
gate. This does not establish long-context quality or provider immutability.

## A1 — length, position, and replay gate

Final record:
`artifacts/api-length/hy3-ioa-8k-32k-v3-20260814-01.json`

The final v3 generator uses deterministic RULER-style multi-word noise. Target
lengths were calibrated from endpoint-reported usage without consulting task
answers.

| Target | Needle position | Repeats | Accuracy | Score std | Actual input tokens | Usage span | Mean latency |
| -----: | --------------- | ------: | -------: | --------: | ------------------: | ---------: | -----------: |
|     8K | front           |       3 |    1.000 |     0.000 |               8,121 |          0 |      2.360 s |
|     8K | middle          |       3 |    1.000 |     0.000 |               8,121 |          0 |      2.406 s |
|     8K | tail            |       3 |    1.000 |     0.000 |               8,122 |          0 |      2.387 s |
|    32K | front           |       3 |    1.000 |     0.000 |              32,645 |          0 |      7.430 s |
|    32K | middle          |       3 |    1.000 |     0.000 |              32,645 |          0 |      4.887 s |
|    32K | tail            |       3 |    1.000 |     0.000 |              32,646 |          0 |      9.620 s |

Total for the final matrix: 18 calls, 366,900 input tokens, 126 output tokens,
and 87.271 recorded request-seconds.

The earlier v1 record is intentionally retained. Repeating one low-entropy word
caused 0/9 at 32K with copying and malformed output. Replacing it with
RULER-style noise restored 32K accuracy. This is a test-construction failure,
not evidence that the model improved. Retaining it demonstrates why benchmark
stimuli require controls rather than silent regeneration.

Conclusion: exact single needle is a zero-noise null zone at 8K/32K and is
useful for replay, position, and stopping calibration. It is saturated and must
not be the primary A2 fitness profile. The latency position pattern is
descriptive only at three repeats.

## Policy-locus qualification

Complete schema-v2 record:
`artifacts/api-policy-pilot/hy3-ioa-policy-pilot-20260814-02.json`

Each item has an approximately 32K source in the original generator's semantic
units, split into eight chunks, and an 8K semantic policy budget. These early
records predate target-tokenizer enforcement and are not length-calibrated A2
evidence. Only the needle chunk position changes.

| Policy               | Budget | Per-position scores (front/middle/tail) |  Mean | Reader input tokens | Wall time |
| -------------------- | -----: | --------------------------------------- | ----: | ------------------: | --------: |
| head truncation      |     8K | 1 / 0 / 0                               | 0.333 |              23,981 |   7.984 s |
| lexical              |     8K | 1 / 1 / 1                               | 1.000 |              24,005 |   7.252 s |
| tail truncation      |     8K | 0 / 0 / 1                               | 0.333 |              23,981 |   7.834 s |
| head-tail truncation |     8K | 1 / 0 / 1                               | 0.667 |              23,993 |   7.528 s |
| full context         |    32K | 1 / 1 / 1                               | 1.000 |              95,417 |  22.750 s |

For the prescribed head → lexical → tail qualification trajectory:

- discovery gain: +0.667;
- last-minus-peak: −0.667;
- final-below-peak: true;
- lexical replay: 3 repeats, mean 1.0, standard deviation 0.0;
- lexical achieves the full-context score with roughly one quarter of the input
  tokens in this controlled profile.

The complete record covers 24 reader calls, including nine replay calls:
263,392 input tokens, 145 output tokens, and 73.689 recorded seconds.

Conclusion: the context-policy locus can generate improvement and regression
well above the observed replay noise while holding the reader fixed. This
qualifies A2 infrastructure. It does **not** show that a research agent can
discover lexical retrieval, because the sequence was prescribed.

## Dynamic fixed-policy gate on the remote API

Records:

- `artifacts/api-dynamic-gate/hy3-ioa-dynamic-visible-20260814-01.json`
- `artifacts/api-dynamic-gate/hy3-ioa-dynamic-visible-20260814-02.json`
- `artifacts/api-dynamic-gate/hy3-ioa-dynamic-visible-20260814-03.json`
- `artifacts/api-dynamic-gate/hy3-ioa-dynamic-visible-128out-20260814-01.json`

The dynamic panel has two sparse multi-hop and two dense competing-value items.
Every source is nominally 32K in the original generator's semantic units;
bounded policies receive a nominal 8K. These early records predate target-
tokenizer enforcement. The three identical fixed-policy runs used the same
dataset fingerprint and profile hash.

| Policy       | Scores across three runs |  Mean | Population std | Gold recall |
| ------------ | ------------------------ | ----: | -------------: | ----------: |
| head-8k      | 0.75 / 0.75 / 0.75       | 0.750 |          0.000 |      0.5625 |
| head-tail-8k | 0.50 / 0.50 / 0.50       | 0.500 |          0.000 |      0.5625 |
| lexical-8k   | 0.25 / 0.50 / 0.25       | 0.333 |          0.118 |      0.5625 |
| full-32k     | 0.50 / 0.50 / 0.50       | 0.500 |          0.000 |      1.0000 |

These 48 calls consumed 737,928 input and 197 output tokens. Increasing the
output reserve from 16 to 128 reproduced the first run exactly (including 68
output tokens and all item scores), so the lexical fluctuation was not caused
by the original output cap. Full context retrieved every gold chunk but still
scored zero on both sparse items; gold recall is therefore not sufficient for
answer correctness in this panel. Head-8k also outscored full-32k, showing a
measurable context-composition effect rather than a monotone length benefit.

### Remote pseudo-discovery

The first autonomous remote trajectory is retained under
`results/autonomous-dynamic/codex-sol-visible-s0-20260814-01/`. Its observed
scores were H0 `0.00`, round 0 `0.25`, and round 1 `0.00`. However, replaying
the exact round-0 bytes five times produced `0.25 / 0 / 0 / 0 / 0` (mean 0.05,
population standard deviation 0.10, span 0.25) in
`round-00-replay-5.json`. The apparent +0.25 discovery gain is therefore no
larger than the observed replay span. Moreover, the round-0 to round-1 code diff
only reused a precomputed word set in place of recomputing the same set.

Conclusion: this remote run cannot support either discovery or regression.
Instead, it demonstrates the protocol's intended failure diagnosis: an
unversioned temperature-zero API can manufacture both a peak and a subsequent
drop. Remote API runs remain transfer/robustness blocks, not the primary noise
floor.

## Pinned local Qwen qualification

The scored profile is
`qwen3.6-27b-128k-bf16-h200x8`: Qwen3.6-27B at the pinned revision above,
vLLM 0.25.1, BF16 model and KV cache, TP8/DP1 across eight H200s, model length
131,072, chunked prefill enabled, prefix caching disabled, and serving seed 42.
The serving-profile hash is
`00182bf242e57f2168c3524e1bcdf59bb22cacccc0b54fd502d58ad8e87d1b8c`;
the non-thinking reader-profile hash is
`6b22e89479fe976c735e40f049031a339b4df6b67f4d6f29860bc1e28850ba2b`.

At server startup, vLLM reported 6.57 GiB of model memory per TP rank,
117.12 GiB of available KV memory per rank, a 7,598,612-token GPU KV cache, and
estimated 57.97-way concurrency at 131,072 tokens. These readings
were captured from qualification stdout, not yet a JSON runtime manifest; the
formal protocol must persist them rather than relying on prose.

### Thinking-mode preflight failure

`artifacts/local-dynamic-gate/qwen3.6-27b-32k-visible-20260814-01.json` is an
invalid scored preflight, retained diagnostically. With thinking enabled and a
512-token output cap, the 16 calls consumed 8,188 of 8,192 possible output
tokens. All policies scored zero except head-tail at 0.25 while reasoning nearly
exhausted the completion budget before a short exact answer. This
pattern is consistent with output truncation and is treated as a decoding
configuration failure, not evidence about context policy quality. All scored
local qualification runs therefore freeze thinking off.

### Non-thinking fixed policies

Records:

- `artifacts/local-dynamic-gate/qwen3.6-27b-32k-visible-nonthinking-20260814-01.json`
- `artifacts/local-dynamic-gate/qwen3.6-27b-32k-visible-nonthinking-20260814-02.json`
- `artifacts/local-dynamic-gate/qwen3.6-27b-32k-visible-nonthinking-20260814-03.json`

| Policy       | Scores across three runs | Population std | Sparse / dense score |
| ------------ | ------------------------ | -------------: | -------------------: |
| head-8k      | 0.75 / 0.75 / 0.75       |          0.000 |           0.50 / 1.0 |
| head-tail-8k | 0.50 / 0.50 / 0.50       |          0.000 |           0.50 / 0.5 |
| lexical-8k   | 0.50 / 0.50 / 0.50       |          0.000 |           0.00 / 1.0 |
| full-32k     | 0.50 / 0.50 / 0.50       |          0.000 |           0.00 / 1.0 |

All persisted item scores, input usage (248,982 tokens/run), and output usage
(56 tokens/run) were identical across the three runs. The schema-v2 fixed-gate
artifacts did not retain raw predictions, so prediction-level identity cannot be
independently reconstructed from those files. The 48 calls took 19.620
request-seconds in aggregate. This establishes a zero observed score replay floor
for this small panel and makes the 0.25 fixed-policy difference measurable. It
does not establish that the same floor holds at 128K or under concurrent scheduling.

## Autonomous local-reader micro-pilot

Three launch attempts are preserved rather than silently discarded:

1. `results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-01/`
   was rejected before evaluation. `PolicyAuditor` found a non-allowlisted
   `__future__` import, module-level compiled regex state, and forbidden dynamic
   `compile` calls.
2. `results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-02/`
   evaluated round 0, then rejected round 1 because the researcher ran mypy and
   left `.mypy_cache` in the workspace. The submission contract permits only
   `policy/` and `manifest.json`.
3. `results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-03/`
   completed two rounds with clean audited submissions and is the only local
   trajectory produced under the legacy selector.
4. `results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-04/`
   reran the same two-round protocol after seeding historical-best from H0 and
   adding exact prompt, researcher identity/process, prediction, and failure
   records. This is the current-protocol qualification trajectory.

The completed trajectory is at
`results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-03/`.
The coding researcher saw visible item failures and gold evidence, edited only
the policy surface, and did not answer items. The frozen reader made one call
per item.

| Artifact        | Observed score | Replay evidence         | Interpretation                      |
| --------------- | -------------: | ----------------------- | ----------------------------------- |
| H0 lexical seed |           0.25 | three replays, all 0.25 | stable starting point               |
| round 0         |           0.00 | five replays, all 0.00  | stable regression                   |
| round 1         |           0.50 | five replays, all 0.50  | stable +0.50 vs parent, +0.25 vs H0 |

The H0 replay record is
`results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-02/h0-replay-3.json`.
Round 0 used broad identifier-link expansion. Round 1 narrowed retrieval to a
governing statement, query-entity records, and one bounded relation hop. Its
five replays used 28,485 reader input tokens each, versus 35,727 for round 0,
and fixed both dense items while leaving the two sparse items incorrect. The
exact round-0 and round-1 candidate SHA-256 digests and every item prediction
are recorded in `round-00-replay-5.json` and `round-01-replay-5.json`.

This legacy run shows that its exact candidate policies are replayable, but it
is not used as autonomous-discovery evidence under the current protocol.

The `-03` campaign was produced before H0 was seeded into the campaign's
historical-best selector. Its summary therefore incorrectly marks the 0.00
round-0 candidate as promoted and told round 1 that the incumbent score was
0.00 rather than 0.25. Exact policy bytes, item scores, and replay conclusions
remain valid, but its promotion metadata is legacy qualification evidence. The
current runner initializes the incumbent from the persisted H0 evaluation;
formal trajectories must use the corrected protocol and new output paths.

The corrected `-04` run reproduced H0 `0.25` → round 0 `0.00` → round 1
`0.50`. The benchmark selector rejected round 0 against H0 and selected round

1. Exact-byte replay returned round 0=`0.00` for all five repeats and round
   1=`0.50` for all five repeats, with identical per-item predictions and token
   usage. The result now persists both researcher prompts and their SHA-256
   digests, the resolved Codex executable SHA-256, normalized process events and
   usage, baseline/candidate predictions, parent artifact IDs, and configured
   reader identity. This is provisional evidence that a coding researcher can produce a
   real, replayable context-policy improvement on visible data. It is not evidence
   that the agent beats matched search, transfers to unseen items, or retains a
   peak over a five- or ten-round search horizon.

The auditable summary and exact replays are
`results/autonomous-dynamic/codex-sol-local-qwen-visible-s0-20260814-04/pilot_summary.json`,
`round-00-replay-5.json`, and `round-01-replay-5.json` in the same directory.
The `-04` summary used the transitional trace schema and retained raw process
payloads; it was scanned without finding common credential patterns but must
remain local. Current schema v3 persists only event metadata, usage, byte counts,
and digests. A release artifact must be regenerated under v3.

### Manifest calibration

Calibration treats each item's outcome relative to its parent policy and uses
the manifest order `(improve, unchanged, regress)`. On only four items per
round, the corrected `-04` pre-evaluation probabilities give:

| Round | Observed outcomes                   | Claimed aggregate delta | Actual delta | Brier | Log loss |   ECE |
| ----: | ----------------------------------- | ----------------------: | -----------: | ----: | -------: | ----: |
|     0 | 0 improve / 3 unchanged / 1 regress |                   +0.59 |        -0.25 | 1.454 |    2.156 | 0.835 |
|     1 | 2 improve / 2 unchanged / 0 regress |                   +0.68 |        +0.50 | 1.212 |    1.832 | 0.615 |

The agent found a better round-1 policy but was poorly calibrated about which
items would change: it assigned high improvement probability to the two sparse
items that remained wrong and low improvement probability to one dense item
that flipped. Calibration is therefore a distinct benchmark outcome, not a
synonym for aggregate discovery.

## Target-tokenized hard-panel calibration

The v2 hard-panel qualification used a disposable visible seed, four items in
each of two profiles, the pinned Qwen tokenizer, a true 8,192-token policy cap,
and the same local Qwen/vLLM non-thinking reader. It made 56 single-reader calls.
The immutable record is
[`qwen-tokenized-disposable-v1.json`](../artifacts/hard-baseline-gate/qwen-tokenized-disposable-v1.json).

The generator's nominal 32,768 whitespace words were 53,517–53,720 Qwen tokens.
This falsifies the old assumption that semantic word counts were a hard context
budget; the runner now replaces every chunk count with evaluator-owned target-
tokenizer counts before policy assembly.

| Condition                           | Overall | Compositional | Dense | Mean gold recall |
| ----------------------------------- | ------: | ------------: | ----: | ---------------: |
| head, target-tokenized 8K           |   0.250 |         0.250 | 0.250 |            0.319 |
| head-tail, target-tokenized 8K      |   0.375 |         0.500 | 0.250 |            0.486 |
| lexical, target-tokenized 8K        |   0.875 |         1.000 | 0.750 |            1.000 |
| no context                          |   0.000 |         0.000 | 0.000 |            0.000 |
| gold only                           |   0.875 |         1.000 | 0.750 |            1.000 |
| bounded oracle, target-tokenized 8K |   0.875 |         1.000 | 0.750 |            1.000 |
| full context, unbudgeted diagnostic |   0.875 |         1.000 | 0.750 |            1.000 |

The pre-registered difficulty gate therefore fails without needing an RSI run:
compositional multi-hop is saturated by lexical retrieval, while dense global
comparison misses the required 0.80 bounded-oracle threshold. The latter's same
0.75 score under gold-only, bounded-oracle, lexical, and full context localizes
the failure to reader/task formulation rather than evidence selection. The
panel has a usable position-sensitive dynamic range—head and head-tail differ—
but is not yet an admissible A2 fitness set.

The scored block consumed 729,902 reader input tokens, 579 output tokens, and
21.55 seconds after server startup. vLLM reported a 7,598,612-token KV capacity,
zero prefix-cache hits, and prefix caching was disabled. These are frozen runtime
and cost observations, not semantic-policy optimization targets.

### Native target-token v3 follow-up

The second disposable qualification used the v3 generator and is stored in
[`qwen-v3-tokenized-disposable-v1.json`](../artifacts/hard-baseline-gate/qwen-v3-tokenized-disposable-v1.json).
It generated 32,730--32,750 actual Qwen tokens per source, with 19,197--19,347
semantic words, so the target-token claim is now native rather than post-hoc.
The run made 56 calls and consumed 575,890 input tokens, 532 output tokens, and
18.57 scored seconds after server startup.

| Condition                | Overall | Compositional | Dense | Mean gold recall |
| ------------------------ | ------: | ------------: | ----: | ---------------: |
| head 8K                  |   0.125 |         0.250 | 0.000 |            0.319 |
| head-tail 8K             |   0.250 |         0.500 | 0.000 |            0.583 |
| lexical 8K               |   0.125 |         0.000 | 0.250 |            0.667 |
| no context               |   0.000 |         0.000 | 0.000 |            0.000 |
| gold only                |   0.500 |         1.000 | 0.000 |            1.000 |
| bounded oracle 8K        |   0.500 |         1.000 | 0.000 |            1.000 |
| full context, unbudgeted |   0.625 |         1.000 | 0.250 |            1.000 |

The compositional repair succeeded as a difficulty profile: the oracle is
perfect, lexical no longer saturates, and positional policies disagree. The
dense repair failed more strongly than v2: complete bounded evidence still
scores zero. That localizes the next change to task wording/reasoning or reader
fit, not retrieval. A2 remains stopped. Schema v3 did not persist raw
predictions, which limited error diagnosis; schema v4 now records them for the
next disposable calibration.

### Dense-repaired v3b follow-up

The dense task was then replaced by a distributed authority comparison: one
cycle/seal rule and six candidate records are required, while each candidate
has higher-looking wrong-cycle and wrong-seal decoys. The new immutable record
is
[`qwen-v3b-tokenized-disposable-v1.json`](../artifacts/hard-baseline-gate/qwen-v3b-tokenized-disposable-v1.json)
(SHA-256 `bf1f732abb2ffdddb5878fbc12165da8493d86ccde49ff01e233a477c1c864c4`).
It used a new dataset fingerprint, generated 32,730--32,750 actual Qwen tokens,
and persisted every item prediction under schema v4.

| Condition                | Overall | Compositional | Dense | Mean gold recall |
| ------------------------ | ------: | ------------: | ----: | ---------------: |
| head 8K                  |   0.250 |         0.250 | 0.250 |            0.327 |
| head-tail 8K             |   0.500 |         0.500 | 0.500 |            0.619 |
| lexical 8K               |   0.375 |         0.000 | 0.750 |            0.631 |
| no context               |   0.000 |         0.000 | 0.000 |            0.000 |
| gold only                |   1.000 |         1.000 | 1.000 |            1.000 |
| bounded oracle 8K        |   1.000 |         1.000 | 1.000 |            1.000 |
| full context, unbudgeted |   1.000 |         1.000 | 1.000 |            1.000 |

The 56 calls consumed 572,420 reader input tokens, 539 output tokens, and 18.35
scored seconds. This repairs the reader/task floor and passes the available
complete-evidence, no-context, fixed-policy-range, and aggregate non-saturation
screens. The two strongest fixed policies, head-tail and lexical, disagree on
3/8 items (0.375), above the 0.20 threshold. It does **not** complete the
pre-registered difficulty gate: the disposable panel has only four items per
profile, gold-drop, counterfactual-following, and repeated-replay variance have
not yet been measured, and the current position strata are too small and
deterministic to establish balance. A2 therefore remains stopped pending those
instruments, executable matched controllers, and the locked hidden-item
evaluator.

### Full-grammar causal and replay screen

The next visible-only qualification scored all 32 restricted `PolicySpecV1`
configurations, then ran full-context, gold-drop, counterfactual-following, and
five exact repeats of the strongest policy. The immutable record is
[`qwen-v3b-causal-replay-disposable-v1.json`](../artifacts/hard-baseline-gate/qwen-v3b-causal-replay-disposable-v1.json)
(SHA-256 `a753e56390365c67c9bfdf8db216dcf46bd7579d7165ed908cbb95d887f22d08`).

All 344 target requests completed normally. They consumed 3,560,362 reader
input tokens, 3,302 output tokens, and 109.68 scored seconds. Full context
scored 1.0; deleting every gold chunk reduced it to 0; consistently rewriting
the answer in the query and gold evidence produced 1.0 counterfactual following.
The strongest policy replayed at `0.75 / 0.75 / 0.75 / 0.75 / 0.75`, giving
zero observed score variance.

The decisive result is a pre-registered difficulty failure. Eleven of the 32
policies score 1.0 on compositional multi-hop, whereas no non-oracle policy may
reach 0.90. Dense remains useful: its strongest policy scores 0.50. The two
strongest aggregate policies both score 0.75 but have identical item outcomes,
so strongest-policy disagreement is 0 rather than the required 0.20. The
strongest policy's profile-position strata are also all 0 or 1 on this
four-item-per-profile panel. Evidence causality and replay pass, but task
non-saturation and disagreement fail; A2 therefore remains stopped.

## What the project is trying to establish

The target claim is not “we built a better RAG policy” or “Hy3 has a long
context.” It is:

> Under a frozen reader and an auditable policy surface, can a coding research
> agent discover context policies that beat strong matched-budget controls,
> predict which items they will fix or break, retain the improvement after
> continued search, and transfer it to sealed documents and offline agent
> trajectories?

The corresponding contributions are:

1. a benchmark protocol that separates researcher, context policy, and reader;
2. replay noise and last-vs-peak reporting that identify discovery–retention
   failures without training variance;
3. calibrated flip manifests and evidence drop/keep/counterfactual instruments;
4. matched random/search/historical-best controls that can falsify the agent
   advantage;
5. a trajectory-context bridge that tests the same locus on LongMemEval-V2
   before any live-agent claim.

A null result remains useful: historical-best may close the gap, random search
may match researchers, or regression may disappear under deterministic
inference. Each outcome answers a process question that current method papers
usually hide.

## Decision after the preliminary run

Do not start A2 or spend next on a 128K matrix. The v3b calibration repairs the
reader-oracle floor and gives an aggregate fixed-policy dynamic range, but it
does not yet measure every causal, replay, and stratum gate needed for a formal
researcher comparison.

Priority order after this qualification:

1. replace the saturated compositional profile while retaining dense, then
   rerun the causal, counterfactual, replay, and larger-sample stratum gates;
2. rerun the complete 32-policy reader screen, not only three static baselines;
3. implement the runtime ledger and a policy-worker-owned
   physical isolation launcher; host-observed preflight cannot self-certify it;
4. only then complete A2 with 2 researchers × 2 profiles × 2 research seeds ×
   5 rounds, retaining invalid attempts and manifest calibration;
5. preflight 128K with the exact pinned tokenizer, reserving system/query/output
   overhead before generating source text; only then consider the registered
   262K serving profile for a 256K source condition;
6. run the implemented LongMemEval-V2 text-only offline compiler and add its
   official evaluator only after the static discovery/retention pipeline passes
   the gate.

One corrected-protocol visible infrastructure micro-pilot has completed; it is
not part of the pre-registered A2 factorial. No formal A2, sealed transfer, A3,
128K/256K dynamic, or long-horizon performance result is claimed yet.
