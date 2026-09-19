# RSIBench-Context

RSIBench-Context is a replayable benchmark for testing whether a coding
researcher can discover and retain better long-document context policies while
the reader model, decoding stack, and evaluator remain frozen.

The implementation follows the protocol in
[`RSIBench-Context-research-report.md`](RSIBench-Context-research-report.md).
The normative project question, bounded-RSI definition, resource contract, task
ladder, and claim boundary are in
[`docs/study-contract.md`](docs/study-contract.md).
The paper-scale A2 claim and difficulty contract are pre-registered in
[`docs/a2-preregistration.md`](docs/a2-preregistration.md); the intended paper
contribution is the protocol conjunction in
[`docs/paper-contribution.md`](docs/paper-contribution.md), and the gated task,
baseline, analysis, and transfer sequence is in
[`docs/execution-roadmap.md`](docs/execution-roadmap.md). Current model-backed
records remain qualification evidence.
It currently includes the bounded policy API, deterministic evaluator and
causal controls, immutable policy lineage, calibrated researcher manifests,
Codex/Claude batch adapters, a conservative policy security audit, finite-search
scaffolding, private counterfactual generation, and validated model
and baseline registries. The local OpenAI-compatible reader rejects redirects
and environment proxies and requires endpoint-reported token usage. Large model
and dataset downloads are explicit and never happen during installation.

## Quick start

```bash
uv sync --extra dev
uv run rsicontext doctor
uv run rsicontext toy-campaign --output artifacts/toy
uv run pytest --cov=rsicontext --cov-branch
```

The frozen open-reader stack is an optional, separately pinned environment:

```bash
uv sync --extra dev --extra serve
```

`vllm==0.25.1` is pinned because serving-version drift changes model support,
tokenization, scheduling, and memory behavior. The default harness installation
remains dependency-light and does not install CUDA packages.

Use `/volume/pt-dev/qjiu/wynckeliao-env/ops/gpu/hold.sh wrap ...` for every
GPU-backed job on the shared host. See `docs/experiment-protocol.md` for the frozen variables,
split semantics, and promotion rules.

The toy campaign deliberately produces scores `0 → 1 → 0`: lexical retrieval
discovers the answer-bearing chunk, a later tail policy regresses, fixed-policy
replay has zero variance, and the benchmark-controlled selector retains round 1.
It qualifies the RSI process without making any claim about model quality.

## External baselines and models

Review acquisition and serving commands before running them:

```bash
uv run python scripts/registry_download.py ruler-v1 helmet longmemeval-v2 gepa recuris
uv run python scripts/registry_preflight.py qwen3.6-27b llama-3.3-70b-instruct
uv run python scripts/serve_dry_run.py qwen3.6-27b-128k-bf16-h200x8
```

The registry pins Qwen3.6-27B, Llama-3.3-70B, RULER, HELMET,
LongMemEval-V2, GEPA, MCE, Meta-Harness, Recuris, RLM, and KVPress to reviewed
revisions.
Acquisition scripts are dry-run by default. This checkout has verified pinned
Qwen3.6-27B weights, LongBench-v2, and LongMemEval-V2 data under ignored local
paths, plus the registered RULER/HELMET/LongMemEval/GEPA/Recuris source
checkouts. The Llama reader is still blocked by gated Meta access; RULER and
HELMET execution still requires their isolated upstream dependency
environments.

## Private prepared-data publication

Prepared researcher-visible data is published separately from evaluator-only
gate/sealed assets. The initial HF package is deliberately a non-benchmark
schema-smoke artifact containing one project-authored synthetic fixture. Build
it only from a clean, committed revision:

```bash
uv run python scripts/build_hf_dataset_release.py \
  --source-revision <40-character-git-sha>
```

The allowlist is `configs/hf_dataset_release.json`. The builder refuses raw
results and sources outside `tests/fixtures`, then emits a dataset card,
machine-readable provenance manifest, and SHA-256 list under ignored
`artifacts/hf-release/`. Official benchmark archives, API responses, and all
gate/sealed records are excluded. A private HF repository is a distribution
control, not the evaluator's physical isolation boundary.

## Tencent API replication reader

The `tencent-copilot-hy3-ioa` profile reads its endpoint and key from
`COPILOT_BASE_URL` and `COPILOT_API_KEY`; credentials are never stored in
artifacts. The endpoint requires SSE, so the reader validates the returned model,
one final usage object, and `[DONE]` before accepting an answer.

```bash
uv run python scripts/api_canary.py tencent-copilot-hy3-ioa \
  --repetitions 5 \
  --output artifacts/api-canary/<unique-record>.json
```

