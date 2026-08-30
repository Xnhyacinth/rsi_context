# Progress

## 2026-08-30

- Restored the repository state: clean private feature branch at `f841dd4`.
- Read the selected planning, experiment-design, review, Git, and validation
  skill instructions.
- Created this persistent execution plan with explicit scientific and software
  completion gates.
- Audited the registry, MuSiQue adapter/tests, and Linux isolation attestation.
  Confirmed that A2 remains blocked on separately pinned real data and an
  executable qualification artifact rather than missing JSON parsing.
- Audited public difficulty gates, runtime identity binding, and locally
  available models/data/artifacts. Narrowed the implementation target to a
  label-safe MuSiQue offline qualification report with immutable input digest.
- Checked public MuSiQue distribution options. Rejected an unverified community
  mirror as the formal source and selected a checksum-pinned official HTTPS
  archive path as the smallest dependency-hygienic prerequisite.
- Inspected the candidate mirror revision and exact LFS digests. Revised the
  implementation choice: use the mirror only for a non-formal offline
  qualification, and removed the otherwise-unused HTTPS acquisition probe.
- Added the qualification-only mirror registry entry, reviewed its dry-run,
  downloaded it to ignored `data/`, and verified the Hub revision and dev-file
  SHA-256. Registry tests pass.
- Computed schema/hop/paragraph distributions over all dev rows. A combined
  tokenizer probe produced no captured output at the 30-second yield boundary;
  it will be rerun as an explicitly polled process rather than repeated
  identically.
- Re-ran the tokenizer analysis as a polled process and completed all 2,417
  rows. The native data is decisively rejected as an 8K-binding long-context
  profile; measured lexical leakage also requires filtering.
- Implemented and ran the aggregate-only MuSiQue qualifier. The first real run
  failed on official integer decomposition IDs; added a failing regression
  test, fixed normalization, revalidated, and reran successfully to the expected
  scientific rejection (exit 2). Raw report is ignored under `artifacts/`.
- Added the test-first deterministic MuSiQue long-context packer and aggregate
  measurement path for packed evaluator items. Focused tests, Ruff, strict
  mypy, and Bandit pass.
- Ran the full 40-item packed profile. Causal leakage/position/hop/binding
  structure passed, but post-compilation token counts undershot the declared
  32,768 target. Started a test-first accounting repair before accepting the
  artifact as exact 32K.
- Added a regression test and post-chunk top-up repair, then completed the
  40-item v2 run. Recorded the native rejection, superseded v1 mismatch, v2
  aggregate measurements, claim boundary, and remaining gates in a dated report.
- Independent risk-first review found three must-fix semantic gaps despite all
  static gates passing: caller-asserted official byte matching, missing
  intermediate-answer leakage checks, and an unattested tokenizer path. It also
  found that requested position labels were not verified on the token axis.
- Replaced those assertions with digest-derived source provenance, exact
  tokenizer-file verification, final/intermediate causal leakage gates, and
  compiled token-axis position checks. Added regression tests and producer-file
  attestation with Git dirty-state reporting.
- Reran native and 40-item 32K qualification as schema-v2 v3 artifacts. Native
  data has 44.81% intermediate-answer non-gold leakage. Strict packing skipped
  111 leaking candidates and cleared every implemented structural/causal check;
  formal eligibility still fails on the intentionally unavailable official
  byte match. Both runs made zero reader/API calls.
- Re-review found a producer/source/tokenizer TOCTOU gap and correctly rejected
  the dirty-tree v3 artifacts as final replay evidence. Added clean-tree entry,
  start/end stability, source drift, tokenizer drift, immutable output, and
  producer environment checks. A clean-commit v4 rerun is now required.
- Third review found no remaining must-fix for the qualification-only scope.
  The final post-fix repository gate passed all 494 tests with 84.17% branch
  coverage; focused tests, Ruff, strict mypy, and high-severity Bandit also pass.
