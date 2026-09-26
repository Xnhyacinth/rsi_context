# R11 fixed-reader development evidence, 2026-09-26

Status: **PostgreSQL fixed-reader source/carry development screen passed; Gate 2,
researcher admission, and benchmark completion remain closed**. The work began
from clean `main@27150a5901e250e8c3f726bc40105ca0a2cfed0b` in four isolated
worktrees. All shared `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
The two PostgreSQL source checkouts remained clean and detached at their
registered 16.0/17.0 revisions. No researcher-authored policy was run.

## Fixed PostgreSQL worker and exact request geometry

`configs/r11_pg_siflow_worker_profile_v1.json` binds Qwen/Qwen3.6-27B,
`enable_thinking=false`, temperature zero, seed 42, 2,048 output tokens, and
the two-stage policy's exact-output system instruction. Its profile hash is
`fbe16d98316cb238132a5b1c87c188d8aba70ecbf872cf32bb47ac7372509f9d`.
The provider revision remains **unknown**. The pinned local Qwen tokenizer
and chat template were used to measure the *actual frozen policy* prompts;
the template trims one trailing newline from each source-survey user message,
which the recorded offsets account for.

| Source | Survey rendered input | Later request rendered input | Survey source span | Later catalog span | Later query span |
| --- | ---: | ---: | --- | --- | --- |
| PostgreSQL 16.0 | 5,685 | 268 | see raw artifact | see raw artifact | see raw artifact |
| PostgreSQL 17.0 | 6,069 | 271 | see raw artifact | see raw artifact | see raw artifact |

The authoritative local geometry artifact is
`artifacts/rsi-core-v1/r11-pg-local-geometry-v2-20260926.json`, SHA256
`f93dff7d2896ae81fffe7fbf21ad44c2bc76ef250438c8da3d522f5e9d0a5f88`.
It contains exact requests, complete token intervals, tokenizer-file hashes,
source/world identities and clean/stable producer attestation. The earlier
local geometry artifact (`r11-pg-local-geometry-20260926.json`) used a
superseded system instruction and is not comparable with the live pilot.

## Siflow compatibility and bounded real task screen

The first synthetic profile canary returned a sentence rather than the exact
`amber` answer (59 input / 8 output provider tokens). The profile instruction
was corrected and frozen **before task requests**. Its matched pre-canary and
post-canary both returned exact `amber`, each with 68 input / 2 output tokens,
and echoed the requested model. The pinned local Qwen template also rendered
the synthetic pre-canary at 68 input tokens. Raw pre/post artifacts have SHA256
`db6fb18adb4a04d22634ee50a3cbb80d156ba3c503c7462df9eb0d6edc124bd9`
and `8561a40c6a159d4c580070fee17a7497bfc0522ffa4312dfa5a51abfd43eced9`.
The failed canary remains preserved with SHA256
`2aa1250f4d80c23ffa041d37e2894371ea4deb6fe9498d0525c1a7c68b4bb302`.

The preregistered adaptive fixed-reader screen used one benchmark-owned policy
over eight PostgreSQL trajectories, capped at 16 attempted worker requests.
It made **11 real Siflow worker calls**, with **36,870 provider input / 256
provider output tokens** and zero unknown-usage calls. All 11 reported
`finish_reason=stop`, echoed `Qwen/Qwen3.6-27B`, and had provider input tokens
equal to their exact local rendered counts. This is adaptive worker accounting;
it is not the single-reader one-call track.

| Intervention | Session results | Final plan | Worker calls |
| --- | --- | --- | ---: |
| Full 16.0 | PASS / PASS | `defer-native` | 2 |
| Full 17.0 | PASS / PASS | `configure-native` | 2 |
| Withheld 16.0 / 17.0 | PASS / FAIL each | none | 0 each |
| Source swapped 16.0 / 17.0 | PASS / FAIL each | opposite source plan | 2 each |
| 17.0 decisive span removed | PASS / FAIL | `defer-native` | 2 |
| 17.0 empty carry, no reread | PASS / FAIL | none | 1 |

The authoritative raw pilot is
`artifacts/rsi-core-v1/r11-pg-siflow-pilot-20260926.json`, SHA256
`ca8cf77fa46fb4f3832ed1b9a5e79c8b7de549a1966499f53a2f6985147118db`.
It preserves each request hash, material hash, prompt/source/query offsets,
provider response hash/model/id/finish/usage, the policy transcript, bounded
call indexes, and clean/stable producer identity. Authentication headers and
the local key are absent. The task calls plus three R11 canaries account for
**37,065 input / 268 output provider tokens** in this development step.

The matched source swap and decisive-span deletion show sensitivity to
source content under this fixed policy. They do not prove that the model
reasoned from the intended table row rather than correlated source cues. The
eight inspected trajectories cannot establish the registered ≥16-item
difficulty screen, saturation, 20% disagreement threshold, or independent
parent effect. PostgreSQL 16/17 are still **one** source lineage, and the
qualified independent-parent count remains **zero**.

## Independent OTel lineage, offline only

The separate OpenTelemetry 1.24/1.43 source pair now has a frozen
model-driven policy with a source survey before the new-instrumentation
request, bounded carry, later model plan, and environment-issued review
receipts. A deterministic fake worker exercised ten cases: both complete
variants, withheld sources, swaps, empty carry with/without reread, and
prior/current receipt failures. Complete source chooses `db.statement` for
1.24 and `db.query.text` for 1.43; the source swaps reverse the plan against
the frozen oracle. The raw artifact
`artifacts/rsi-core-v1/r11-otel-model-screen-20260926.json` has SHA256
`85f5d8d001690213f5f93415f5c084e8e9b4f6bfec51d002676685715355d915`.
It has pinned source/world/policy hashes and clean producer attestation.
This is structural **fake-worker** evidence: OTel fixed-reader solvability,
actual provider usage, and final-template offsets remain unmeasured.

## Reproduction and remaining gates

From a clean checkout with the pinned roots configured, the OTel offline
screen is:

```bash
RSICONTEXT_OTEL124_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.24.0 \
RSICONTEXT_OTEL_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0 \
uv run --no-sync python scripts/r11_otel_model_screen.py \
  --output artifacts/rsi-core-v1/r11-otel-model-screen-replay.json
```

For PG, run `scripts/r11_pg_prompt_geometry.py` with the same pinned source
roots and Qwen tokenizer, then supply its output as `--geometry-reference` to
`scripts/r11_pg_siflow_pilot.py`. The latter resolves the key from
`SIFLOW_API_KEY`, the endpoint from `SIFLOW_BASE_URL`, refuses a dirty producer
checkout or changed geometry/profile/source identity, and writes only to a new
output path. The existing local credential loader is
`/volume/pt-dev/qjiu/wynckeliao-env/ops/env/local-env.sh`; its contents are
never copied into evidence.

Next: run a separate, preregistered fixed-reader item difficulty and
non-saturation screen, validate the OTel lineage with a real fixed reader,
and move the researcher valid-update-rate pretest to a trusted immutable host
where the policy jail ancestor checks pass. Current `/usr` ownership causes
the jail to fail closed, so this R11 fixed-reader screen is **not** a
researcher pretest or an A2 launch authorization.
