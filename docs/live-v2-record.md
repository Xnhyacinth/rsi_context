# The four-arm live first run (2026-09-24, r2b-live-v2)

The first live run of the FULL five-cell apparatus (four arms + the
recuris S0-matched control). Artifact:
`artifacts/rsi-core-v1/r2b-live-v2.json` (shared checkout; ~50 min
wall). Governed by docs/stats-contract-v1.md; transcribed here because
the artifact path is gitignored.

## Headline: four_outcome = **regresses** (Δ_update = −1)

The first non-ties outcome in the project's history — an HONEST
negative, reported as measured.

| Arm | dev (project / decisions) | eval_mirror (project / decisions) |
| --- | --- | --- |
| strong_model_fixed | 0/1 (decisions 1/3: award ✗, fu1 ✓, fu2 ✗) | **1/1 (3/3)** |
| unassisted_update (round: ok, 15,176 out tokens) | 0/1 (0/3) | 0/1 (2/3: award ✗) |
| non_adaptive_search (no usable candidate; baseline stands) | 0/1 (1/3) | 1/1 (3/3) |
| recuris_s0_matched | 0/1 (1/3) | 1/1 (3/3) |
| recuris_adapted (2 rounds, both BOUNCED — see the bug) | — | 1/1 (3/3) |

(The earlier table's bare "0/3" mixed denominators: a cell's PROJECT
completion is 0/1 while its DECISION count may be 1/3 — both are
reported, never merged into one number.)

Deltas: Δ_update = −1 (the rewritten policy lost the mirror's award,
which the baseline wins); Δ_search = 0; Δ_recuris = 0 (both bounce —
no package change; its eval run IS the S0-matched shape, hence 3/3).

## The diagnosis (transcript-attributed — the audit machinery's payoff)

1. **The unassisted rewrite REGRESSED the award**: the researcher
   rewrote the policy into a card-scanning loop (its worker replies
   enumerate every supplier with covers/exception fields — a
   per-card survey), then committed `pinnacle-courier` on dev (the
   decoy, quoting its own lapsed-bonding clause as the reason!) and
   `orbit-hosting` on mirror (a calibration supplier, not a carriage
   candidate). The parse also captured a trailing backtick
   ('pinnacle-courier`') — the reply's formatting bled into the plan
   value. The rewrite made selection WORSE than the baseline's
   note-based choice (vesper-instruments: right family, wrong role).
2. **A REAL validator bug found and fixed**: both recuris rounds
   bounced with 'evidence must cite one of the failed decisions
   [award, followup_2]' — but the meta-agent HAD cited them, by their
   failure strings ('commit gate[s5-act-verify]: plan
   'vesper-instruments'...'). The check matched the decision NAME
   ('award') against strings that name STAGE IDS; the word 'award'
   never appears in any failure string. Citation by failure string now
   passes (pinned; the name form still passes; citing a passing
   decision still bounces). The bounce consumed 8,136/8,774 meta
   tokens and froze the package at neutral — the recuris arm's
   mechanism was NEVER actually exercised live; that remains untested
   pending a re-run (a NEW declared run; this one stands).
3. **The id-pinned prompts verifiably fixed fu1 live**: fu1 passes on
   dev for both fixed-shaped arms (R2b's display-name failure mode is
   gone; the remaining dev failures are the award selection error and
   the fu2 currency misjudgment 'current' vs 'reverify').
4. **fu2 fails on dev for a REASON worth studying**: the fixed arm's
   worker answered status=current — a genuine diagnosis error (the
   s5 evidence is at revision 2? the worker reasoned 'nothing
   invalidated it' despite the s7 supersession). On mirror the same
   arm answers correctly (the flipped scope changes the reading).
5. **The mirror award now PASSES for all fixed-shaped arms** (3/3 on
   eval) — the id-pinned award prompt + the fixed mirror gate hold
   live.

## What this run licenses (and does not)

- Licenses: the five-cell live apparatus works end-to-end (cost
  ledgers: 8,136/8,774 meta tokens, per-cell worker calls 13-19, all
  recorded); the four outcomes are real (this one is regresses); the
  failure attribution is transcript-grade; one more validator defect
  found and fixed by the run itself.
- Does NOT license: any claim about the recuris mechanism (its rounds
  never ran past the bounce — the citation bug blocked them); any
  generalization (one seed, one family, dev-phase n=1, descriptive
  only — the contract's standing rule).

## Obligations after this run (done in the same commit)

- The citation validator fix + pin (above).
- This transcription.

## Next (declared, not yet run)

- A NEW live run with the fixed validator (the recuris loop finally
  exercisable: dev FAILS live, so repair targets exist) — v3, after
  the r3 unified entry or before it, per the user's call.
