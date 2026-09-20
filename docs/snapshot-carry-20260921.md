# Frozen-snapshot carry implemented (2026-09-21)

Status: **engineering record** — review round 4 deliverable 2 (the
carry-boundary implementation). New module:
`src/rsicontext/participant/snapshot.py` (879→887 tests; ruff, strict
mypy over 121 files, full suite green). This closes the gap
`docs/world-audit-20260920.md` §5.1 documented: the harness had only the
blunt wipe-everything boundary; the contract's frozen-learning-snapshot
carry now exists as executable code.

## Design (one mechanism, no new abstraction layer)

`freeze_session(store, dev_session, agent_files_root, …) -> FrozenSnapshot`
freezes, as ONE immutable unit:

- **memory** — the dev session's final canonical state, re-validated at
  the load boundary (schema digest + byte cap, via the existing
  `session/state.py` machinery);
- **code_files / skill_files** — the agent tree, read into safe
  relative-path maps (`.py` → code; everything else → skills/config/
  workflows — all valid state carriers per the participant interface).
  The split is audit bookkeeping only: **both channels enter every
  branch unchanged**, satisfying "code and memory carry EQUALLY".

A snapshot is byte-frozen: canonical sorted-key JSON + sha256 digest, no
mutation surface (the only "mutator" is `append_note`, which refuses by
construction and is test-asserted).

`run_evaluation_branch(snapshot, kind, session_id, instances,
hook_factory, byte_cap)` runs one branch by COMPOSING the existing
`run_session_flow` (no parallel runner): a fresh `SessionStateStore`
per branch, the session begun under the branch's kind, and
snapshot-aware adapters — the branch session's FIRST `load_state`
returns the snapshot's memory (the carry); subsequent loads read the
branch's own evolving state; every save lands only in that branch's
session. All store discipline (canonical form, cap, schema, memory-op
ledger, transcript) applies unchanged, and `run_leak_probe_then_gate`
composes on top exactly as before: the probe still scans branch state
for unauthorized canary tokens — authorized carry is the snapshot's
validated payload, not a leak. The hook receives `(state, LearningCarry)`
where `LearningCarry` is the read-only (memory, code_files, skill_files)
view.

Branch kinds: CONTINUATION / NEW_WORLD / REGRESSION / REPLAY — the
review's branch table, mapped onto `SessionKind` (REPLAY kind for
replay, GATE for the evaluation kinds).

## The four review acceptance cases, as tests (tests/test_snapshot.py)

| Review case | Test | Verified behavior |
| --- | --- | --- |
| rule learned into a SKILL file → usable in a new-world branch | `test_same_rule_in_code_skill_and_memory_gets_identical_carry` | the same rule in code, skill, AND memory channels reaches every branch identically; hooks observe all three |
| the same rule as a memory object → identical carry treatment | same test + `test_branch_store_adapters_read_snapshot_memory_on_first_load` | first branch load returns the snapshot's memory; the branch's own state evolves after |
| a branch produces new state → parent/siblings unaffected | `test_branch_state_never_writes_back` | two branches run mutating hooks; the frozen snapshot's canonical bytes are bit-identical before/after |
| new world reuses an old world's entity name → not auto-cleared | `test_same_name_entity_across_worlds_is_not_auto_cleared` | carried `entity_notes` meet the new world; the framework provides carry, the participant discriminates |

Plus: `test_freeze_captures_code_skills_and_memory_together`
(freeze composition + immutability refusal),
`test_freeze_requires_a_begun_session_with_state`,
`test_branches_carry_schema_and_cap_discipline` (an 8-byte cap refusal,
never truncation), `test_snapshot_advances_s0_to_s1` (the improver's
`state_update` becomes S1's memory through the same freeze mechanism —
one mechanism, not a special case), `test_snapshot_digest_is_deterministic`.

## What this does NOT claim

- No claim that the arm_comparison harness now measures cross-world
  learning: that script still wipes state at world boundaries; the fix
  for future comparisons is to run worlds as `run_evaluation_branch`
  calls over one frozen snapshot, which this module now enables. The
  next trajectory (deliverable 5) uses this path directly.
- No claim about what is "good experience": the framework owns
  permissions and isolation; the participant owns organization and use.
- The DS arm's code edits travel via `code_files` once the agent tree is
  snapshotted; wiring the DS round output into `freeze_session` /
  `FrozenSnapshot.from_parts` is deliverable-5 work (the registration
  surface already accepts `agent_files_changed` + `state_update`).
