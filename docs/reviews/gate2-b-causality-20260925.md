# Gate 2 B-session causal check (2026-09-25)

This is a narrow repair of the B renewal legality contract, not a new
independent parent. `b1` and `b1-reverse` swap the mother and mirror
materials within one lineage; `b2` composes `b1` with a second pause.
None supplies the different source corpus required for full Gate 2.

## Decision and evidence ledger

| Decision | Required prior state | Current evidence | Legal action | Later state |
| --- | --- | --- | --- | --- |
| `b1` / reverse, session 1 award | None | Supplier cards, protocol, environment-issued passing customs verification | Finalize `migration_commit` | The finalized record survives the session reset in the project sandbox. |
| Session 2 renewal | `migration_commit` finalized **before session 2 starts** | Between-session customs revision 3; a new environment-issued passing customs verification at the current check revision | Finalize `corridor_reaward` | Without the prior finalized record, a fresh passing verification alone cannot legalize a renewal. |
| `b2`, session 3 second renewal | `corridor_reaward` finalized **before session 3 starts** | Between-session cold-chain revision 4 leaves revision-3 customs evidence current; the renewal still requires passing customs evidence | Finalize `corridor_reaward_2` | Missing the earlier renewal blocks the second renewal; the fourth, fresh-project session has no prior-record requirement. |

The evaluator checks `prior_finalized_record` at the act/verify stage
using the finalized IDs saved at **session entry** by the shared runner.
The participant sees the renewal condition in the stage prompt, but not
the evaluator-only precondition. This check is additional to the existing
legal-plan, environment-issued-verification, and scoped-revision checks.

## Counterfactuals and present limits

- The reference B policy can finalize the first award and a valid renewal.
  Omitting the first award while keeping a new passing revision-3 check
  and a finalized renewal record must fail the session-2 gate. The `b2`
  second renewal has the same test when the earlier renewal is absent.
- The original revision-1 customs verification is superseded at revision 3,
  while the revision-3 verification backing the new award is current.
  An unrelated prior sandbox record leaves the renewal legal.
- This proves dependence on **external project state across a reset**.
  It does not prove that a worker must use its private `carry`: the sandbox
  and metered reread remain valid recovery paths. It also does not prove
  independent-project diversity or real-model difficulty. A prior
  finalized record can have failed its own session-1 evaluator gate; full
  project success still requires that earlier decision separately.

Tracked builder byte hashes at this review:

- `src/rsicontext/lifecycle/material_b_group.py`: SHA256 `7ce04da96910d0c1d95a048c4acce263a7dfe98d5164eff26a6a80b557ab7084`
- `src/rsicontext/lifecycle/material_m2_parents.py`: SHA256 `7fddecfeca99fd825f347f006f6e90ee1e28866d51541bf9bcb30640011afca8`

Instantiated evaluator-side material hashes (ordered session `to_dict()`
values, JSON sorted keys, UTF-8, compact separators): `b1`
`96f1590158c59677d5d176b3ffcfac5f7d6c10ef886c2c4b00cea914540f802f`,
`b1-reverse`
`7c1d3fb0baf2fc9c4c6e0a97cf38849f3c81bae5c7f55c383efa32cbff0d24dd`,
and `b2`
`d038f5d46d442ebd86ac295c8e4a4814e54c91a35894f0910ffa622a0eb00811`.

The source materials are repository-authored synthetic supplier dossiers,
not independently collected projects. The above hashes identify builder
bytes, including the B2 builder in the shared M2 parent module; runtime
material hashes must also appear in the frozen experiment manifest.
