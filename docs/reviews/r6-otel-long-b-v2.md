# R6 OTel long B: prior verification gate

Status: **versioned development candidate, not a qualified or scored
benchmark item**. The R5 `material_otel_long_b.py` builder, instance IDs,
tests, and recorded hashes remain unchanged. R6's
`material_otel_long_b_v2.py` rebuilds the same pinned OTel source and
constructed local material, changes both instance IDs, and opts the
second-session commit into a stronger evaluator gate.

## Material and contract

The source root is the detached OpenTelemetry semantic-conventions
commit `89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`. The builder
checks the two complete source files against the R5 byte hashes:
`database-spans.md` SHA256
`1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91`
and `sql.md` SHA256
`e451e533f90fbcc01ecc23f6d60aaa49d249dad79227f79ddeef548288eb32ea`.
The source-to-proposition ledger, constructed-material disclosures, and
measured source-document token count are in `r5-otel-long-b.md`.

The first session selects `database/dup`, obtains an environment-issued
`dual-emission` PASS verification for that plan, cites it, and finalizes
`migration_commit`. The second session requires that earlier finalized
record to have existed **before** session 2 and that its provenance
pointed, at session entry, to an environment-issued PASS verification
whose check is `dual-emission` and whose subject matches the prior
record's plan. The optional transition map permits the later
`hold-raw-enable-parameterized` plan for prior `database/dup`. It does
not add prior fields or oracle values to `StageView`.

Canonical JSON SHA256 (`to_dict()`, UTF-8, sorted keys, compact
separators, `ensure_ascii=False`):

| R6 v2 object | SHA256 |
| --- | --- |
| Session 1 | `e4e69a9334ee141bf5c0dcb2e323e3b81f423aa6dd10a834065de15c1165f23e` |
| Session 2 | `171c3a099e1c382d2253a31b0dd27835cdffef78300a692b2a33d0700f8903ea` |
| Ordered pair | `b6c165629868d89295e16ece0e3f4e635fd90d4937c3d7c6e0b647b38a1b0bbd` |

## Construction evidence and limits

Before the runner change, source-independent regression tests reproduced
four passing-invalid cases: a failed prior verification followed by a
forced finalize; a verification backfilled after session start; a
participant-written fake PASS record; and a passing prior verification
for the wrong prior plan under a transition map. After the opt-in gate,
these are rejected while the legal path and old worlds pass. The tests
also reject a PASS with a wrong check or subject. The R6 v2 full
two-session scripted witness passes; forcing the first receipt to FAIL
while still finalizing the prior record makes **both** sessions fail.

The gate certifies an environment-issued PASS verification record in
the prior award's provenance. It does not certify that the worker read
the delivered receipt, nor does it replace the first session's entire
legality gate. The present OTel material has only one legal prior plan;
the optional transition map is tested as a grader contract but does
not yet demonstrate two distinct legal prior plans producing different
later actions. Real-model difficulty, full rendered request length,
and independent-parent qualification remain open. The grader assumes
the worker reaches `ProjectState` only through the typed action surface;
the separate process-isolation gate must still hold before live use.

Replay with `RSICONTEXT_OTEL_SOURCE_ROOT` set to the detached checkout:
`uv run --no-sync pytest -q tests/test_prior_verification_gate.py
tests/test_otel_long_b.py tests/test_otel_long_b_v2.py`. The common
grader tests are source-independent; source-dependent cases skip with
a named reason when the checkout is not configured.
