# R12 OpenTelemetry fixed-reader development preregistration

Status: frozen **before** any OTel task API request. This is a stop-early
development test of a second independent source lineage, not a qualification
panel or researcher update-rate pretest. R11 PostgreSQL 16/17 is one lineage;
OpenTelemetry 1.24/1.43 is another. Versions and interventions within a
lineage are paired observations, not independent parents.

## Claim and material

The narrow claim is that one frozen, benchmark-owned model-driven policy can
read the supplied full upstream database client span convention, retain the
query-text attribute across a process reset, and commit the source-supported
attribute only after environment-issued review receipts. The request concerns
**new** instrumentation with one parameterized SQL SELECT and one query-text
field; it does not test migration of existing instrumentation. The authentic
1.24 source's recommended row is `db.statement`; 1.43's is `db.query.text`.
The complete source and license, Git revisions, selected-file hashes, and
decisive row byte spans are fixed in
`configs/r10_otel_source_contrast_manifest_v1.json` (SHA256
`2e7ff401215164e06fd3bd819d6d99e51bf94d60ecb75241397e040647bd884b`).
The source roots must remain clean and detached at
`cafda7127683b7f667e27cdbd3220510b6f998c9` and
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`.
The constructed 1.43 deletion removes the sole complete line beginning
``| [`db.query.text`]`` (including its trailing newline) from the pinned raw
database-spans file and changes no other byte. The removed row SHA256 is
`e72da5becec0b61970037df08120d2f2e5f5fd1596405f520224f219237173c8`;
the resulting raw file SHA256 is
`09f04822434b135bf4be57406e51e561bb488764cc9e581962425ba11f306946`.
With the unchanged `[[doc:upstream-db]]\n` marker, the constructed visible
source-text SHA256 is
`80fab68f70ce6d1542c5cfeb45b95b1e6cf6dbbfe4d67aadbb59f87dd9ccd97c`.

## Reader and evidence contract

Use Qwen/Qwen3.6-27B through a dedicated R12 Siflow development profile:
temperature zero, seed 42, `enable_thinking=false`, 2,048 output-token cap,
one exact-output system instruction, and strict response-model echo. The
provider revision is currently unobservable; even a passing block cannot
support a versioned T2 statistical claim. Only a fixed benchmark-owned policy
may call the model; no researcher-authored policy, sealed item, or evaluator
label is sent. Every target and auxiliary dispatch must be counted. The
policy is adaptive with two expected worker calls per complete trajectory;
it is separate from the semantic single-reader one-call track and from KV.

Before task HTTP, require a clean/stable producer attestation, the dedicated
profile hash, pinned tokenizer-file/runtime hashes, exact request JSON hash,
full rendered input-token count, and source/carry/query token intervals. In
session 1, measure the authentic Recommended row within the full source user
message. In session 2, measure the retained model-authored attribute and the
later project request; do not describe these as a same-call source-to-query
distance. A local/provider prompt-token mismatch, wrong model echo, missing
usage, non-`stop` finish, malformed SSE, or request-hash drift halts further
calls and remains in the attempt denominator. Unknown provider usage stays
unknown. For the registered deletion diagnostic alone, require the exact
constructed deletion material hash and record the missing row explicitly;
arbitrary missing or ambiguous rows fail preflight.

Run one profile-matched synthetic pre-canary and one post-canary. A failed
pre-canary stops before task requests. The post-canary checks the access
window; either canary failing invalidates the block as reader evidence. The
canaries have separate call and token totals from the task screen.

## Eight fixed interventions

The same frozen policy, source-conditioned private oracle, review procedure,
profile, and max-turn budget apply throughout. Only the named input or
receipt changes. The row deletion is a separately hashed constructed
counterfactual, never represented as an authentic upstream revision.

| Order | Case | Changed input | Required structural interpretation | Expected calls if prior calls valid |
| ---: | --- | --- | --- | ---: |
| 1 | full-124 | authentic 1.24 source | PASS/PASS, `db.statement` | 2 |
| 2 | full-143 | authentic 1.43 source | PASS/PASS, `db.query.text` | 2 |
| 3 | withheld-124 | both upstream documents withheld | no source survey; later FAIL | 0 |
| 4 | withheld-143 | both upstream documents withheld | no source survey; later FAIL | 0 |
| 5 | swapped-124 | only 1.43 upstream document bytes substituted | action follows substitute; frozen 1.24 oracle later FAIL | 2 |
| 6 | swapped-143 | only 1.24 upstream document bytes substituted | action follows substitute; frozen 1.43 oracle later FAIL | 2 |
| 7 | recommended-row-removed-143 | exact 1.43 Recommended query-text table row deleted | diagnostic: record model choice, failure, and residual cues; no assumed pass/fail | at most 2 |
| 8 | empty-carry-no-reread-143 | erase bounded carry at reset and disallow source reread | later FAIL without a legal plan | 1 |

The global cap is **16 attempted worker requests**, including rejected
responses and transport failures, across at most eight trajectories. The
nominal path needs no more than 11 calls. Stop after a failed complete-source
trajectory, a preflight/transport/response failure, or the attempt cap. Record
every case's full-session completion, later plan legality, prior/current
receipt provenance, carry bytes, model calls, exact request/material hashes,
provider input/output tokens, unknown-usage count, latency if available,
model echo, finish reason, and named failure. Preserve raw evidence in an
ignored immutable output path; publish only a development summary.

## Decision rules and next queue

The two authentic full cases must both complete with opposite plans before
the other paid diagnostics have scientific value. Withheld and swapped cases
test source dependence; the deletion case asks whether the table row matters
beyond version-era cues; empty carry is interpretable only under the explicit
no-reread arm. The initial review receipt tests procedural provenance, not
source understanding. This eight-case inspected sample cannot estimate the
registered ≥16-item difficulty floor, any `≥0.90` saturation kill, `≥20%`
top-two policy disagreement, position robustness, or parent-level effect.

If the stop-early test survives, next freeze a separate ≥16-item development
panel with two reader families, full/source-free/decisive-removal and
equal-length irrelevant controls, early/middle/late placements, complete
project outcomes, named failures, and provider usage. These are development
items; any inspected task cannot later serve as an unseen gate. A qualified
parent count changes only after that evidence and the R9 identity/causality
gates pass. The researcher valid-update-rate pretest remains closed until an
unchanged jail passes its adverse tests on a trusted immutable host.
