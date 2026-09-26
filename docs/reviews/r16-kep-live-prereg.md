# R16 KEP-753 five-arm fixed-reader preregistration

Status: **offline only, no R16 paid request made**. R15's original offline
and real evidence is unchanged. The R15 KEP `--execute` command remains closed.
This new version uses one benchmark-owned generic policy and five constructed
material arms. A separate guarded runner may be considered after independent
review of this registration, the clean producer, and the offline fake chain.

## Common task and materials

The source is clean detached
`kubernetes-enhancements-kep753@13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`.
The authentic README SHA-256 is
`ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21`.
The five arms share the same first request (S, A, B; legal hold), order
amendment (A, S, B), review procedure, fixed generic R16 policy, and frozen
Qwen profile. The policy's model survey says “supplied reference”; it does
not name KEP. First and amended request text also says “reference”. All
material variations are in the survey source. The model is invoked once per
survey, once for the first plan, and once for the amended plan.

1. **Authentic full source:** complete pinned README, legal S2 plan `admit`.
2. **Deidentified source-free:** generic marker and answer-free withheld text;
   neither the model-visible source nor either later brief names KEP. Legal S2
   plan remains `admit`.
3. **Identity-only:** KEP-753 title and pinned source URL are visible, while
   the rule text is withheld. Legal S2 plan remains `admit`.
4. **Two explicit rules neutralized:** authentic README except ordered-prefix
   blocks 780–794 and 835–848 are removed. The conservative upper-bound at
   774–778 remains; this arm is diagnostic. Legal S2 plan remains `admit`.
5. **Same-identity conservative rule:** a **constructed benchmark
   counterfactual**, never claimed as authentic upstream. Three byte spans
   774–778, 780–794 and 835–848 are replaced with mutually consistent
   all-sidecar calculation text. All bytes outside those spans are verified
   unchanged. The source retains the model-visible KEP title/identity and the
   same request text. Under this rule S1 is 1100m and still legal `hold`; S2
   changes from authentic 800m `admit` to 1100m **`hold`**. Only the private
   S2 legal-plan oracle changes. Its evaluator-side source URI is explicitly
   `benchmark:constructed/...`, not the authentic GitHub URL.

The source-free, identity-only and edited arms have evaluator-side
`benchmark:constructed/...` URIs. These metadata fields are not forwarded by
the fixed policy; its three model requests contain only source/brief text.
The exact five world hashes, visible source hashes, policy hash, source byte
edits and 14 registered prompt hashes are in
[`configs/r16_kep_geometry_v1.json`](../../configs/r16_kep_geometry_v1.json).

## Evidence location and interpretation

The pinned Qwen final-chat template places authentic README blocks 774–778,
780–794, and 835–848 at half-open token intervals **[8897, 8954)**,
**[8954, 9057)** and **[9437, 9585)** in the source survey. The deidentified
and identity-only arms have no corresponding rule span. The neutralized arm
keeps the first block at **[8897, 8954)** and has replacement intervals
**[8954, 8965)** and **[9345, 9357)**. The constructed counterfactual's three
replacement intervals are **[8897, 8947)**, **[8947, 9012)** and
**[9392, 9496)**. Every span has original/replacement SHA-256 and line/byte
offsets in the geometry. These are local final-chat positions, with provider
parity checked by exact usage during a future live block.

The project question is in a **separate later model call**, so no
original-source-to-question distance within one chat is defined. Later
request geometry records the question's exact token interval and its distance
from the model-retained formula, which is a different kind of evidence. Model
prior knowledge, surface cues elsewhere in the README, and the fixed answer
grammar remain possible. The five-arm comparison and private oracle flip are
stronger controls, but this single constructed task alone does **not** qualify
an independent long-context parent or prove causal dependency.

## Fixed budget and stop rule

The 14 exact requests cover five survey variants, three first-plan variants,
and six amendment variants. Taking each case/stage's largest allowed prompt
gives **66,579 local input tokens** across five cases. At most **15 task HTTP
calls** request 15 × 2,048 = 30,720 output tokens: the task
local-input-plus-requested-output ceiling is **97,299**. Two 62-input
exact-profile canaries add 4,220, yielding **17 global HTTP attempts** and
a **101,519** planning ceiling; auxiliary calls are forbidden. These are
prospective admission limits, not observed provider usage or a price estimate.

The strict pre-canary must pass before any task call. The authentic full-source
case runs first; if either session fails, if any worker request or usage fails,
or if it exceeds three calls, stop before all controls and the post-canary.
If full source passes, run the four controls in the registered order and one
post-canary. Control failures are recorded without retry. A completed block
requires 15 task attempts, two canaries, exact model echoes, stop finishes,
local/provider input agreement and no unknown usage.

[`configs/r16_kep_paid_launch_v1.json`](../../configs/r16_kep_paid_launch_v1.json)
binds the geometry SHA-256, profile, endpoint, canary registration, producer
bytes and caps. The runner authenticates committed bytes, pinned tokenizer
snapshot/runtime, clean detached source and world hashes **before credential
resolution**. It reserves a private external run directory (0700) and
evidence files (0600), then journals each dispatch before transport and each
response hash/provider usage afterward. The journal excludes headers, secret
and response body. Missing or out-of-contract usage ends the block. Fake
transport usage is labeled synthetic and never counted as real Siflow usage.

After integration review, the prospective command is:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r16_kep_paid_runner.py --execute \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --run-dir /volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1
```

The external parent directory must exist. Load the Siflow credential through
the protected local environment loader, never the command or artifacts. The
runner never retries a request or overwrites an existing run directory.
