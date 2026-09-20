# research-v3 main world implemented (2026-09-21)

Status: **engineering record** — review round 4 deliverables 3+4 (the
hand-audited main world + the executable failure classes). 887→909
tests; ruff, strict mypy (122 files), full suite green. Task card:
`docs/task-card-research-v3.md` (frozen BEFORE this implementation).

## What landed

1. **Sandbox v3 semantics** (`lifecycle/env.py`, backward-compatible):
   - `finalize` LOCKS its target record — later `update_record` /
     `finalize` on it raise a named error. Supersession proceeds by NEW
     records (the behavior the improvement opportunity rewards). No
     existing call site finalizes-then-updates (verified: all v1/v2
     material and hooks create+finalize once), so no behavioral change
     for research-v1/v2.
   - `Action` gains OPTIONAL finalize preconditions:
     `precondition_refs` (referenced records must exist),
     `precondition_current_revision` + `precondition_revision_scope`
     (in-scope checks must carry the current protocol revision —
     PARTIAL invalidation: records outside the scope are untouched),
     `precondition_scope_constraint` (a domain-scoped required check).
     Preconditions are evaluated BEFORE any field is written, so a
     refusal leaves state untouched. Omitted fields = exact v2
     behavior.
2. **The migration-decision world** (`lifecycle/material_v3.py`,
   family `research-v3` registered in `spec.py`): five candidate plans
   with buried exception clauses, a scoped finance-domain constraint, a
   delegation surface, a partial rule change (replica-lag check only),
   and a commit whose finalize carries the world's preconditions.
   Legal plan set {aurora, cumulus, ember} is DERIVED from the material
   (task card §Scoring), not a hidden gold string; `answer_aliases`
   carries it for audit; the final check is
   `migration_commit.status == final`, and legality is enforced at the
   action boundary.

## Deliverable 4: the five failure classes, executable (tests/test_material_v3.py)

| Class | Test | Observable behavior |
| --- | --- | --- |
| 1 compression-loss of exception | `test_failure_class_1_missing_cutover_support_is_refused` | borealis (finance, no cutover) commit refused: "scope constraint … requires online-cutover verification" |
| 2 stale conclusion after supersession | `test_failure_class_2_stale_conclusion_is_refused` | draco commit on revision-1 replica-lag evidence refused: "stale protocol revision (in rule-change scope)" |
| 4 plan on outdated state | `test_failure_class_4_finalized_record_cannot_be_silently_revised` | finalized record cannot be updated in place; recovery = new superseding record (passes) |
| 5 declared vs actual | `test_failure_class_5_declared_vs_actual` | finalize referencing nonexistent records refused: "unknown record" |

(Class 3, delegation-without-provenance, is exercised by the delegation
path's required return fields — the stage-3 prompt and the task card
define the refusal; a dedicated test lands with the real-reader
trajectory where a sub-agent actually returns.)

## All four legal solution paths pass (engine validity, layer 2)

`test_all_legal_paths_pass[full-notes|reread|delegation|avoidance]` —
each scripted strategy completes and passes the final check. The
avoidance path (committing non-finance cumulus) is deliberately legal
and cheaper: a strong fixed strategy succeeding is a result, not a task
failure. Counterfactuals: partial-scope verification
(`test_counterfactual_scope_is_partial_not_global` — revision-1
disk-encryption records do NOT block commits), gold-drop analog
(finance plans without cutover support have no legal commit), recovery
(the reread path works from lost notes; its cost is the caller's
ledger).

## What this does NOT claim

- Layer 3 (real-system behavior) is untested here: no real reader has
  run this world. That is deliverable 5.
- One parent world: variants derived from this material count as ONE
  world for statistics; independent worlds need independent material.
- The stage-1 corpus here is benchmark-authored (the task card's
  anti-invention rule anchors every constraint to a named document);
  wiring real-corpus passages as the document substrate for VARIANT
  worlds is constructor work for the pool stage (deliverable 6), not
  for this world's validity.
