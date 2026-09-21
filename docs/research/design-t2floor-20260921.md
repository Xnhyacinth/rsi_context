# T2 variance-floor integration for the v3 trajectory matrix — design findings (2026-09-21)

## (i) Existing T2 machinery inventory

All of it lives in one module, **library + tests only — no script imports it**:

- `src/rsicontext/reader_tiers.py`
  - `ReaderTier` enum (T1/T2/T3): lines 34–46
  - `GateEvidence` (canary booleans, `variance_floor_value`, `variance_repeats`,
    version, access window, echo): 49–99
  - `MIN_VARIANCE_REPEATS = 5`: 122
  - `evaluate_tier`: 125–173 — T2 requires canaries ok AND floor measured AND
    repeats ≥ 5 AND version+window+echo recorded; else T3. Canary failure sets
    `batch_invalidating` (162–168).
  - `check_rejection_ceiling(observed, ceiling, evidence)`: 176–205 — above
    ceiling ⇒ T3 rejection for that block; at/below falls through to `evaluate_tier`.
  - `profile_tier`: 208–230 — profile-level floor (pinned `provider_revision`).
- Tests: `tests/test_cost_tiers.py:207-221` (missing floor / repeats<5 ⇒ T3),
  `:258-268` (ceiling reject; at/below falls through), `:271+` (profile_tier).
- Contract text: `docs/benchmark-contract-v2.md:178-185`.
- Canaries: **not implemented anywhere as runtime code** — hy3 scripts measured
  them ad hoc; `reader_call` (trajectory_v3.py:115-149) records no model echo.

## (ii) Sensitivity: where reader variance can reach a score-graded cell

- `TrajectoryHook.on_stage` (trajectory_v3.py:238-248): the reply feeds **notes**
  only; notes feed later prompts (234-236) and are frozen into snapshot memory
  (`run_dev_session` store.write, 409).
- **Keyword-collision channel (real, narrow)**: `_survey_text` is the *prompt*
  incl. the notes prefix (244). `_first_plan_name` (86-105) scans prompt lines —
  a note line ending in "plan" hijacks plan choice; `_survey_checks` (108-112)
  and `PLAN_PREFERENCE` membership (226) scan prompt text incl. notes. So live
  replies can alter committed plan/check fields ⇒ gate outcome and partial
  credit. Observed 0 flips in the live matrix, but the channel is open.
- Score-surface ranking: (a) notes-derived or reader-as-judge scores — fully
  reader-sensitive; (b) partial credit over `final_check` failures — sensitive
  only via the collision channel today, fully sensitive once a "realistic
  participant" parses replies; (c) gate-binary — effectively insensitive (4/4
  live runs stable). The next-rung score-graded design lands in (a)/(b).
- `--researcher`: feedback is deterministic gate text, but the author model's
  output varies **per run** (s29's broken strategy) — above-reader variance,
  not in-batch.

## (iii) Minimal integration (no new modules; offline-testable)

Pre-registered now, in code, before any live score-graded run:

1. **Constants** after `_KNOWN_CHECKS` (trajectory_v3.py:83):
   `_VARIANCE_CEILING = 0.05` (anchor: minimal reportable contrast 0.20, hy3
   precedent; ceiling at 1/4 of it) + `from rsicontext.reader_tiers import
   MIN_VARIANCE_REPEATS` in the import block (~line 60) — single source of ≥5.
2. **Pure scorer** after `evaluate_branches` (~line 518):
   `_snapshot_score(branch_results) -> float` = pass fraction over all
   `final_checks` entries — the statistic the matrix already reports (x/6).
3. **CLI** in the parser (523-545): `--variance-repeats` (default 0 = off) and
   `--variance-cell` (default `"S1"`); repeats>0 and < MIN_VARIANCE_REPEATS ⇒
   stderr + return 2; cell must exist in `branch_results`.
4. **Repeats block** after the branch_results loop (after line 728, before
   `elapsed`, 730): resolve the snapshot (`f0`/`s0`/`snapshots[cell]`) and its
   strategy; run `evaluate_branches` N **fresh** times with
   `seed_suffix=f"-s{args.seed}-vr{i}"` (session-id distinct, policy identical —
   same request profile temp 0/seed 42); score each; report
   `payload["variance_floor"] = {cell, repeats, scores, sd, flip_rate,
   ceiling, within_ceiling}`. SD = sample stdev (ddof=1); flip_rate =
   1 − modal share (the honesty statistic at n=5 with discrete scores).
   Do NOT reuse the already-computed cell as one of the N (fresh-request only).
5. **Wiring test** (`tests/test_trajectory_wiring.py`): offline
   `--varariance-repeats 5` ⇒ `repeats==5`, `sd==0.0`, `flip_rate==0.0`,
   `within_ceiling is True`, cell recorded; `--variance-repeats 4` exits 2.
6. Optional: `matrix_analyze.py` surfaces `variance_floor` in its header.

Claim rule (floor usage): a reported S_n→S_m score delta must exceed
max(2×observed_sd, any pre-set floor) — written into the matrix doc when the
first score-graded run is preregistered. Cost: 5 repeats ≈ 150 reader calls.

## (iv) What this floor CANNOT cover

- **Researcher-arm nondeterminism**: strategy is re-authored per live run;
  branch repeats from a frozen snapshot cannot see it (the seed axis exposes
  it only by repetition across runs).
- **Dev-session drift**: snapshot memory is frozen from ONE dev session; the
  floor measures post-freeze variance only.
- **Cross-run endpoint drift**: in-batch floor is per-run; version/window/echo
  recording and pre/post canaries (echo not even captured in `reader_call`)
  are separate, still-unwired T2 gates.
- **Fixed-decoding scope**: repeats at temp 0/seed 42 bound fresh-request
  replay variance, not sampling-temperature variance.
- **Statistic-specific**: defined for pass-fraction; a new graded score needs
  its own floor re-measured. World-material variance is a design axis (pool),
  never covered. n=5 makes the SD itself noisy — report raw scores alongside.
