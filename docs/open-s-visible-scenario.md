# Frozen open-S visible scenario (2026-09-01 window envelope)

Status: **qualification-only**. `rsi_launch_eligible=false`. Not A2, not official
HELMET, not researcher advantage until a matched control exists.

This card freezes the live open-S exploration task. Do not retune the split,
envelope, reader, scorer, or seed after launch. Historical 8K landscape and the
failed 8K dual-role campaign remain locked artifacts; they are not this cell.

## Task

HELMET PopQA k1000 unique queries, gold passage rank ≥ 200, project-local
`extractive_span_match`. Source file key remains
`helmet-rag-popqa-k1000-to-8k` (the HELMET jsonl name). The **pack envelope is
not 8K**.

## Scene

Long-document evidence routing for a frozen long-context reader. The researcher
edits an isolated folder strategy system \(S\) (`policy/*.py`) so one frozen
reader call answers better. Legal strategies share the same envelope:

- long-context full-as-fits (source order up to the window)
- retrieve / RAG selection
- truncation
- reorder / hybrid rank-then-pack
- in-item working memory

Policy code may not invent unbound summary text, call the reader, use the
network, or answer the question.

## Bindings

| Field | Value |
| ----- | ----- |
| Track | `open-s-harness-v1` |
| Seed | `seeds/open_s_v1/` (byte-identical H0) |
| Split | unique PopQA k1000, min gold rank 200, **offset 64** (skips locked 40-item diagnostic and the failed 8-item 8K campaign) |
| n | 8 visible items |
| Rounds | 5 researcher slots after H0 |
| Pack envelope | reader window − output − 2048 template reserve (hy3: 131072 − 64 − 2048 = **128960**) |
| Reader | `tencent-copilot-hy3-ioa`, T=0, seed 42, 64 output tokens, 600s timeout |
| Researcher | `tencent-copilot-hy3-ioa-researcher`, T=0, seed 42, 32768 output tokens |
| Verifier | `extractive_span_match` |
| Isolation | AST audit + fresh policy worker; not a container |
| Claims | no pooling with Qwen, A2, KV, or official leaderboards |

Items longer than the window still require selection. Unused tokens do not
carry. Each scored turn must change the policy tree; identical parent copies
are invalid.

## Launch

```bash
uv run python scripts/autonomous_public_pilot.py \
  --output results/open-s-hy3-popqa-window-20260901 \
  --policy-track open-s \
  --initial-policy seeds/open_s_v1 \
  --reader-max-output-tokens 64
```

Defaults on `--policy-track open-s` already bind offset, n, rounds, and the
window pack budget. Do not pass `--pack-tokens 8192`.
