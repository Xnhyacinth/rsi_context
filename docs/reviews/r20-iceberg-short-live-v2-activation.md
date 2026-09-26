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
`26a62e88611d8e26d7e17bd28529913651a7ac7d0c65ccf3c43f776c4aed2241`.
The [v1 registration](../../configs/r20_iceberg_short_registration_v1.json)
remains SHA-256
`a528a02fd8b90d9a69ed0a1bb68c0a0ee89bb854026c459e2e5b7a65d4936e58`.
The runner and final result now name v2. The runner requires the committed manifest, every
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
