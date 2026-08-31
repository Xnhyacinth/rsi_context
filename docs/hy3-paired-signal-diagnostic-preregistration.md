# hy3 paired signal-to-noise diagnostic preregistration

## Question and status

Can a fixed semantic context-policy contrast produce a paired task effect that
is distinguishable from the scorer-level replay noise observed in the
2026-08-31 hy3 PopQA H0 block? This is an evaluator-only diagnostic. It is not
an autonomous researcher run, a formal A2 launch gate, or an assertion that the
provider's hidden weights are frozen.

The prior block is fixed by result-file SHA-256
`23cb05483f4023be803765ab966875d8c5c91b496767b034c3c85e6bc35271e7`,
contract SHA-256
`a3eb98fd0a97ff4f0860ec39bb73944ee211d95c63b3ae1990d7a5d8d2c960c2`,
an observed any-flip item rate of 0.05, and a Wilson 95% upper bound of
0.1650387736914096.

## Fixed panel and policies

- Dataset: the same first 40 unique HELMET PopQA k1000 questions with minimum
  gold-passage rank 200.
- Source/token axis: the same pinned HELMET source and Qwen tokenizer snapshot.
- Reader request profile: `tencent-copilot-hy3-ioa`, temperature 0, seed 42,
  64 output tokens, and an 8,192-token context-policy budget.
- Reference H0: `LexicalPolicy`.
- Fixed comparator: whole-chunk head truncation. The comparator was selected
  from the preregistered static baselines because the offline pack landscape
  predicts a large evidence-allocation contrast; no comparator hy3 score has
  been observed on this 40-item panel.
- Task scorer: `extractive_span_match`.

## Schedule and budget

Each policy is evaluated three times on every item. For every repetition, item
order is shuffled; for every item, the two policy calls are shuffled. The
schedule is generated once from seed 1729 and its digest is stored in the
contract. A mid-canary block occurs after exactly 120 of 240 task calls.
Pre/mid/post canaries contain three calls each. The immutable total cap is
249 target-reader calls. Calls are sequential; there are no retries or
after-the-fact extensions.

## Primary estimand and fixed thresholds

For each policy and item, the three binary scorer outcomes are reduced by
majority vote. The primary estimand is the mean paired majority-score contrast
`lexical - head` over the fixed 40-item panel.

The diagnostic identifies a policy signal above the prior bounded-block noise
margin only if all conditions hold:

1. the paired mean contrast is at least 0.20 in the preregistered direction;
2. the minimum of the three repetition-level aggregate contrasts exceeds the
   prior 0.1650 sensitivity bound;
3. the deterministic 10,000-resample paired item bootstrap 95% interval has a
   lower bound greater than the prior 0.1650 sensitivity bound;
4. the exact two-sided McNemar/binomial test on discordant majority outcomes is
   at most 0.05;
5. for each policy, an item is unstable when its three scorer outcomes are not
   all equal; both lexical and head unstable-item rates must be at most 0.10;
6. a worst-case sensitivity contrast, formed by replacing the majority-vote
   contrast of every item unstable under either policy with -1, exceeds the
   prior 0.1650 sensitivity bound;
7. all canonical canaries pass, task input usage is stable within every
   item-policy cell, and the observed model alias matches the contract.

Bootstrap seed is 20260831. Equality at a threshold passes only where stated
with “at least” or “at most.” The exact result, not a rounded display value, is
used by the evaluator.

## Outputs and interpretation

The public result is aggregate-only: per-policy repetition scores, paired
effect and interval, discordant counts and exact p-value, unstable-item
counts/rates/Wilson bounds, worst-case sensitivity contrast, token/latency
totals, canary summaries, private-ledger digest, and failure reasons. Item IDs,
predictions, schedules, and item-level outcomes are saved in an immutable
evaluator-private ledger under a separate repo-external directory. This
diagnostic runs without a researcher process and never copies that ledger into
the public result bundle. Directory separation and mode checks do not prove a
different-UID or mount-namespace boundary, so this remains trusted-host
evaluator evidence; it cannot satisfy the physical-isolation gate for RSI.

The schedule uses Python's `random.Random` MT19937 implementation and the
algorithm fixed in the contracted producer: for each repetition it shuffles
the zero-based input item indices, then independently shuffles policy IDs
`[0, 1]` for each adjacent item pair. The input item order and resulting
schedule digest are bound in a contract persisted before the first API call.
Any transport, parse, scorer, or persistence failure invalidates the whole
block. A valid block must contain exactly 249 attempted and completed target
calls and 240 valid task outcomes; missing outcomes are never scored as zero.

A pass means that this fixed-panel baseline contrast clears the current
bounded-block noise margin under the preregistered conservative sensitivity
analysis. It permits implementation of the evaluator-only
causal/static landscape. It does not make hy3 a frozen-weight reader and does
not set `rsi_launch_eligible=true`. A failure keeps autonomous RSI and live
long-horizon reader experiments blocked.
