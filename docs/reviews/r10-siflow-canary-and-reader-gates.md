# R10 Siflow compatibility canaries and fixed-reader gates

Status: **compatibility probes only**. No benchmark source, policy code, or
sealed question was sent to Siflow. These calls do not qualify a B/C task or
admit model-authored policy execution on the current host.

The registered Siflow model-catalog endpoint returned the requested IDs
`Qwen/Qwen3.6-27B`, `glm-5.2`, and `deepseek-ai/deepseek-v4.1-flash` as
available. The root-owned adjacent `ops/env/local-env.sh` supplied only the
API key; it did not set `SIFLOW_BASE_URL`. For these probes the endpoint was
set explicitly to the existing code-owned
`https://api.siflow.cn/model-api/chat/completions`. No credential was written
to an artifact. Both profiles leave `provider_revision` null, so the access
window and echoed model names are recorded without claiming a pinned server
revision.

The existing `scripts/api_canary.py` ran three repetitions per registered
profile, with the same synthetic evidence question and no policy interpreter:

| Profile | UTC start | Answer/model echo | Provider input | Provider output | Raw artifact SHA256 |
| --- | --- | --- | ---: | ---: | --- |
| `siflow-qwen3.6-27b-r4-dev-2048` (`92b23950…`) | `2026-09-25T17:43:43Z` | `amber` × 3; `Qwen/Qwen3.6-27B` × 3 | 80 × 3 = **240** | 2 × 3 = **6** | `a8179a8568c126b0bae14dae88d8f19e7f0c2e72bcf691d76b52f76d93923ae8` |
| `siflow-glm-5.2-worker2` (`16a11bb1…`) | `2026-09-25T17:44:54Z` | `amber` × 3; `glm-5.2` × 3 | 72 × 3 = **216** | 169 × 3 = **507** | `02389b9797a3f5c6f5d031242bc0e427f800d3f79dd269d2ec5add3a30b28f65` |

Raw records are in the ignored, preserved
`artifacts/rsi-core-v1/r10-siflow-{qwen,glm}-canary-20260926.json` files.
Both answered correctly with stable provider-reported usage. GLM charged
substantially more output tokens for this same short answer; the record does
not expose why. Qwen is the lower-token initial development reader, subject
to the actual task pilot. The canary's three repeats cannot estimate a task
replay floor, difficulty, or cross-parent effect.

## Admission gap for a B-specific fixed reader

Independent scientific review of the R9 PostgreSQL pair found three
different questions that need separate interventions: (1) does source text
change the chosen action, (2) does model-authored carry survive a reset and
matter when reread is controlled, and (3) do earlier actions and receipts
constrain the later legal commit? R9's script parser answers only a narrow
part of (1). Its visible request names `failover = true` and both candidate
plans, making exact lookup plausible. The sequence runner preserves its
document registry across reset, so a later reread can recover source facts
without memory. R9's generic first-session review PASS is procedural
provenance, not evidence that early source content was used.

The legacy R3 B/C live entry calls `_live_responder_factory()` without an
explicit thinking switch, whereas the R4 Qwen worker profile fixes
`enable_thinking=false`. The legacy `PolicyHook` bills whitespace estimates;
provider usage appears only in a separate sidecar. Its historical outputs
cannot be treated as profile-matched, exact-token B/C evidence. A new
development pilot must bind one registered profile to its actual request
payload, preserve per-attempt provider usage/echo/finish reason, and mark
unknown usage explicitly.

The stop-early development screen will use one frozen B-specific
model-driven policy across both authentic PostgreSQL revisions. It will
separate full source, both documents withheld, decisive 17.0 entry deleted,
and source-swapped diagnostics, with the same constructed task and profile.
For eight trajectories with two worker calls each, the predeclared cap is
**16 attempted worker requests**, plus separately reported canaries. Before
HTTP, the exact system/user messages, tokenizer files, chat template,
generation wrapper, decisive source span, later query span, and final-token
positions must be recorded; local rendered counts will be compared with
provider prompt tokens. An unexplained mismatch blocks a geometry claim.
The screen can falsify source dependence early; it is too small to establish
the existing ≥16-item difficulty screen, saturation, or 20% disagreement
thresholds. Any inspected result stays development-only.

The current host also fails the trusted policy-jail ancestor check at
UID-1000-owned `/usr` paths. A paid researcher candidate/update-rate pretest
still requires unskipped jail tests on a trusted immutable runtime. A static,
trusted fixed-reader call is a different channel and must never be reported
as the researcher pretest.
