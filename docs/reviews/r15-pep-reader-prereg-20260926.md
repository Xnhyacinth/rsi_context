# R15 PEP historical-license fixed-reader development screen

Status: **offline geometry frozen; task HTTP closed**. This is a
benchmark-owned adaptive two-call policy over the R14
historical PEP 621/639 two-session card. It is not a qualified parent, a
sealed task, a current PyPA compliance test, or a researcher policy run.
`scripts/r15_pep_reader_screen.py --execute` refuses before credential or
network access. The geometry and local planning budget are frozen; the exact
provider canaries and launch gate remain pending. No provider results are
reported here.

The public `run_pep_screen` function requires the committed
`configs/r15_pep_fixed_reader_registration_v1.json` and matching tracked
`configs/r15_pep_fixed_reader_geometry_v1.json`. The registration records
the geometry's exact SHA-256, profile hash, tokenizer manifest hash, source
revision, and local-input-plus-requested-output planning ceiling. At dispatch, the
screen verifies the registration bytes against its Git HEAD blob, the
artifact bytes, all six current world/material hashes, the clean detached
source and selected file hashes, the pinned tokenizer files and runtime,
the shared profile file, and selected producer bytes against a clean
worktree. It compares selected producer file hashes rather than requiring
the dry-run's Git revision to equal the later registration commit.

## Identity and boundary

The source repository must be clean and detached at
`6822259db9c95f02da739b3e2830a4aa1ae35134`. PEP 621 and PEP 639
source SHA-256 values are pinned in `material_pep_r14.py` and checked before
world construction. The R15 reader profile is
`configs/r15_siflow_fixed_reader_profile_v1.json`:
Qwen/Qwen3.6-27B, `enable_thinking=false`, temperature 0, seed 42, 2,048
output tokens per request, exact system prompt, strict model echo, and Siflow
SSE usage. Its provider revision is null; even a passing pilot cannot prove a
versioned T2 effect. The local tokenizer is
`Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b`, with
both tokenizer files hashed before measurement. The local template is exact
only for those bytes and the pinned optional runtime; provider prompt-token
parity still requires a real preflight.

The source document, project request, and receipts are separated. PEP text
and URL are source material; the archival fixture and candidate plans are
constructed visible material. Only the evaluator holds the legal plan for
each version. The fixed policy asks the worker once in session 1 to retain a
`form=...` finding, then once after a process reset to select a `plan=...`
from the later request. `form=unknown` is a valid first reply and **still
produces a second model call**; a source-free arm is therefore truly model
invoked. The policy requests and inspects two procedural receipts before
finalization. Both candidate plans receive PASS receipts, so receipt
feedback does not reveal the private content answer.

## Registered cases and limits

The order is frozen for this development screen. Each case is a complete
two-session trajectory under the same fixed policy, reader profile, action
budget, and private oracle. Both source versions share the same later
request, stage IDs, and visible axes.

| Order | Case | First-session source shown | Interpretation |
| ---: | --- | --- | --- |
| 1 | `full-pep621` | Complete authentic PEP 621 with header and URL | Feasibility; legal later plan `license-table` |
| 2 | `full-pep639` | Complete authentic PEP 639 with header and URL | Feasibility; legal later plan `license-string` |
| 3 | `identity-only-pep621` | PEP 621 header and exact URL; all substantive rule text withheld | Public-identity shortcut control |
| 4 | `identity-only-pep639` | PEP 639 header and exact URL; all substantive rule text withheld | Public-identity shortcut control |
| 5 | `source-free-pep621` | Neutral withheld marker and URL; no version identity | Answer-free model-invoked control |
| 6 | `source-free-pep639` | Same neutral marker and URL as case 5 | Answer-free model-invoked control |

Identity-only and source-free documents are **constructed interventions**,
never upstream files. They change only the first-session source document.
The complete PEP source is already public and reveals `PEP: 621/639` and
`pep-0621/0639.rst`; an answer from identity alone blocks a rule-dependency
claim. Source-free arms may guess the correct action for one version. Report
both complete-project outcomes and paired actions, not a single average.
One PEP repository remains one source lineage regardless of arms or calls.

There are at most **6 trajectories and 12 worker attempts**. Each case has
a hard pre-dispatch cap of 2 model requests. Every valid first finding
(`license-table`, `license-string`, `unknown`) has a separately registered
second request, so the dry-run captures the full dynamic request set rather
than one fake answer path. A prompt absent from the geometry registry, a
prompt registered under another case or call index, a
request hash mismatch, local/provider token mismatch, wrong model echo,
missing usage, malformed SSE, non-`stop` finish, or attempt-cap violation
stops further paid calls. Valid usage from a rejected response remains
counted; missing usage remains unknown. Stop after either complete-source
case fails. Pre/post canaries and their tokens must be recorded separately
from task attempts before this can be launched.
The pre-dispatch budget also rejects a request that would make cumulative
local input exceed the reviewed six-case worst-case bound. Exact provider
input must equal that local count per call; response output is capped by the
profile. The registered planning ceiling sums local input and twelve
requested 2,048-token output bounds; actual provider usage must be recorded
and checked separately.

The task result schema records each source/world/policy/profile/request
hash, local evidence and query intervals, both-session completion, final
plan legality, receipt provenance, carry bytes, attempts, provider
input/output or unknown usage, latency, model echo, finish reason, and named
failure. The policy transcript retains a bounded prompt/reply head, while
the immutable case and request hashes identify the exact full material.
The R12 strict reader capture is reused rather than adding a second SSE
parser; its source file is included in producer attestation.

## Offline preparation and decision gate

The first runnable step is a credential-free local dry-run from a **clean
committed worktree** with the pinned PEP checkout and tokenizer snapshot:

```bash
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r15_pep_reader_screen.py --dry-run \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/python-pep-process \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b \
  --output artifacts/rsi-core-v1/r15-pep-local-geometry-20260926.json
```

The output reports exact local rendered-token counts and evidence/query
intervals for each registered request, with source Git/bytes, tokenizer,
profile, policy, and producer identities. It also sums the maximum local
input tokens across all three valid response branches for each case and
reports the 12 × 2,048 profile output-token ceiling. It makes no network
call. The committed registration now fixes its SHA-256 and planning envelope.
Before task HTTP, run a real exact-profile pre-canary with provider usage;
run a post-canary only under the launch stop rules. Synthetic canaries remain
contract tests, not provider evidence.
If identity-only or source-free behavior already solves both versions,
retain the diagnostic and reject this lineage for the intended
long-context dependency claim; do not relabel it as a qualified parent.
