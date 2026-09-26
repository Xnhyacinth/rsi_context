# R18 Iceberg row-scan source contrast: offline candidate

**Decision: retain as an unqualified development candidate.** The offline
builder, scripted action witness and tokenizer geometry pass their focused
checks. No frozen reader, researcher, Siflow API or GPU was run. Neither a
scripted witness nor local tokenization shows that a model uses the source.

## Source and selected context

The registered Apache-owned Iceberg checkout was independently observed
clean, detached at `071d5606bc6199a0be9b3f274ec7fbf111d88821`, with
the official origin. The builder verifies selected **bytes and license**, not
Git HEAD; the geometry audit additionally rejects a changed HEAD, attached
branch, dirty checkout or wrong origin. Complete [`format/spec.md`](https://github.com/apache/iceberg/blob/071d5606bc6199a0be9b3f274ec7fbf111d88821/format/spec.md)
is 184,975 bytes, SHA-256
`e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb`.
The `LICENSE` SHA-256 is
`2c0e4b3b8c7a873194c6517058f9a62c59fa00a37d1e24bf80a538e1c885b9b2`.

The authentic model-visible body is one unchanged, contiguous raw byte
slice: inclusive lines **90–1179**, half-open file bytes **[6608,125333)**,
118,725 bytes, SHA-256
`51863fe50379b9fe460206cf0ecb58d9c238239058604f87e209497de548dc45`.
No unrelated material pads it. It spans the sequence overview, explicit
data/file distinction, delete applicability, and equality-column row rule.
Its exact byte slice is checked after checking the whole file. The shared
model-visible wrapper identifies the Iceberg release/path/commit and says
“selected reference body”; it does not identify which arm is constructed.
The source-free arm removes that wrapper; identity-only keeps the *same*
wrapper as the authentic arm and replaces the body with the common
`[SOURCE WITHHELD]` marker. The evaluator ledger alone labels the constructed
body. Domain-specific terms in the fixed later request may still let a model
infer Iceberg; actual source-free and identity-only model runs are mandatory.

## Whole-file rule audit and causal intervention

The exact source's lines 90–96 describe snapshot sequence assignment and
inheritance, but do not choose the counter for equality deletes. Line 108
says deletes generally apply to older same-partition data. Lines 686–688
define `sequence_number` as content age for delete planning and expressly
exclude `file_sequence_number` from delete pruning. Lines 700–703 allow an
explicit older data sequence on a newly added file and require existing
entries to carry both assigned numbers. In Scan Planning, line 848 requires
the data file's **data** sequence to be strictly less than an equality
delete's data sequence; lines 849 and 853 permit an unpartitioned equality
delete across partitions. Line 851 repeats the generic “older” rule.
Line 1136 requires equality-column values to match for an applicable delete
to remove a row. A targeted whole-file search found no further explicit
equality-delete comparator; position deletes and deletion vectors retain
their separate less-than-or-equal rules.

The constructed source changes four complete original spans and nothing
else. It uses **file** sequence only for equality-delete applicability;
position deletes and vectors continue to use data sequence. Generic “older”
prose becomes a reference to the type-specific rule so it cannot contradict
the changed comparator. The line-90 overview and line-700 inheritance remain
true, and the global-partition and equality-column rules remain exact. This
is a deliberately constructed diagnostic, **not an Iceberg revision**.

| Original lines | File byte interval | Purpose | Original SHA-256 |
| --- | --- | --- | --- |
| 108 | `[8154,8468)` | Generic older-file cue | `3ab428d0c30b10462da01c939aa6b9d01e1982f6421bb0f38a685eb4eaf20598` |
| 687–688 | `[69879,70437)` | Data/file sequence distinction | `c26e375bb51ac761e673c8f6b9ff95454a1df5ac84244cae2455416db3d3bb9a` |
| 848 | `[89745,89846)` | Equality-delete comparator | `15ca68c6fb5aaf6d62d8af08ea0e55d98dc46cb610ab86bf6ede8b9f3576687d` |
| 851 | `[90014,90137)` | Generic scan summary | `f4ff4b27425c449351999c44aa4f30dd95cc9f9129b6e08f9ba093d6593bb4c5` |

The builder checks every original span hash and verifies that all untouched
segments remain exact. The complete constructed *pack* SHA-256 is
`a4d0e6a0a3f1e7097d42e1cee3f3ebb83fb9c081e10eebe9ae3c2e10c4925493`.
Individual replacement hashes and byte lengths are returned by
`iceberg_source_ledger()` and recorded in
[`r18-iceberg-geometry.json`](r18-iceberg-geometry.json).

## Two sessions and private oracle

Session 1 presents the source before any constructed table facts, obtains an
environment-issued `review-complete` receipt, and finalizes `source_review`.
After a reset, session 2 presents an identical format-version 2 request in
every arm. The
existing file entry has status 0 and **explicit** data-content sequence 7
and file-addition sequence 12; no null value can accidentally inherit 12.
Its row has field id 1 equal to 42. Both equality-delete files pass query
and metric filters:

| File | Delete sequence | Partition | `equality_ids` / value | Authentic scope | Constructed scope |
| --- | ---: | --- | --- | --- | --- |
| E1 | 8 | unpartitioned, global | `[1]` / 42 | 7 < 8; row matches | 12 < 8 is false |
| E2 | 13 | same spec 2, region A | `[1]` / 99 | 7 < 13; row differs | 12 < 13; row differs |

The private later legal plan is `suppress-row` under the authentic pack and
`emit-row` under the constructed rule. Both action names receive the same
environment-issued *procedural* `scan-reviewed` PASS receipt; that receipt
does not reveal technical legality. The final gate separately requires the
first finalized record, its original environment receipt, a current later
receipt, and the source-dependent legal plan. The fixed request, record
interface, stage order, axes, and all predecision observations are identical
between the authentic and constructed arms.

| Arm | S1 evaluator-world SHA-256 | S2 evaluator-world SHA-256 | Private plan |
| --- | --- | --- | --- |
| Authentic contiguous pack | `004a3fa0a5e7bad900dc06d2f28eee22ed57dc3b7feca7dec981a3e34e182ebe` | `4d1a03f7dc0e21bf6dd3ee306409cb31a350bace1a5030a1be0d740a9367b406` | suppress |
| Deidentified source-free | `ac7af1de0ac77b5dbef04310556389bd57564c1f717efcff14a3809377d3edba` | `4d1a03f7dc0e21bf6dd3ee306409cb31a350bace1a5030a1be0d740a9367b406` | suppress |
| Identity-only | `e0d5fa11ef40be442963faf80444020a19e546a32b7b62b29ac69bae0d26ee08` | `4d1a03f7dc0e21bf6dd3ee306409cb31a350bace1a5030a1be0d740a9367b406` | suppress |
| Constructed file-sequence rule | `d63708d473b22f028c2d276bfb5497c9ea74a4684bd17038e544d4263d83f815` | `90161428c22dc6c2f2d573df5adf11f017670c1bf9ccb6b0b92cc62b7d386ee0` | emit |

World hashes use `canonical_instance_json` and include private fields; they
are not model-visible hashes. The **exact model-visible source-document**
SHA-256 values are `d1bcbf671a0742f659c06b5ff458f4cf51e89961c9523ba4391e4645479d1a92`
(authentic), `c9490c664d96bafde64a161331694b2db3ed7982871c3cb267b7cd8771969e3e`
(constructed), `1e61adb1939dc4af3c2147fa740f9e85c31acfe8062929e7acda46925562ad2e`
(source-free) and `e5ce05c126e6e146d4ea96b5cbab9cebf61c27c0e59fa070555e12be90730ac2`
(identity-only). The fixed later request document has SHA-256
`270713688e20ce9a1e8a4f7a9236746a1f9707f6188d838efc0c0ae6436ccc81`
in every arm. Complete system-plus-user message hashes are in the geometry
JSON. The offline scripted wiring witness carries
only a source-rule selector in session 1, reads the facts in session 2, then
passes both authentic and constructed sessions. A fixed suppress action
fails the constructed arm; a fixed emit action fails the authentic arm.
Withheld controls produce no source-supported plan in this **script**, not a
measured model failure. The `DocumentRegistry` can preserve legally revealed
session-1 source for metered reread after reset, so this witness does not
prove that carry is necessary or that a model retains all rule clauses.

## Exact local chat geometry and admission limit

The versioned offline geometry artifact is
[`r18-iceberg-geometry.json`](r18-iceberg-geometry.json), SHA-256
`aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448`.
It binds the clean source checkout, profile hash
`b9e0df1d39f4c74b684661a7b0fd8741c3e183d1203ca21ce69`, pinned
tokenizer files, and tokenizer runtime (`transformers 5.15.0`,
`tokenizers 0.22.2`, `jinja2 3.1.6`); the script rejects drift in each.
Counts render the *complete* system and
user messages, generation wrapper, and disabled-thinking chat template. The
prospective fixed reader's two prompt functions are in
`scripts/audit_r18_iceberg_geometry.py`; a future runner must call these
unchanged and verify provider input parity. No provider usage is claimed.
The S1 answer grammar permits mixed field values, but the geometry audit
registers S2 prompts only for the two coherent data/file rule bundles and
the all-unknown bundle. A future live runner must treat every other S1 reply
as a named failure **before** S2 dispatch, or version a larger prompt and
budget registration; the current geometry does not cover those continuations.

| Prospective worker input | Final-chat input tokens | 32K remaining after 2,048 requested output |
| --- | ---: | ---: |
| Complete 184,975-byte file, separate hypothetical survey | 42,169 | **−11,449; reject for 32K** |
| S1 authentic contiguous pack | 24,883 | 5,837 |
| S1 constructed pack | 24,894 | 5,826 |
| S1 identity-only | 261 | 30,459 |
| S1 source-free | 126 | 30,594 |
| S2 valid multi-clause data/file carry | 321 | 30,399 |
| S2 unknown multi-clause carry | 317 | 30,403 |

For authentic S1, exact final-chat token intervals are: counter evidence
`[13893,13905)`, comparator `[17893,17907)`, global exception
`[17981,17997)`, equality-row match `[24398,24412)`, and later query
`[24801,24874)`. Their evidence-to-query gaps are 10,896, 6,894, 6,804
and 389 tokens, respectively. The constructed S1 offsets and all S2
retained-rule/query offsets are in the JSON. These are S1 within-chat gaps;
there is no single final-chat token distance across the process reset.
`DescriptionAxes` has a
matched-arm **nominal whitespace scale** only; it is not these final-chat
token counts. The complete source exceeds 32K despite fitting the provider
profile's larger advertised context. Do not silently truncate it.

Reproduce the tokenization without a model call from the project root:

```sh
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/audit_r18_iceberg_geometry.py
```

Next gate: independently review the source-rule intervention and private
oracle, wire a fixed reader to the frozen multi-clause prompts, prove
source-full feasibility in two reader families, then run real source-free,
identity-only and position controls. No paid call is admitted by this
offline scaffold. Researcher jail admission and effective-update-rate
measurement remain separate and unverified on this host.
