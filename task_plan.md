# Real long-context, long-memory, and long-horizon qualification

## Goal

Advance from static causal qualification to real long-memory evidence without
launching an ineligible researcher matrix: qualify LongMemEval-V2 with the
frozen tokenizer and evaluator strata, execute 128K+ offline trajectory-policy
baselines, and specify a separate live long-horizon transfer gate while keeping
the researcher, policy, and frozen reader/evaluator boundaries intact.

## Success criteria

- The selected implementation follows the normative `study-contract.md` and
  `a2-preregistration.md`; no result is mislabeled as A2 or publication-scale.
- Researcher-editable code remains under top-level `policy/` and cannot access
  evaluator labels, network, reader configuration, or hidden splits.
- The changed critical path has behavior-first tests, including negative
  boundary tests and policy-activation evidence where applicable.
- A real-data offline qualification or an explicit preregistered rejection
  artifact is produced without fabricating missing metrics.
- Pytest with branch coverage, Ruff, strict mypy, and Bandit pass.
- A risk-first code review has no unresolved must-fix findings.
- The focused diff is committed and pushed to the existing private branch.

## Phases

### Phase 1 — Repository and evidence audit

**Status:** complete

- Read the complete experiment/data/evaluator paths and current registry pins.
- Identify the smallest unimplemented blocker in the frozen execution queue.
- Check worktree, ignored-artifact policy, environment, and available data.

### Phase 2 — Test-first boundary or qualification implementation

**Status:** complete

- Add failing tests for the identified behavior and boundary.
- Implement the smallest change that makes those tests pass.
- Record exact inputs, revisions, hashes, and non-publication claim level.

### Phase 3 — Valid experiment execution

**Status:** complete

- Run offline qualification and/or a gate-safe smoke experiment.
- Do not launch A2, sealed evaluation, or paid broad API search unless all
  preregistered launch gates pass.
- Save raw artifacts only in ignored locations and summarize real results.

### Phase 4 — Verification and independent review

**Status:** complete

- Run focused and full tests with branch coverage.
- Run Ruff, strict mypy, and Bandit.
- Perform risk-first code review; fix and revalidate all must-fix findings.

### Phase 5 — Git handoff

**Status:** complete

- Inspect the exact diff and secret/data-boundary status.
- Commit with a focused conventional message and push the private branch.
- Report achieved evidence, remaining gates, and next executable experiment.

### Phase 6 — Real LongMemEval-V2 audit

**Status:** complete

- Audit the pinned real data, actual lengths, image subset, evaluator types,
  adapter token accounting, and existing offline trajectory packer.
- Select a text-only, exact-evaluator primary profile and separately label weak
  judge transfer evidence.

### Phase 7 — Long-memory qualification implementation

**Status:** complete

- Add behavior-first tests for frozen-tokenizer counts, provenance, immutable
  aggregate reports, and 128K+ binding.
- Implement only the missing qualification path; do not broaden the researcher
  grammar or live harness.

### Phase 8 — Real-data offline baselines

**Status:** completed — operational gate failed

- Run full-context/truncation/lexical-or-recency context policies on qualified
  real trajectories using the frozen reader only after difficulty gates pass.
- Report exact and judge strata separately, with target/auxiliary calls and
  replay evidence.

### Phase 9 — Live long-horizon transfer design

**Status:** pending

- Freeze tools, task policy, skills, state kernel, and evaluator; expose only
  trajectory select/compress/order/verify triggers as the transfer policy.
- Select a pinned real benchmark and require matched retry, shared first
  rollout, A/A replay, policy activation, last/peak/best, and tokens/success.

### Phase 10 — Verification and Git handoff

**Status:** complete

- Run branch-coverage pytest, Ruff, strict mypy, Bandit, and risk-first review.
- Commit and push only reproducible qualification evidence to the private
  branch; keep raw data and evaluator-only artifacts ignored.

### Phase 11 — Locked autonomous RSI qualification

**Status:** complete (stopped at preregistered pre-canary gate)

- Materialize an immutable per-run budget contract before the first reader
  call, binding the real dataset, reader/researcher identities, initial policy,
  scorer, five slots, pack budget, feedback cap, process limits, and selection
  semantics.
- Enforce the contract inside the visible runner: every missing, invalid, or
  timed-out submission consumes one slot; every valid candidate receives one
  reader call per item; no candidate can exceed the prompt or process budget.
- Run pre/post API canaries and one five-round real PopQA qualification only if
  the contract implementation and clean-producer gates pass. Keep this block
  outside the matched A2 estimand.
- The 2026-08-30 hy3 pre-canary failed exact-answer, answer-replay,
  usage-replay, and immutable-version checks. The five-round campaign was
  therefore not launched; this is a valid gate outcome, not an incomplete RSI
  curve.

### Phase 12 — Matched A2 enablement

**Status:** pending

- Freeze two qualified real profiles, physical evaluator isolation, host spend
  caps, replay-noise evidence, Random-5 and Sequential-5 feedback parity.
