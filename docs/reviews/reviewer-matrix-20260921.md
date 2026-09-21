# Review — replication-matrix commits `bb70fdb`, `4f14675`, `3dbc452`

Scope: committed state only (`git show <sha>:<path>`; artifacts read from disk at
`/volume/pt-dev/qjiu/rsi_context/artifacts/trajectory-v3/matrix-*.json`; working tree never edited).
Repo HEAD during review: `3dbc452`; note a **later commit `33c2304` already fixes F1/F2** — see Context.

Method: read all three commits; ran `scripts/matrix_analyze.py` against every artifact on disk
(matrix + legacy); re-ran `scripts/trajectory_v3.py --offline --rounds 3 --seed {11,11,29}` in a
detached worktree at `bb70fdb`; reproduced the contamination mechanism by hand-driving
`TrajectoryHook` on the orinoco variant; ran the wiring test; ran ruff/mypy at each commit.

---

## Context: `33c2304` post-dates `3dbc452`

`main` is now at `33c2304` ("fix: multi-round memory accumulation + survey-text decontamination"),
whose message states self-review of THIS matrix found two coupled defects and fixes them. Two
observations matter for the review verdict:

1. F1 and F2 below **reproduce independently at `bb70fdb`** (I re-derived them before reading the
   fix commit's contents, and confirmed F1 by direct execution).
2. The **doc `3dbc452` still carries the numbers those bugs produce**, and the fix commit did not
   touch the doc. So the record currently on `main` is not explained by the code on `main`.

## Fix commit's own prose is wrong on one point — `33c2304`

Its message says "S1 committed an illegal cross-world plan". At `bb70fdb` **S1 cannot commit the
contaminated plan.** `_freeze_from_parts` (bb70fdb:767-780) freezes `memory=dict(state_update)`,
i.e. `{"notes": [...]}` only, so every `S_n` snapshot carries an **empty** memory. `_survey_text`
is per-hook, so the leak needs notes to *arrive* in the same hook instance. Confirmed by
inspection of all four matrix artifacts: round-1 `state_update` notes are
`"round 1 ran; see rounds[0] for its outcome"` (researcher) and `"round 1: strategy unchanged
(scripted arm)"` (scripted) — neither mentions a plan name, and S1/S2 pass with no `'aurora'`-style
cross-world failure anywhere. The contamination is a **latent** bug that becomes reachable once
memory accumulates (which is exactly what the fix then added) — not an S1 event in this matrix.

---

## Findings

### F1 — must-fix · HIGH CONFIDENCE (reproduced) · multi-round memory never accumulates
`scripts/trajectory_v3.py:767-780` (`_freeze_from_parts`), called at :691.

```python
memory=dict(state_update),          # bb70fdb:777
```

The docstring at :768 claims "Freeze S1 = S0's **code/skills** + the improver's state update +
strategy file" — and indeed only `code_files`, `skill_files` and `schema` come from `s0`. The
**memory** channel of the carry is replaced, not continued.

- **Scenario**: `--rounds 3`. S0 memory = `{"notes": [...dev session notes...]}`. Round 0 freezes
  S1 with `memory == {"notes": [<round-0 note>]}`. Round 1's author, however, is handed
  `stub.write_text(strategy_text)` (:644) — the **code** channel does accumulate, so the
  researcher sees round 0's file. The **memory** channel does not: the `LearningCarry.memory` each
  branch hook receives at `snapshot.py` `branch_store_adapters` is only that round's string.
- **Outcome**: at `--rounds 3` the S3 snapshot's memory contains exactly one round-2 note. The
  dev-session notes and all earlier rounds' notes are gone. `snapshot.py`'s module docstring is
  explicit that the carry is "memory + code + skills" and that "both enter every branch
  unchanged" — the snapshot-level invariant holds; `trajectory_v3.py` simply never puts the parent
  memory into the new snapshot.
- **Why existing guards miss it**: `FrozenSnapshot` validates shape and caps, not continuity;
  the wiring test asserts only `isinstance(rounds[0]["state_update"], dict)` (test:93) and never
  inspects `FrozenSnapshot.memory`; nothing in `tests/` constructs a snapshot chain.
- **Aggravating**: the round's state update is also **not cumulative**. Round 0 writes "rule
  changes invalidate only in-scope verifications"; round 1 writes "round 1: strategy unchanged
  (scripted arm)" — so a memory reader of S2 cannot see the round-0 learning that produced the
  passing strategy. Only the `code_files` channel actually carries round N-1's learning.
- **Fix** (as `33c2304` does): merge parent memory with the round's additions.

### F2 — must-fix · HIGH CONFIDENCE (reproduced) · `_survey_text` contaminated by carried notes
`scripts/trajectory_v3.py:245` (`self._survey_text = prompt`), consumed at :219 / :226 / :292.

`prompt` is built at :234-237 as `working notes + stage.prompt_text + documents`. The
plan-derivation and `PLAN_PREFERENCE` match therefore run against notes as well as the current
world's documents.

- **Reproduced** (detached worktree at `bb70fdb`, `build_research_v3_variant("orinoco")`, whose
  survey never mentions "aurora"):

  | carried notes | `choose_plan()` |
  |---|---|
  | `[]` | `'kestrel'` (legal) |
  | `[{"stage": "act", "summary": "we committed aurora on the finance world"}]` | `'aurora'` (**not in orinoco's legal set**) |

- **Scenario / outcome**: a plan name from a *different* world's memory is honored on the current
  world because it appears in the notes prefix. With strategy `PLAN_PREFERENCE = ['aurora',
  'kestrel', 'basalt']` and the marker test at :226, the first preference resolves against the
  notes rather than the world, producing an illegal plan submit.
- **Latent at this matrix** (memory is empty, F1); **reachable at `--rounds >= 2`** once F1 is
  fixed, or whenever a caller passes a snapshot whose memory carries stage notes.
- **Why existing guards miss it**: the leak probe and the state-boundary rules police *canaries*
  and cross-branch writes, not self-authored notes; the notes are legitimate carry. The defect is
  that a *plan-name match* is performed against material the participant wrote rather than the
  material it is reading.
- **Fix** (as `33c2304` does): set `self._survey_text = docs`.

### F3 — must-fix (for a claims document) · HIGH CONFIDENCE · documented "15/18" matches no counting
`docs/matrix-v3-20260921.md:67-70`.

The same sentence mixes two counting units. Verified against all four artifacts:

| unit | S0 (pre) | S1+S2 (post) |
|---|---|---|
| variant-cell (2 variants × 3 kinds = 6/snapshot) | 0/24 | 42/48 |
| kind-cell (branch kind passes iff both variants pass = 3/snapshot) | 0/12 | 21/24 |
| **(S1 only) size of the one broken intermediate** | — | **15/18** |

The table immediately above that sentence (`:25-30`) is kind-cell, and the doc defines its cells as
"2 variants × 3 branch kinds" (`:32`) — which agrees with "12/12" and "24/24" but **not** with
"15/18". `15/18` is arithmetically exactly "all 18 S1 cells except researcher-s29's 3 failing
ones" — i.e. it silently drops S2, the round in which the repair is observed, contradicting the
next clause ("itself repaired by round 1"). The only 15/18-shaped figure actually supported is
"after round 0 alone", before the repair. Under the state that round 1 is supposed to be judged
by: 18/18. Under the document's own stated cell definition: 21/24.
- **Fix**: pick one unit and state it, or report both.

### S1 — should-fix · HIGH CONFIDENCE · round-outcome integrity is bypassable
`scripts/trajectory_v3.py:645-668`; consumer `scripts/matrix_analyze.py:71-74`.

The probe at :645 runs *before* `try:` and `_researcher_round` carries **no timeout** of its own
(`api_researcher.py:282-308` only wraps URL open/read; retry backoff can add further wall time).
A round that raises here — e.g. `APIResearcherTransportError("researcher endpoint unreachable:
<URLError>")` — is recorded as `failed: ...` with `usage: {}`, but the loop then **continues**,
freezes the next snapshot (with empty memory, per F1) and the run exits **0**.

Concrete: if every researcher round times out, the artifact still reports `rounds: 2`, a full
`snapshot_branches` matrix, and (with the stub's `STRATEGY_RERVERIFY = False`) an
S1/S2 identical to the fixed arm — which the analyzer then prints as `round 0: failed: ...` under
the same header as a good run. Nothing distinguishes "the loop ran and the model failed" from
"the matrix was produced" at the exit-code level or in any completeness field.
- Secondary: the same path can write a raw URLError / HTTP payload into `ds_arm.rounds[n].
  researcher_record.round_outcome` (persisted JSON, and on the in-process path the feedback payload
  carries named gate failures). Not a credential leak (the `Authorization` header is not in
  `str(exc)`), but it is unredacted infrastructure detail in a research record.
- **Fix**: return non-zero when a round outcome is `failed:`.

### S2 — should-fix · HIGH CONFIDENCE · "probe surface sampling" / "probe world order" do not exist
`scripts/trajectory_v3.py:23-26` (module docstring), `:432-434` (`evaluate_branches` docstring),
`:539` (`--seed` help).

`seed_suffix` threads only into `instance_id` (:451, :455) and the branch `session_id` (:483). The
branch surface is a fixed tuple at :438-442, the variant order is `_VARIANT_IDS[variant % 2]`
(:450), and `evaluate_branches` never consults the seed for anything else. `instance_id` itself is
interpolation-only (`spec.py:258` `to_dict`, `runner.py:152` `to_dict`) and is never formatted into
`StageView.prompt_text` or into documents — so the seed cannot reach the reader or the gate.

**Observable consequence** (this is the substantive part, not the wording): a whole trajectory in
this script is seed-independent. My offline runs prove it — `s11a` vs `s11b` are byte-identical
apart from `elapsed_seconds`, and `s11` vs `s29` differ in exactly one path, `/seed`
(`11 -> 29`). Same disk artefact for the scripted arm: `matrix-scripted-s11-r2.json` and
`matrix-scripted-s29-r2.json` are identical once `seed`/`elapsed_seconds` are removed. Since every
run is live with `temperature: 0.0, seed: 42` (:132), all seed-attributable variance lives outside
this script.
**Consequence for the doc**: `docs/matrix-v3-20260921.md:14-16` claims the seed axis produces
"presentation variance", and `:54-56` claims "the seed axis made the variance visible instead of
hiding it in a single favorable draw". Under the committed runner the seed is recorded provenance
only; the code-level claim should be corrected (doc-level causes: see C2).
- **Fix**: either delete the sampling/order claims, or make the surface actually seed-varied.

### C1 — note · MEDIUM CONFIDENCE · analyzer counts a superset of the doc's cells
`scripts/matrix_analyze.py:21-25, 39-41`.

`_cell_pass` requires *all* `final_checks` entries to pass, but `evaluate_branches` appends one
entry **per run record** (trajectory_v3.py:489-495). So with `--rounds 2` plus the final `--rounds`
runs, each branch cell aggregates every pass of that cell, not the run's final check. It matches
today only because everything in the matrix is binary and uniform. Introspecting the committed
matrix-analyzer output against the artifacts finds no `final_checks` payload that would expose the
difference, so I could not make the miscount fire — hence MEDIUM, not HIGH.
- Related, same function: an **unrun/failed** branch renders as `0/0`, and `0/0` prints like a
  genuine zero. Demonstrated by synthesizing an all-errored S1: the analyzer prints
  `S1: continuation: 0/0 | ...` with no marker, so a total wiring failure reads as "nothing passed".

### C2 — note · MEDIUM CONFIDENCE · "zero strategy crashes" is not evidence for the failing cell
`docs/matrix-v3-20260921.md:32-34`, `:69-70`.

The claim matches the artifacts (I counted `strategy_errors` across every cell of all four runs:
zero occurrences). But for the `plan ''` failure the hook's own fallback plan would also be
refused, so absence of crashes carries no discriminating power for the one cell the doc builds its
narrative on. Worth hedging to "no strategy raised" rather than presenting it as a control.

### C3 — note · LOW CONFIDENCE · `round_outcome: "ok"` does not mean "changed"
`scripts/trajectory_v3.py:648-662`.

`"ok"` is emitted for any non-empty proposed file, including one byte-identical to the stub.
`researcher-s11-r2` round 0 ships `WORLD_PROFILES = {}` with `PLAN_PREFERENCE = []`, so the
world-generic policy arrives through the interface defaults (`STRATEGY_RERVERIFY = True` →
`revision = 2` at :298) rather than through the model's own edits. I could not measure how much of
the seed-11 outcome is attributable to the model's text versus the pre-existing interface — so this
is FLAGGED AS UNCERTAINTY, not asserted (I did not isolate it by re-running an unmodified stub).

### C4 — note · HIGH CONFIDENCE · strict mypy gate is red at the reviewed commits
`pyproject.toml:44-48` sets `strict = true; files = ["src", "tests", "scripts"]`. At `4f14675` /
`3dbc452`, `mypy scripts/trajectory_v3.py scripts/matrix_analyze.py` = **16 errors in 2 files**
(parent `bb70fdb^` = 13 errors in 1 file). `matrix_analyze.py` contributes 2
(`:21`, `:35`, bare `dict` under strict). Pre-existing debt is not this diff's fault, but the
reviewed commit adds to it rather than holding the line. ruff is clean on all three files.

---

## Area-by-area

1. **Multi-round correctness** — 2 findings (F1 accumulation, F2 contamination). *Verified clean:*
   round N's feedback cannot leak round N+1. Feedback is built (`:645`) from `probe(current,
   current_strategy)` where `current` is the snapshot **before** the round's freeze and
   `current_strategy` is the strategy **before** the round's edit — i.e. genuinely the previous
   round's state; the regenerated feedback matches the artifact (`researcher-s29-r2` S1 failure
   `commit gate: plan '' is not in the legal set` is exactly what round 1's strategy diagnoses out
   loud). *Verified clean:* the cumulative strategy runs on the wire — `stub.write_text(
   strategy_text)` at :644 then `strategy_text = proposed` at :662, and grading uses
   `rounds_payload[round_index-1]["strategy_text"]` at :722-724, so the string that reaches
   `TrajectoryHook` is the one written back. *Verified clean:* S0 uses **no** strategy —
   `current_strategy = None` at :623 is passed to the S0 probe at :645, and the recorded S0
   branches pass `strategy_text=None` at :713-719; the recorded S0 failure strings (stale
   revision) match the F0 control exactly, confirming S0 is genuinely strategy-free.
   *Verified clean:* F0 is strategy-free — `strategy_text=None` at :706-712.
   *Deferred:* after F1 is fixed, the round's `ds_state_update` is still **replaced** (scripted
   round 1 writes `"round 1: strategy unchanged (scripted arm)"`), so accumulated memory would
   carry round-0's learning but not a durable record that round-1 was a no-op edit.
2. **Seed semantics** — 1 finding (S2), and the core property holds. No code path lets
   `args.seed` select world material, plan names, check names, surface, or variant order
   (`_VARIANT_IDS[variant % len]` at :450 is seed-free; the material builders are constant). No
   seed-dependent dict ordering: the only unordered traversal is `for entry in profile.values()`
   at :277, which extends a flat list and a dict whose lookups are exact-key. *Offline determinism
   verified by execution:* same seed → identical artifact bytes (modulo `elapsed_seconds`).
   *Not verifiable offline (stated limit):* two same-seed **live** runs are not byte-identical for
   the researcher arm — `researcher-s11-r2` vs `researcher-s29-r2` differ in 22 paths (strategy
   text, per-round usage, S1 cell results, `fixed_arm.dev_totals.tokens_in` 1816 vs 1818), and
   nothing in the harness enforces identical live repeats. The feedback bytes are not persisted,
   so a reader-drift explanation is inference from the differing token totals, not proof.
3. **Analyzer vs schema** — 1 note (C1). Legacy handling verified working on the three legacy
   artifacts on disk (`live-20260921.json`, `researcher-live-20260921.json`,
   `transfer-live-20260921.json`): the `s0_branches`/`s1_branches` branch and the
   `improvement.researcher_record` fallback both fire, and the header degrades gracefully to
   `seed=None rounds=None` (correct — legacy artifacts legitimately lack the keys).
   `_snapshot_order` (`:77-81`) keyed on `sorted()` is correct for F0/S0..S9+; its only observable
   effect is row order, as it is applied after an explicit `"F0"` special case and its `"F0"`
   branch is unreachable dead code (row order is in practice dict insertion order). Legacy
   `live-20260921.json` prints `0/0` because its cells genuinely lack `final_checks` (commit
   `bc735d7` added them) — correct behaviour, but see C1's readability point. A **mixed** cell
   (one variant passes, one fails) is reported honestly: the analyzer prints `1/2`, not `0/2`
   (verified by synthesizing one).
4. **Doc vs artifacts** — 1 must-fix (F3) plus C2, C3, S2's doc consequence. *Verified against the
   JSONs:* the table's `0/6`, `6/6` (all four runs, including researcher-s29's S2), the narrative
   string `plan '' is not in the legal set` (present verbatim in S1 and absent from S2),
   `round 0: ok` / `round 1: ok` for both researcher runs, "zero strategy crashes", "12/12" and
   "24/24" under the document's stated cell definition. `3dbc452` does **not** track the matrix
   artifacts (`/artifacts/` is gitignored), so "verify against actual artifacts on disk" is the
   only available evidence class — the doc's cited paths do all resolve to present files.
5. **Test adequacy** — see below.

## Test adequacy

Not pinned by any test, at any commit:

- `--rounds > 1` is **never exercised**: no test or script in `tests/` passes `--rounds`
  (`git grep '"--rounds"' tests/` is empty). The wiring test asserts `rounds == 1` and
  `len(rounds) == 1`, i.e. it pins the *shape* while actively pinning the count that excludes the
  new behaviour — which is why F1/F2 shipped green.
- The path the team-lead asked about — **a round that produces an empty strategy on a LATER round
  keeping the previous** — is not tested. In fact it cannot trigger a distinct code path in
  researcher mode: `strategy_text` is only assigned at `proposed is not None and
  proposed.strip()` (:649-662), so an empty proposal already leaves the previous strategy in
  place, and the record says `no-strategy-file`. No test covers `no-strategy-file` at all.
- `_freeze_from_parts` memory continuity: untested — nothing asserts that `S_n.memory` contains
  `S_{n-1}.memory` (this is the missing assertion that would have caught F1).
- `matrix_analyze.py` has **no tests at all** (`git grep matrix_analyze tests/` is empty); every
  finding in area 3 was found by execution, not by the suite.
- Seed semantics are completely unpinned: no test runs `--seed 11` vs `--seed 29` and asserts the
  material/plan/check names are identical. The property holds by construction, but nothing would
  fail if a future edit made the surface seed-dependent.
- `--rounds 0` → exit 2 is handled (:547) but untested; `--rounds` negative likewise.

## Verdict

`bb70fdb` restructures the trajectory correctly in the dimensions it was aiming at — S0 is
genuinely strategy-free, F0 is strategy-free, the per-round feedback is regenerated from the
*previous* snapshot and demonstrably reaches the next round's strategy, and the strategy file is
cumulative in both authoring and grading — and `4f14675`'s analyzer reads both artifact shapes
faithfully on real data. But the multi-round *memory* half of the carry contract is not implemented:
`_freeze_from_parts` discards the parent snapshot's memory every round (F1), which also makes the
survey-text contamination (F2, reproduced) a live hazard for the next `--rounds >= 2` run rather
than a merely latent one; the doc's headline `15/18` matches no counting unit its own table uses
(F3); and the round-outcome integrity is bypassable so a wholly-failed research loop can exit 0 and
still look like a matrix (S1). The reviewed code's own successor commit `33c2304` fixes F1 and F2 —
but the numbers it invalidates are still what `docs/matrix-v3-20260921.md` records. Suggest:
re-run the matrix under `33c2304`, correct the doc to one counting unit, add the three missing pins
(rounds > 1 memory continuity, a seed-invariance assertion, and an analyzer test), and make a
failed round a non-zero exit.
