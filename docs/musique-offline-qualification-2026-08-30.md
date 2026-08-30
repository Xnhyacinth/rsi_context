# MuSiQue causal-profile offline qualification — 2026-08-30

## Claim level

This is a tokenizer-only, zero-reader-call qualification. It is not A2, an
official MuSiQue score, a researcher result, or evidence of long-context model
improvement. Raw aggregate artifacts remain ignored under `artifacts/public-t0/`.

The source is a third-party Hugging Face mirror pinned at revision
`763b65f844118a148e92bb88e7de5cb191b4c5dc`. The dev JSONL has 2,417 rows,
30,439,728 bytes, and SHA-256
`15fa63794d18a94ce12411aca6e2327e65b6e83b0b1490efab3f1962e48abf3b`.
It is qualification-only until its bytes are matched to the archive distributed
by the MuSiQue authors.

## Native-source rejection

The frozen Qwen3.6-27B tokenizer measured the native source distribution:

| Measurement                                        |                         Value |
| -------------------------------------------------- | ----------------------------: |
| Items                                              |                         2,417 |
| 2-hop / 3-hop / 4-hop                              |             1,252 / 760 / 405 |
| Source tokens, min / median / p95 / max            | 1,038 / 2,450 / 3,588 / 5,285 |
| Sources exceeding the 8,192-token pack             |                          0.0% |
| Final answer or alias in supporting paragraphs     |                        99.79% |
| Final answer or alias in non-supporting paragraphs |                        13.74% |
| All intermediate answers in supporting paragraphs  |                        99.96% |
| Any intermediate answer in non-support paragraphs  |                        44.81% |

Native MuSiQue is therefore rejected as an A2 long-context profile. It is not
pack-budget binding, and nontrivial subsets permit final- or intermediate-answer
retrieval from non-support evidence.

## Deterministic 32K construction

The long-source compiler keeps the target supporting paragraphs; discards
targets with native final- or intermediate-answer leakage; filters every
external paragraph containing the target final answer, aliases, or intermediate
answers; deduplicates paragraph text; and fills the source with cross-item
distractors. It controls gold placement on the compiled tokenizer axis and
remaps decomposition support indices after ordering. It does not call a model.

The 40-item qualification uses construction seed `20260830`, target length
32,768, and fixed pack budget 8,192. It balances front, middle, tail, and
distributed evidence at 10 items each, and cycles 2/3/4-hop targets. The strict
compiler skipped 111 candidates with native causal-answer leakage. The target,
position, and seed ledger is committed only as selection SHA-256
`ffc9ec05761abeeac103777c649285352b2d13b2610c137a4a56529d5e80bfbc`;
item identifiers and labels are not emitted.

The first packed artifact was retained as a superseded diagnostic. Paragraph-
level selection targeted 32,768 tokens, but whitespace-normalized compiled
chunks measured only 32,427–32,620. A test-first repair now verifies compiled
token totals and tops up distractors before returning a policy item.

The v2 artifact is also superseded because it checked only final-answer leakage,
trusted a caller-provided source-match boolean, did not attest tokenizer bytes,
and treated requested position labels as observed positions. Independent review
found these semantic gaps after the original static checks passed.

The strict v3 measurements are diagnostic until repeated from a clean commit:

| Measurement                                      |                             Value |
| ------------------------------------------------ | --------------------------------: |
| Items                                            |                                40 |
| 2-hop / 3-hop / 4-hop                            |                      14 / 13 / 13 |
| Front / middle / tail / distributed              |                 10 / 10 / 10 / 10 |
| Compiled source tokens, min / median / p95 / max | 32,768 / 32,812 / 32,924 / 32,996 |
| Sources exceeding the 8,192-token pack           |                            100.0% |
| Answer or alias in supporting chunks             |                            100.0% |
| Answer or alias in non-supporting chunks         |                              0.0% |
| All intermediate answers in supporting chunks    |                            100.0% |
| Any intermediate answer in non-support chunks    |                              0.0% |
| Requested positions matching token-axis strata   |                            100.0% |
| Duplicate target identifiers                     |                                 0 |
| Reader/API calls                                 |                                 0 |

The packed structure clears the implemented length, hop-diversity, support, and
lexical-leakage checks. Its artifact records `worktree_dirty=true`, so it cannot
serve as the final reproducibility artifact. The CLI now rejects dirty starts
and producer/source/tokenizer drift; a clean-commit rerun is required. Even that
rerun will remain **fail** until the mirror is byte-matched to the
author-distributed archive.

## Bugs found by real-data execution

1. Official decomposition IDs are integers, while the original fixture used
   strings. The adapter now accepts non-negative integer or non-empty string
   IDs and normalizes them to strings.
2. Paragraph-level token sums can exceed the compiled chunk sums because the
   chunker normalizes whitespace. The packer now checks the actual compiled
   total and adds answer-clean distractors until the target is met.
3. Final-answer-only leakage checks missed intermediate answers in 44.81% of
   native items. Packing and aggregate gates now check both classes.
4. A source-match boolean was not provenance. The gate now derives equality
   from source and official-member digests; this CLI cannot provide an official
   digest and therefore remains fail-closed.
5. A configurable tokenizer path could be mislabeled as the frozen tokenizer.
   The CLI now verifies exact tokenizer JSON/config bytes before counting.
6. Requested position labels were not observations. Every packed item is now
   checked against compiled target-token offsets.

These failures occurred before any reader call and now have regression tests.

## Remaining gates

- Byte-match the pinned mirror files against `musique_v1.0.zip` from the authors.
- Freeze visible/gate target identities and independent evaluator-only seeds.
- Add per-gold-hop drop/keep and counterfactual construction checks.
- Run the 40-item frozen-reader difficulty landscape, replay, and position
  strata under a qualified local runtime.
- Complete scored policy-worker physical-isolation attestation and spend caps.

Until those gates pass, no hy3 or local-reader researcher loop is authorized on
this profile.
