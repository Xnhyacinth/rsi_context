# R3 correctness boundary and next experiment gates (2026-09-24)

Status: prospective plan and evidence audit, **not** a statistical contract for a
completed run. This note does not change `artifacts/rsi-core-v1/r3-live.json` or
its recorded scores. The R2a/R2b rules in `docs/stats-contract-v1.md` remain
historical; that file explicitly leaves B/C endpoints, formal sample size, and
confidence intervals open. Freeze a new, versioned manifest and contract before
the next scored live comparison. Do not relabel old R3 as preregistered evidence.

## Scientific question and current evidence

The target is whether project experience improves a model-driven agent's
reading, retention, verification, and action policy on **unseen projects**, and
whether any gain survives changes of project, rule, and action history at a
reasonable total cost. The intended contribution is a controlled, auditable
memory–action dependency task family and a comparison protocol, followed by
empirical findings. A positive update result is not required; a valid null,
regression, or sufficient fixed policy is informative. The project goal note
(`docs/goal-value-contribution.md`) separates implemented environment
semantics from unvalidated model difficulty and still-pending findings.

R3 is a first live developmental record, not an estimate of benchmark-level
improvement. In `scripts/r3_compare.py`, the B/C sequence branch constructs a
fresh `ProjectState` for each session, even when the project's later session
must inherit the prior session's records, verifications, and revisions. The
same branch omits the arm's `initial_state`; the frozen Recuris worker reads
`state['recuris_memory']`, so B/C package delivery is absent from this path.
The B decision rules populate `decisions` but omit `failure_detail`, depriving
the improver of the named failed-decision evidence that the M2 rule set can
provide. These are measurement and feedback defects, not failures of the
scientific hypotheses. Treat all B/C arm comparisons in old R3 as pipeline
diagnostics; do not cite their deltas as update, memory, or recovery effects.
The A path does not have these sequence-entry defects, but its one mother and
one mirror remain same-family development material; its live repair followed
by mirror regression is a useful case study, not transfer evidence across
independent projects. All R3 unassisted-update arms retained their baseline
after truncated researcher output, so their zero deltas do not measure a
successful policy revision. Keep the raw artifact and the original table in
`docs/r3-live-record.md` unchanged, with a visible erratum there.

The M2 offline panel (`artifacts/rsi-core-v1/m2-validity-panel.json`) reports
10/10 reference-solvable cases and a deterministic rule/material audit. Its
responders are scripted and some cases are twins of a parent. It establishes
basic construction and grading reachability, neither real-model difficulty
nor ten independent projects. The A dossier's `bulk_cards` are currently
name-filterable; increasing them alone does not establish hard long-context
selection (`docs/task-card-research-v4-dossier.md`).

## Gate 0 — repair and offline admission before another live matrix

Owner: harness implementation and independent code reviewer. Admission needs
behavioral tests and one fresh offline artifact, not merely a passing type
check.

1. Run B's first two sessions on the **same** project environment and its
   fresh-project third session on a new one. Run both C sessions on their
   shared project environment. Test that a submitted record and a
   verification/revision from an earlier session affect the later legal
   answer, while B's new-project session cannot inherit them. Reconcile
   other parent sequences against their material builders and
   `run_session_sequence`.
2. Inject the arm's `initial_state` package into **each** B/C hook as
   arm-level configuration; the worker's mutable cross-session state still
   obeys the carry-only persistence contract. A Recuris probe card must
   appear in applicable **metered model prompts**, its card ID in
   `memory_delivered`, and neither in stages excluded by invocation. Test the
   actual `r3_compare` dispatch, not only the worker policy in isolation.
3. Populate B's `failure_detail` for every failed decision with its matching
   gate or follow-up failure; successful decisions have no failure string.
   Exercise a deliberately failing B case and confirm the dev feedback trace
   contains that detail. No eval failure text may enter an improver input.
4. Confirm all repaired B/C arms use the intended dev/eval worlds, shared
   arm-level budget and registry, complete decision vector, and full cost
   ledger. Re-run the scripted reference and compare its decisions to the
   legal-state audit. Record the new code revision and a new output path; do
   not overwrite R3.

Gate 0 fails if any causal state, memory-delivery, feedback, or accounting
probe fails. Fix the instrument and re-run the offline admission before
spending on live calls. A corrected score is a **new** result.

