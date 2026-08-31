# hy3 PopQA operational replay — 2026-08-31

## Scope

This is a bounded, configuration-frozen black-box qualification block. It is
not a frozen-weight A2 run, a researcher trial, or evidence of RSI. The block
used the committed producer at `e23f84566a78e752a7e4f220942adeb68c0b0a8b`,
the `tencent-copilot-hy3-ioa` request profile, the lexical H0 policy, 40 fixed
HELMET PopQA k1000 items, an 8,192-token policy pack, five task replays, and
three pre/mid/post canary blocks. The immutable call cap was 209.

The source documents contained 95,387–132,550 canonical Qwen tokens (median
116,077.5). The result artifact is aggregate-only; it contains no item IDs,
predictions, or item-level scores.

## Immutable identities

- Contract SHA-256: `a3eb98fd0a97ff4f0860ec39bb73944ee211d95c63b3ae1990d7a5d8d2c960c2`
- Dataset fingerprint: `07f96c10b8f9fff7f7516480b443c4324b99092edf3d004c79a75dc71f1d3b23`
- Contract-file SHA-256: `3c2b822859ef00bcf6590d70b574b9c93563f78ee743e792f1fc8ac24f1808a2`
- Result-file SHA-256: `23cb05483f4023be803765ab966875d8c5c91b496767b034c3c85e6bc35271e7`
- Producer-attestation SHA-256: `147b289ed03fe1e2b5b0b9a4d455b024ee8d771e56dabb7fdbdde58f6d1e15da`

## Result

| Measurement                    |                       Observation |
| ------------------------------ | --------------------------------: |
| Reader calls                   |                         209 / 209 |
| Aggregate task scores          | 0.600, 0.600, 0.600, 0.600, 0.600 |
| Aggregate-score population SD  |                             0.000 |
| Items with a scorer-level flip |                            2 / 40 |
| Any-flip item rate             |                             0.050 |
| Wilson 95% upper bound         |                            0.1650 |
| Canonical canary correctness   |                             9 / 9 |
| Canary input-token stability   |                     pass (all 67) |
| Observed model-alias stability |                  pass (`hy3-ioa`) |
| Raw canary-answer stability    |                              fail |
| Output-token stability         |                              fail |
| Operational block              |                              fail |
| RSI launch eligible            |                             false |

The pre, mid, and post canary mean latencies were 1.788 s, 2.337 s, and
1.686 s. Their recorded completion timestamps span approximately 522.9 s.
That span includes task and anchor calls between the first and last records; it
is not a per-task latency estimate or a full-process wall-clock measurement.

## Interpretation

The stable aggregate score is a false deterministic signal. Two item-level
score trajectories changed while opposite changes cancelled in the aggregate.
An aggregate-only replay gate would therefore have accepted this reader block
incorrectly. Stable input-token usage and a stable model alias also did not
imply stable task behavior.

This block establishes non-zero evaluator noise for this fixed panel and time
block. It does not estimate a PopQA population noise rate, cross-time drift, or
hidden model revision. It also does not estimate a policy effect: only H0 was
run. No researcher-visible score or autonomous RSI loop may be launched from
this result.

## Next admissible experiment

The next API experiment must be a separately contracted diagnostic, not A2:
interleave H0 with fixed alternative policies under matched calls and randomized
order, retain repeated H0 anchors, and compare paired policy deltas with the
observed replay distribution. The meaningful delta and stopping rule must be
fixed before calls. LongMemEval-V2 and live long-horizon execution remain
frozen-policy transfer profiles until this signal-versus-noise condition and
the task-specific causal/difficulty gates pass.
