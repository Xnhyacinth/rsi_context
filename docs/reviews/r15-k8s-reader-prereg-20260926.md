# R15 KEP-753 fixed-reader development screen preregistration

Status: **offline dry-run only; `live_ready=false`**. The KEP resource-order
world is a two-session B/longitudinal development card in the existing KEP
source lineage. This screen has no model result and does not qualify an
independent parent. `--execute` refuses before credential or transport access
until the integration owner freezes parent materials and provider canaries.

## Frozen inputs and budget

| Item | Registered value |
| --- | --- |
| Source | Detached, clean `kubernetes-enhancements-kep753@13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`; full README SHA-256 `ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21` |
| Canonical first / second evaluator world | `4565339a3636212ede2dd7fd3ef9e4f4d961e613c939a0f6c2a6010e3e96042a` / `542cae04f4b34a356bf321771bc988590bb238dd49afad7250c69cd57100a99e` |
| Benchmark-owned policy | `k8s_model_fixed_r15.py` policy text SHA-256 `089533cb1f647739d683c9c9420fed7432b9235e224b1d032a29cdcf20d5b757` |
| Shared Qwen profile | `siflow-qwen3.6-27b-r15-bc-dev-2048`, profile hash `b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69`, file SHA-256 `c3bb91d662d588e0a0a69101fb8fd851a1c910ded66e4387d4afccc9c9002ff6` |
| Tokenizer/template | Registered Qwen snapshot (`tokenizer.json` `5f9e4d49…`, `tokenizer_config.json` `dbfb3c20…`), manifest SHA-256 `8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290`; `transformers==5.15.0`, `tokenizers==0.22.2`, `jinja2==3.1.6`, `enable_thinking=false` |
| Request endpoint identity | `https://api.siflow.cn/model-api/chat/completions` in the *fake* transport; no network request is made |
| Limits | 3 registered trajectories, at most 9 worker attempts total, at most 8 charged calls per trajectory including verifications, 2048 output tokens per worker request, 262144 total model length |

The benchmark-owned reader asks the model once to classify the resource rule
before seeing the project request, once for the first plan, and once after the
order amendment. It accepts only the enumerated formula/plan reply grammar and
completes environment-issued review/finalization actions. Both possible plan
subjects receive a passing **procedural** receipt; the private legal plan is
checked at finalization. Every requested worker call is metered, and the
complete two-session outcome is retained for each trajectory.

## Three source arms

1. `full-source`: complete pinned README in the first survey; visible source
   document SHA-256 `cb15e53588b1224ad0d6b70b497d28c4c51a625b4dec13604403c7f63011f1af`.
2. `source-free`: answer-free marker with neither formula nor source identity;
   visible source document SHA-256
   `fd3a80b49ad9e01019440895c73ebbeecb27760dbe5a6aa1a2fb37af3ba72595`.
   The model is still invoked in all available stages.
3. `both-order-rules-neutralized`: full README except the two explicit
   ordered-prefix rule blocks, lines **780–794** (bytes 37550–37989, original
   span SHA-256 `501730735b2c8397ddd7f19062551a0976d497a749122bcfa411f1f116191f34`)
   and **835–848** (bytes 39626–40268, original span SHA-256
   `8cf06b1272661b01402a79e3c74eff995c018074f2f237e3b76bfc7ca38fdf42`).
   The edited raw README SHA-256 is
   `143aa58b56e1339f746c4b0f3ee34e29a7af4c79054b0de9b2d92f9e9ce7c72c`;
   visible source document SHA-256 is
   `ccff8cf8463cb461ceab5bc6a721cb2f57c84708c44752384c30ff916895d406`.
   Every byte outside those blocks is checked unchanged. The simpler upper
   bound remains, so this is removal of the two **explicit** ordered rules;
   a model may still infer or recall the true rule.

The first and second constructed requests, their private oracle, stage order,
and budget stay fixed across the three arms. This is a diagnostic development
screen, not a causal estimate: source-free knowledge, fixed hold-then-admit
patterns, and residual indirect cues remain possible.

## Geometry and usage boundary

The dry-run enumerates every accepted dynamic later prompt before the capped
screen: 3 formula replies (`prefix`, `conservative`, `unknown`) × 2 first-plan
replies (`hold`, `admit`) across all three source arms. Deduplication produces
**12 exact final-chat requests**: 3 survey, 3 first-plan, and 6 amendment
variants. Each is rendered with the pinned local chat template and receives a
prompt hash, canonical JSON request hash, exact input tokens, evidence/query
offsets when available, and an output-cap check. During the fake SSE screen,
each actual request must match a registered prompt and request hash, exact
profile hash, current case, and expected stage **before transport dispatch**.
The canonical evaluator world hashes are checked separately. Provider-template
parity remains unverified until a strict fresh Siflow canary and real run.

The dry-run's nine SSE responses and token counts are **synthetic**. The output
keeps `provider_usage_total=null`, labels each attempt `synthetic_sse`, and
reports `synthetic_usage_total` separately. It cannot be cited as actual Siflow
usage or a Qwen success rate. Unexpected response model, non-stop finish,
missing usage, request drift, model-length excess, or attempt-cap refusal ends
the screen with a named status and no later transport calls. The CLI records
clean/stable producer attestations before writing a dry-run artifact.

Reproduce after committing a clean producer tree and installing the pinned
optional tokenizer runtime into the project-local environment:

```bash
uv run --frozen --no-sync python scripts/r15_k8s_reader_screen.py --dry-run \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --output /tmp/r15-kep-offline-screen.json
```

The artifact is a synthetic contract check. A paid screen additionally needs
parent-level preregistration of exact materials, all 12 request hashes,
code identity, case budgets, and fresh strict model-echo/finish/usage canaries.
The current `--execute` entrypoint refuses pending those gates.
