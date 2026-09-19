# Contract-level test list for Phase B

Status: **enumerated backlog — to be implemented in Phase B alongside the
runtime**. 2026-09-19. Parent: [`benchmark-contract-v2.md`](benchmark-contract-v2.md).
The 628 existing tests must stay green throughout (regression gate); the
tests below are the new-contract gate — passing them demonstrates the v2
contract is implemented, not merely un-regressed.

## 1. State-boundary contract (participant-interface-v1.md §State)

- `test_state_resets_at_split_boundaries`: a stateful registration run on a
  visible session then a gate session produces byte-empty initial state at
  gate session start.
- `test_gate_sessions_contain_only_gate_items`: gate-session item IDs ∩
  visible item IDs = ∅.
- `test_state_byte_cap_enforced_at_serialization`: state exceeding the `B`
  byte cap raises at the serialization boundary (not silently truncated).
- `test_canonical_state_serialization`: sorted-key JSON byte-stability
  across two serializations of equivalent dicts; `PYTHONHASHSEED=0` pinned in
  worker env (assert via env construction test).
- `test_state_schema_validation_on_load`: malformed/oversized/state-with-
  filesystem-paths state blobs are rejected on load.

## 2. Leak probe (contract §Protocol semantics)

- `test_visible_gold_canary_absent_from_gate`: inject gold tokens in a canary
  visible session; assert absence in all gate-session state transcripts and
  packs.
- `test_leak_probe_registered_in_manifest`: the probe run is recorded and
  referenced.

## 3. Replay duality (contract §Protocol semantics)

- `test_deterministic_replay_transcript_equality`: N=5 repeats of the same
  stateful registration on fixed recorded reader outputs produce identical
  state transcripts + packs + ledgers.
- `test_fresh_request_replay_records_variance`: fresh-request replay output
  includes per-item variance statistics, separate from the deterministic
  column.

## 4. Control fairness (participant-interface §arms)

- `test_same_task_stream_across_arms`: fixed/experience/open-S arms receive
  byte-identical task streams and order.
- `test_same_feedback_bandwidth_across_arms`: `F` schema and byte budget
  identical across arms per round.
- `test_experience_arm_strategy_frozen`: experience-accumulation arm's `A_0`
  code hash is unchanged before/after a campaign; only `Σ` differs.
- `test_stateful_control_slot_available`: the registration API can express a
  stateful Random-K arm (interface slot, even if the arm ships later).

## 4b. Order and seed controls (Fragility-of-Self-Improving-Agents constraint)

- `test_multi_seed_recorded`: every reported cell carries ≥ 2 research seeds
  and seed IDs are manifest fields.
- `test_shuffled_order_arms`: the task-order seed is a recorded contract
  field; shuffled-order runs are expressible and their stream bytes are
  recorded (order randomization is a controlled input, not a nuisance).

## 5. Task-family qualification gates (task-family-research-v1.md)

- `test_gold_drop_causes_material_drop`: counterfactual removing gold
  evidence reduces final-state correctness on the qualification panel.
- `test_provenance_drop_increases_stale_failures`: stripping provenance
  fields raises failure classes 2/3 rates.
- `test_saturation_kill`: no strategy ≥ 0.90 overall; top-two disagreement
  ≥ 20% (runs on the qualification panel, marked slow/integration).
- `test_independent_document_bases`: qualification instances do not share a
  dominant hidden factor (document-base overlap below threshold).

## 6. Cost ledger (contract §two-column cost)

- `test_cost_ledger_two_columns`: a run record carries `C_improve` and
  `C_deploy` fields with per-horizon N reporting; memory-op ledger (writes/
  reads/bytes/ops) present per session.
- `test_reader_calls_all_accounted`: model-pool calls (including sub-agent
  and improvement-process calls) all appear in the ledger; a hidden extra
  call fails the audit.

## 7. Reader tiers (contract §tiers)

- `test_t2_gates_enforced`: a T2 registration without canary/variance-floor/
  echo records is refused at qualification; drift in canary invalidates the
  batch.
- `test_t3_excluded_from_efficiency`: T3 registrations cannot enter
  efficiency comparison columns.
- `test_pool_fixed_at_registration`: model pool swaps mid-campaign are
  rejected.

## Implementation notes

- New package layout: `src/rsicontext/lifecycle/` (runtime), `src/rsicontext/
participant/` (registration/adapters), extending `campaign/`, `eval/`,
`security/`, `experiment/ledger.py`.
- Slow/integration tests marked (existing suite runs in ~60 s; qualification
  gates run on panels, not per-commit).
- Every qualification gate failure is an engineering record (contract
  §honesty) — tests encode that by reporting gate-failure distinctly from
  assertion failure where applicable.
