# R18 source-dependency and calibration execution ledger

Status: **in progress**. The R18 branches started from clean
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
