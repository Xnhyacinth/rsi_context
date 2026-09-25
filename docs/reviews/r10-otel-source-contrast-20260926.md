# R10 OpenTelemetry 1.24/1.43 B source-swap development pair

Status: **second independent source-parent lineage under development, not a
qualified benchmark parent or measured reader result**. This is one
OpenTelemetry lineage with two matched source variants, separate from the
PostgreSQL lineage. It adds **zero qualified independent parents**. No Siflow
API, GPU, live database, or telemetry runtime was used.

## Source and task boundary

The official [v1.24.0 database client span convention](https://github.com/open-telemetry/semantic-conventions/blob/cafda7127683b7f667e27cdbd3220510b6f998c9/docs/database/database-spans.md#L188-L200)
marks `db.statement` Recommended in the call-level attribute table. The
official [v1.43.0 database client span convention](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/database-spans.md#L112-L132)
marks `db.query.text` Recommended in the span-definition table. Both files
also contain additional migration and sanitization guidance. The official
[v1.26.0 changelog](https://github.com/open-telemetry/semantic-conventions/blob/v1.26.0/CHANGELOG.md#v1260)
explicitly records the `db.statement` to `db.query.text` rename. The constructed
request explicitly says **new instrumentation**, one placeholder-parameterized
SQL SELECT, exactly one query-text attribute, and adoption of the supplied
convention. It excludes existing-instrumentation migration and dual emission.
The constructed request does not name either candidate attribute; the exact
key must come from the source table.
The source distinction is therefore the recommended attribute in the supplied
table, not a claim that all real OpenTelemetry instrumentation must emit only
one field. Review records, receipts, action names, and legality checks are
constructed sandbox material.

The canonical upstream remote resolved the lightweight `v1.24.0` tag to
`cafda7127683b7f667e27cdbd3220510b6f998c9`, matching the local tag;
`v1.43.0` remains at the registered
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`. Before acquiring the new
checkout, `configs/registry.json` gained the exact revision and verified
Git-revision checksum. The reviewed registry dry-run gave one expected
destination (`data/otel-semconv-v1.24.0`), `dry_run=true`, no warnings and one
unknown size. A shallow tag clone was then detached at that exact commit and
verified clean. The pre-existing 1.43 checkout was also detached and clean.
`configs/r10_otel_source_contrast_manifest_v1.json` records both complete
database files, complete Apache-2.0 LICENSE files, Git blobs, sizes, SHA256,
and raw byte/line span hashes. The builder refuses changed selected bytes.
The full license text is exposed alongside each source document. The manifest
contains no machine-local paths.

## Matched action and receipt chain

Both variants use the same instance IDs, prompts, stages, request, neutral
source-document metadata, review oracles, and initial visible StageView fields
apart from the upstream file bytes. Source revisions stay in evaluator-side
manifests; neither visible source URL nor document title names a version. The
private legal set alone changes with the supplied convention.

Session 1 exposes the full source and accepts a generic `convention_review`
only after a `review-complete` PASS receipt. A fresh policy process starts
session 2 with bounded carry and persistent project state. The later
`query_attribute_plan` requires that earlier verified finalization, its own
subject-bound `plan-reviewed` PASS receipt, and the source-supported plan.
Both candidate plans receive identical PASS review receipts; those receipts
do not reveal which attribute is correct. The actual commit precondition
checks source-conditioned legality only after the review/action path.

| Frozen offline policy/intervention | v1.24.0 sessions | v1.43.0 sessions | Later plans |
| --- | --- | --- | --- |
| Parse the Recommended query-text row, carry its field | PASS/PASS | PASS/PASS | `db.statement`, `db.query.text` |
| Always choose `db.statement` | PASS/PASS | PASS/FAIL | same action |
| Always choose `db.query.text` | PASS/FAIL | PASS/PASS | same action |
| Swap only upstream document text, retain each private oracle | PASS/FAIL | PASS/FAIL | action follows swapped text |
| Withhold both upstream documents | PASS/FAIL | PASS/FAIL | no action |
| Erase carry with no reread | PASS/FAIL | PASS/FAIL | no action |
| Omit earlier verified finalization | not run | FAIL/FAIL | later gate rejects missing prior record |

The source-aware parser reads table rows and chooses the unique Recommended
query-text candidate; it has no revision-specific answer map. Tests compare
every initial visible StageView field with only source text replaced. The
source-free policy has the same action and receipt transcript across versions
but cannot pass both. This establishes a **scripted source-to-action contrast**
and separate prior-receipt provenance. The no-carry test is a **no-reread arm**;
the full tool surface can permit metered registry reread, so this does not
claim that carry is necessary across all allowed policies. The initial review
oracle passes in both worlds; it tests provenance, not source understanding.

Canonical UTF-8 compact sorted-key JSON SHA256 for `LifecycleInstance.to_dict()`:

| Source | Session 1 | Session 2 |
| --- | --- | --- |
| v1.24.0 | `8f4e16611e0a3157569ed5b8d7bf57b5c18657ec82811051b25b418ab2decb2a` | `2c5481db051b34c2523b2f4cc869ccefe9bf18aeb9c9d1283d9d722433cf6366` |
| v1.43.0 | `30365b2fac09f007ca8f4e78168546a37a4fc71264fac8d27dd99abaa7289ae7` | `0d588f0e3ac3eeff642d19e7d818b439e713e20466a54c2a7a1db1d3436deb38` |

Builder SHA256: `8359eacf6d0462ef18ac3bef6aab6f3a65c243f18e16c469344982e2aa1b723a`.
Manifest SHA256: `2e7ff401215164e06fd3bd819d6d99e51bf94d60ecb75241397e040647bd884b`.

Replay with:

```bash
RSICONTEXT_OTEL124_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.24.0 \
RSICONTEXT_OTEL_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0 \
uv run --no-sync pytest -q tests/test_otel_source_contrast.py
```

This pair is intentionally not admitted to any scored split. Final rendered
worker-chat token counts and evidence offsets, fixed-reader difficulty,
source-swap reader behavior, and researcher valid-update rate remain unmeasured.
The older convention is Experimental and the newer one Stable, so a measured
reader may exploit status or version-era cues within the source; a stronger
question must test whether it uses the actual table row. The OTel C candidate
shares this same parent and must not be counted separately. KEP-753 is another
candidate lineage, but its current C world uses short curated excerpts and
has no matched source-conditioned opposite-action pair. The R8 PEP B task
still passes with a source-free semantic answer map. Neither is promoted by
this result.
