# Task card: research-v4 "dossier" (A-group main task, R1 slice)

Frozen 2026-09-23 BEFORE the constructor's acceptance tests were run
against it (the v3 convention). Status: R1 longitudinal slice —
STRUCTURE load-bearing (horizon + memory); corpus SCALE is a
parameterized axis (`bulk_cards`), not yet frozen for main runs.

## What the participant must do

One supplier-selection project across EIGHT stages: survey a large
dossier (20+ supplier cards, protocol, memo), a scoped award constraint,
a delegation surface, a mid-project documentation rule change, the
primary-award commit (gate: environment-issued, subject-bound,
current-revision verification), then TWO follow-up requests separated by
a FINAL rule change — each graded by its own expected_state_delta over
followup_conclusion records.

## The three long-axis commitments and where they carry weight

| Axis | STRUCTURE present (R1) | Evidence level (R1.1, honest) |
| --- | --- | --- |
| **Long horizon** | 8 stages; decisions at s5/s6/s8 depend on s1 evidence (4+ stages, across a commit); a final rule change AFTER the commit invalidates specific evidence | Stage grammar + time-point commit grading pinned; **NOT yet shown**: later correct behavior depends on EARLY ACTION RESULTS (vs sequentially-graded questions) — that is C-group's requirement |
| **Long memory** | Stage-crossing retention is REQUIRED and both paths exercise it; follow-up 2 = scope-tracked staleness | Remember-path test (zero RE-READS — its verification ACTIONS are billed); **NOT yet shown**: real models select what to keep for unknown future needs; cross-SESSION recovery is B-group |
| **Long context** | Distant/buried decisive facts; `bulk_cards` scales the corpus (0/100/400 → 22/122/422 docs) | Scaling is a DIAGNOSTIC axis, not validated difficulty: filler is currently name-filterable (`filling-*`), so bulk measures robustness-to-ignorable-text, NOT selection among similar candidates; **NOT yet shown**: bulk increases effective processing difficulty for real policies |

## Load-bearing ledger (the no-lie constraint)

R1.1 proposition-level ledger (decision <- proposition <- evidence
path). Each decisive PROPOSITION has one textual source; env
verification is a PARALLEL legal route (text is not the only path — a
system may verify without having read the card):

| Proposition | Sole textual source | Grounds | Removal simulation |
| --- | --- | --- | --- |
| "Atlas's bonded corridor satisfies customs-preclearance" | card-03 | the award's memory basis | delete → memory-based selection loses its basis; the env-verification path REMAINS legal (test-pinned) |
| "Pinnacle's customs bonding lapsed" | card-17 | the decoy exclusion | decoy-path evidence only — a correct system that never read card-17 is NOT required to have excluded Pinnacle |
| "hospital-adjacent exemption transfers" | card-05 | FUTURE B-group material | NOT current required evidence (recorded, untested) |
| "Vesper's hub covers the five northern checkpoints" | card-08 | follow-up 1's answer | delete → the follow-up's proposition is unanswerable from the corpus (test-pinned) |

Everything else is plausible bulk; no card lies; irrelevant perturbation
(bulk growth) leaves the legal answers unchanged (test-pinned).

## Two REFERENCE execution paths (oracle-assisted fixtures — NOT
strategy-capability evidence)

1. **Reference memory path** — a script that hard-codes the answers'
trigger strings at s1 ("bonded corridor" → atlas-carriage) and carries
them. It proves the environment/grading run end-to-end; it does NOT
prove extraction or retention skill. ZERO RE-READS (its verification
ACTIONS are billed through the unified accounting — "zero tool calls"
was a mis-claim, fixed in R1.1).
2. **Fixed-evidence-location re-read path** — re-reads the SAME three
  cards (03/17/08) at the same decision points. It proves the registry
  + metering work; it does NOT prove adaptive evidence search.

The strong MODEL fixed baseline for R2 uses the same worker and
discovers candidates from the material — it is NOT one of these two
scripts.

Simple-legal-wins: neither path is penalized beyond its metered cost.

## R1.1 semantic corrections (frozen)

- **Scoped revisions**: the env tracks PER-CHECK revisions. s4 is a
  documentation-only update (EMPTY scope): it advances the wall clock
  and invalidates NOTHING — customs evidence acquired at s2 stays valid
  for the s5 award (pinned: an s2-evidence commit passes WITHOUT
  re-verification). s7 supersedes customs-preclearance only
  (cold-chain-integrity evidence stays valid — pinned).
- **Time-point commit grading**: the award gate is judged AT s5, on the
  env state at that moment — later rule changes cannot retroactively
  stale a legitimate commit. Follow-ups are graded at the END (their
  contract); their failures name the broken stage.
- **Follow-up 2 = Option A (diagnosis)**: the expected value is DERIVED
  from the sandbox (the commit's cited evidence vs the check's current
  revision). Different legal histories yield different correct answers;
  a fresh s8 verification does not retroactively cure the commit's stale
  citation (pinned).
- **Unified billing**: request_verification is charged identically
  whether it arrives as a tool call or an Action (the action path was
  the free channel before); ids are budget-scoped and unique across
  turns; the token cap checks the CUMULATIVE total; ask_model is
  budget-gated BEFORE the call.

## The traps (all are world semantics, none is a trick)

- The decoy (card-17): best headline SLA, newest fleet — fails
  customs-preclearance via the env oracle (verdict=fail, pinned).
- The mid-project rule change (s4) is a DOCUMENTATION update (revision
  2, cold-chain scope) that does NOT change award evidence — the trap
  for scope-blind "re-verify everything" policies (they pay cost, gain
  nothing).
- The final rule change (s7, revision 3, customs-preclearance scope)
  fires follow-up 2's reverify ONLY for that check; cold-chain evidence
  stays valid (pinned).

## Constraints and fairness

- Same env semantics as v3: env-issued verification, receipts, budget
  enforcement, DocumentRegistry re-reads, the on_turn policy surface
  (incl. ask_model, reread, delegate, multi-turn recovery).
- `information_scale_tokens` remains whitespace-approximate (labeled);
  scale axes are reported per-run.
- Filler cards are deterministic (`filling-NNN-partners`), never carry
  decisive strings (pinned), and are legal bulk suppliers.

## What this task is NOT yet

- Not a family: ONE mother world. Variants for dev distribution and
  additional independent projects (real-document instantiation like the
  Option-2 path) come after the arms run on this slice.
- Corpus scale for MAIN runs is unfrozen (calibrate after arms; do not
  let the old 900-word calibration numbers masquerade as the setting).
- B-group (cross-session state) and C-group (execution & recovery) are
  separate cards, not yet built.
