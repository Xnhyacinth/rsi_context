# Score-graded outcomes on the v3 surface — analysis (2026-09-21)

Scope: what is already graded vs placeholder, what the v3 world can grade
deterministically today, and the smallest honest grading layer. All claims
were checked by running the code (probe scripts in `$CLAUDE_JOB_DIR/tmp/`).

## (i) Existing vs placeholder inventory

| Signal | Where | Status |
| --- | --- | --- |
| `stale_references` (tuple of superseded record ids a finalized commit still cites) | `src/rsicontext/lifecycle/runner.py:279-305`, wired at `:275`, tested `tests/test_area6_gaps.py:243-273` | REAL, evaluator-side, computed from the sandbox snapshot |
| `StageRecord.provenance_retention` | `runner.py:165-180`, set `:244`; gold ids packed for the whole stage-1 corpus at `material_v3.py:233` | REAL but ≈constant: stage 1's gold = every survey doc, so citing any one doc yields 1.0 |
| `StageRecord.stale_fact_rate` | hard-coded `runner.py:246`; docstring calls it a qualification-battery placeholder `:94-97` | PLACEHOLDER (always 0.0) |
| `StageRecord.delegation_completeness` | hard-coded `runner.py:247` | PLACEHOLDER (always 0.0) |
| Commit gate (`final_check.failures`, count + message text) | `runner.py:308-400`, applied `:258-264`; material `material_v3.py:291-300`, `material_v3_variant.py:401-410` | Binary pass/fail, but the failure TEXTS are already a coarse ordinal (see (ii)) |
| `cost` | `runner.py:272` — `tokens_in/out` literal 0.0, `wall_seconds` measured | Half placeholder |

Measured run shapes (same hook as `scripts/trajectory_v3.py:261-324`), all 5 stages,
`provenance_retention` printed per stage:

- main / S0 shape (legal plan, rev-1 evidence): `passed=False`, 1 failure, `stale_references=0`,
  `prov_ret=[0.0, 1.0, 1.0, 1.0, 1.0]`
- main / S2 shape (legal plan, rev-2 evidence): `passed=True`, 0 failures, `stale_refs=0`, same `prov_ret`
- main / S2 + a `supersedes` link: `passed=True`, 0 failures, `stale_references=0` — the stale-reference
  metric cannot fire on any run the matrix actually produces, because the un-repaired shape is refused by
  the participant's own finalize precondition and fails the *branch* ("ran": false) instead of reaching the metric.

## (ii) Per-candidate graded signal

(a) **Partial credit over the required-verification set** — NOT computable from the v3 material today.
`commit_precondition` is keyed by the COMMIT record id (`material_v3.py:292`), i.e. it names *this world's*
`migration_commit` — and every v3 world uses that same record id (`material_v3_variant.py:33`). A world-pool
requirement set is therefore not expressible. The legal paths also differ in kind (avoidance legitimately
cites a rev-1 irrelevant check and passes; probe above), so a "required set" would encode one path's shape.
Verdict: needs constructor changes + an audited `plan_requirements` for all plans; not infrastructure-free.

(b) **Plan-choice quality (cheapest legal plan vs committed)** — the cost bands survive only as prose in
`DocumentRef.text` (`material_v3.py:70,82,95,109,125`); no structured field. Grading it means (1) a
structured `cost_band` in material, (2) deciding whether cheapest-legal is a *better* outcome, which the task
card denies (`docs/task-card-research-v3.md:103-106` — avoidance is "legal, cheaper, and a correct outcome";
the four paths are "all must succeed"). Any "plan-quality score" would penalize a sanctioned path —
misleading, and unfair to the arms it grades.

(c) **Reread cost** — genuinely observable in the hook (`scripts/trajectory_v3.py:185`, appended at `:252`),
but it is NOT evaluator-side: no lifecycle surface carries reader calls, and a reread is a legitimate path
(`docs/task-card-research-v3.md:60-66`). Reporting it is fine as cost; "grading" it is not. Also vetoed
right now by the evidence in (iii): the hook's `rereads` list is appended unconditionally for every
participant, so today it is a constant.

