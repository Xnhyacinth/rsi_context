# LongMemEval-V2 medium offline profile — 2026-08-31

## Claim boundary

This is an aggregate-only stress profile of the pinned LongMemEval-V2 medium
text track. It is not a passing qualification, an official benchmark score, an
A4 transfer result, or evidence that a researcher improved a policy. It made
zero reader and auxiliary calls and emitted no item identifiers, labels, or
item scores.

The existing qualification gate is preregistered for the small 100-trajectory
tier. The medium run therefore had to return `passed=false`; changing that gate
after seeing the measurements would have changed the experiment.

## Frozen inputs and artifact

- Producer Git revision:
  `108956e25a1df7072e16f1e74fe49d2713af501d`
- LongMemEval-V2 data revision:
  `f152293e235517d504809563c833d7190b8c713b`
- Frozen tokenizer:
  `Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b`
- Tokenizer manifest digest:
  `8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290`
- Aggregate artifact SHA-256:
  `d3cdea4b6de7b07aafab3bccebca7577f7e560d2b33f90968bdc8cf8295f48c4`

The consumed question, trajectory, and medium-haystack hashes all matched the
pinned release. The artifact remains ignored under `artifacts/public-t0/`.

## Aggregate result

| Measurement                             |                                      Observed value |
| --------------------------------------- | --------------------------------------------------: |
| Text-only questions                     |                                                 422 |
| Deterministic / weak-judge questions    |                                           294 / 128 |
| Unique trajectory artifacts             |                                                 419 |
| Trajectories per question, min / max    |                                           387 / 500 |
| Source tokens, min / median / p95 / max | 35,537,984 / 98,749,552 / 150,073,538 / 157,819,509 |
| States, min / median / p95 / max        |                   5,000 / 7,605.5 / 24,074 / 24,156 |
| Sources beyond 32K / 128K / 256K        |                                  100% / 100% / 100% |
| Largest atomic chunk                    |                                      135,980 tokens |
| Reader / auxiliary calls                |                                               0 / 0 |
| Qualification verdict                   |       expected fail: primary gate is the small tier |

The three recorded failures are exactly the tier-bound conditions: primary
qualification requires `small`, the released manifest differs from the small
manifest, and medium does not contain exactly 100 trajectories per question.
No source, tokenizer, producer, schema, or evaluator-family check failed.

## Loader feasibility repair

The first medium attempt exposed a computational defect rather than a data
failure. The small release has two unique haystacks, while medium has 447 across
all questions. The old loader tokenized every trajectory again for every
distinct haystack. After almost three hours it had reached about 30 GB RSS and
had not completed.

Commit `108956e` caches immutable rendered text and token counts by trajectory
inside one loader invocation. Artifact-specific document IDs and offsets are
still rebuilt independently. A failing overlap test observed ten tokenizer
calls before the repair and five unique-block calls afterward. The final suite
passed 589 tests with 83.60% branch coverage; Ruff and strict mypy passed,
Bandit found no issue in the changed source, and independent review found no
must-fix. The clean medium run then completed in roughly nine minutes with
about 4 GB RSS near completion.

This is a behavior-preserving data-pipeline optimization, not an RSI policy
improvement and not part of any model-score comparison.

## Scientific interpretation

Medium is substantially harder than a nominal 128K or 256K document task. The
policy must map tens to more than one hundred million source tokens and hundreds
of trajectories into a bounded rendered request. Its 419 unique histories also
remove the small tier's two-history concentration as the sole transfer setting.

The 135,980-token maximum atomic state proves that trajectory-level selection
alone is insufficient. The transfer compiler needs deterministic intra-state
splitting with source-span provenance before it can compare full trace, recency,
lexical, hybrid, or evolved policies at 32K/64K/128K rendered limits.

Medium remains a frozen-policy transfer profile. Optimizing on these same 422
questions and then reporting their score would mix discovery with test-set
adaptation. Autonomous policy discovery should first use qualified visible
long-document routing and causally annotated multi-hop profiles, with medium
receiving zero policy updates.

## Next executable gates

1. Implement and test deterministic intra-state splitting and complete rendered
   chat-token accounting.
2. Freeze the 294-item deterministic scorer stratum; report the 128 weak-judge
   items separately.
3. Qualify full-trace-when-feasible, 32K/64K/128K recency, lexical, hybrid, and
   random controls under the same reader-call and rendered-token envelopes.
4. Measure reader A/A replay before interpreting any policy delta.
5. Transfer only a policy selected without medium evaluation feedback; use a
   matched frozen-policy retry for later live long-horizon validation.
