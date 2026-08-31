# Progress

## 2026-08-31 elastic allocator and autonomous-loop decision

- Implemented a frozen elastic rendered-input envelope with evaluator-owned
  per-item overhead, policy-only desired length/priority, deterministic
  order-invariant weighted water filling, and exact public-digest tie breaking.
- Added complete-batch preflight that independently revalidates allocation
  identities, totals, item maxima, endpoint output reserve, and batch caps
  before any target call. Added a frozen chat-render token-count boundary.
- Changed the A2 controller to refuse the legacy fixed-budget schema
  unconditionally. This is a zero-reader-call safety change, not A2 enablement.
- Added behavior tests for order invariance, weighted/capped allocation,
  evaluator-owned overhead feasibility, forged-allocation rejection, complete
  item coverage, quota overrun, endpoint limits, and complete chat wrappers.
- Audited MGM and Recuris against their current papers and official code. Kept
  the benchmark-owned five/ten-slot loop, component-scoped manifests,
  structured traces, and paired admission; rejected whole-repository evolution,
  evaluator/private-test exposure, and provisional-lineage success claims.
- Formal hy3 RSI remains blocked by the failed Phase 13b uncertainty and
  instability gates. The next safe experiment after a clean commit is the
  LongMemEval-V2 medium zero-reader qualification/replay, not a new researcher
  trajectory.

## 2026-08-31 paired signal diagnostic

- Added an initial preregistration, behavior tests, and a matched interleaved
  diagnostic implementation; the first focused run correctly exposed a
  non-serializable schedule digest and one strict-mypy return issue.
- Independent method review found that a point-estimate-above-noise rule could
  not support the intended claim. Revised the preregistration to require the
  bootstrap lower bound and every repetition to exceed the prior noise upper,
  constrain instability in both policies, and use a worst-case unstable-item
  sensitivity contrast.
- Locked an evaluator-only immutable ledger as part of the evidence contract;
  public results will expose its digest but no item-level data.
- Implemented the paired runner and fixed CLI: exact 249-call accounting,
  deterministic interleaving, immutable pre-call contract, private per-call
  evaluator ledger, pre/mid/post canaries, conservative statistics, and fixed
  PopQA/tokenizer/profile/prior-artifact identities.
- Extracted the shared pinned PopQA/tokenizer inputs used by both hy3 CLIs,
  preserving the existing replay behavior and tests instead of duplicating
  acquisition logic.
- Focused checks currently pass: 5 paired-runner tests, 4 paired-CLI tests,
  8 legacy replay-CLI tests, Ruff, strict mypy, and Bandit.
- Independent correctness and security reviews found that the first public
  builder accepted arbitrary self-consistent experiment identities and that
  the private ledger shared the public directory. Both were treated as
  must-fix findings rather than documentation caveats.
- Locked the public tier to the exact PopQA panel, hy3 profile, 8K/64 budgets,
  token/source/prereg/prior evidence, scorer, lexical policy, and head policy.
  Added a regression that an arbitrary 40-item public contract fails closed.
- Moved the item-level ledger to a required repo-external, non-overlapping 0700
  evaluator directory; public output is restricted to ignored `results/`.
  Redacted the full endpoint to a digest and verified the ledger is mode 0600.
  This remains trusted-host evidence, not formal UID/namespace isolation.
- Added a prospective transport cap so the 250th call is rejected before it is
  sent, plus schedule-position, arbitrary-public-identity, symlink/private-path,
  endpoint-redaction, and permission tests. Focused runner/CLI checks now pass.
- Post-fix independent correctness and security reviews report no remaining
  must-fix for the trusted-host qualification scope. Both retain the explicit
  residual that same-UID directory separation is not formal physical isolation.
- Final merge gate passes: 577 tests, 83.58% branch coverage, full Ruff, strict
  mypy over 176 files, Bandit high-severity scan, and `git diff --check`.
- Committed and pushed the clean diagnostic producer as `cf19dff`, then ran the
  exact 249-call block without retries or extensions. Lexical scored 0.600 on
  average versus 0.325 for head truncation, for a paired majority contrast of
  +0.275; all three repetition contrasts exceeded the prior 0.1650 bound and
  exact McNemar was significant (`p=0.00341796875`).
- The preregistered gate nevertheless failed correctly. The paired bootstrap
  95% interval was [0.125, 0.425], and the worst-case contrast after assigning
  -1 to every item unstable under either arm was only +0.100. Lexical had 2/40
  unstable items and head had 4/40; a large observed policy contrast therefore
  does not yet establish a replay-robust optimization signal.
- All 249 calls completed, all nine canaries were semantically correct, task
  input usage and model alias were stable, and output usage remained unstable.
  The repo-external ledger is mode 0600 under a 0700 directory, and its SHA-256
  matches the public aggregate binding. No item-level ledger content was moved
  into the repository.
- Recorded the aggregate evidence in
  `docs/hy3-paired-signal-diagnostic-2026-08-31.md`. Phase 13b remains
  qualification-only with `rsi_launch_eligible=false`; no researcher, A2,
  LongMemEval reader, or live long-horizon run is authorized by this result.
- Independent method review reproduced the paired delta, McNemar p-value, and
  both failed decision conditions. It also tightened the claim from policy
  “headroom” to sensitivity between two tested baselines: improvement above H0
  remains unestablished, and hidden provider weights remain unattested.
- Revised the unlaunched A2 design from a fixed 8K primary to an elastic context
  envelope. Fixed 8K remains a controlled diagnostic, while formal researchers
  may choose item-level length, compression, or no compression under identical
  per-item maximum, per-candidate batch, call, timeout, and retry caps.
