# hy3 visible open-S analysis — 2026-09-01

Status: qualification-only. `rsi_launch_eligible=false`. Not A2, not official
HELMET or LongMemEval scores, not researcher advantage, not live tau²/SkillFlow.

## Review: fairness, completeness, determinism

The loop under test is isolated `policy/` + frozen H0 + frozen hy3 reader +
deterministic string scorer. hy3-ioa is an unversioned alias occupying two
roles with different profiles. It is not the paper's pinned Qwen reader.

| Condition | Binding |
| --------- | ------- |
| Split | HELMET PopQA k1000 unique queries, gold rank ≥ 200; **skip the locked first 40** from the 2026-08-31 paired diagnostic |
| Envelope | **Blocks A–C:** 8,192 policy tokens (locked). **Block D / live open-S:** reader window minus output and template reserve (hy3 pack 128960) |
| Reader | `tencent-copilot-hy3-ioa`, T=0, seed 42, **64** output tokens |
| Researcher | `tencent-copilot-hy3-ioa-researcher`, T=0, seed 42; Blocks A–C used 8192 output tokens; Block D uses **32768** and parent-tree merge |
| Verifier | `extractive_span_match` on PopQA; LongMemEval pack uses `answer_string_present` only, **not** the official scorer |
| Open-S H0 | `seeds/open_s_v1` in a fresh interpreter. This is query-overlap ranking, **not** `LexicalPolicy` BM25 |
| Isolation | AST audit + fresh policy worker. Not a container. Dirty worktree is recorded, not hidden |
| Claims | no pooling with Qwen, A2, KV, or official leaderboards |

Live long-horizon researcher loops remain out of scope.

## Block A — PopQA frozen landscape (hy3 reader only)

16 unseen items. One interleaved pass. No researcher.

| Arm | Role |
| --- | ---- |
| `open-s-h0` | frozen seed, fresh-process |
| `head` | whole-chunk truncation |
| `head-tail` | handwritten position control |
| `hand-hybrid` | handwritten `PolicySpecV1` QUERY_BM25 + TWO hops + RANK + EDGE_INTERLEAVE |

Schedule seed 20260901. For each item the four arms are shuffled once. Missing
calls invalidate the block; they are never scored as zero.

Public output is aggregate-only: per-arm mean score, mean gold recall, token
and latency totals. Item predictions stay out of the public JSON.

## Block B — dual-role open-S visible campaign (hy3 researcher + hy3 reader)

Eight further unseen items (offset 56). Two researcher rounds from the same
open-S seed. Visible gold feedback is allowed. Gate/sealed unused.

Do not claim researcher advantage: there is no matched Random-N / sequential
control, no replay floor on this panel, and hy3 is unversioned. Report last,
peak, historical-best, invalid slots, and H0.

## Block C — LongMemEval-V2 small pack (zero reader)

Full text-only small tier. Policies: last-k (recency), lexical, random.
Primary table: deterministic evaluator stratum (294). Weak LLM-abstention
stratum (128) reported separately. Metric is answer-string presence in the
pack, not official LongMemEval accuracy. No researcher.

## Block D — window-envelope dual-role open-S (current)

Frozen card: `docs/open-s-visible-scenario.md`.

Eight unseen items at **offset 64**. Five researcher rounds. Pack budget is the
reader window (128960 on hy3), not 8K. Identical parent copies are invalid.
Full-as-fits, RAG, truncation, and reorder are all legal. Qualification only.

Do not overwrite Blocks A–C. Do not claim researcher advantage without a
matched control.
