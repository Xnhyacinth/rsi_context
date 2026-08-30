# LongMemEval-V2 offline qualification — 2026-08-30

## Claim boundary

This is a real-data, aggregate-only qualification of the pinned LongMemEval-V2
small text track. It is not an official benchmark score, an A4 transfer result,
or evidence that an RSI researcher improved a policy. It made zero reader and
auxiliary model calls and emitted no item identifiers, answers, labels, or item
scores.

The purpose is narrower: establish that the offline trajectory source is
genuinely long under the frozen reader tokenizer, preserve the released task
semantics, separate deterministic and weak evaluators, and decide whether a
frozen-reader policy experiment is technically and scientifically eligible.

## Frozen inputs

- Producer Git revision:
  `122b19cdc57dbb6fefce0c87a26a3661f0a79269`
- LongMemEval-V2 data revision:
  `f152293e235517d504809563c833d7190b8c713b`
- Frozen tokenizer:
  `Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b`
- Tokenizer manifest digest:
  `8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290`
- Consumed files: released `questions.jsonl`, `trajectories.jsonl`, and
  `haystacks/lme_v2_small.json`; every observed SHA-256 matched the pinned
  released value.

The faithful text renderer retains trajectory domain, environment, goal,
outcome, and start URL, plus every state's step, URL, action, thought, and
accessibility tree. Screenshots and image questions are excluded from this
text-only profile.

## Aggregate result

| Measurement                             |                                    Observed value |
| --------------------------------------- | ------------------------------------------------: |
| Text-only questions                     |                                               422 |
| Excluded image questions                |                                                29 |
| Deterministic-evaluator questions       |                                               294 |
| Weak LLM-abstention questions           |                                               128 |
| Unique shared trajectory artifacts      |                                                 2 |
| Trajectories per question               |                                               100 |
| Source tokens, min / median / p95 / max | 25,665,918 / 25,665,918 / 26,347,607 / 26,347,607 |
| States, min / median / p95 / max        |                     1,737 / 1,737 / 3,358 / 3,358 |
| Sources beyond 32K / 128K / 256K        |                                100% / 100% / 100% |
| Largest atomic chunk                    |                                    127,192 tokens |
| Reader / auxiliary calls                |                                             0 / 0 |
| Qualification verdict                   |                                              pass |

The evaluator-family distribution is 68 `mc_choice_match`, 1
`mc_choice_set_match`, 199 `norm_phrase_set_match`, 26 ordered phrase-set, and
128 `llm_abstention_checker` questions. The first four families form the
deterministic primary stratum. The LLM-abstention stratum must remain a separate
weak-evaluation result.

## Replay

The full qualification was executed twice from the same clean commit. The two
JSON reports are byte-identical and each has SHA-256
`1f20123d438a3a6fccd8968d33448202ab7251746cb2bf42f86bcd12909d6518`.
This establishes zero observed replay variance for data compilation and
aggregate length measurement. It does not establish the reader/API replay
floor, which requires repeated frozen-reader calls.

Raw reports remain ignored under `artifacts/public-t0/`.

## Scientific interpretation

The track is decisively non-toy in source length and memory structure. A policy
must reduce roughly 25–26 million source tokens and 100 historical trajectories
to a bounded reader request. It therefore tests trajectory selection,
compression, ordering, provenance retention, and stale/relevant-state handling
on genuine interaction histories.

However, the 422 questions reuse only two independent history artifacts. The
unit of uncertainty is therefore not 422 independent memories. Later
confidence intervals must cluster by shared history and question family; this
track is best treated as an offline transfer bridge, not the sole primary RSI
fitness environment.

The 127,192-token maximum state also blocks a naive whole-state implementation.
It cannot enter a 32K or 64K pack, and it leaves inadequate room for query,
instructions, chunk wrappers, and chat template at a nominal 128K limit.
Silently skipping it would confound selection quality with chunk granularity.

## Gates before a frozen-reader baseline

1. Define a deterministic intra-state splitter with byte/span provenance and a
   preregistered maximum atomic size. Do not label a lossy renderer `full-trace`.
2. Retokenize the final rendered request, including chunk identifiers,
   separators, query, instructions, and chat template; fail closed on the exact
   reader context limit.
3. Isolate the reader worker so it receives only query, context pack, and an
   opaque invocation ID. Dataset objects, question IDs, evaluator functions,
   and answers remain evaluator-only.
4. Integrate the pinned official deterministic scorers for the 294-item primary
   stratum. Report the 128 weak-judge items separately.
5. Run matched truncation/recency, lexical retrieval, deterministic random
   search, and the frozen hand-hybrid at identical rendered budgets and call
   counts. Repeat unchanged-policy reader calls before claiming policy deltas.
6. Use LongMemEval-V2 for frozen-policy transfer after discovery on the
   low-noise static causal track. Do not optimize and report on the same shared
   histories as if they were an independent sealed test.

Live long-horizon validity remains a later, separate policy-on/off transfer with
frozen tools, action policy, skills, state kernel, and evaluator. This offline
qualification neither replaces nor pre-validates that experiment.