- Marked the existing 32-configuration executable A2 plan and 10,720-call
  projection invalid for launch. They must be rebuilt with dynamic budget rules,
  matched controls, batch/trajectory accounting, new difficulty landscapes, and new
  hashes before any researcher receives scores.
- Independent method audit supported elastic envelopes but required exact scope
  and token semantics. The revision now gives each candidate/split an independent
  batch cap, compiles the whole panel before any reader call, forbids cross-item
  mutable state and cross-round banking, and counts complete rendered requests
  on the frozen tokenizer rather than provider usage.
- Predeclared request canaries select `Lmax`; precommitted spend feasibility
  selects the mean 8K-or-32K batch tier. Reader scores cannot choose either.
  Formal panels exclude prior PopQA qualification items, and replay/causal
  checks are repeated at the selected elastic lengths.
- Second method audit closed the original seven blockers and found three final
  specification ambiguities. Added order-invariant weighted water-filling so H0
  is batch-feasible, separated historical `pack-8K/32K` from elastic
  `rendered-mean-8K/32K`, and fixed the efficiency tie-break and token-matched
  lexical baseline to pre-dispatch deterministic constructions.
- Final independent check found no remaining must-fix in the protocol text. The
  elastic design is ready for test-first implementation, but no elastic run or
  executable A2 eligibility is claimed.

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
- Committed and pushed the locked qualification producer as `a036c4a`. A real
  five-replay hy3 pre-canary then failed exact-answer, answer-stability,
  usage-stability, and provider-revision gates: two answer forms were observed,
  while output usage varied between two and three tokens.
- Stopped before the planned eight-item, five-slot campaign, exactly as the
  preregistered launch rule requires. This block used five canary calls and made
  zero main-reader, researcher, or candidate-policy calls; no post-canary was
  needed because no experiment ran.
- Recorded the aggregate gate evidence in
  `docs/hy3-locked-qualification-gate-2026-08-30.md`. The next primary cell must
  use a pinned local reader; hy3 remains eligible only as a separately labeled
  API replication reader or researcher unless a future preregistered canary
  establishes a usable replay floor and version identity.

## 2026-08-31 — hy3-primary continuation

- Changed the execution priority at the user's direction: hy3-ioa is now the
  default reader, with an explicitly operational/configuration-frozen evidence
  tier rather than an unverifiable weight-snapshot claim.
- Re-audited all five stored hy3 canary blocks. Across 21 calls the semantic
  answer was always `amber`; raw output alternated between `amber` and
  `amber.`, and input usage changed from 65 tokens on 2026-08-14 to 67 tokens
  on 2026-08-29/30. This motivates scorer-level within-block replay plus
  pre/mid/post drift anchors, not a raw-string-only launch rule.
- Started Phase 13. The first implementation target is a scorer-bound
  task-level replay artifact on real PopQA items. Broad RSI, LongMemEval reader
  scoring, and live long-horizon calls remain gated until this evidence exists.
- Locked the public Phase 13 block to 40 fixed items × five task replays plus
  three pre/mid/post canary blocks (209 total calls), with zero observed
  scorer-level flip/SD thresholds. Results report the non-zero Wilson upper
  bound and hard-code `rsi_launch_eligible=false`.
- Replaced caller-supplied contract guards with internal persisted-file checks,
  bound a clean Git producer attestation and source/tokenizer identities, and
  made contract/result/failure writes atomic. Mocked CLI success, failure-ledger,
  source-drift, and tokenizer-drift paths now pass before any paid run.
- Final pre-run validation passed 565 tests with 83.97% branch coverage, full
  Ruff, strict mypy over 171 source files, Bandit with no medium/high findings,
  `git diff --check`, and an independent review with no remaining
  blocker/high/medium findings.
- Committed and pushed the qualification producer as `e23f845`, then ran the
  clean-HEAD 209-call lexical H0 block on 40 real PopQA k1000 items. The run
  completed all calls but failed the operational gate: aggregate scores were
  0.600 × 5 with SD 0, while 2/40 items flipped (rate 0.05; Wilson upper 0.1650).
- Pre/mid/post canonical canaries were 9/9 correct, input usage stayed at 67,
  and the model alias stayed `hy3-ioa`; raw output form and output-token usage
  were not stable. No researcher, alternative policy, LongMemEval reader, or
  live long-horizon run was launched.

## 2026-08-31 — LongMemEval-V2 medium stress profile

- The first clean medium compilation exposed repeated tokenization across 447
  distinct haystacks. It was stopped before writing an artifact after almost
  three hours and about 30 GB RSS; continuing would not have changed the
  scientific estimand.
- Added a failing overlap test, then cached immutable rendered trajectory text
  and target-tokenizer counts within one loader invocation while rebuilding
  artifact-specific IDs and offsets. The final suite passed all 589 tests with
  83.60% branch coverage; Ruff, strict mypy, targeted Bandit, and independent
  review passed with no must-fix.
- Committed and privately pushed the repair as `108956e`, then completed the
  pinned medium profile in roughly nine minutes. It made zero model calls and
  produced aggregate artifact SHA-256
  `d3cdea4b6de7b07aafab3bccebca7577f7e560d2b33f90968bdc8cf8295f48c4`.
- All 422 text-only items exceed 256K: source lengths are 35.54M--157.82M
  tokens, with a 98.75M median and 150.07M p95. The largest atomic state is
  135,980 tokens, so deterministic intra-state splitting remains mandatory.
- The verdict is the expected preregistered rejection because the primary
  qualification gate names the small 100-trajectory tier. Medium is retained
  as a zero-update frozen-policy transfer profile, not relabeled as passing A2.
