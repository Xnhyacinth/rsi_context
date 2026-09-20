# Task card: research-v3 main world (2026-09-21)

Status: **frozen task card** — review round 4 deliverable 3, step 1 (the
card freezes BEFORE the constructor; the constructor implements it, never
the reverse). Version marker `research-v3` per
docs/legacy-seal-20260921.md. This world is hand-audited; automated
variants derive from it and count as ONE parent world (never as
independent samples).

## User goal

The project owner must choose ONE deployment plan for a data-warehouse
migration, from a set of candidates, and execute it in the sandboxed
project state: the committed configuration must satisfy every CURRENT
constraint, be supported by CURRENTLY-VALID evidence, and the required
preparatory operations must actually have been performed and remain
un-reverted at the end.

## Material (what exists, where)

Real PopQA/KILT passages are the document substrate; the candidate/
constraint/verification facts are benchmark-authored and deterministic,
each anchored to a specific document id (the constraint text is
generated so its satisfaction is checkable against those documents
only — same anti-freeform-invention rule as v1/v2).

Documents (with ids, at their stage of arrival):

| id | content | arrives |
| --- | --- | --- |
| `doc-cand-a`…`doc-cand-e` | five candidate plans; each states capability, cost band, and — buried in prose — an EXCEPTION clause (e.g. "unsupported on clusters below v9" / "requires read-replica window") | stage 1 (survey) |
| `doc-verif-db` | verification protocol: which check validates which property (e.g. replica lag check validates the online cutover property) | stage 1 |
| `doc-exception-x` | one further exception, stated ONCE, in a low-salience sentence | stage 1 |
| `doc-constraint-k` | the new constraint (scope: applies to plans touching the finance domain ONLY) | stage 2 (constraint injection) |
| `doc-delegation-targets` | the documents a sub-agent may be asked to verify | stage 3 (delegation) |
| `doc-rule-change` | a version supersession: verification results obtained with the OLD protocol revision are stale; the new revision changes the replica-lag threshold | stage 4 (rule change) |
| (no documents) | — | stage 5 (act & verify) |

## Events (environment events, NOT prescribed steps)

| event | content | scope |
| --- | --- | --- |
| stage 2 | constraint K arrives: "finance-domain plans must support online cutover" | scoped: finance domain only; non-finance plans are NOT affected |
| stage 3 | a sub-agent verification offer is available (the participant MAY delegate checks; the return must carry finding/source/applicability or be treated as unusable) | optional |
| stage 4 | verification protocol superseded: old-protocol verifications are stale (scope: replica-lag checks ONLY); the new threshold changes which plans pass | partial invalidation — conclusions outside the scope survive |

The five failure classes (v1 spec) map to this world as: (1)
compression loss of an exception (the exception in `doc-exception-x` or a
candidate's buried clause interacts with constraint K); (2) stale
retained conclusion (a pre-supersession verification is applied after
stage 4); (3) delegation without provenance (a stage-3 return without
source/applicability is used to justify a commit); (4) plan on outdated
state (the sandbox's own earlier records — see action semantics — are
not consulted after the rule change); (5) declared vs actual mismatch
(finalize claims "migrated" while the sandbox lacks the required
preparatory record states).

## Information permissions

- The stage-1 corpus is available for RE-READ at later stages **at a
  ledgered cost** (one reader call per re-read document, accounted in
  the memory-op ledger + token columns): legitimate alternative path —
  a system that saved little can still recover by re-reading.
- Stage-5 receives no documents (answer reconstructed from retained
  state or from re-read results already in state).
- Nothing grants access to any document outside the instance's own set.

## Action semantics (sandbox)

`create_record` / `update_record` / `finalize` over typed records; NEW
v3 semantics (env change, backward-compatible — see implementation
record):

- records: `candidate_status` (one per candidate: verdict + evidence doc
  ids + protocol_revision), `verification_run` (check + result +
  revision + doc id), `migration_commit` (the chosen plan + required
  preparatory records + status).
- `finalize` on a record LOCKS it: later `update_record` on a finalized
  record is refused (a stale conclusion cannot be silently revised
  after being committed; the participant must re-verify and create a
  superseding record — or catch the invalidation BEFORE finalize).
- `migration_commit.finalize` has a PRECONDITION: the
  `candidate_status`/`verification_run` records it references must
  exist, carry the CURRENT protocol revision where the rule change's
  scope applies, and — for finance-domain plans — satisfy constraint K.
  A commit that references stale-scope records is refused at apply time
  (a wrong plan is a REFUSED action, not a silent zero: failure is
  observable and explainable, per the review's "不能只是把最终答案写
  入一个字段再把动作命名为 submit").

## Legal solution paths (all must succeed; the benchmark must not
prescribe which)

1. **Full-notes strategy**: stage-1 notes keep every exception clause
   + provenance; constraint K checked against notes; post-stage-4
   re-verification of the in-scope check; commit passes precondition.
2. **Reread strategy**: minimal notes; before commit, re-read
   `doc-verif-db` + the candidate's doc at ledgered cost; construct
   fresh verification records; commit.
3. **Delegation strategy**: stage-3 sub-agent returns
   finding/source/applicability for the finance check; principal
   re-runs only the replica-lag check post-supersession; commit.
4. **Avoidance strategy**: choose a NON-finance candidate unaffected
   by constraint K and outside the supersession scope — legal, cheaper,
   and a correct outcome (the task must not force the hard path; a
   strong fixed strategy succeeding is a result, not a task failure).

## Scoring (final + necessary-history conditions)

Final check (ObjectiveChecker, exact/alias):

- `migration_commit.plan` ∈ the legal plan set (after applying
  constraint K + the superseded-threshold rule: a fixed, published
  derivation from the material, not a hidden gold string — the
  owner-audited answer set is enumerable from the documents);
- referenced records exist and carry revision stamps consistent with
  the rule-change scope (necessary-history condition: the check
  inspects the sandbox's actual records, not the pack text);
- the required preparatory `verification_run` records are present and
  not superseded.

Per-stage secondary metrics (v1 spec §Metrics): provenance retention,
stale-fact application rate (count of finalized-then-invalidated
conclusions still referenced), delegation-return completeness,
declared-vs-actual match.

Counterfactual variants (diagnostic, same parent world):
gold-drop (remove the exception-bearing docs → the K-interacting plans
must become unverifiable), irrelevant-perturbation (edit unrelated
prose → outcome unchanged), fact-swap (swap an exception clause → the
legal plan set changes and committed plans must follow), recovery
(remove the participant's stage-1 notes before stage 4 → the reread
path must still succeed; its cost is reported).

## Improvement opportunity (what a BETTER strategy buys)

Reusable mechanisms, not per-item fixes: keeping exception clauses with
provenance; scope-aware invalidation (re-verify only in-scope
conclusions); re-read-before-commit under budget; requiring
source/applicability fields from sub-returns. These transfer to
variant worlds (different candidates/constraints/exceptions, same
dependency structure).

## Qualification bar (three evidence layers — legacy-seal §4)

1. **Semantic/label validity**: every constraint derivable from a named
   document; the legal plan set enumerable by hand from the material
   (this card IS that audit); disambiguation explicit.
2. **Engine validity**: the four legal paths above each complete under
   scripted hooks (oracle participants); the precondition refusals
   fire correctly; the counterfactual variants move outcomes in the
   predicted direction.
3. **Real-system behavior**: success and failure explainable along the
   evidence–state–action chain; no failure dominated by label defects,
   fixed gold positions, or stage-5 answer exposure (v2's closure
   carried over).
