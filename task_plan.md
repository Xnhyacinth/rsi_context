# A2 qualification and evaluator hardening

## Goal

Advance the next preregistered RSIBench-Context unit without launching an
ineligible researcher matrix: qualify the real causal multi-hop data path,
harden and test the frozen evaluator boundary needed by that path, execute the
largest scientifically valid offline/smoke experiment available, and leave a
reviewed, reproducible Git commit.

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

**Status:** in_progress

- Inspect the exact diff and secret/data-boundary status.
- Commit with a focused conventional message and push the private branch.
- Report achieved evidence, remaining gates, and next executable experiment.

## Decisions

| Decision                                                     | Rationale                                                                                                |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Keep static causal qualification primary                     | It has the lowest replay noise and is the current normative blocker.                                     |
| Treat all-hy3 runs as API replication                        | The alias lacks an immutable provider revision and failed the latest strict post-canary.                 |
| Do not implement unrestricted harness evolution yet          | It would break matched-search identification and overlap Recuris/AHE before the primary benchmark works. |
| Use a pinned community MuSiQue mirror only for qualification | It provides immutable LFS bytes now; formal A2 still requires byte-matching the official archive.        |
| Drop the unused HTTPS downloader probe                       | It cannot establish an official archive checksum before first acquisition and adds unsupported surface.  |

## Errors encountered

| Error                                                           | Attempt | Resolution                                                                               |
| --------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------- |
| New HTTPS registry tests failed before implementation           | 1       | Expected TDD red state confirmed.                                                        |
| Official MuSiQue archive has no published checksum              | 1       | Use a pinned mirror for qualification only; keep official-byte matching as an A2 gate.   |
| Combined cleanup patch missed autoformatted plan lines          | 1       | Split the patch into exact, smaller edits.                                               |
| Combined tokenizer/statistics probe returned no captured output | 1       | Run the tokenizer analysis as a separately polled process.                               |
| Real MuSiQue row used integer decomposition IDs                 | 1       | Added a regression test and normalized official non-negative integer IDs to strings.     |
| Packed v1 compiled below its declared 32,768-token target       | 1       | Added a regression test and top up after measuring compiled chunk tokens.                |
| Reviewer found v2 causal/provenance assertions were incomplete  | 1       | Added intermediate leakage, derived digests, tokenizer attestation, and token positions. |

## Next step

Commit the reviewed qualification code, rerun native and packed qualification
from that clean commit, then update the report with the clean artifact identity.
