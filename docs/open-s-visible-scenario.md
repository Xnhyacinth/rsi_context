# Frozen open-S visible scenario (2026-09-01 selection-blind 8K)

Status: **qualification-only**. `rsi_launch_eligible=false`. Not A2, not official
HELMET, not researcher advantage until a matched `normal` arm exists on this
split.

This card freezes the live open-S admission cell. Do not retune the split,
envelope, loop, reader, scorer, or seed after launch. Prior window-envelope
cells remain locked artifacts; they are not this cell.

## Task

HELMET PopQA k1000 unique queries, gold passage rank ≥ 200, project-local
`extractive_span_match`. Source file key remains
`helmet-rag-popqa-k1000-to-8k` (the HELMET jsonl name). The pack envelope is
**selection-binding 8192**, so ranking can drop evidence.

## Scene

Long-document evidence routing for a frozen reader. The researcher edits an
isolated folder strategy system \(S\) (`policy/*.py`) so one frozen reader call
answers better. H0 is source-order packing under 8K. Search is
**selection-blind**: every proposal starts from the seed, later scores are
withheld, and historical-best is recorded only after all slots. This is the
open-loop sampling arm, not a claim that feedback accumulates.

Policy code may not invent unbound summary text, call the reader, use the
network, extra reader/LLM loops, or answer the question.

## Bindings

| Field | Value |
| ----- | ----- |
| Track | `open-s-harness-v1` |
| Seed | `seeds/open_s_v1/` (H0 = source-order full-as-fits) |
| Split | unique PopQA k1000, min gold rank 200, **offset 104** (does not overwrite 64/72/80/88/96) |
| n | 8 visible items |
| Rounds | 5 researcher slots after H0 |
| Pack envelope | **selection-binding 8192** |
| Reader | `tencent-copilot-hy3-ioa`, T=0, seed 42, 64 output tokens, 600s timeout |
| Researcher | `tencent-copilot-hy3-ioa-researcher`, T=0, seed 42, 32768 output tokens |
| Loop | `search_mode=selection-blind`, `lineage_rule=next-from-seed`, `feedback_schema=visible-score-cost-v1` |
| Verifier | `extractive_span_match` |
| Isolation | AST audit + fresh policy worker; not a container |
| Claims | no pooling with Qwen, A2, KV, or official leaderboards |

Each scored turn must change the policy tree relative to the seed. Identical
parent copies are invalid. A matched `normal` arm on this same split is
required before any iteration claim.

## Launch

```bash
uv run python scripts/autonomous_public_pilot.py \
  --output results/open-s-hy3-popqa-blind-8k-20260901 \
  --policy-track open-s \
  --initial-policy seeds/open_s_v1 \
  --reader-max-output-tokens 64
```

Defaults on `--policy-track open-s` bind offset 104, 8K pack, selection-blind,
and score-cost feedback.

## Completed (do not overwrite)

`results/open-s-hy3-popqa-blind-8k-20260901/`: H0 **0.375**; r0/r1/r2/r4
**0.750**; r3 invalid `promotion.decision`; `discovery_gain=0.375`; 40 reader
calls. All parents were the seed. Qualification-only. Open-loop sampling, not
an iteration claim. A matched `normal` arm on this split is still required.

## Prior locked cells (do not overwrite)

`results/open-s-hy3-popqa-fresh-20260901/` (offset 96, pack 114624, normal,
gold): H0 0.500; peak 0.625; `discovery_gain=0.125`. Qualification-only.
