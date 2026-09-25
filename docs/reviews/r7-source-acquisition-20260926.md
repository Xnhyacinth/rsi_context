# R7 pinned source intake, 2026-09-26

All R7 worktrees began at `main@186cc4f9c331f1db9ca008f23c8650902026bd64`
with `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`.
Each ran `uv sync --extra dev --frozen --link-mode copy` before edits. The
PEP, PostgreSQL, broker, and integration worktrees own separate branches.
Neither new source is a qualified benchmark parent or a scored world.

## Registry and reviewed acquisition plans

The registry now pins the [Python PEP repository](https://github.com/python/peps)
at `6822259db9c95f02da739b3e2830a4aa1ae35134` and the
[canonical PostgreSQL source repository](https://git.postgresql.org/git/postgresql.git)
at `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`. Both are `git` source
entries with the exact commit in `revision` and `checksum.value`. Registry
SHA256 is `5d9f26873e0a677be2475e60ec877f964752c7436f20c01c8d1377612c0e0862`.

Before each acquisition, `scripts/registry_download.py` printed a reviewed
`dry_run=true` plan for the exact registered URL, commit, and isolated
`rsi_context_external/data/<id>` destination, with no warning and one unknown
size. The ignored raw plans are:

| Source | Dry-run artifact | SHA256 |
| --- | --- | --- |
| PEP | `artifacts/rsi-core-v1/r7-pep-source-dry-run-20260926.json` | `e52be0b7d68cf507187897ede249456e7359f6cc0858a43304178ea9319e67fa` |
| PostgreSQL | `artifacts/rsi-core-v1/r7-postgresql-source-dry-run-20260926.json` | `7da8afd0dd1038b76a2a1256bbde6feaf109bb51ded9da723f838665f1959554` |

Both checkouts are detached at the exact registered commits and have empty
`git status --porcelain`. The PEP checkout is 34,587,685 bytes locally; the
PostgreSQL checkout is 167,486,875 bytes. The canonical PostgreSQL server did
not honor Git's blob filter, so a shallow `REL_17_0` fetch was used and its
HEAD was checked against the independently resolved commit before any material
was recorded. Neither checkout follows a mutable branch for an experiment.

## Selected-file and span identity

The portable per-file Git blob IDs, byte lengths, SHA256 values, line ranges,
raw byte offsets, and span SHA256 values are committed in
`configs/r7_pep_source_manifest_v1.json` (SHA256
`948459e9b719eb107327d999545c21471ce5b417eff4dd83a561a6661a7391c4`)
and `configs/r7_postgresql_source_manifest_v1.json` (SHA256
`130419a8608030d2ed3ee969327cae8171f9d9fdd15e875255a340951733f57c`).
`tests/test_r7_source_manifests.py` checks the registry pins, clean detached
HEADs, file bytes, Git blob IDs, and exact raw spans when both source-root
environment variables point to the checkouts. The focused run passed 30 tests.
The generated local evidence ledger
`artifacts/rsi-core-v1/r7-source-acquisition-20260926.json` records those
checks per file and span, with SHA256
`f224b9862806df604528e75303825985116480771a5720d14d8d2556394de549`.

The selected PEP 1, 621, and 639 files each state public-domain/CC0 terms;
the conclusion applies only to those files. PEP 621 and 639 point to maintained
PyPA specifications and are historical source context, not a current packaging
compliance oracle. The pinned PostgreSQL `COPYRIGHT` grants documentation use
with notice retention. Its 17.0 SGML describes asynchronous slot sync and
standby readiness using `synced AND NOT temporary AND NOT conflicting`; the
mutable current PostgreSQL 17 HTML wording differs. The constructed C task
must use the pinned wording and retain the license notice where required.

No PEP B or PostgreSQL C instance has passed a source-to-action causal test,
final rendered tokenizer-position audit, fixed-reader difficulty test, or
independent-parent qualification. No Siflow API or GPU was used. The R3 v3
preflight fixes the old registry SHA and is retained unchanged as a historical
snapshot; a new versioned preflight must freeze these additions before any
reported experiment uses them.
