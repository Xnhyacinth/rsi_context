# R17 KEP conditioned arithmetic diagnostic result

**Status: completed paid development diagnostic; no parent qualification.**
The clean, committed producer `work/r17-kep@aaa9d40cd4d6e77ecbba2b1627cf2ae307aa1aa4`
ran the four preregistered, R16-conditioned target requests with one pre- and
one post-canary. The registration SHA-256 was
`9479b293c7bb6bac6b681f0177f40ccec546f86c7aa5494718200b5e45984dc7`;
the guarded launch SHA-256 was
`4c1f66f00a7881fe87ae951b816b59e2317480705355eca4a76cb87566b618a3`.
The input R16 paid `task.json` was verified against its immutable SHA-256
`15520c0aedba2d471d7e85085b1d05813a366b22f401ae5b641e669468e6a36d`.
This is a prospective diagnosis **conditioned on an observed failed answer**,
not a new source-reading benchmark trajectory. It neither changes R16's
failure nor establishes source causality.

| Call | Provider input/output tokens | Actual reply | Evaluator readout |
| --- | ---: | --- | --- |
| Pre-canary | 62 / 2 | Fixed canary | Passed |
| Exact R16-style replay with prior `hold` | 277 / 11 | `plan=hold-at-1000m` | Legal plan false |
| Sidecar membership probe | 301 / 16 | `A=300m`, `B=0m` | Reversed from private `A=0m`, `B=300m` |
| Numeric plan with prior `hold` | 320 / 20 | `1200m`, `hold` | Arithmetic false; plan consistent with reported number |
| Numeric plan without prior | 308 / 20 | `1200m`, `hold` | Same observed answer; arithmetic false |
| Post-canary | 62 / 2 | Fixed canary | Passed |
| **Total** | **1,330 / 71** | **6 calls** | Unknown usage 0; auxiliary calls 0 |

The pinned authentic ordered-prefix calculation for the amendment is 800m,
so the private legal plan is `admit-at-1000m`. The membership probe shows that
the model did not assign the sidecar to the correct init container on this
request. Both numeric replies were also wrong and identical despite removing
the prior-plan line. These independent single-call probes indicate rule
application and arithmetic remain plausible failure locations; they do not
identify the model's internal computation or estimate an anchoring rate. The
correct `formula=prefix` classification in R16 was too coarse to establish
that the model retained an executable ordered-prefix rule.

The private run is
`/volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/kep-arithmetic-diagnostic-v1/`.
It has mode 0700 and each evidence file has mode 0600. The producer identity
records `worktree_dirty=false` and `producer_files_match_head=true` at the
above Git commit. All four target responses had the pinned Qwen model echo,
`stop` finish and exact local/provider input parity (`277`, `301`, `320`,
`308`). The journal has six `dispatched` and six `response-received` entries,
without retry or missing usage. The total local-input-plus-requested-output
planning amount was **13,618 tokens** at the registered ceiling; actual
provider usage was the 1,330/71 tokens above, not that requested ceiling.

| Private evidence file | SHA-256 |
| --- | --- |
| `identity.json` | `80febd717f3cfbe34702d0ab215eaf0b7ca34715c3d75e0a005f81ba6514802a` |
| `task.json` | `c3ec0144de17c477e64d2aae97c2c3ec48d3ebb201e6c74c111b09b412ad84ec` |
| `attempts.jsonl` | `76e72ba3a745566ef13b27a752ad1abe1f182f745540d69a5cc506ef25300c0f` |
| `final.json` | `63772029729ce41f1f55f37775c674479bd33613f8d2aca286bac12f17c2df2b` |

Before paid admission, the reviewer reproduced and fixed a fourth-reply
format error that could have incorrectly marked the block complete. The
accepted regression stops before the post-canary and leaves
`provider_block_valid=false`; nine focused tests passed with the pinned
tokenizer, and the reviewed fix found no remaining issue in that scope.
The complete repository merge gates are recorded in the R17 execution
ledger. The next KEP task, if pursued, needs a **new** versioned reader that
retains the actual ordered-prefix rule in model-visible carry, plus source-free,
identity-only and counterfactual controls under a fresh budget. Do not reuse
this diagnostic as a parent pass or alter its immutable result.
