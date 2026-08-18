# Asset inventory and reader identity — 2026-08-17

## Qwen3.5 as primary frozen reader: no

Qwen3.5 (Feb 2026) is the **previous** generation. The paper/reproducibility
anchor is already newer: Qwen3.6-27B rev
`1b559cf7215ebe67ff10758e14f6293ba883223b` on vLLM 0.25.1. Switching the
primary reader would invalidate Repair A/B/C landscapes, tokenizer
calibration, and serving-profile hashes. Qwen3.5 may later be a **separate
transfer block** after a registry pin; it must not replace `qwen3.6-27b`.

A still-newer open model (e.g. Qwen3.8, if used) is the same rule: new
identity, new landscape, not a silent upgrade.

## Already on disk at pins

| Asset               | Path                       | Pin                                                 | Size              |
| ------------------- | -------------------------- | --------------------------------------------------- | ----------------- |
| Qwen3.6-27B         | `models/qwen3.6-27b`       | `1b559cf7215ebe67ff10758e14f6293ba883223b`          | 52G, 15/15 shards |
| HELMET code         | `data/helmet`              | `af609c4d51b97fc35012099380aa889da961c42d` detached | 30M               |
| RULER code          | `data/ruler-v1`            | `c3f5e3b4f87f97e048793bb510a3a6b19a46bf3a`          | 19M               |
| LongMemEval-V2 code | `data/longmemeval-v2`      | `2cc8c540bdb87fe6761629b585e727e1c4704520`          | —                 |
| LongBench-v2 data   | `data/longbench-v2-data`   | `2b48e494f2c7a2f0af81aae178e05c7e1dde0fe9`          | 445M              |
| LME-V2 data         | `data/longmemeval-v2-data` | `f152293e235517d504809563c833d7190b8c713b`          | 6.7G              |

## Missing for official HELMET RAG+Recall

Git tree has no `data/kilt/*.jsonl`. Payload is `data.tar.gz` on
`princeton-nlp/HELMET`. Registry now has `helmet-data` at
`bc560a6b8165c696ad4bc3d1612c64b5794ba328` (11.27 GB). Downloaded,
sha256 `9d693981aa3c065b8b2ff82ddf946141cdc4ece4524f18bff6f3fbd2a86982d9`
matches LFS. Extracted under `data/helmet-data/data/` (~30G jsonl plus the
tarball, 41G total). `data/helmet/data` is a symlink into that tree.
RAG/Recall paths used by the pinned configs are present (`kilt/`, `ruler/`,
`json_kv/`). Do **not** wget dataset `main`.

Not acquired: Llama-3.3-70B (gated), LLaMA-2-7B (LongLLMLingua, not scheduled).
