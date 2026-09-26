# R19 Iceberg short S2 rule feasibility preregistration

**Scope:** test whether the frozen non-thinking Siflow Qwen reader applies the
Iceberg row-scan counter rule when the coherent rule bundle is already given
in a short second-session prompt. This removes source extraction and process
reset. It is a task-feasibility screen, not long-source dependency, B/C
researcher evidence, or a qualified parent. The `file` rule is a constructed
counterfactual, not an authentic Iceberg revision.

The two target requests reuse the R18 `decision_user` function and the same
constructed S2 facts. Their system message, request, strict comparison,
same-or-global partition rule, all-equality-ids row rule, API parameters and
plan options are identical. The *only* model-visible change is
`counter=data` versus `counter=file` in the retained rule bundle. The private
evaluator oracle is `suppress-row` for data and `emit-row` for file; it lives
in `src/rsicontext/analysis/iceberg_short_private_r19.py`, whose mapping
identity is SHA-256
`f57d92eedf5905a0d89cac579c440d9c045ef39bb9daa04bb8e97ecebbbee24c`.
The request registration contains no case-to-correct-plan mapping.

## Frozen material and request geometry

| Input | SHA-256 / identity |
| --- | --- |
| Source checkout revision | `071d5606bc6199a0be9b3f274ec7fbf111d88821` |
| Whole `format/spec.md` bytes | `e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb` |
| Fixed S2 request text | `270713688e20ce9a1e8a4f7a9236746a1f9707f6188d838efc0c0ae6436ccc81` |
| Registry | `7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0` |
| R18 geometry | `aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448` |
| R15 Qwen profile | `b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69` |
| Tokenizer manifest | `8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290` |
| [`registration`](../../configs/r19_iceberg_short_registration_v1.json) | `d148c6ebac48a98638fef4e6950be627787bc47733c1a0aeb49da809c276554d` |
| [`launch`](../../configs/r19_iceberg_short_paid_launch_v1.json) | `ca56a029343cd94bb06ab903e3510af7d5e4017e3af1a54c28f909e073d6044e` |

The runner checks a clean detached source checkout, pinned source/license
bytes, registry, committed launch and every bound code/dependency byte,
tokenizer files and runtime (`transformers 5.15.0`, `tokenizers 0.22.2`,
`jinja2 3.1.6`) before reading credentials. The source is used only to
reconstruct and hash the common S2 request. No 118,725-byte S1 source pack
enters either model prompt.

| Counter arm | Prompt SHA-256 | Full API request SHA-256 | Final-chat input | Evidence interval | Query interval |
| --- | --- | --- | ---: | --- | --- |
| data | `e6610a22057fec5896e8714dbdcc5b0cd3cbb6eb7afb61237fdbdd1c0531811a` | `b3bec5d51f987ec30f53116c5d64600759e665d56ecbfdf5e495037333c429ed` | 321 | `[30,55)` | `[288,312)` |
| file | `dc4648824ea8ff0a47450422c48b1ed7b4e1aa10c75cc1f71beec0d697dc7723` | `18ffad6fc052772349dc21f4b071f2bcf5d5bbb8cbbcf313446a1d5af819f24e` | 321 | `[30,55)` | `[288,312)` |

The complete request hashes include `Qwen/Qwen3.6-27B`, temperature 0,
seed 42, `max_tokens=2048`, streaming usage and disabled thinking. These
are local final-chat token counts; provider input parity remains a launch
gate. The maximum per request is 321 + 2,048 = 2,369 tokens, inside the
32,768-token benchmark window.

## Bounded dispatch and interpretation

- One strict profile canary precedes the target pair; one follows two
  format-valid target replies, even if either plan is wrong. A failed first
  canary prevents targets. Malformed replies, provider/protocol failure,
  unknown usage, or a cap refusal stop without another target or post-canary.
  A format-valid wrong first plan **does not censor** the file-counter arm.
- Maximum HTTP requests: **2 target + 2 canary = 4**, no retries and **0
  auxiliary**. The target local input sum is 642 tokens; target requested
  output is 4,096, giving 4,738 planning tokens. Two canaries add 124 local
  input and 4,096 requested output; the global planning ceiling is **8,958**.
  These are ceilings on registered requests, not observed provider usage.
- The fsynced private journal reserves a new run directory before credential
  resolution; it records dispatch, request/response hashes, provider usage,
  and named failures without request bodies, headers or keys. Missing usage
  stays unknown and stops dispatch. Exact model echo, stop reason and input
  parity are checked on every response. No existing run directory is reused.
- `provider_block_valid` means both canaries and both target replies passed
  their identity, stop, usage and request gates. `task_feasible` separately
  requires the private correct pair. A complete but wrong paid block remains
  evidence, prints both fields and exits nonzero; it does **not** admit the
  long-source experiment. Synthetic injected tests never set
  `provider_block_valid=true`.

The offline registration can be recomputed without credentials:

```sh
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r19_iceberg_short_offline.py \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b
```

The guarded live CLI is
`scripts/r19_iceberg_short_paid_runner.py --execute --source-root <pinned-source>
--tokenizer-path <pinned-tokenizer> --run-dir <new-private-external-dir>`.
It is reserved for a clean committed producer and independent review. No
Siflow or GPU call was made while preparing this preregistration.

## Clean-commit synthetic verification

At clean producer commit `f0a6f37ff3405acbaecdf8993a2d6ae24cf5edc2`, a
separate injected-SSE full-chain run used the real committed-launch check and
`require_clean_producer`. Only the network transport was replaced. The
[private run directory](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/iceberg-short-synthetic-f0a6f37-v1/)
contains `identity.json` SHA-256
`ed6f4fb1e66588b4bb27589401dcb16006fce54534113c2c6cacf18d03e48225`
and `final.json` SHA-256
`321858aa83378a73c0202aaa4c644d4d4c6942401c3721bdfbea504aaf0f5286`.
It attests the clean producer and exact launch hash, records
pre-canary → data → file → post-canary, four injected requests, zero unknown
usage, and private 0700/0600 permissions. Its `task_feasible=true` is a
synthetic wiring result; `provider_block_valid=false`, and it gives no model
behavior evidence.
