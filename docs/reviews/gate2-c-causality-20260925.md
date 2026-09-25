# Gate 2 C cross-session action dependency — 2026-09-25

## Defect and causal rule

Before this change, the C1, C1-mirror, and C2 renewal stages accepted a
correctly verified `corridor_reaward` even when session 1 never created or
finalized `migration_commit`. The second-session answer was thus obtainable
from its renewal notice and oracle alone; the earlier award did not change
the later legal action. The regression in `test_c_group.py` reproduced this:
session 1 failed while session 2 passed.

The public renewal prompts now say that the named primary award must have been
finalized before the resumed session. Their frozen `commit_precondition`
declares `prior_finalized_record: migration_commit`. At `run_lifecycle` entry,
the evaluator snapshots the environment's `finalized_record_ids`; its commit
gate checks that snapshot. A participant-authored `status: final` field does
not count, and a `migration_commit` finalized after resume cannot satisfy the
prerequisite retroactively. This uses the shared `ProjectState` across the
real `run_session_sequence` reset and preserves the participant's separate
carried state, the environment-issued verification oracle, and the existing
revision-2 verification requirement.

## Interventions and limits

The targeted regression runs the same legal second-session verification and
re-award after suppressing all first-session actions. All three C lineages
must fail on the named prior award, even though the re-award itself is
finalized. A second intervention creates and finalizes the primary award
*during* session 2; it still fails. The original reference recovery paths
pass C1, its mirror, and C2. A note added to an unrelated survey card leaves
the legal path unchanged.

This is an action-dependency qualification, not a claim that a real model
finds the solution or that all C material is independent. The earlier award
can be any environment-finalized `migration_commit`; its own legality remains
checked at the first-session time point. The sequence-level success requires
both sessions to pass. The Gate 2 ledger and real-model difficulty pilot
remain separate gates.
