# Repair B cheap probes — 2026-08-16

Do not overwrite these files. Do not start A2 from them.

| File                                         | Query                                                    | Gold-only                    | Oracle                        | Full | Lexical        | Calls |
| -------------------------------------------- | -------------------------------------------------------- | ---------------------------- | ----------------------------- | ---- | -------------- | ----- |
| `qwen-repair-b-query-contract-probe-v1.json` | seal-match + “named by that rule” + listing ban          | **0.0** (8/8 `INSUFFICIENT`) | 0.25                          | 1.0  | 0.0            | 56    |
| `qwen-repair-b-query-contract-probe-v2.json` | seal-match + “return only the exact terminal identifier” | **0.875** (1× `fx-`)         | **0.875** (1× `INSUFFICIENT`) | 1.0  | 0.0 (8× `fx-`) | 56    |

Same seed `hard-repair-b-query-contract-disposable-v1`. Fingerprints differ because
query text is bound. v1 is a failed instruction. v2 clears the cheap floors
(gold-only ≥ 0.85, oracle ≥ 0.80, no non-oracle ≥ 0.90). Full 32-policy screen
must use a **new** seed.

Efficiency (v2): 570,510 input / 515 output tokens, 17.97 reader-seconds, $0.
