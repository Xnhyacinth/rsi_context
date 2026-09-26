# R17 KEP arithmetic and prior-decision diagnostic

Status: **offline registered; no R17 paid request dispatched**. This is a
post-hoc development diagnostic prompted by the immutable R16 failure. It is
not a new benchmark trajectory, a parent qualification, or a source-dependency
result. Do not revise the R16 full-source outcome or resume its stopped
five-arm launch.

## Observed condition and unchanged task

R16 paid `task.json` has SHA-256
`15520c0aedba2d471d7e85085b1d05813a366b22f401ae5b641e669468e6a36d`.
Its authentic source survey returned `formula=prefix`; the first plan was
`hold-at-1000m`; the amended plan also returned `hold-at-1000m` and failed the
private legal-plan gate. The third R16 request had prompt SHA-256
`f6cf02f400497f844984ba116b96cc16102bc78a75f6cc952e26871401f1bb21`.
R17 verifies these bytes and outcomes before constructing a prompt. The formula
and first decision are **observations from the failed R16 run**, not evaluator
answers inserted into a new source-reading task.

All four R17 calls use the exact same R16 model-visible amendment, SHA-256
`198bf01062a787132bab32cdb58e624cf31625434ebdd4d04b2c007629ee5431`:
regular init A (800m), native sidecar S (300m), regular init B (500m), application
400m, overhead 0m, node capacity 1000m. The pinned KEP source builder and
private legal-plan contract are checked when registering, but the source text
and oracle are not sent in these R17 calls. The same frozen Qwen profile is
used: SHA-256
`b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69`.

## Prospective contrasts

| Order | Call | Only diagnostic change | Readout |
| --- | --- | --- | --- |
| 1 | `legacy-with-prior` | Exact R16 amended request, including prior `hold`; no numeric output | Fresh stability check for the failed decision format |
| 2 | `rule-membership` | Ask which sidecar millicores count beside init A and B; no overall CPU or plan | Test whether the coarse `prefix` label is applied to the changed order |
| 3 | `numeric-with-prior` | Require `effective_cpu_m` and plan, retain prior `hold` | Distinguish arithmetic error from threshold/plan error |
| 4 | `numeric-without-prior` | Same numeric task, omit only the prior-decision line | Test whether prior-plan cue affects arithmetic or choice |

The private rule-membership values under the authentic ordered-prefix rule are
0m added to A and 300m added to B. The private effective request is 800m.
Wrong membership suggests difficulty applying or retaining the rule after the
order change. Correct membership with a wrong effective request suggests an
aggregation difficulty. Because these are separate model calls, their combined
pattern does not prove one causal failure point. These private values remain
evaluator-only.
For numeric replies, the evaluator records exact format, arithmetic correctness,
whether the plan follows the *reported* number's 1000m threshold, and whether
the plan is legal. None of these evaluator values appear in the prompts.
An incorrect reported number with an internally consistent plan suggests a
calculation or rule-application failure in that call. If the number is 800m
but the plan is `hold`, the same-call evidence points to threshold mapping or
decision execution. If the numeric calls differ
by prior cue, anchoring is a plausible mechanism; one pair does not estimate an
anchoring rate. A passing replay does not erase R16's failure. The R16 survey's
`formula=prefix` is a coarse classification and may reflect prior knowledge or
prompt alternatives rather than a learned source rule; these R17 calls cannot
resolve that source-causality ambiguity.

[`configs/r17_kep_diagnostic_v1.json`](../../configs/r17_kep_diagnostic_v1.json)
freezes the exact prompt and request SHA-256 values, final-chat token spans,
model profile, R16 artifact condition and call order. Its SHA-256 is
`9479b293c7bb6bac6b681f0177f40ccec546f86c7aa5494718200b5e45984dc7`.
The four prompts have respectively 277, 301, 320 and 308 local final-chat input
tokens, totaling **1,206**. There are exactly **four target calls**, **zero
auxiliary calls**, and at most **8,192 requested output tokens** under the
frozen 2,048-output profile; task planning ceiling is **9,398** local input plus
requested output tokens. A future paid runner would also require separately
registered pre/post canaries, giving at most six HTTP attempts and a 13,618
planning ceiling if both canaries use the existing 62-input/2,048-output
profile. These ceilings are not observed provider usage or a cost estimate.

## Offline result and paid admission

The local fake chain executed all four registered target requests, checked
request bytes and local/provider usage parity, and exercised the diagnostic
classification. Its illustrative answers deliberately vary; they are not
model outputs. Reproduce it with:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r17_kep_diagnostic_offline.py \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --r16-task /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b
```

The guarded runner is
[`scripts/r17_kep_diagnostic_paid_runner.py`](../../scripts/r17_kep_diagnostic_paid_runner.py).
Its frozen launch manifest is
[`configs/r17_kep_diagnostic_paid_launch_v1.json`](../../configs/r17_kep_diagnostic_paid_launch_v1.json),
SHA-256 `353e138ee3392bfbda0376d9f623a453820ebb85f52a664dcf5312f44686b020`.
It binds committed producer/registry/profile bytes, tokenizer snapshot and
runtime, source revision and README, and the immutable R16 observation before
credential resolution. Its private, fsynced attempt log records each dispatch
before transport and the response hash and usage afterward. The runner enforces
four task calls, two exact-profile canaries, six total HTTP attempts, zero
auxiliary calls, exact model/stop/provider-input parity and the 13,618 planning
ceiling. It stops on protocol or usage failure and never retries or overwrites
an existing run directory. The synthetic full-chain test uses an injected
transport and is not model evidence.

**Paid admission remains pending independent code and science review.** No R17
Siflow request has been made. After that review, the prospective command is:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r17_kep_diagnostic_paid_runner.py --execute \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --r16-task /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --run-dir /volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/kep-diagnostic-v1
```

The R16 paid artifact directory must remain immutable. Even if R17 paid
execution completes, report it as a conditioned mechanism diagnostic, not a
qualified parent.
