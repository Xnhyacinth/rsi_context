# R16 KEP-753 fixed-reader paid development preregistration

Status: **admission code and geometry frozen; no R16 paid request made in this
worktree**. The R15 KEP `--execute` entrypoint remains closed. The separate
R16 runner requires a committed launch, clean producer, pinned source and
tokenizer, strict exact-profile canary, and a private durable journal before
task dispatch. Results remain development evidence until reviewed and run.

## Registered materials and calls

- Source is clean detached
  `kubernetes-enhancements-kep753@13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`;
  the full README SHA-256 is
  `ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21`.
  Both canonical private world hashes, all three case world hashes, visible
  source hashes, intervention byte spans, and the policy hash are frozen in
  [`configs/r16_kep_geometry_v1.json`](../../configs/r16_kep_geometry_v1.json).
- The shared R15 Qwen profile hash is
  `b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69`,
  with `enable_thinking=false`, temperature zero, seed 42, and requested
  output ceiling 2,048 per call. Provider revision is unavailable; this is a
  development screen.
- The fixed sequence is `full-source`, `source-free`, then
  `both-order-rules-neutralized`. Each case has a source survey, first
  resource request, and amended order request. The exact 12 allowed request
  hashes and local Qwen final-chat geometry are frozen. The evaluator checks
  the complete two-session outcome, and the case/stage preflight refuses
  other prompts before transport.
- The first full-source case must pass **both sessions** with valid model echo,
  stop finish, provider usage, and all three request identities. Otherwise
  stop before controls and the post-canary. A failed pre-canary also stops
  before any task call. If full-source passes, run both controls and one
  post-canary. A control failure is evidence, not an automatic retry.

## Decisive rule geometry

The pinned README contains two explicit ordered-prefix rule blocks at lines
780–794 and 835–848. Their original byte-span SHA-256 values are
`501730735b2c8397ddd7f19062551a0976d497a749122bcfa411f1f116191f34`
and `8cf06b1272661b01402a79e3c74eff995c018074f2f237e3b76bfc7ca38fdf42`.
In the full-source survey's exact final chat, these blocks occupy half-open
token intervals **[8959, 9062)** and **[9442, 9590)** out of 21,257 input
tokens. The source-free arm contains neither block. In the neutralized arm,
the original blocks are absent and the two registered replacement spans
occupy **[8959, 8970)** and **[9350, 9362)**. Outside the registered byte
spans, the original source is unchanged.

The project question appears in later, separate model calls, so a
source-block-to-question distance inside one final chat is undefined. The
geometry records the later question token intervals and the distance from the
**model-retained formula** to each question. That retained text is not the
original rule evidence. The neutralized source keeps a simpler upper-bound
formula, and model prior knowledge may also suffice. Consequently this
three-arm screen is diagnostic; a full-source pass alone does not establish
long-context dependency.

## Budget and evidence

The 12 variants imply a worst-path sum of **44,112 local input tokens** over
the three cases, using the largest allowed request at every case/stage. At
most **9 task HTTP calls** request 9 × 2,048 = 18,432 output tokens, making
the task local-input-plus-requested-output ceiling **62,544**. Two 62-input
canaries add 4,220, for **11 global HTTP attempts** and a **66,764** global
planning ceiling. Auxiliary HTTP calls are prohibited. This is an admission
bound, not a measured provider bill.

[`configs/r16_kep_paid_launch_v1.json`](../../configs/r16_kep_paid_launch_v1.json)
binds the geometry SHA-256, endpoint, profile, canary registration, producer
file hashes and those caps. The runner reads only committed bytes and checks
source, world, policy, tokenizer snapshot and pinned runtime before credential
resolution. It reserves an external 0700 run directory and 0600 evidence
files before requests. The append-only attempt journal records each dispatch
before transport and each response hash and provider usage after transport;
it contains no headers, credential, or full response body. Missing or
out-of-contract usage stops the block. The task, canaries, and final result
retain separate usage fields; injected fake usage is labeled synthetic.

The prospective run command, **only after integration review**, is:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r16_kep_paid_runner.py --execute \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --run-dir /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1
```

The private external parent directory must already exist. Load the Siflow
credential through the local protected environment loader; never place it in
the command, tracked files, or an artifact. The runner does not retry a
failed request automatically, and the run directory cannot be overwritten.
