# R20 Iceberg short live v2 launch preparation

The v2 launch activates the already registered R20 four-arm S2 feasibility
screen. It makes no change to the model-visible request, private oracle,
source, tokenizer, profile, canary, or call budget. The v1 launch remains
byte-identical with SHA-256
`3bd1b78f5bf02fd7eb3a1d6e7d42d380e4a3fa82c9c4c6a4425a0e859418fb78`
and `live_enabled=false`. Its synthetic result remains a v1 result.

The [v2 launch](../../configs/r20_iceberg_short_paid_launch_v2.json) has
`schema_version=2`, scope `r20-iceberg-short-paid-feasibility-v2`, and
`live_enabled=true`. SHA-256:
`2e9cec18f3ace313064d0c1ddfd86222d266060f735e7b763bbb6a96d81cf230`.
The [v1 registration](../../configs/r20_iceberg_short_registration_v1.json)
remains SHA-256
`a528a02fd8b90d9a69ed0a1bb68c0a0ee89bb854026c459e2e5b7a65d4936e58`.
The runner now names v2 and requires this exact committed manifest, every
bound producer byte, clean worktree, pinned source/tokenizer/runtime, and
private oracle before credential resolution.

The fixed maximum is four target calls plus two profile canaries, zero
auxiliary calls and no retries. The target planning ceiling is 8,976 local
input plus requested output tokens; two canaries add 4,220, for a global
ceiling of 13,196. Provider usage must be returned, remain within the journal
caps, and be reconciled with the worker and canary records. A complete block
with a wrong A/B/C plan is recorded but does not mark `task_feasible=true`.
The unknown-rule D response remains diagnostic with no private correct plan.

This preparation made **no Siflow or GPU call** and did not load API
credentials. The exact offline registration can be regenerated with:

```sh
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r20_iceberg_short_offline.py \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b
```

At clean producer commit `d29c1d8a764a8fd3e68c01a94342a0ea38c84484`, an
injected-SSE run passed the real committed-launch, source, tokenizer,
runtime, canary, journal, and end-attestation checks. Its
[private artifact](/volume/pt-dev/qjiu/rsi_context_external/r20-live-preflight/iceberg-short-live-v2-synthetic-d29c1d8/)
has identity SHA-256
`698e8b46a9dff19a9950c5802fc48e9505586c7dbe4008e80a215915fafcf1d7`
and final SHA-256
`7bd6e30e858fc8eefbc712e88cbf106b163d21a9236f03ba0b8ce1d397849460`.
It records four injected target requests, two injected canaries, zero unknown
usage, 13,196 planned tokens, private 0700/0600 permissions, and
`provider_block_valid=false`. Its `task_feasible=true` verifies wiring only;
no model behavior was observed. The committed focused suite passed 9 tests;
scoped Ruff, strict mypy, and Bandit passed. Independent review precedes any
paid block. The CLI uses a fresh external private run directory and fails
closed on launch, material, credential, or provider-protocol drift.