Run this from a shell that already exports the two variables; never copy their
values into a command, config, or artifact. The 2026-08-14 five-replay artifact
was answer/model/usage stable. A 2026-08-29 three-replay preflight returned the
same model and input usage but varied between `amber.`/3 output tokens and
`amber`/2, so that batch failed the exact replay gate. The provider also exposes
no immutable model revision. `hy3-ioa` is therefore an API replication/debug
reader, not a replacement for the pinned Qwen paper backbone. See
[the API experiment plan](docs/api-hy3-experiment-plan.md) for length gates, the
RSI matrix, long-horizon transfer, stop rules, and record layout. The bounded
[2026-08-29 diagnosis](docs/hy3-ioa-diagnostic-2026-08-29.md) separates working
transport/8K retrieval from the failed immutable-revision requirement.

Initial 8K/32K length replay, fixed-policy dynamic-range qualification, and a
visible-only autonomous micro run have completed. Remote candidate replay showed
that one apparent discovery was within provider noise, so `hy3-ioa` remains a
replication reader rather than the noise-floor anchor. See the
[preliminary analysis](docs/preliminary-results-2026-08-14.md) and run the
reproducible probes with:

```bash
uv run python scripts/api_length_canary.py tencent-copilot-hy3-ioa \
  --lengths 8192 32768 --repetitions 3 --output artifacts/api-length/<unique>.json
uv run python scripts/api_policy_pilot.py tencent-copilot-hy3-ioa \
  --output artifacts/api-policy-pilot/<unique>.json
```

## Pinned local Qwen qualification

The reproducibility anchor is Qwen3.6-27B revision
`1b559cf7215ebe67ff10758e14f6293ba883223b`, served by vLLM 0.25.1 with BF16
weights/KV, TP8, prefix cache disabled, seed 42, and the official
`chat_template_enable_thinking=false` request switch. The local dynamic runner
records both API-profile and serving-profile hashes:

```bash
export RSICONTEXT_LOCAL_VLLM_ENDPOINT=http://127.0.0.1:8017/v1/chat/completions
uv run python scripts/api_canary.py local-qwen3.6-27b-128k-bf16-h200x8 \
  --repetitions 5 --output artifacts/api-canary/<unique-local-record>.json

uv run --no-sync python scripts/local_dynamic_gate.py \
  --output artifacts/local-dynamic-gate/<unique>.json

uv run --no-sync python scripts/autonomous_dynamic_pilot.py \
  --output results/autonomous-dynamic/<unique> \
  --local-serving-profile qwen3.6-27b-128k-bf16-h200x8 \
  --researcher-executable /volume/pt-dev/qjiu/.npm-global/bin/codex \
  --researcher-model gpt-5.6-sol --rounds 2
```

On the four-item visible qualification panel, the corrected-protocol real
researcher trajectory was H0 `0.25` → round 0 `0.00` → round 1 `0.50`. The
selector rejected round 0 against H0 and selected round 1. Both candidates
replayed five times without an item, prediction, score, or token-usage change.
This is visible-only autonomous-discovery qualification; it is not a paper-scale
estimate or evidence of gate/sealed transfer. The earlier `-03` trajectory is
retained as legacy evidence because it predates the H0-initialized selector.

## Hard-panel stop decisions

The first target-tokenized hard-panel calibration is preserved at
[`artifacts/hard-baseline-gate/qwen-tokenized-disposable-v1.json`](artifacts/hard-baseline-gate/qwen-tokenized-disposable-v1.json).
Its nominal 32,768 semantic words measured 53,517--53,720 Qwen tokens. Under a
true 8,192-token policy cap, head/head-tail/lexical scored
`0.250/0.375/0.875`; no-context scored `0`, and gold-only, bounded-oracle, and
unbudgeted full context each scored `0.875`.

This is a pre-A2 no-go, not a positive benchmark result. Compositional retrieval
was saturated by lexical selection, while dense comparison remained at `0.75`
even with complete evidence.

The native target-token v3 follow-up is preserved at
[`artifacts/hard-baseline-gate/qwen-v3-tokenized-disposable-v1.json`](artifacts/hard-baseline-gate/qwen-v3-tokenized-disposable-v1.json).
It generated 32,730--32,750 actual Qwen tokens. Compositional now has useful
dynamic range (head `0.25`, head-tail `0.50`, lexical `0`, oracle/full `1.0`),
but dense comparison scored `0` under gold-only and bounded-oracle and only
`0.25` under full context. Overall bounded-oracle accuracy is `0.50`, below the
pre-registered `0.80` floor. A2 therefore remains stopped while the dense task,
matched policy space, and physical isolation are repaired.

The dense-repaired v3b follow-up is preserved separately at
[`artifacts/hard-baseline-gate/qwen-v3b-tokenized-disposable-v1.json`](artifacts/hard-baseline-gate/qwen-v3b-tokenized-disposable-v1.json).
It retained native 32K target-token accounting and scored head/head-tail/lexical
`0.250/0.500/0.375`, no-context `0`, and gold-only/bounded-oracle/full-context
`1.0`. The reader/task floor is therefore repaired and the visible panel has a
real context-allocation signal. This is still a partial difficulty screen, not
an A2 result: causal removal/counterfactual checks, larger-sample strata,
replays, executable matched controllers, and formal hidden-item isolation
remain pending. Head-tail and lexical disagree on 3/8 items, so the disposable
disagreement threshold itself is already met.

