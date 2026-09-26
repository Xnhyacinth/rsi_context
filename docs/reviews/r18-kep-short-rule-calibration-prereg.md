# R18 KEP short-input rule calibration

Status: **offline registration and synthetic transport only; no R18 paid call**.
R16's long-source reader classified the formula as `prefix` but held after the
order change. R17's paid, short-input diagnostic returned sidecar membership
`A=300m, B=0m` and effective request `1200m` with `hold` in both numeric
conditions. This new development experiment asks whether the same frozen model
can execute the task when the authentic ordered-prefix rule is placed directly
in its short input. It is an **oracle-projected source-rule feasibility
baseline**, not a long-source dependency result or parent qualification.

## Pinned input and two-by-two design

The immutable R16 and R17 paid `task.json` inputs have SHA-256
`15520c0aedba2d471d7e85085b1d05813a366b22f401ae5b641e669468e6a36d`
and `c3ec0144de17c477e64d2aae97c2c3ec48d3ebb201e6c74c111b09b412ad84ec`.
The source is clean detached KEP revision
`13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`; README SHA-256 is
`ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21`.
The projected material uses **only exact source lines 780–794**, whose
raw-span SHA-256 is
`501730735b2c8397ddd7f19062551a0976d497a749122bcfa411f1f116191f34`.
The joined model-visible rule SHA-256 is
`66f65040f60b5afb62477c87a37f5cfbedab064af421b499e99553220ef15ad9`.
This span gives both the earlier-sidecar membership rule and the resulting
Pod effective-request max formula. The later KEP status-aware section is not
needed here because the constructed request supplies CPU requests and zero
Pod overhead; omitting it avoids a partial second formula. The projected text
contains no case-specific membership, effective request or plan answer.

| Order | Material | Probe | Output |
| --- | --- | --- | --- |
| 1 | Coarse `formula=prefix` only | Membership beside regular init A and B | `a_sidecar_m`, `b_sidecar_m` |
| 2 | Same coarse label | Effective CPU and plan | `effective_cpu_m`, `plan` |
| 3 | Exact pinned rule excerpts | Same membership probe | Same two fields |
| 4 | Same exact excerpts | Same effective CPU and plan probe | Same two fields |

All four requests use the byte-identical R16 model-visible order amendment,
SHA-256 `198bf01062a787132bab32cdb58e624cf31625434ebdd4d04b2c007629ee5431`.
The paired prompts differ **only in supplied rule material** for each probe.
They omit the prior `hold` cue, so this experiment does not estimate its effect.
Every request is a fresh target-model call with the frozen non-thinking Qwen
profile SHA-256
`b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69`.
The registry SHA-256 is
`16807ab8ae22734f2a90cc64df843587a9b290bdf8b4dba79f154efabc81c934`.

The evaluator-only values are A sidecar 0m, B sidecar 300m, effective request
800m and legal plan `admit-at-1000m`. These values are **not** forwarded in the
rule material or instructions. The frozen evaluator classifies answer format,
membership, arithmetic, threshold consistency and legal plan separately.
Correct explicit-rule answers with incorrect coarse-label answers would show
that the model can execute the short task when given the rule; it would not
show that it can extract or retain the rule from 21k-token source. Incorrect
explicit answers would weaken the task's feasibility as a benchmark case.
Because probes are separate model calls, mixed results do not prove an internal
failure step or estimate a success rate.

## Geometry and budget

The exact registration is
[`configs/r18_kep_short_calibration_v1.json`](../../configs/r18_kep_short_calibration_v1.json),
SHA-256 `7da8e437c760390c5ca72e701274ea2543bf08825423e0fc9299254b0aec8a50`.
Final-chat inputs are 300, 306, 399 and 405 tokens. Each has a unique
rule-to-amendment span; all are under 500 input tokens. Four target requests
sum to **1,410 input tokens** and at most **8,192 requested output tokens**,
for a task planning ceiling of **9,602**. Auxiliary calls are forbidden. A
future two-canary guarded block would have at most **six HTTP attempts** and
**13,822** local input plus requested output tokens. These are prospective
limits, not observed provider use or a price estimate.

The offline command verifies the immutable paid inputs, source byte spans,
registry, tokenizer and prompt registration, then runs a fake SSE chain:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r18_kep_calibration_offline.py \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --r16-task /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json \
  --r17-task /volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/kep-arithmetic-diagnostic-v1/task.json \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b
```

Fake answers deliberately make coarse probes wrong and explicit probes right
to exercise accounting and classification. They are **not model evidence**.

The guarded runner is
[`scripts/r18_kep_calibration_paid_runner.py`](../../scripts/r18_kep_calibration_paid_runner.py).
Its launch manifest is
[`configs/r18_kep_short_paid_launch_v1.json`](../../configs/r18_kep_short_paid_launch_v1.json),
SHA-256 `1d0e90a86c8234358a6b6b75900832e94a6c3cd7ea94d36f0c096bc4ecbb5929`.
It binds committed producer, registry and profile bytes, exact tokenizer
snapshot/runtime, clean detached source revision and README, both immutable
paid observations, this registration, endpoint and caps before credential
resolution. Its private fsynced journal records each dispatch before transport
and response hash and provider usage afterward; missing or out-of-contract
usage stops without retry. A complete block requires four target responses,
two exact-profile canaries, model echo, `stop` finishes and exact provider/local
input parity at the 13,822 planning ceiling. The fake full-chain test also
checks private file permissions,
synthetic/provider usage separation, failure stops and no overwrite.

**Paid admission awaits independent code and science review.** No R18 Siflow
request has been made. The prospective command, after that review, is:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r18_kep_calibration_paid_runner.py --execute \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --r16-task /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json \
  --r17-task /volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/kep-arithmetic-diagnostic-v1/task.json \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --run-dir /volume/pt-dev/qjiu/rsi_context_external/r18-paid-runs/kep-short-calibration-v1
```

Completion would provide feasibility evidence for this one short task only.
It would not qualify a KEP parent, establish long-source dependency, or
retroactively change R16/R17 results.
