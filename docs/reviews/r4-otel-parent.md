# OTel database migration: independent A development parent

Status: **one constructed development candidate**, not a qualified Gate 2
parent or a scored model result. Builder:
`src/rsicontext/lifecycle/material_otel_parent.py`. It does not register the
world in any benchmark split.

## Source identity and proposition ledger

The source is OpenTelemetry semantic-conventions `v1.43.0`, detached commit
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`, Apache-2.0. Its acquisition
and license checks are recorded in
`artifacts/rsi-core-v1/r3-gate2-source-acquisition-20260925.json`.

| Proposition used by this world | Exact pinned span | Source file SHA256 | Consequence in the constructed task |
| --- | --- | --- | --- |
| `database` emits stable database conventions and stops the earlier experimental conventions; `database/dup` emits both for a phased rollout. | [Database client spans, lines 35–39](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/database-spans.md#L35-L39) | `1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91` | The fictional local requirement to feed *both* collectors selects `database/dup`. |
| Non-parameterized `db.query.text` should not be collected by default without sanitization; parameterized text has a different default. | [SQL conventions, lines 178–179](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/sql.md#L178-L179) | `e451e533f90fbcc01ecc23f6d60aaa49d249dad79227f79ddeef548288eb32ea` | A later fictional request to collect unsanitized non-parameterized query text is held. |

The cited excerpts are embedded verbatim in stage 1. `local-*` documents,
the two local collectors, rollout window, validation oracle, verification
receipt, actions and record names are **constructed benchmark material**.
They do not describe any real OpenTelemetry deployment or upstream approval.
The evaluator's legal plan and simulated validation outcome are excluded from
the participant's `StageView` by the existing runner boundary.

## Decision and intervention ledger

1. **Survey:** retain the distinction between stable-only and dual emission,
   plus the SQL text rule. The source documents are not re-attached later.
2. **Constraint and action:** a fictional rollout must keep legacy and stable
   collectors fed concurrently. The candidate chooses a source-supported mode,
   requests an environment-issued `dual-emission` check, and finalizes the
   `migration_commit` with that receipt as provenance. The visible requirement
   and evaluator gate both require the receipt, with no auxiliary record.
3. **Follow-up:** after the commit, the candidate must use the earlier SQL
   source to record whether the raw-query-text proposal may proceed.

The scripted reference path passes. Removing the migration excerpt makes its
choice unknown and the commit fail. Removing the SQL excerpt leaves the
follow-up unresolved. Changing the environment's dual-emission verdict to
failure makes the commit gate fail. Adding an unrelated page-index document
leaves both reference decisions unchanged. These are **construction checks**;
the reference is a deterministic text-following witness, not a researcher or
reader model.

Canonical JSON hashes (`sort_keys=True`, compact separators, UTF-8):

| Object | SHA256 |
| --- | --- |
| All stage documents' `to_dict()` values, stage order | `73175e8a9424b8898404080db7e877ab3e0d1ec16881fa00456657a664e8cc8d` |
| Complete evaluator `LifecycleInstance.to_dict()` | `99bebe5143d37270bfe26ad40ed3e9fee666a8ea877d7f7f36bcc5a9471704ab` |

The stage-1 text has an estimated 175 whitespace-separated tokens. The
follow-up has one fixed constructed answer, so its scripted success is **not**
a difficulty claim or a demonstrated source-conditioned answer change. This
compact candidate proves a distinct source lineage and a working dependency
path, but it does **not** yet test long-context search pressure, reader
difficulty, robustness to alternate wording, or cross-parent generalization.
It must be independently reviewed and expanded before use in a frozen
benchmark split.
