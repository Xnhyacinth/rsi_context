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
- Committed the reviewed implementation as `6aebfad`, then reran native and
  packed qualification from that clean tree. Both v4 artifacts passed start/end
  producer, source, and tokenizer stability checks; packed v4 exactly reproduced
  v3 and still fails only the unavailable official-source byte match.

## 2026-08-30 — Real long-memory continuation

- Started Phase 6 in response to the requirement to use genuinely long,
  complex long-context/long-memory/long-horizon tasks rather than toy inputs.
- Chose pinned LongMemEval-V2 offline trajectories as the next executable real
  track. Static MuSiQue remains the low-noise causal track; live long-horizon
  remains a separately gated transfer rather than a mixed fitness function.
- Audited all 451 question records and the clean official evaluator checkout.
  Identified 294 text-only deterministic-evaluator questions, 128 text-only LLM
  abstention questions, and 29 image questions; verified all four consumed core
  data files against the released checksum manifest.
- Added a failing test showing the adapter ignored a supplied frozen tokenizer,
  then changed trajectory chunk compilation to require a target token counter
  and tokenizer identity. The identity now enters the dataset fingerprint; all
  20 adapter tests pass after updating call sites.
- Added an aggregate-only full-tier qualifier with exact released-file hashes,
  clean producer start/end attestation, immutable output, zero reader calls,
  and explicit 32K/128K/256K binding measurements. Shared provenance and frozen
  tokenizer checks now serve both MuSiQue and LongMemEval qualification paths.
- Recomputed evaluator families directly from the pinned 451-row release and
  corrected an earlier one-item audit error: the 422 text-only items comprise
  294 deterministic and 128 LLM-abstention items. The gate now checks every
  evaluator-family count and rejects unknown families instead of guessing.
- The full repository gate passes: 506 tests, 83.81% branch coverage, Ruff, and
  strict mypy. Bandit reports no medium/high findings; its 11 low findings are
  pre-existing subprocess sites outside this change.
- Risk-first review found and closed two high-severity qualification defects:
  Git status alone could be bypassed with index flags, and the initial renderer
  omitted canonical trajectory metadata. Producer files are now byte-matched
  to their `HEAD` blobs, and faithful text artifacts retain trajectory
  domain/environment/goal/outcome/start URL plus state step/URL.
- The reusable gate now independently binds the pinned source revision, exact
  small-tier released hashes, complete evaluator-family table, and composite
  tokenizer identity. A follow-up review caught and fixed metadata chunks being
  miscounted as states; a real adapter-to-measurement fixture now covers state
  counts and maximum atomic-chunk length.
- Final post-review verification passes all 514 tests with 84.15% branch
  coverage, full-repository Ruff, strict mypy, and no medium/high Bandit
  findings.
- Committed the reviewed qualifier as `122b19c` and ran the full pinned
  LongMemEval-V2 small text tier twice from that clean producer. Both runs
  passed, made zero model calls, and emitted byte-identical aggregate JSON with
  SHA-256 `1f20123d438a3a6fccd8968d33448202ab7251746cb2bf42f86bcd12909d6518`.
- Real histories are 25.67M–26.35M frozen-tokenizer tokens and 1,737–3,358
  states, with 100% binding beyond 256K. The largest atomic state is 127,192
  tokens, so deterministic intra-state splitting and final rendered-prompt
  accounting are now explicit blockers before any reader baseline.

## 2026-08-30 — Locked autonomous RSI continuation

- Re-audited the normative study contract, A2 preregistration, A2 call
  projection, campaign loop, API researcher, and real public pilot. The core
  five-slot behavior exists, but visible pilot outputs do not yet bind pack,
  feedback, process, scorer, initial-policy, or total-call budgets into one
  immutable pre-run artifact.
- Kept formal A2 fail-closed. Its two task profiles, replay/noise evidence,
  physical isolation, host spend caps, and matched-controller evidence are not
  all qualified, so changing `qualification_only` would violate the protocol.
- Added a schema-v2 pre-run contract that binds the evaluator-owned H0 snapshot,
  actual visible-item payload, scorer and module source, complete semantic
  budget, reader/researcher runtime identities, five-slot allocation, process
  limits, environment names, and per-turn/aggregate researcher ceilings.
- Closed failure-accounting gaps found in independent review: every reader
  attempt is charged before transport, H0 failures produce a failure artifact,
  invalid manifests consume a slot without reader calls, real timeouts are
  covered, and researcher mutation of the contract or H0 snapshot fails before
  candidate evaluation.
- The locked public runner now requires attested endpoint, prompt, timeout,
  transport, model, and researcher identities. It remains explicitly visible
  qualification with `formal_process_isolation=false`; formal A2 is still
  disabled.
- Independent risk review found and closed four further failure paths: rejected
  policy trees now record evaluator-owned parent bytes; only the audited
  single-request reader transport is accepted; API profiles/executables/package
  source are snapshotted or continuously checked; partial reader failures mark
  token/cost accounting incomplete.
- The public token budget is now explicitly a pinned
  `qwen-canonical-token-axis`, not a claimed hy3-native cap. The contract binds
  the Qwen revision, tokenizer class, and exact `merges.txt`, `vocab.json`,
  `tokenizer.json`, and `tokenizer_config.json` digest set. Locked runs reject
  missing or weak token-axis identities before any reader call.
- Final pre-run verification passes all 543 tests with 84.03% branch coverage,
  full Ruff, strict mypy over 167 files, targeted Bandit, and three independent
  risk-review rounds with no remaining blocker or high finding.
