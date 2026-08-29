# Operations

## Environments

The core package uses the project-local `.venv` managed by `uv`. Optimizers
with conflicting dependency graphs run in separate project-local environments
and communicate through JSON artifacts. The vLLM server and KVPress tracks have
independent locks; neither may upgrade the core environment in place.

## GPU ownership

Every GPU command on this host must be wrapped so the resident hold process is
restored even after a crash:

```bash
bash /workspace/wynckeliao/ops/gpu/hold.sh wrap 0,1 -- <command>
```

## Model canaries

The primary Qwen3.6-27B canary progresses through 8K, 128K, and 262K with
prefix caching disabled. The registered dense-model profiles use one TP8 engine
on the eight-H200 host; data parallelism is fixed at one. Llama-3.3-70B is a
128K TP8 confirmation reader and requires accepted gated-model access.

Never use an unpinned model or tokenizer revision. Do not use unofficial RoPE
scaling for the confirmation model. Record engine-reported KV capacity before
each promoted configuration.

Qwen3.6 thinks by default. Short-answer evaluation must send
`chat_template_kwargs={"enable_thinking": false}` and record that field in the
reader identity. The default-thinking 512-token-cap run is an invalid protocol
probe, not a comparable benchmark result.

`scripts/serve_dry_run.py` emits a `profile_hash`; copy that digest into the run
spec. Construct model-backed readers with `OpenAICompatibleReader.from_run_spec`
and pass the loaded `ServingProfile` and `RegistryEntry`. The factory rejects
profile hash, model ID/revision, tokenizer revision, model length, or seed drift.
The default transport is for an allowlisted local vLLM endpoint, ignores
environment proxies, refuses all redirects, limits responses to 1 MiB, and
rejects responses without token usage.

Local vLLM and remote providers use the same `OpenAICompatibleReader` transport.
Only the frozen API profile and resolved endpoint differ. The registered local
profile explicitly permits a missing API key; it reads only
`RSICONTEXT_LOCAL_VLLM_ENDPOINT` and never needs a dummy credential:

```bash
export RSICONTEXT_LOCAL_VLLM_ENDPOINT=http://127.0.0.1:8017/v1/chat/completions
uv run python scripts/api_canary.py local-qwen3.6-27b-128k-bf16-h200x8 \
  --repetitions 5 --output artifacts/api-canary/<unique-local-record>.json
```

Generate and review the hold-wrapped server command with
`scripts/serve_dry_run.py` before starting vLLM. Formal local runs additionally
require `OpenAICompatibleReader.from_run_spec` and the runtime/isolation
attestation; passing the compatibility canary alone is insufficient.

The registered Tencent Copilot profile uses the same proxy/redirect/size
controls but requires strict SSE. Run `scripts/api_canary.py` before and after
each API campaign. The record contains endpoint/profile/model/usage/latency but
never the credential. A missing provider revision is recorded as `null` and
prevents treating the API alias as an immutable checkpoint.
The canary also lists HTTP-observable fields and explicitly marks GPU seconds,
peak HBM, KV capacity, prefix-cache state, and scheduler state unobservable.
Any answer, usage, or returned-model drift invalidates that API batch.

KV capacity, HBM, GPU time, prefix-cache counters, and scheduler state are runtime
instruments for cost and reproducibility. They are frozen controls in the semantic
policy track, not researcher-editable objectives. Run numerical KV allocation as a
separate track only; never combine it with semantic-policy discovery scores.

## Download policy

Installation downloads only development dependencies. Model, dataset, and
third-party source downloads are explicit registry operations with a dry-run
default. Before a download, verify free space, access requirements, revision,
license, and destination. Afterward record checksums and do not silently follow
an upstream `main` branch.
