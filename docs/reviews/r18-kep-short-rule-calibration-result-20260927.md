# R18 KEP short-rule calibration result

**Decision: the short-input feasibility gate failed for this reader and task.**
The guarded Siflow block completed with exact model echo
`Qwen/Qwen3.6-27B`, both profile canaries passed, and all four target replies
had valid formats and `stop` finishes. The model gave an incorrect answer to
both rule-membership probes and both effective-request probes, including
those with the authentic ordered-prefix formula visible immediately before
the amendment. Do not spend on a KEP full-source source-dependency screen
using this task/profile based on these four observations.

| Rule material | Probe | Provider reply | Evaluator check |
| --- | --- | --- | --- |
| Coarse `formula=prefix` | Sidecar membership beside A/B | `A=300m, B=0m` | Incorrect; private values are `A=0m, B=300m`. |
| Coarse `formula=prefix` | Effective request and plan | `1100m, hold` | Arithmetic and legal plan incorrect; threshold internally consistent. |
| Exact KEP lines 780–794 | Sidecar membership beside A/B | `A=800m, B=800m` | Incorrect; private values are `A=0m, B=300m`. |
| Exact KEP lines 780–794 | Effective request and plan | `1100m, hold` | Arithmetic and legal plan incorrect; threshold internally consistent. |

The evaluator-only effective request is `800m` and legal plan is `admit-at-1000m`.
This oracle applies the source excerpt's **request-only formula** to the
constructed new-Pod amendment with zero overhead. The later KEP discussion
of `Status.ResourcesAllocated` is outside this constructed request; the
result makes no claim about general live scheduler accounting. Separate
fresh calls for membership and arithmetic cannot identify a unique internal
failure step or estimate a success rate. In particular, the explicit-rule
`A=800m, B=800m` reply resembles the two total init-use maxima, rather than
the requested sidecar-only contributions; output-field confusion is one
possible explanation, not a demonstrated mechanism. The prompt supplies a
short selected source excerpt, so this is not a long-source retrieval or
independent-parent result.

The committed [registration](../../configs/r18_kep_short_calibration_v1.json)
has SHA-256 `7da8e437c760390c5ca72e701274ea25423e0fc9299254b0aec8a50`;
the guarded [launch](../../configs/r18_kep_short_paid_launch_v1.json) has
SHA-256 `1d0e90a86c8234358a6b6b75900832e94a6c3cd7ea94d36f0c096bc4ecbb5929`.
The immutable paid block is under
`/volume/pt-dev/qjiu/rsi_context_external/r18-paid-runs/kep-short-calibration-v1/`.
Its `identity.json`, `attempts.jsonl`, `task.json`, and `final.json` SHA-256
values are respectively
`5019f3cf6408576dd9e28da80d41f5c3aed8b6171469215a5be3099e96f1d4b3`,
`f44a661665e59941e37682ed506d77799038bdf03078292aede0b3909106e461`,
`7dc8a42af1dfa8a13c2e317be69c29765bfab9d9284d4fcaa65261cc17114274`,
and `6081edc9ffc22e5363c2f97edde1c354cf6114d8be7f13b071abd6f0dc49a07e`.
The directory is mode `0700`, each file `0600`, and the producer remained
clean. Each of the six calls has one journaled dispatch and response event;
there was no retry or auxiliary call.

Provider-reported usage was **1,410 input / 74 output tokens for four target
calls**, plus **124 input / 4 output tokens for two canaries**, for **1,534
input / 78 output tokens total** and **zero unknown-usage attempts**. The
local input lengths were 300, 306, 399 and 405 tokens; provider input parity
held for all target calls. The 13,822-token local-input-plus-requested-output
ceiling was an admission bound, not actual usage or cost.

Offline and guarded fake transport tests passed **9/9** on the clean
integration branch before the paid launch. An independent static review and
`codex review --base origin/main` found no actionable blocker; the Codex
review also ran 17 focused tests with branch coverage and targeted Ruff,
strict mypy and Bandit. These checks support the execution/accounting result,
not the model's answer quality.