(d) **Staleness count at commit time** — real but degenerate on the current surface: the gate already fails
any in-scope stale reference, and `stale_references` (the finalized-commit-driven version of this) is
unreachable because the refusal short-circuits the branch first (evidence above).

(e) **Gate failure count (N distinct gate failures, 0 = pass)** — already produced by the current code path
(`final_check.failures`), no new computation: `runner.py:258-264` appends gate failures to the checker's
failures, and a passing commit has an empty list (probe: 1 vs 0). Honest ordinal at n≤3, deterministic,
not gameable — a participant cannot make the gate emit fewer failures without emitting a better commit.

## (iii) Recommendation — minimal layer (one signal, no new machinery)

Grade `gate_failure_count` (= `len(final_check.failures)` restricted to `commit gate:` entries), nothing else.

- Where computed: in the script layer at `scripts/trajectory_v3.py:evaluate_branches` (~`:499`), beside
  `final_checks`; and rendered by `scripts/matrix_analyze.py` (~`:35`) as a second column next to pass/ran.
  Zero src/ change: the data is already in `LifecycleRunRecord.final_check.failures`.
- Wiring test to pin: extend `tests/test_trajectory_wiring.py:22` (`test_offline_trajectory_closes_the_loop`, already asserts both the pass shape and the `{"error": ...}` shape) (or `tests/test_commit_gate.py`) with an
  offline `trajectory_v3` run asserting the emitted cells carry `gate_failure_count` and that the S0 cells
  read 1 while the S2 cells read 0 on all three surfaces (main/orinoco/parana).
- Precondition: report it only over cells with `ran: true`. A refused finalize aborts the branch
  (`run_session_flow` -> `run_lifecycle` raises; `scripts/trajectory_v3.py:508-516` records
  `{"ran": false, "error": ...}`) — visible in `artifacts/trajectory-v3/live-20260921.json`, whose F0 and S0
  cells carry `ProjectStateError: ... stale protocol revision 1` and therefore no `final_checks` at all.
  Current matrix artifacts have zero such cells, but the counterfactual variants and the reread/recovery path
  are documented to produce them (`docs/task-card-research-v3.md:127-133`), so the analyzer must not average
  over a missing cell.
- Honest at 2×2×2 because the observable it reports is ≤3-valued (0 / 1 / refused) and deterministic; floor
  and ceiling are observed, not assumed, and no data is discarded.

**Prerequisite before ANY score-graded cell (blocks this whole rung, not just this signal):** the reader
variance floor. The current hook does one `temperature: 0.0, seed: 42` reader call per stage and discards
the reply into `notes` (`scripts/trajectory_v3.py:124-134,247-248`); plan choice and re-verify decisions come
solely from the strategy file. So the only score-carrying path is the strategy → the matrix's 3-vs-15 split
measures researcher-strategy quality, not participant graded quality, and a "score" would have a variance
floor of exactly zero. Either report the metric as *strategy quality* and say so, or make the reader's
reply feed the plan/verification decisions first. `docs/matrix-v3-20260921.md:78-81` already names this.

## (iv) Non-recommendations

- Do NOT grade reread cost per cell: not evaluator-side, legitimately optimal on the reread path, and the
  hook's `rereads` list is currently unconditional (`scripts/trajectory_v3.py:252`) — a constant.
- Do NOT grade provenance_retention: pinned at 1.0 for every stage after survey (gold = all survey docs,
  `material_v3.py:233`), and inflatable by citing all docs in one pack string (probe:
  `prov_ret=[1.0]*5` for a hook that cites every doc id in a pack text and still passes).
- Do NOT grade plan-quality / cheapest-legal: cost bands are unstructured prose, and the task card
  explicitly sanctions the cheap-avoidance outcome; the score would penalize a legal path.
- Do NOT report any weighted composite or 0-1 "quality score": every candidate weight is unmeasured, and a
  composite would manufacture precision the 2×2×2 (one parent world pair, history-sharing cells) cannot carry.
- Do NOT fill in `stale_fact_rate` / `delegation_completeness` yet: the first needs a supersession without a
  refusal (unreachable on runs the matrix produces), the second needs a persisted delegation return record
  (stage 3 currently only emits `StageResponse`, `runner.py:236-250` — no return field exists anywhere).
