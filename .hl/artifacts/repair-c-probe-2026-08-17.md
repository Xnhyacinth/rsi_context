# Repair C dense probe — 2026-08-17

Do not overwrite this file. Do not start A2 from it.

| File                                | Profile | Gold-only | Oracle  | Full | Lexical | Head | Head-tail | Calls |
| ----------------------------------- | ------- | --------- | ------- | ---- | ------- | ---- | --------- | ----- |
| `qwen-repair-c-dense-probe-v1.json` | dense   | **1.0**   | **1.0** | 1.0  | **0.0** | 0.25 | 0.0       | 56    |

Seed `hard-repair-c-dense-probe-disposable-v1`. Fingerprint
`612d7d10798e9cd71b29f4dda7422715a1029ad904b163e8f75db96b75be3042`.
Tokenizer `Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b`.
Source tokens 32,736–32,746.

Kill-list vs actual: gold-only ≥ 0.85, oracle ≥ 0.80, lexical < 0.90 all
passed. Query still lists six `nd-` IDs and forbids `ds-`/`dossier`.
Full 32-policy screen must use a **new** seed and 16 items/profile.
