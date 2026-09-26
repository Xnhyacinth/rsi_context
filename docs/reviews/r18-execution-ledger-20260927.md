# R18 source-dependency and calibration execution ledger

Status: **KEP paid calibration complete; Iceberg remains an unqualified offline
candidate**. The R18 branches started from clean
`main@781565c9a4f4933f4af83d9e7dcf9a3f8024ef5c`; the original
untracked `logs/` in main remains untouched. Each worktree has its own
project-local environment synced from the unchanged `uv.lock` SHA-256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
with frozen resolution and copy link mode.

| Branch | Owner and bounded task |
| --- | --- |
| `work/r18-registry` | Integration owner: register the pinned Iceberg source, review the acquisition dry run, and audit acquired bytes. |
| `work/r18-iceberg` | Independent worker: offline two-session Iceberg task construction and equivalent-rule audit; no paid call. |
| `work/r18-kep` | Independent worker: prospective short-input KEP feasibility calibration and guarded, bounded Siflow launch proposal. |
| `work/r18-integration` | Integration owner: reconcile task and source contracts, review code, decide paid admission, run full gates, merge and clean branches. |

The Iceberg registry addition and byte audit are committed and merged into
the integration branch. The current `configs/registry.json` SHA-256 is
`16807ab8ae22734f2a90cc64df843587a9b290bdf8b4dba79f154efabc81c934`.
The [reviewed dry-run plan](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/iceberg-registry-plan.json)
has SHA-256 `bcedb0cb54755a6ba6ccce840e2ce46b6e1c03ea4c3b3a5f2cffae90509b8203`.
The official source checkout is clean and detached at commit
`071d5606bc6199a0be9b3f274ec7fbf111d88821`; its selected spec and
license bytes, blob IDs, spans, and hashes are in the
[source byte audit](r18-iceberg-source-byte-audit-20260927.md).

The Iceberg branch must establish an answer-changing source contrast without
changing the non-source request, metadata or receipt behavior, then test
source-free, identity-only and fixed-default controls. A constructed rule
flip is a causal probe, not another authentic revision. The KEP branch tests
whether a prospective reader can carry the actual ordered-prefix rule and
perform the arithmetic in short input. Its result cannot repair the R16/R17
post-hoc evidence or by itself qualify a long-source parent. Any paid block
requires committed prompt/material hashes, final-chat geometry, clean
producer, canary, request cap, provider usage journal and review before
credential resolution.

No R18 model or GPU calls had been made when this ledger was opened. The
researcher effective-update-rate pretest still lacks a trusted host jail and
live worker adapter; see the [R17 runtime audit](r17-researcher-runtime-and-budget-audit-20260927.md).

## R18 outcome and next admission

The [KEP paid calibration](r18-kep-short-rule-calibration-result-20260927.md)
completed four target requests and two exact-profile canaries with **1,534
provider input / 78 output tokens**, zero unknown usage and no auxiliary
calls. The explicit short authentic rule did not produce a correct membership
or effective-request answer. This fails the prospective short-task feasibility
screen for the frozen Qwen reader and prompt; no further KEP source-dependency
spend is justified from these results. The constructed new-Pod oracle and
scope limits are in the result note.

The [Iceberg offline candidate](r18-iceberg-row-scan-candidate.md) uses a
contiguous, authentic 118,725-byte slice of a pinned 184,975-byte spec and
four explicitly constructed rule edits. Its source-conditioned private action
changes while the fixed request and procedural receipts stay matched.
Offline tests and exact [local chat geometry](r18-iceberg-geometry.json)
establish construction and a 24,883-token authentic S1 input, not a model
dependency result. The full-file prompt is 42,169 tokens and misses the 32K
benchmark window. A next paid screen would need a new committed launch and
request hashes, a real two-session fixed reader with controlled source
reread, source-free and identity-only model controls, two reader families,
provider usage accounting and an explicit rule for mixed S1 replies. No
Iceberg provider or GPU call was made in R18.

## Integration verification and historical launch behavior

The first full branch-coverage run reached **1582 passed, 16 skipped,
6 failed, 80.55% coverage**. Its
[preserved log](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/full-pytest-integration.log)
has SHA-256 `eac2714468e5b03d76ca89c6c171dbcebc866652a8f22c858e08b78af5f68445`.
All six failures were old R16/R17 synthetic full-chain tests expecting their
immutable launch manifests to run after the R18 registry addition. Both
historical `_read_launch()` functions actually refused at the first causal
check: `configs/registry.json` differs from the bound old SHA-256
`e063e0c4291de8e560d5928ce2c847b003ede8c0b2bd69a85265df0707a1a6a7`.
No HTTP request was attempted. The historical launches and producer files
remain unchanged. The tests now run those chains only against their exact
bound registry, and two new regressions prove current-registry refusal
before credential resolution or HTTP dispatch.

The clean rerun passed **1584 tests, 22 skipped, 80.54% branch coverage**;
the [full pytest log](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/full-pytest-integration-rerun.log)
has SHA-256 `c972e6573fdf48ea9aac1fa6d6e9babb96af4456cd76be0784180559095540a1`.
Fifteen skips are the host jail trust gate at non-root-owned `/usr/bin`, one
is live API smoke without a configured endpoint, and six are the historical
synthetic chains. The suite used the pinned source/tokenizer roots, a dummy
API key and an unset `SIFLOW_BASE_URL`; it made no provider call.

Repository `ruff check .` passed. Configured strict mypy passed **398 source
files**. Bandit over `src scripts` reported the unchanged **81 LOW, 2 MEDIUM,
0 HIGH** baseline and no R18/Iceberg file; its
[JSON report](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/bandit-integration.json)
SHA-256 is `6a0298c9d76e506442db4b11982945acd025c66255ce231ee09933713739891c`.
Independent science review cleared Iceberg for offline merge only.
`codex review --base origin/main` found no actionable defect in the integrated
branch; its [report](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/codex-review-integration.log)
SHA-256 is `593106b96391b2ee04c46c21512d74b8e82dc2fc90c34eb037c7a3721fa49713`.
A separate `codex review --commit df91475124e68856b4fe7004fe6dd7b7c5a23a7e`
found no actionable issue in the historical-test fix; its
[report](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/codex-review-history-tests.log)
SHA-256 is `b70ce3ef30e74757f3a73a60ca45f9605a9042500986d1aa291df0970fa9d2b5`.
An additional, nonrequired `ruff format --check .` found 18 files needing
formatting, including four R18 KEP files. Three of those are byte-bound by
the already executed paid v1 launch; they were not rewritten after evidence
collection. A future formatted revision would need a new launch and hashes.

## Why these screens precede a benchmark score

[RULER](https://arxiv.org/abs/2404.06654) adds multi-hop tracing and
aggregation to retrieval probes, while
[LongMemEval](https://arxiv.org/abs/2410.10813) separately tests multi-session
reasoning and knowledge updates. Their task categories motivate the
**inference** that RSIBench must show both source-conditioned rule application
and a changed later action across sessions; a long document or correct fact
lookup alone does not establish that behavior. The more direct policy-edit
comparison and related-work boundaries are in the
[R14 design note](r14-related-work-design-20260926.md).

R18's development sequence is: (1) show the prospective KEP reader can apply
the rule when it is short and explicit; (2) validate an Iceberg authentic
versus constructed-rule contrast, source-free/identity-only controls and
non-source invariance offline; (3) if those gates pass, freeze a small paid
fixed-reader screen with exact final-chat token positions, two reader
families and provider usage; (4) only then consider this parent for a future
matched policy-edit experiment. Report parent-project and trajectory units,
not individual decisions or alternate views as independent samples.
