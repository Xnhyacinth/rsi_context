# R18 Apache Iceberg source acquisition plan

**Status: registry and dry-run reviewed; source not yet acquired.** The
Apache-owned `apache-iceberg-1.9.2` tag was resolved through `git ls-remote`
to tag object `21c5127ef8d8b677c28a566f8951f2a1d14c754d` and peeled
commit `071d5606bc6199a0be9b3f274ec7fbf111d88821`. The new
`apache-iceberg-spec-1.9.2-intake` entry in `configs/registry.json` pins
that exact commit, the official
`https://github.com/apache/iceberg.git` URL and a public Apache-2.0
license claim that must be checked against selected notices after download.
Its current registry SHA-256 is
`16807ab8ae22734f2a90cc64df843587a9b290bdf8b4dba79f154efabc81c934`.

The reviewed read-only
[`registry plan`](/volume/pt-dev/qjiu/rsi_context_external/r18-preflight/iceberg-registry-plan.json)
has SHA-256 `bcedb0cb54755a6ba6ccce840e2ce46b6e1c03ea4c3b3a5f2cffae90509b8203`.
It reports `dry_run=true`, one unknown-size Git artifact and no warnings.
The destination is
`/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake`.
The plan's acquire command clones the registered URL and checks out the
registered commit detached. To avoid materializing unrelated project files,
the actual command may use `--filter=blob:none --no-checkout` and a sparse
checkout of `format/spec.md` plus the top-level `LICENSE`, then detach at
the same commit. Verify the final HEAD, clean Git status, selected Git blob
IDs, raw SHA-256, byte counts and license notices before building any task.

This is **source intake only**. The pinned spec's sequence inheritance,
scan-planning and equality-delete sections are a multi-section task
hypothesis, not a legal-action oracle, model result or qualified independent
parent. No source variant may be reported without a separate exact-byte
material ledger, semantic equivalent-rule audit, model-visible control
checks and final-chat geometry.
