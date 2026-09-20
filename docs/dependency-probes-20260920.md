# Dependency-structure probes: research-v1 fails all four (2026-09-20)

Status: **development diagnostic record (review step 3, completed)**. The
probes implement the external review's dependency-verification questions
against the current research-v1 family on the T2 reader. Artifacts:
`artifacts/qualification/probe-{longdoc,factswap,irrelevant,nohistory}-20260920.json`.

## Verdicts

| Probe | Question | Result | Verdict |
| --- | --- | --- | --- |
| longdoc-necessity | do long documents participate in the answer? | gold-evidence 0.625 = short-rule-only 0.625 | **FAIL** — removing all evidence does not change the hit rate |
| fact-swap | does the answer follow edited evidence? | flip rate 0.125 | **FAIL** — answers barely depend on the evidence text |
| irrelevant-perturbation | is the answer stable under irrelevant edits? | stability 0.625 | **FAIL** — irrelevant edits move answers more than relevant edits |
| no-history | is cross-stage memory necessary? | empty-state 1.0 = stateful 1.0; **8/8 items have the answer literally present in the final stage's prompt** | **FAIL — structural leakage: the act_verify stage's gold-anchor document contains the answer** |

## Root structural finding

The five-stage lifecycle is **decoratively coupled**: the final
act_verify stage receives the gold anchor document (whose text contains
the answer), so a participant that ignores every earlier stage and reads
only the last prompt solves the task. This explains every downstream
observation, including the n=16 panel's behavior: within-family
"difficulty" was dominated by item label defects (fixed by alias scoring
+ entailment gating, landed 2026-09-20), and whatever memory/notes
strategies arms adopted were largely irrelevant to the outcome.

## Consequences (task-family revision, replacing the withdrawn items)

1. **Stage leakage must close**: the act_verify stage's evidence set may
   not contain the answer-bearing gold passage. Design options (pick in
   the family revision): (a) final stage receives only a verification
   CHECK (e.g. a checksum/clue that discriminates candidate answers
   without containing them); (b) answer-bearing evidence appears only in
   EARLY stages, and the final stage must reconstruct from retained
   state; (c) act_verify's expected state references a fact only
   derivable by combining early-stage evidence with the rule-change
   event.
2. **Evidence dependence must be real**: after the fix, the fact-swap
   flip rate must be high (answers follow edited facts) and
   irrelevant-perturbation stability high. These two probes become the
   family's standing regression instruments.
3. **Long-document load-bearing**: the survey-stage corpus must contain
   the answer-bearing material that the final stage does NOT receive;
   longdoc-necessity then must show gold ≫ short-rule.
4. **Memory necessity must be structural**: with (b)/(c), empty-state
   runs must fail; the no-history probe re-runs as a standing gate.
5. The qualification panel's remaining pending gates (gold-drop,
   provenance-drop) are subsumed by these four probes once the family is
   revised: gold-drop ≈ evidence-missing, provenance-drop ≈ the
   provenance-metric probes.

## What stands (from the earlier records)

- Alias-aware scoring + gold-entailment gating: landed
  (`lifecycle/material.py`), kills the label-defect class.
- Channel parity: verified equal (root-cause report).
- Contract amendments (snapshot/branches, fixed-arm redefinition,
  source/time/scope state rule): landed in the specs.
- Independent-worlds constructor: landed (`src/rsicontext/worlds/`) —
  the revised family builds on it directly (worlds become the unit whose
  early stages carry the answer-bearing material).

## Disposition

The research-v1 family as currently constructed is **not qualified**; the
revision above is mandatory before any further arm comparison. No
conclusion about arms, methods, or improvement may be drawn from runs on
the unrevised family (the n=16 panel record already says this for other
reasons; this record extends it with the structural cause).
