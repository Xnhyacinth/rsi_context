# R9 PostgreSQL 16/17 B source-swap development pair

Status: **offline matched-source B causal witness, not Gate 2 qualification**.
The pair is one proposed PostgreSQL parent lineage with two source variants.
It shares the upstream PostgreSQL lineage with the R8 C development world;
the new version pair does not count as two independent parents. It adds zero
qualified independent parent lineages and contains no scored model run,
Siflow call, GPU work, or PostgreSQL server observation.

## Source intake and exact identity

The [official PostgreSQL 16 `CREATE SUBSCRIPTION` documentation](https://www.postgresql.org/docs/16/sql-createsubscription.html)
does not list a `failover` parameter. The [PostgreSQL 17 documentation](https://www.postgresql.org/docs/17/sql-createsubscription.html)
does: `failover` makes the associated logical slots eligible for standby
synchronization, and its default is false. The
[17.0 release notes](https://www.postgresql.org/docs/release/17.0/) identify
logical failover slot synchronization as a new native capability. The
constructed task asks about *native `CREATE SUBSCRIPTION ... WITH (failover =
true)` support only*; extensions, manual slot recreation, and claims about
real deployment readiness are outside that question.

The official Git remote resolved the lightweight `REL_16_0` tag to
`c372fbbd8e911f2412b80a8c39d7079366565d67` and `REL_17_0` to the
already registered `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`.
Before the new acquisition, `configs/registry.json` gained an exact 16.0
revision and verified Git-revision checksum. The reviewed
`uv run --no-sync python scripts/registry_download.py postgresql-rel-16-0
--destination /volume/pt-dev/qjiu/rsi_context_external` output had
`dry_run=true`, one expected destination under `data/postgresql-rel-16-0`,
the exact commit, no warnings, and one unknown size. A shallow canonical
Git clone of that tag then produced a detached, clean checkout at the
registered SHA. The PostgreSQL License in `COPYRIGHT` permits documentation
reuse with notice retention; each source variant embeds its complete pinned
notice. No mutable branch is used as benchmark material.

`configs/r9_postgresql16_source_manifest_v1.json` records the 16.0
`COPYRIGHT` and complete `create_subscription.sgml` file sizes, SHA256,
Git blob IDs, and raw byte/line span hashes. The preexisting
`configs/r7_postgresql_source_manifest_v1.json` records the 17.0 counterparts.
The 16.0 parameter-catalog span covers lines 100–406 and closes without a
`failover` entry; the 17.0 pinned SGML adds that entry at lines 420–430.
The builder checks complete selected-file SHA256 values before exposing either
variant. Its source `DocumentRef` uses the same canonical repository URL,
neutral title and ID in both worlds; the exact revision remains in the
evaluator manifest and checkout. This avoids a release-tag metadata cue in
the visible view while retaining an independently auditable byte pin.

## Matched world and private legality

Both variants have the same constructed request, prompts, stage and instance
IDs, axes, source-document metadata, first-session review oracle, and
second-session review oracle. The only source-visible difference is the
upstream SGML and COPYRIGHT text. `tests/test_postgresql_source_contrast.py`
compares each initial *actual* `StageView` field after substituting only
source text, and checks that the private legal-plan set is the one changed
evaluator field. The source-free policy takes an identical action transcript
and sees identical prior and current review receipts in both variants before
committing. A `decision-reviewed`
PASS proves only a local review occurred; it gives no feature-support answer.
The runner checks the private legal-plan set only after the `act_verify`
stage. Both proposed actions receive the same PASS review oracle, so
predecision action receipts cannot reveal which version's action is legal.

The first session reads the complete pinned SGML and finalizes a generic
`source_review` after an environment-issued `review-complete` PASS. A fresh
policy process starts session 2 with bounded carry and persistent sandbox
state. The same question asks whether the constructed project may use native
`WITH (failover = true)`; the legal action is `defer-native` under the 16.0
parameter catalog and `configure-native` under the 17.0 catalog. The second
gate also requires the earlier review's PASS-before-finalize provenance and
a current subject-bound review receipt. All sandbox record names, receipts,
and actions are constructed, not observations of a PostgreSQL deployment.

Canonical JSON SHA256 for each `LifecycleInstance.to_dict()` (sorted keys,
compact separators, UTF-8, `ensure_ascii=False`):

| Source | Session 1 | Session 2 |
| --- | --- | --- |
| REL_16_0 | `81ebed5cf1bad4fa96dd6669a425c82acd481fc04b15c09d32ad8a98b60` | `8fa63480b3d0f18111a275e6090de1ad3d9eca0bf6f8287936a221f3c25e06e2` |
| REL_17_0 | `06da6ec51aa05fd0df21320e11d38949189de98a6c8526f7b6c2a5288bac98cc` | `6d85c6613bfdbb896f189852a871dec5ff14ce719b87d901d517ba29d136713f` |

## Frozen offline policy vectors

One unchanged scripted policy parses SGML parameter terms in session 1 and
carries the supported-parameter result through the process reset. Two
unchanged source-free controls choose a constant action. Each row gives
the two-session PASS vector under 16.0 and 17.0, respectively:

| Frozen policy / intervention | REL_16_0 | REL_17_0 | Later plans |
| --- | --- | --- | --- |
| Source-aware SGML term parser | `[PASS, PASS]` | `[PASS, PASS]` | `defer-native`, `configure-native` |
| Source-free, always configure | `[PASS, FAIL]` | `[PASS, PASS]` | `configure-native`, `configure-native` |
| Source-free, always defer | `[PASS, PASS]` | `[PASS, FAIL]` | `defer-native`, `defer-native` |
| Source-aware policy, both upstream documents withheld | `[PASS, PASS]` | `[PASS, FAIL]` | `defer-native`, `defer-native` |
| Source-aware policy, prior finalize omitted | not run | `[FAIL, FAIL]` | later gate rejects absent prior award |

This B task is a source-swap intervention with byte-identical non-source input and
opposite source-supported legal answers. It establishes deterministic
source-to-action causality for the *scripted witness* and rules out a constant
source-free action passing both versions. It does not establish that a fixed
reader actually uses the source or that the long context creates difficulty:
the witness is a parser, the two source files are roughly 23–25 KB, and
final-chat token offsets and model error rates are unmeasured. The test may
also be easier than the original C task because the constructed question
names the relevant SQL option. Before any Gate 2 claim, run a frozen reader
on both source variants with identical prompt and worker configuration,
source-withheld and source-swapped controls, and record full usage and answer
vectors. Count both variants as **one PostgreSQL parent**, never two.

The replayable registry dry-run snapshot is
`artifacts/rsi-core-v1/r9-postgresql16-dry-run-20260926.json` (SHA256
`c1093c2709a3467e3d2fc5c6bc97d1f4b5484955b59942052343d10cb22e5ec4`).
