# R5 OTel two-session long-source B candidate

Status: **development construction witness; Gate 2 qualification rejected for
now**. This is a B task variant of the existing OTel source lineage, not a new
independent parent or a model result. Builder:
`src/rsicontext/lifecycle/material_otel_long_b.py`. No benchmark split
registration or model API call was made.

## Frozen material and decision ledger

The evaluator loads the two complete official OpenTelemetry semantic-convention
files from detached commit
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d` (`v1.43.0`, Apache-2.0).
The builder checks their exact SHA256 bytes before returning any world. The
existing portable `configs/r4_parent_source_manifest_v1.json` pins these same
files and Git blobs; this candidate adds no source file or new acquisition.
The source checkout is an input to the builder, not a hidden source embedded
in a policy. Both source files are shown in session 1 and are absent from
session 2's attached documents.

| Required proposition | Official pinned span | Whole-file SHA256 | Span SHA256 |
| --- | --- | --- | --- |
| `database` emits stable conventions only; `database/dup` emits old and stable together. | [database-spans.md 35–43](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/database-spans.md#L35-L43) | `1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91` | `573ce7eafcf5245488271f96397b2f99d9b72dc7ff429474261752c11be5520d` |
| Raw non-parameterized query text needs sanitization before default collection; literals should be replaced. | [database-spans.md 367–386](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/database-spans.md#L367-L386) | same file | `9127b51adc60efbf292db8f9032936d23679382c83ffcc9a7a1ec74472d3d973` |
| Parameterized query text is collected by default without parameter values; the non-parameterized rule is repeated here. | [sql.md 178–183](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/sql.md#L178-L183) | `e451e533f90fbcc01ecc23f6d60aaa49d249dad79227f79ddeef548288eb32ea` | `66bddec36add448c96c82a137a78960323ffe16e52038f731a106fedfb0a6d2a` |

The two collectors, rollout window, validation receipts, privacy proposal,
record names, and oracle outcomes are **constructed benchmark material**, not
claims about an actual OTel deployment. The local material says the legacy and
stable collectors must both keep receiving events during the first window.
The source selects `database/dup`; a passing environment `dual-emission`
receipt is required to finalize `migration_commit`. After a real session
reset, a later instrumenter proposes both unsanitized raw non-parameterized
query text and parameterized query text without parameter values. The source
supports holding the first and allowing the second. The worker must request a
new `query-text-safety` receipt and finalize `query_text_rollout` with both
decisions. The second gate additionally requires `migration_commit` to have
been environment-finalized **before** session 2 began. Its source is only in
session 1, so a worker must retain or explicitly reread the relevant rules.

The complete files have 6,253 whitespace words. Using pinned
`Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b` tokenizer
bytes (SHA256
`5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`),
`tokenizers==0.22.1` counted **12,708** tokens for the two source documents
including their document headers and **12,735** for a direct concatenation of
the survey prompt plus those documents, with special tokens disabled. This
is an exact measurement of those strings, **not** the eventual worker API
prompt: policy-authored prompt framing, chat template, system text, and
provider-side counting remain unmeasured. The world metadata's token field
uses the project's whitespace estimate and must not be read as this tokenizer
measurement. The source files are complete upstream prose, with no generated
padding.

Canonical JSON (`ensure_ascii=False`, sorted keys, compact separators) SHA256:

| Object | SHA256 |
| --- | --- |
| Session 1 `LifecycleInstance.to_dict()` | `1d64911fd2ce9e01824ac87d31e7ed47a85c56e89202b188b59bd0dc4c493955` |
| Session 2 `LifecycleInstance.to_dict()` | `20149c3593d2ab358f2b1d6a5fb0e6e65cf83c0464551db8f26da68319ade2d0` |
| Ordered two-session pair | `9ae874bb05dc46f76e78cf54e52452576a111d783876c1cd29e8a20d1635fc58` |
| Session 1 source `DocumentRef.to_dict()` values | `a40162d1f141e1adfd672ac5123e5aee37e9eda941797448e136c02638d74a6a` |

## Construction checks and rejection boundary

The deterministic reference uses only `StageView`, environment receipts, and
the bounded carry state. Both sessions pass through `run_session_sequence`;
the hook is rebuilt, and session 2 receives only the persisted carry. Removing
the migration-mode line breaks both decisions. Removing the privacy rules
from **both** source documents (the rule is duplicated upstream) leaves the
first decision legal but breaks the second. Flipping either validation
receipt blocks the reference at the corresponding step. Omitting the prior
finalized award, or creating it only after resume, makes the later gate fail
with a named cause. An unrelated local office note leaves both decisions
unchanged. A changed source byte is rejected before world construction.

There is an important limit: `prior_finalized_record` checks the existence
and timing of an environment-finalized record, not whether that earlier award
passed its own receipt gate. A policy can forcibly finalize the migration
after a failed dual-emission receipt: session 1 correctly fails, but the
isolated session-2 gate can still pass. The full project fails, yet this does
**not** prove that the earlier receipt controls the later legal action. Nor
can the current grader vary session-2 legal plans by the value of the earlier
mode. The adversarial test records this behavior. A stronger causal claim
needs a shared grader change with a prior-validity or prior-plan predicate,
followed by new intervention tests. Fixed-reader difficulty and full
policy-rendered input length also remain unmeasured. Therefore this candidate
is not admitted as a qualified B parent or a scored benchmark item.