The restricted common grammar now has 32 configurations. On the repaired panel
with the pinned Qwen tokenizer, compositional has 32 profile-local behavior
classes and dense has 22, so both exceed the minimum of 20. Matched controllers
must sample these class IDs without duplicates. This is only a structural pass:
all 32 policies still need real-reader scoring because a graph policy may
saturate the current compositional task.
The final control suite must also include an exhaustive gold-aware selector over
those classes; Random-5 and Sequential-search-5 alone do not match the free
visible-gold information available to a researcher.

The complete grammar screen is recorded at
[`artifacts/hard-baseline-gate/qwen-v3b-causal-replay-disposable-v1.json`](artifacts/hard-baseline-gate/qwen-v3b-causal-replay-disposable-v1.json).
It made 344 successful calls. Full/gold-drop/counterfactual scores were
`1.0/0.0/1.0`, and the strongest policy replayed five times at 0.75 with zero
observed variance. However, 11 policies scored 1.0 on compositional and the top
two policies had zero item disagreement. This is a decisive A2 no-go: retain
dense, replace compositional, and rerun the complete grammar screen before any
researcher trajectory.

The Repair A generator keeps five gold statements and isomorphic competing
two-hop terminals, without `retired` status cues or a hops=3 grammar expansion.
Structural tests lock hops=0/1 RANK missing gold C, hops=2 RANK recovering C
only on a proper subset, RANK vs coverage disagreement, and hops=0 MMR not
always packing C. Dense is unchanged. This does not replace the Qwen 32-policy
rescreen, matched A2 factorial, or physical isolation. The matched-controller
surface (Hamming-1 sequential search, gold-aware recall, byte-identical
`RoundFeedback`, spend caps, restricted V1 keys, and A2 launch refusal) is now
executable as code; launch remains blocked.

Gate and sealed decoy bodies now use distinct key-value/review grammars rather
than sharing the visible templates behind different wrappers. This closes the
wrapper-only transfer shortcut structurally; it does not expose or score hidden
items, and future hidden fingerprints must be frozen inside the isolated
evaluator.

## Researcher boundary

The initial editable artifact for restricted A2 is `policy/seed.py`. The open-S
harness track starts each trajectory from a byte-identical `seeds/open_s_v1/`
copy; see `docs/open-s-harness.md` and the frozen visible card
`docs/open-s-visible-scenario.md`. Open-S pack budget is the frozen reader
window, not 8K. It is a separate leaderboard. A researcher
may change only Python files in a staged policy directory and must submit a
manifest matching `schemas/manifest.schema.json`. `PolicyAuditor` is a fail-closed static gate,
not a proof that arbitrary Python is safe to execute. It is a precheck before
the isolated evaluator required by formal gate/sealed runs. Host-level namespace
observations do not prove that the scored candidate worker cannot read hidden
data, so the current preflight deliberately cannot issue `formal_eligible=true`.
That decision must be issued by a locked policy-worker launcher on a separate
container-enabled worker or node.

This host cannot currently provide that boundary. Rootless namespaces and
read-only bind mounts work for qualification, but there is no Podman/bwrap,
Docker daemon, delegated writable cgroup, or minimal read-only container rootfs.
Formal gate/sealed runs therefore require a separate container-enabled worker;
the host runner remains visible-only.

The deterministic counterfactual generator is an evaluator-harness fixture. It
uses opaque policy-facing IDs and disjoint natural two-hop templates, but its
Python object is not a confidentiality mechanism and is not the paper's private
sealed set.

## What remains before a paper-scale run

- complete official RULER, HELMET, LongBench-v2, and long-horizon evaluators (the
  LongMemEval-V2 text-only offline compiler is implemented, but has no score yet);
- build and independently host the 1,200-item audited private sealed set;
- execute every formal gate/sealed item and replay in a non-root, no-network,
  read-only-rootfs container with cgroup-owned process cleanup, rather than
  relying on interpreter freshness or host namespaces;
- emit a runtime manifest covering the GPU, vLLM/CUDA stack, scheduler, shard and
  batch assignment, and environment lock;
- attest that the live endpoint was started from that runtime manifest; configured
  model and serving hashes alone are declarations, not runtime proof;
- enforce aggregate wall-time and call-ledger budgets in the paper-scale runner
  (the current single-call reader only caps its request timeout);
- run the replicated 2-researcher × 2-task-profile × 2-research-seed × 5-round
  pilot before committing to the 64-trajectory main matrix;
- apply the native target-token generator and final rendered-prompt accounting
  to every A2/128K/256K cell;
- add GEPA/MCE/Meta-Harness optimizer adapters in their isolated environments.

Current model-backed records are visible qualification evidence only. They do not
support a sealed transfer, cross-researcher discovery rate, or long-context SOTA
claim.
