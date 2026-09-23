# R2b record — the three-arm comparison (wiring + runs)

Arms (stats-contract-v1 governed): strong-model-fixed,
unassisted-update (one round), non-adaptive strategy search (K=3
declared candidates, independent proposals, first-usable-zero-error
selection rule declared before the run; never dev-score or eval
selection). Both deltas reported: Δ_update (update vs fixed) and
Δ_practical (search vs fixed). New this round: the model-call audit
transcript (policy.py) — every ask_model prompt/reply recorded with
stage context, so failures are attributable (the R2a live failure was
not).

## Runs

- Offline (scripted worker; wiring): `r2b-comparison.json` —
  update outcome: ties (deltas zero; search arm identical to fixed
  because the deterministic offline candidate is a legal but
  non-scoring edit — the offline sim's known limitation).
- Live: `artifacts/rsi-core-v1/r2b-live.json` (shared checkout path,
  post-postmortem fix) — results transcribed below after the run.

## Live results (2026-09-23, three arms, shared-checkout artifact)

| Arm | Cell | passed | decisions | model_calls |
| --- | --- | --- | --- | --- |
| strong_model_fixed | dev | false | all fail | 13 |
| strong_model_fixed | eval_mirror | false | award+fu2 PASS, fu1 fail | 15 |
| unassisted_update (round: ok) | dev | false | all fail | **0** |
| unassisted_update | eval_mirror | false | all fail | **0** |
| non_adaptive_search | eval_mirror | false | award+fu2 pass, fu1 fail | 15 |

four_outcome_update: **ties** (Δ_update = 0, Δ_practical = 0).

Honest readings (each now ATTRIBUTABLE via the audit transcript):

1. **CORRECTION (post-run diagnosis, 2026-09-23)**: the update arm's
   model_calls=0 was initially read as "the researcher's rewrite
   removed the model channel". That mechanism is WRONG. The artifact's
   policy_errors carry `policy load failed: SyntaxError: unterminated
   string literal` for both cells — the researcher's 16,384-token
   output was truncated mid-string (the same reasoning-dominated cap
   failure as R2a), the "def on_turn" SUBSTRING check accepted it, but
   the policy never compiled: every stage returned "policy
   unavailable" with zero actions. Nothing ran. Fixes applied for the
   next declared run: a selection-time LOAD GATE (scan+compile+on_turn,
   not substring) in the round acceptance; the fu1 prompt now pins the
   id format (the actual fu1 break was answer FORM — the worker knew
   the right supplier, its reply parsed to the display form 'Vesper'/
   'Orbit' against the exact-match 'vesper-instruments'/'orbit-hosting';
   per the diagnosis, notes were retained, truncation never engaged).
2. **The id-pinned award prompt fixed the name-normalization gap**:
   the fixed arm's award now PASSES on the mirror variant (R2a's
   failure mode — worker answering display names — is gone). NOTE
   (later audit): the mirror award gate was simultaneously defective
   (plan_requirements keyed to the mother winner — fixed in e969c12;
   see goal-value-contribution.md §6), so that pass was partially
   confounded; both fixes are in for the next run.
3. **Search arm**: 3 candidates — one no-policy, two usable; one
   usable candidate had policy errors on dev, so per the DECLARED
   rule the baseline stands (recorded, not re-picked). Its eval run
   matches the fixed arm exactly (the standing baseline IS the
   selected artifact).
4. fu1 (calibration supplier extraction) fails across all arms — the
   worker's extraction of the hub-coverage card is the remaining
   selection weak point; transcripts retained for the next round's
   prompt-level diagnosis.

This run licenses: three-arm wiring + declared selection rule working
under the contract; audit-based failure attribution (C3's
diagnosability, first live demonstration); id-normalization fix
verified. Still NO improvement claim — ties, reported as measured.

## Notes

- The R2a live postmortem (lost artifact) is recorded in
  docs/r2a-record.md and goal-value-contribution.md §6; runs now
  default/write to the shared checkout path.
- The award prompt now pins the supplier id format (the display-name
  normalization gap the R2a failure exposed — see the value doc's
  mechanism table).
