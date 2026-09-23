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

| Axis | What carries it | Verification |
| --- | --- | --- |
| **Long horizon** | 8 stages; decisions at s5/s6/s8 depend on evidence from s1 (4+ stages, across a commit); a final rule change AFTER the commit invalidates specific evidence | Stage grammar test; follow-up grading names the broken stage |
| **Long memory** | The winning candidate's qualification = one exception clause (card-03) + the check named only in the protocol; follow-up 1's answer = card-08 facts; follow-up 2 = scope-tracked staleness (customs-preclearance superseded, cold-chain-integrity NOT) | Remember-path test (zero re-reads, still passes); ledger uniqueness tests |
| **Long context** | Distant+buried decisive facts (the decoy's disqualifier sits in card-17 amid plausible bulk); `bulk_cards` scales the corpus deterministically (0/100/400 → 22/122/422 docs, ~0.8K/4.3K/14.8K approx-words) while the four decisive strings stay single-source | Corpus-scaling test; reread-path pays metered cost |

## Load-bearing ledger (the no-lie constraint)

| Fact | Sole source | Breaks what |
| --- | --- | --- |
| "bonded corridor satisfies the customs-preclearance check" | card-03 | the award (only qualification of atlas-carriage) |
| "customs bonding lapsed ... pending renewal" | card-17 | the decoy trap (pinnacle-courier looks strongest) |
| "mutual-aid annex ... exemption transfers" | card-05 | the exemption-transfer grounds (future B-group use) |
| "northern service hub covers the five northern checkpoints" | card-08 | follow-up 1's answer (vesper-instruments) |

Everything else is plausible bulk; no card lies; removing a load-bearing
card removes EXPLAINABLE information (the specific decision it grounds),
not just score.

## Two legal paths (acceptance)

1. **Remember** — compress conclusions at s1 (four details), carry them
   across the commit and both follow-ups; ZERO tool calls (test-pinned).
2. **Re-read** — keep a corpus index, reread decisive cards at each
   decision point through the DocumentRegistry; METERED cost
   (test-pinned: budget.calls >= 3).

Simple-legal-wins: neither path is penalized beyond its metered cost.
If a memory-light policy is cheaper and correct, it wins.

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
