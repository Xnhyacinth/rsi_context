# Bounded verification: fix commits 40ced73 and c2e2f3a

Reviewer: reviewer-v3. Method: same commit-extraction method as the original review —
`git archive` of each commit into $CLAUDE_JOB_DIR/tmp/rev<sha>, run on the repo venv,
working tree untouched. Scope limited to the four requested points; no new analysis.

Relevant suites at c2e2f3a (test_trajectory_wiring, test_snapshot, test_commit_gate,
test_worlds_v3, test_material_v3): 43 passed.

## 1) 1.1 at 40ced73 — deep copy at ALL THREE boundaries: VERIFIED

Mechanism: `_fresh_memory()` (snapshot.py:332-345) — `json.loads(canonical_state_bytes(...))`,
a canonical-bytes round trip, applied at each boundary:
  - branch first load: snapshot.py:368 (`load_state` -> `_fresh_memory(snapshot.memory)`)
  - LearningCarry construction: snapshot.py:450
  - from_parts: snapshot.py:275
`dict(...)` is retained only for the file maps and schema (flat str->str, no aliasing risk).

Runtime evidence, in-place mutation repro from the original finding, run against a
LearningCarry-BEARING hook (mutating both `state` and `carry.memory` in place) over two
branches:
  snapshot.memory after two mutating branches: {'nested': {'keep': 1}, 'notes': ['kept from dev']}
  snapshot unchanged (canonical_bytes == before): True
  from_parts output independent of its source snapshot: True

Direct sibling-isolation assertions (not inferred):
  A first load: {'notes': ['kept from dev', 'A-note']}
  B first load: {'notes': ['kept from dev', 'B-note']}
  B saw no A-note: True;  distinct store objects: True
  A session state has no B-note: True;  B session state has no A-note: True

Verdict for item 1: FIXED — all three boundaries are structurally independent, and the
snapshot plus sibling branches are unaffected by in-place nested mutation through either
the adapter path or the LearningCarry path.

## 2) 1.3 at 40ced73 — BranchRecord.store is the real branch store: VERIFIED

`BranchRecord.store` (snapshot.py:474) is the same `store` object created at :446 and passed
to `run_session_flow`. Evidence:
  ops recorded on rec.store.ledger("b1"): ['write']   (branch activity present)
  rec.store.session_kind("b1"): gate                  (the branch's own session)
  branch notes written by the hook ARE in rec.store.read("b1"): True
Probe reach, both directions, against that store:
  clean branch state  -> LeakProbeResult(transcript_entries_scanned=2, state_bytes_scanned=315)
  planted canary token written into the branch's own state -> LeakProbeError raised

Blast-radius note (zero severity, pre-existing API friction): `assert_canary_absent` requires
a LIST of tokens (`_checked_tokens` raises TypeError on a tuple), so it cannot be called with
a tuple even though the module's canary params are tuples elsewhere. It cost one repro
iteration; worth a docstring line if the probe is going to be called ad hoc.

Verdict for item 2: FIXED — the record exposes the store the branch actually wrote through
(same object, not a fresh empty one), and the probe demonstrably detects a planted canary in
real branch state while passing clean state.

## 3) 2.1R and 2.2 re-runs at 40ced73 — both FIXED

2.1R, all three worlds, both bypass shapes:
  main (aurora)   bare create_record -> passed=False
                  finalize no-refs  -> passed=False
  orinoco (kestrel) bare create_record -> passed=False
                  finalize no-refs  -> passed=False
  parana (basalt) bare create_record -> passed=False
                  finalize no-refs  -> passed=False
Failure text (same on all six): "commit gate: plan '<plan>' is committed without any
referenced records; the required verifications are missing". Matches the requested semantics
— absence of references is now evidence for failure, not neutral.

2.2 at 40ced73: crash-strategy repro still yields the six branch cells failing the gate, and
`strategy_errors` is now recorded ("strategy exec raised ValueError: ..."). The swallow at
`except Exception: return {}` is gone in the sense that matters — the crash is named. Note the
namespace is still discarded on a crash, so a strategy that fails mid-body binds nothing even
for names defined before the raise; that is a defensible reading of "crashing strategy" and is
not a defect, just the current semantics.

Verdict for item 3: FIXED — no-refs commits fail on main and both variants; crashes are named.

## 4) c2e2f3a — crashing strategy distinguishable from a genuine no-help pass: VERIFIED
   (with one line of nuance)

Real run at c2e2f3a (offline trajectory, artifact inspected): all six S1 cells pass with
`strategy_errors == []` — so the new assertion is satisfied by the genuine pass, not just
present in the source.

Assertion firing, tested by applying the wiring test's exact assertion sequence to real
artifacts and to the crash-shaped cell:
  real passing S1 cell               -> test PASSES
  crashed S1 cell (same shape)       -> test FAILS on assert 'final_check_passed'
  crashed but hypothetically passing -> test FAILS on assert 'strategy_errors'

So the two outcomes are genuinely distinguishable end-to-end, with a nuance worth recording:
for a crash the FIRST assertion to fire is `_final_check_passed` (the crash falls back to
revision-1 evidence, so the gate fails), and `strategy_errors == []` is the secondary net that
fires only if a crashed strategy still produced a passing commit. That ordering is correct —
it means a crash can never be mistaken for a clean pass — but it also means a reader of a
test failure sees "final check failed" first and must consult `strategy_errors` to learn the
cause was a crash rather than a genuine no-help edit. The artifact carries both fields
side by side, so the diagnosis is available; no code change implied.

Verdict for item 4: FIXED — a crashing strategy now yields non-empty strategy_errors in the
branch record, the wiring assertion would fire on a crash, and the two outcomes are
distinguishable end-to-end.

## Overall

All four verification points PASS. The 1.1 fix is the one I scrutinised hardest, since my
original repro was specifically the in-place nested-mutation shape that shallow copies cannot
survive: the canonical-bytes round trip is applied at all three boundaries, sibling isolation
holds by direct assertion (not inference), and the LearningCarry path is covered as well as
the adapter path. 1.3's store is the real one and the probe reaches real branch state in both
directions. 2.1R closes the no-references hole on all three worlds, and 2.2 plus c2e2f3a make
a crashed researcher edit observably distinct from an unhelpful one. Nothing in this bounded
pass reopens a finding; the only remaining items are the Area 6 test-gap notes recorded in
docs/reviews/reviewer-v3-20260921.md, which were agreed as next-round work.
