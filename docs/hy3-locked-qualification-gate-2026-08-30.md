# hy3 locked autonomous-RSI qualification gate — 2026-08-30

## Intended cell

This was a qualification-only, visible PopQA experiment. The preregistered
cell used eight real items, five autonomous researcher slots, an evaluator-owned
initial policy, and the pinned Qwen canonical token axis. It was not a matched
A2 comparison and could not estimate researcher advantage without Random-5 and
Sequential-5 controls or physical evaluator isolation.

The producer was commit
`a036c4a5bd6ec41ce43b25ec4573f8fdd53a8ac0`. Before any live call, the code
gate passed 543 tests with 84.03% branch coverage, Ruff, strict mypy over 167
files, targeted Bandit, and independent risk review with no remaining blocker
or high-severity finding.

## Pre-canary result

The frozen-client canary requested `hy3-ioa` five times with temperature 0 and
seed 42. The endpoint returned the requested model alias on all five calls, but
the preregistered freeze gate failed:

| Check                 | Observation                                                                                  | Result      |
| --------------------- | -------------------------------------------------------------------------------------------- | ----------- |
| Exact expected answer | At least one response differed                                                               | Fail        |
| Answer replay         | Two distinct answer forms                                                                    | Fail        |
| Usage replay          | Input tokens were always 67; output tokens were 2 or 3                                       | Fail        |
| Provider revision     | No immutable provider revision was exposed                                                   | Fail        |
| Runtime observability | Answer, token usage, latency, response ID, and response model were visible                   | Partial     |
| Systems observability | GPU-seconds, KV capacity, peak HBM, prefix-cache state, and scheduler state were unavailable | Unavailable |

The local raw-canary artifact produced by this run is
`results/autonomous-dynamic/hy3-locked-popqa-20260830/pre-canary.json`, with
SHA-256
`35975a714fc79317f47afe98c5721c8a9dfd545dbf1c356a62f895fdca02ec7d`.
The result directory remains ignored because it can contain evaluator runtime
artifacts; the digest and aggregate result are the committed evidence.

## Gate decision and accounting

The five-round RSI campaign was not launched. Therefore the attempted calls in
this block were exactly the five pre-canary calls: zero main-reader calls, zero
researcher calls, and zero candidate-policy evaluations. A post-canary was not
applicable because no experiment ran.

This stop is the intended behavior of the protocol. Fixed client parameters do
not make a black-box alias a frozen reader when output replay varies and the
served revision is unobservable. Under this condition, a policy score change
cannot be separated from reader drift, so neither improvement nor regression
would be attributable to autonomous context-policy research.

The result is evidence about endpoint qualification only. It is not evidence
that a coding researcher can or cannot discover a useful policy, and it is not
a PopQA policy result.

## Consequence for the study

The primary discovery and reliability estimands must use a pinned local reader
whose weights, tokenizer, serving configuration, decoding, and replay floor are
attested. The hy3 alias may remain a separately labeled external-replication
reader or a researcher, but it cannot currently replace that primary reader.
The next executable step is the pinned-local-reader qualification; hy3 should
only be retried in a separately preregistered replication block, not repeatedly
probed until a favorable canary appears.