The repaired checkout has a separate scripted artifact at
`artifacts/rsi-core-v1/r3-corrected-offline-v2-20260924.json`. Its B development
baseline passes 6/6 decisions after project-state continuity is restored;
this is an offline wiring result, not a live capability result. Targeted
R3/Recuris/B-session/R2a regressions passed 56 tests in this checkout. The
old live artifact remains untouched. The R3 entry now builds a run-identity
manifest with code, material, model-profile, and configuration hashes for new
runs; this addition cannot retroactively identify the old live artifact. A
new scored matrix still requires a frozen statistical contract and admission
through the gates below.

## Gate 1 — researcher usability and model difficulty pilot

Freeze the pilot's model/profile, request and completion caps, retries,
candidate count, dev feedback, and cost ledger before running it. Use a small
fixed manifest of A/B/C development cases and the **same configured
researcher budget** across the update and search attempts. The R3
`finish_reason=length` events show why the current cap must be reviewed in a
new versioned configuration, but neither a larger cap nor prompt shortening
can be retroactively applied to R3. Record every attempt, including truncation,
invalid Python, load/audit rejection, accepted change, unchanged snapshot,
worker failures, and all researcher/worker/tool tokens and wall time. The
readiness endpoint is the **valid-update rate** (valid submitted snapshots /
all planned attempts), alongside whether at least one attempted change in
each claimed method/group actually reaches a metered worker decision. If this
does not occur, report an engineering feasibility result and revise the pilot;
do not run or interpret a comparative efficacy matrix yet. This gate is about
executability, never selecting a setting because it improves the score.

With the instrument usable, run a fixed-policy difficulty pilot on qualified
candidate projects. Inspect wrong decisions and full traces, not just project
passes. Keep easy cases for retention/regression checks. The existing
benchmark contract's development diagnostics (`docs/benchmark-contract-v2.md`;
single-policy saturation at 0.90 and top-two disagreement at 20%) can inform task revision,
but any case inspected or revised after this pilot remains development
material; it cannot later be treated as unseen evaluation.

The fixed A-development v3 usability run has now produced two executable,
changed policies in two planned attempts with provider-reported usage and
matching run identity. One passed and one failed that development world;
neither was selected by score. The pilot omitted `PolicyAuditor` from its
pre-worker gate, and a post-run audit flagged draw 1's string `.replace()` as
`FILE_WRITE`; therefore candidate admission remains open even for A. B/C
usability, independent-project difficulty, and transfer remain unmeasured. See
[`r3-researcher-pilot-v3-20260924.md`](r3-researcher-pilot-v3-20260924.md)
for the exact artifact hashes, token counts, and limits.

A corrected `PolicyAuditor` later passed both saved A candidates in a
separate post-run audit. The v4 implementation now audits each candidate's
exact in-memory source and Python-only directory before loading it, with a
byte-hash match; its live run is paused pending process/container isolation
from credentials and evaluator-only material. This post-run audit does not
retroactively change the v3 protocol or supply an A/B/C effectiveness result.

## Gate 2 — independent project and causal-task qualification

Author additional parent projects with different source material and
dependency structure, not supplier-name or answer swaps. Register a parent
ID for each lineage; mirrors and parameter variants inherit that ID. Build
separate A/B/C coverage with a controlled mix of evidence distance, session
resets, scoped rule changes, and action dependencies. Do not count a group as
qualified merely because another group is. Use disjoint source segments and
document a material hash, provenance, and author review for each parent.

Each parent needs a reviewer-executable ledger of decision → required
proposition → available evidence/verification → legal action → later state.
Qualification probes must show: (a) full evidence admits at least one legal
solution; (b) remove decisive text and parallel verification separately and
then together, recording which justification and legal action each removal
eliminates; (c) changing an early commit/verification changes a specified
later legal answer; (d) changing the
scope of a rule revision distinguishes still-current from superseded evidence;
and (e) irrelevant material perturbation leaves the legal answer unchanged.
For B, prove the dependence crosses a real session reset; for C, prove a
receipt or write changes a later available action/answer. Audit information
shown to the worker against evaluator-only labels. Reference scripts prove
solvability only; a real-model pilot must establish difficulty and separation
of plausible policies. Reject invalid worlds before the formal manifest is
frozen; archive rejection reasons and do not silently replace worlds after
results are observed.

