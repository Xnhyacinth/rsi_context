# hy3 paired context-policy signal diagnostic — 2026-08-31

## Scope

This is the completed evaluator-only experiment preregistered in
`hy3-paired-signal-diagnostic-preregistration.md`. It compares a fixed lexical
context policy with fixed whole-chunk head truncation on 40 HELMET PopQA k1000
items. Source documents contain 95,387–132,550 canonical Qwen tokens (median
116,077.5), while both policies receive the same 8,192-token construction
budget and the same `hy3-ioa` reader request profile.

The run used three randomized, interleaved repetitions per policy and three
pre/mid/post canaries, for exactly 240 task calls and 249 total reader calls.
There were no retries, extensions, researcher calls, or post-outcome threshold
changes. This is not autonomous RSI, a frozen-weight claim, or a formal A2 run.

## Immutable evidence

- Producer revision: `cf19dffb4b328d5d8f37f76efdc5964a1651f881`
- Contract identity SHA-256:
  `7fad5684d5a61dc11a6a5ba795c9792bfc8760e3779fe87b60bd23b0f5e8da28`
- Contract-file SHA-256:
  `eea82ca5942f4788fcd1dfb8d76300843371e0af2d7983e445b99cb1e97e5739`
- Result-file SHA-256:
  `d5cc1735b07436bef05ae1506886e95a1a3503493a2c452109f919e595367a14`
- Producer-attestation SHA-256:
  `1bcd49a8dcaa119186765e96ce52ec0c122e3be16a4bbdcf81158dcd8356e855`
- Evaluator-private ledger SHA-256:
  `22c9b54170c57dc2ef733520ea8b4260c2b9d3665721d0514afe4dcd82c02c4e`

The public artifact is aggregate-only. The per-call ledger remains outside the
repository in a mode-0700 directory as a mode-0600 file; only its digest was
checked against the public result. This is trusted-host separation, not the
different-UID or mount-namespace isolation required for formal RSI.

## Result

| Measurement                  |               Lexical |       Head truncation |
| ---------------------------- | --------------------: | --------------------: |
| Mean score                   |                 0.600 |                 0.325 |
| Repetition scores            | 0.600 / 0.575 / 0.625 | 0.325 / 0.350 / 0.300 |
| Unstable items               |                2 / 40 |                4 / 40 |
| Unstable-item rate           |                 0.050 |                 0.100 |
| Pairwise replay disagreement |                0.0333 |                0.0667 |
| Mean latency per task call   |               2.548 s |               2.544 s |
| Total API input tokens       |             1,045,977 |             1,031,631 |
| Total API output tokens      |                   858 |                 1,033 |

| Paired decision quantity            |              Observation |                  Required |
| ----------------------------------- | -----------------------: | ------------------------: |
| Lexical minus head mean contrast    |                   +0.275 |           at least +0.200 |
| Three repetition contrasts          | +0.275 / +0.225 / +0.325 |        each above +0.1650 |
| Paired bootstrap 95% interval       |           [0.125, 0.425] | lower bound above +0.1650 |
| Lexical-better / head-better / tied |              12 / 1 / 27 |                  reported |
| Exact two-sided McNemar p-value     |            0.00341796875 |              at most 0.05 |
| Worst-case unstable-item contrast   |                   +0.100 |             above +0.1650 |
| Semantic canaries                   |                    9 / 9 |                     9 / 9 |
| Task input usage / model alias      |          stable / stable |               both stable |
| Output usage                        |                 unstable |           diagnostic only |
| Qualification decision              |                 **fail** |       all gates must pass |
| RSI launch eligible                 |                **false** |               fixed false |

The two task arms used 2,077,608 API input tokens and 1,891 output tokens in
total. Their recorded task-call latency sums to 611.0 seconds; the nine
canaries add 16.4 seconds. These are sums of per-call observations, not billed
cost, GPU-seconds, KV-cache use, HBM use, or end-to-end process wall time. The
black-box endpoint does not expose those physical-system quantities.

## Interpretation

The fixed panel contains a large observed lexical-versus-head policy contrast.
Moving from head truncation to lexical evidence allocation changed majority
accuracy by 27.5 percentage points with nearly identical mean reader latency.
This supports sensitivity to the two tested context-allocation policies. It
does not establish improvement headroom above lexical H0 or non-saturation
across the full policy grammar. No experimenter-side weight update occurred;
the provider's hidden weights and revision were not attested.

The stronger claim needed for iterative RSI did not pass. The bootstrap lower
bound remains below the prior replay-noise sensitivity bound, and the
precommitted adversarial treatment of every unstable item reduces the contrast
to 10 points. A significant McNemar test does not repair that failure because
it measures the fixed-panel paired outcome, not uncertainty caused by repeated
black-box reader variation.

This separation is itself the useful result: there is measurable sensitivity
to the two tested policies, but the present 40-item black-box block cannot yet
attribute smaller round-to-round changes or regressions to a researcher rather
than replay instability. Starting a five-round researcher loop now would
produce an RSI curve whose causal interpretation is weaker than the fixed-policy
contrast evidence.

## Next admissible step

Do not rerun this panel, relax the threshold, or launch A2. A subsequent API
experiment should be independently preregistered on unseen PopQA items, with a
sample size chosen for a replay-aware lower bound and an instability sensitivity
rule fixed before calls. Only a passing held-out signal block may authorize the
evaluator-side causal/static landscape. Physical evaluator isolation,
task-specific causal qualification, spend caps, and matched Random-5 versus
Sequential-5 accounting remain separate launch gates before any coding
researcher sees scores.

LongMemEval-V2 work may continue now only as download, compilation, policy
packing, or other analysis with zero reader calls. A hy3-scored frozen-policy
transfer requires its own preregistered qualification-only block and cannot
bypass this failed discovery-signal gate. A live long-horizon researcher loop
remains out of scope until it has its own frozen environment, bounded editable
harness, replay floor, and matched search controls.