- Enable the existing 2×2×2×5 A2 runner only when every preregistered launch
  condition is backed by an immutable evidence digest rather than a caller
  assertion.

### Phase 13 — hy3-primary scorer-aware qualification

**Status:** in_progress

- Replace raw-string and usage equality as semantic launch gates with a
  scorer-bound replay contract while retaining both as drift/cost diagnostics.
- Bind the operational-freeze evidence tier, pre/mid/post anchor schedule,
  task scorer, item order, repetition budget, and invalidation rules before the
  first scored API call.
- Qualify actual PopQA items under repeated H0 evaluation before allowing any
  policy landscape evaluation. A passing block means only that the fixed
  40-item panel showed no scorer-level flip in five consecutive replays; it
  does not establish a frozen weight snapshot, population-wide noise floor, or
  permission to expose scores to a researcher.

### Phase 14 — Unified long-context and long-memory API runner

**Status:** pending — blocked from autonomous scores by Phase 13 noise

- Reuse the same contracted API profile within separately bounded PopQA k1000,
  packed MuSiQue, and deterministic LongMemEval-V2 text blocks. Do not merge
  different time blocks as if they shared one immutable weight snapshot.
- Add deterministic final-prompt token enforcement, intra-state splitting for
  LongMemEval, aggregate-only result artifacts, and per-task exact/judge
  scorer separation.
- Freeze a 40-item difficulty and causal landscape with no-context, gold-only,
  bounded oracle, gold-drop, counterfactual/parametric deletion, policy-order,
  and position strata. Define the meaningful policy delta from that landscape,
  then compare replay noise to signal before autonomous rounds.
- Keep 128K/256K as source-length strata unless the API length canary
  establishes a larger accepted rendered prompt. A Phase 13 pass authorizes
  this evaluator-only landscape, not RSI.

### Phase 15 — hy3 matched micro-RSI and long-horizon transfer

**Status:** pending

- Run two researchers × two qualified task profiles × two seeds × five slots
  only after both profiles pass difficulty/causal qualification,
  replay-to-delta, physical isolation, spend-cap, and matched-control parity
  gates backed by immutable digests. Use Random-5 and Sequential-5
  feedback/call parity and interleaved H0 anchors.
- Freeze tools, task policy, skills, environment, and evaluator for live
  transfer. Expose only trajectory select/compress/order/memory-update/verify
  policy surfaces. LongMemEval/live execution is frozen-policy transfer and
  external-validity evidence, not long-horizon RSI; keep its outcomes out of
  discovery fitness.

## Decisions

| Decision                                                     | Rationale                                                                                                         |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Keep static causal qualification primary                     | It has the lowest replay noise and is the current normative blocker.                                              |
| Use hy3 as the primary bounded-block black-box profile       | The user prioritizes API execution; only request configuration is frozen, while hidden weights remain unattested. |
| Do not implement unrestricted harness evolution yet          | It would break matched-search identification and overlap Recuris/AHE before the primary benchmark works.          |
| Use a pinned community MuSiQue mirror only for qualification | It provides immutable LFS bytes now; formal A2 still requires byte-matching the official archive.                 |
| Drop the unused HTTPS downloader probe                       | It cannot establish an official archive checksum before first acquisition and adds unsupported surface.           |

## Errors encountered

| Error                                                                    | Attempt | Resolution                                                                               |
| ------------------------------------------------------------------------ | ------- | ---------------------------------------------------------------------------------------- |
| New HTTPS registry tests failed before implementation                    | 1       | Expected TDD red state confirmed.                                                        |
| Official MuSiQue archive has no published checksum                       | 1       | Use a pinned mirror for qualification only; keep official-byte matching as an A2 gate.   |
| Combined cleanup patch missed autoformatted plan lines                   | 1       | Split the patch into exact, smaller edits.                                               |
| Combined tokenizer/statistics probe returned no captured output          | 1       | Run the tokenizer analysis as a separately polled process.                               |
| Real MuSiQue row used integer decomposition IDs                          | 1       | Added a regression test and normalized official non-negative integer IDs to strings.     |
| Packed v1 compiled below its declared 32,768-token target                | 1       | Added a regression test and top up after measuring compiled chunk tokens.                |
| Reviewer found v2 causal/provenance assertions were incomplete           | 1       | Added intermediate leakage, derived digests, tokenizer attestation, and token positions. |
| New operational-replay test helper lacked a strict return type           | 1       | Added the explicit `OperationalReplayContract` annotation before continuing.             |
| Source identity arguments were patched into the dataset fingerprint call | 1       | Moved them to the operational replay contract after strict mypy exposed the mismatch.    |

## Next step

Pre-register a matched, randomized, interleaved H0-versus-fixed-policy
signal-to-noise diagnostic with repeated H0 anchors and an immutable call cap.
Do not expose scores to a researcher, call the API reader frozen, or start the
five-round campaign: the first real block had zero aggregate SD but 2/40
item-level flips. Long-memory and live long-horizon work remains offline or
frozen-policy transfer until the diagnostic and task-specific causal gates pass.