## Gate 3 — formal comparison to freeze before scaled calls

Write `stats-contract-v2` (or equivalent versioned contract) and a manifest
before any formal arm starts. The following are choices to fix there, not
post-hoc degrees of freedom:

| Design item | Prospective rule |
| --- | --- |
| Main endpoint | Project completion within each A/B/C group: all required decisions and end-state checks pass. Report each group separately; do not pool unlike tasks into one percentage. |
| Independent unit | Parent project/trajectory. All sessions, decisions, mirrors, seeds, and fresh model repeats within it are clustered observations, not additional independent projects. |
| Comparisons | Pair arms on the same parent, reader profile, tool budget, order protocol, and evaluation material. Include strong fixed; frozen strategy with accumulated experience; unassisted strategy update; same-budget non-adaptive search; and an actually delivered Recuris package. An external method enters only after its own fidelity and budget audit. |
| Update selection | Fixed round and candidate counts; final snapshot is the last produced under the declared rule. Invalid attempts and fallback retention remain in the denominator. No selecting a snapshot on evaluation score. |
| Analysis | Per-parent paired project-success differences and clustered uncertainty intervals, by group; decision-level failure anatomy is secondary. Predeclare how any multiple primary group tests will be interpreted. Repeated requests estimate service variance, not project diversity. |
| Budget fairness | Declare equal opportunity for improvement calls/feedback and candidate screening where the attribution comparison requires it; separately report actual `C_improve`, per-project `C_deploy`, and `C_improve + N·C_deploy` for declared deployment horizons N. Model, tool, validation, memory-maintenance, and retry spend all count. |
| Stopping/failures | Fixed manifest, order seeds, rounds, caps, endpoint retry policy, and run window. Every planned-and-started unit is reported. Method errors, invalid outputs, budget exhaustion, and infra failures follow the predeclared failure rule; no reruns or replacements triggered by scores. |
| Validity checks | Same-policy fresh-request variance, model/profile echo and usage canaries, prompt/card delivery, source-material hashes, and dev/eval information isolation. Freeze the remedy for a failed batch before observing arm outcomes. |

Set the number of **independent parents** from pilot variance, a stated
minimum effect of practical interest, and available budget; document the
calculation and the feasible precision before the formal run. Do not choose
sample size, evidence strata, or a favored reader after looking at formal arm
deltas. If the feasible number is too small for a claimed population effect,
publish per-parent cases and descriptive uncertainty only. Hold out new
parents for migration, and distinguish continuation on a known parent from
transfer to one never used for improvement. Use multiple task orders and a
second reader family when qualified; report those strata rather than folding
them into a pooled headline without a predeclared model.

The worker `model_tokens_in/out` fields are local whitespace word estimates
from `PolicyHook._ask_model`, labeled as such in newly produced R3 artifacts.
The new live responder also records provider-reported worker token usage per
call. Keep those units and researcher usage separate, and reconcile missing
usage on failed calls before any cost comparison. No dollar net-benefit claim
follows from the current developmental runs.

## Release/claim boundary

Gate 0 licenses a corrected development run. Gate 1 licenses a claim that the
researcher interface can produce executable updates and that the task has
observed model difficulty on the pilot panel. Gate 2 licenses an independent
project benchmark candidate. Only a frozen Gate 3 run licenses comparative
statistical and transfer claims. If a gate fails, preserve its artifact,
diagnose the specific mechanism, and version any subsequent experiment.

Related-work positioning remains narrow. [SEAGym](https://arxiv.org/abs/2606.17546)
already evaluates frozen update-validation, held-out in-distribution and
out-of-distribution transfer, replay, and cost. [EvoPathBench](https://arxiv.org/abs/2609.24663)
(arXiv submission dated 2026-09-21) freezes evolving artifacts at successive
checkpoints and tests generalization, retention after unrelated learning, and
adaptation to changed rules. These individual evaluation views are therefore
not novel claims. The independent-world scan
(`docs/research/scan-worlds-20260921.md`) and benchmark contract
(`docs/benchmark-contract-v2.md`) also credit task streams, cross-session
memory, and matched controls to adjacent benchmarks. The project's proposed
value must be demonstrated by **auditable causal dependencies, independent
project diversity, and valid costed comparisons** in this task family.
