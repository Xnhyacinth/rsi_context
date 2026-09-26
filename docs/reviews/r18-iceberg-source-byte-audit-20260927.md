# R18 Iceberg 1.9.2 specification source byte audit

**Status: source acquired, task not yet qualified.** After the committed
registry entry and reviewed dry-run in
[`r18-iceberg-acquisition-plan-20260927.md`](r18-iceberg-acquisition-plan-20260927.md),
the official `https://github.com/apache/iceberg.git` repository was cloned
with `--filter=blob:none --no-checkout`. A sparse checkout materialized only
`format/spec.md` and top-level `LICENSE`, and HEAD was detached at
`071d5606bc6199a0be9b3f274ec7fbf111d88821` (the peeled
`apache-iceberg-1.9.2` tag). The external source is
`/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake`.
Its Git status is clean and `origin` is the registered Apache URL.

| Selected file | Raw bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `format/spec.md` | 184,975 | `7dec296200b722289d7ca8399e481fc1b4948386` | `e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb` |
| `LICENSE` | 15,980 | `76f6113d9811998dffb7d7aebcdf20efa404cddf` | `2c0e4b3b8c7a873194c6517058f9a62c59fa00a37d1e24bf80a538e1c885b9b2` |

The spec's opening comment carries an Apache Software Foundation license
notice and points to Apache License 2.0; the top-level license file is
retained. The raw Markdown has 1,788 LF-delimited lines. These initial
dependency-bearing intervals are exact raw-file byte slices, with inclusive
line numbers and half-open byte offsets:

| Candidate evidence | Lines | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| Data versus file sequence numbers, inheritance and v1 default | 686–708 | `[69561, 72567)` | `504315b831ab9043827ccee1fdb951a96a20e0ced32d2e3366a7a4bb383526e7` |
| Scan-planning delete applicability and partition exception | 836–855 | `[88520, 90511)` | `d0710dd7dcb503c24c5c8cc1876d917b5ea8eda9394e58fd05251e4f5e59c1f0` |
| Equality-delete column matching | 1130–1137 | `[123020, 123980)` | `bb0e419f9bc21910e038400546e8fd8b31059fa5af64e3ec5e770a704d21dc95` |
| Dropped delete-column rule | 1179 | `[125003, 125333)` | `36947ba45e3fb18d1507367dc7ac22130b996456ac0a6648780ea98342bb42b7` |

The selected rules differ in kind. A data file's data sequence number, not
its file sequence number, governs delete planning; v1 manifest sequence
numbers default to zero. An equality delete requires a strictly older data
sequence number and matching partition or an unpartitioned delete spec.
Whether a row is deleted also depends on its equality-column values, even
when a delete column is later dropped. A candidate task may need to combine
these separated sections, but a longer file and separated spans alone do
not prove model-visible dependence or a long-context benchmark result.

**Remaining gates:** scan the entire pinned spec and other legitimately
needed source for semantic equivalents; independently adjudicate a fixed
constructed table state and opposite-rule private legal action; keep all
non-source observations identical; run deidentified source-free, identity-only
and default-plan controls; measure final-chat token offsets and actual reader
behavior before any paid call. Do not treat a constructed source rewrite as
a second authentic Iceberg revision or count this intake as a qualified parent.
