# R12 OpenTelemetry fixed-reader development evidence, 2026-09-26

Status: **bounded real fixed-reader development screen completed; Gate 2 and
researcher admission remain closed**. The experiment followed the committed
[R12 preregistration](r12-otel-fixed-reader-prereg-20260926.md), revised for
scientific interpretation before task API calls. All R12 code worktrees began
clean at `main@a7849acd269518bd8be087176bb7dbe7a9346e8d`, sharing
`uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
OTel 1.24/1.43 source roots remained clean and detached at
`cafda7127683b7f667e27cdbd3220510b6f998c9` and
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`.

## Identity, geometry, and compatibility gate

The dedicated profile
`configs/r12_otel_siflow_worker_profile_v1.json` binds
`Qwen/Qwen3.6-27B`, `enable_thinking=false`, temperature zero, seed 42,
2,048 maximum output tokens, strict echo, and the exact-output worker system
instruction. Its profile hash is
`bb16a4abddbac0be49944a7e22bbb1180354f9d5043ad186685bfce512d6d0e5`;
provider revision remains null. The local tokenizer is the pinned
`Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b` snapshot
with `transformers==5.15.0`, `tokenizers==0.22.2`, and `jinja2==3.1.6`.

| Authentic source | S1 rendered input | Full-source token interval | Recommended-row token interval | S2 rendered input | Retained attribute / later request intervals |
| --- | ---: | --- | --- | ---: | --- |
| 1.24 | 3,460 | [80, 3451) | [2978, 3026) | 225 | [72, 76) / [81, 216) |
| 1.43 | 8,912 | [80, 8903) | [2129, 2204) | 225 | [72, 76) / [81, 216) |

Intervals are half-open and from exact final rendered chat requests. S1
source and S2 project request occur in separate model calls; their positions
are not a same-request distance. The registered 1.43 row deletion renders
8,837 S1 input tokens, has no Recommended-row interval by design, and is
accepted only for visible-source SHA256
`80fab68f70ce6d1542c5cfeb45b95b1e6cf6dbbfe4d67aadbb59f87dd9ccd97c`.
The integrated local geometry artifact is
`artifacts/rsi-core-v1/r12-otel-local-geometry-integrated-20260926.json`,
SHA256 `4082641b1598cec2f9b215141c8e718065b7bde442a44ddec40cdf9495d4c38c`.
Its producer is clean `9778e6d7bbdc7f8f97550df0d00e16c48c0c8335`;
source, profile, tokenizer, policy, world and request hashes are preserved.

One profile-matched synthetic pre-canary and one post-canary both returned
exact `amber`, echoed `Qwen/Qwen3.6-27B`, and reported **68 input / 2 output
tokens** each. The local template also rendered the canary at 68 input
tokens. Their raw artifact SHA256 values are
`bced883f0ce9b2210bdd1a62c7d44b741fb4ab9c2e68a21daba76c13e84a8502`
and `d840b933bdbe39b3a6aa4fd6418e4a0f37c30a8fe2bf687d622cb4aeb95637e5`.
The access window ran from `2026-09-26T13:37:54Z` to
`2026-09-26T13:38:53Z`; the canaries are compatibility checks, not score
variance estimates.

## Eight predeclared trajectories

The same frozen benchmark-owned, two-call adaptive policy and private oracle
ran in the preregistered order, with a global cap of 16 attempted worker
requests. It made **11 real Siflow worker calls**, consuming **43,618
provider input / 55 provider output tokens** with zero unknown-usage calls.
Every call reported `finish_reason=stop`, echoed the requested model, and had
provider input tokens equal to its local rendered count. The two canaries
bring the R12 provider total to **43,754 input / 59 output tokens**.

| Case | Session completion | Later plan | Worker calls | Interpretation |
| --- | --- | --- | ---: | --- |
| full-124 | PASS / PASS | `db.statement` | 2 | source-supported complete trajectory |
| full-143 | PASS / PASS | `db.query.text` | 2 | opposite source-supported trajectory |
| withheld-124 | PASS / FAIL | none | 0 | fixed policy rejected absent source before model |
| withheld-143 | PASS / FAIL | none | 0 | same procedural no-source guard |
| swapped-124 | PASS / FAIL | `db.query.text` | 2 | action followed substituted 1.43 source |
| swapped-143 | PASS / FAIL | `db.statement` | 2 | action followed substituted 1.24 source |
| recommended-row-removed-143 | PASS / PASS | `db.query.text` | 2 | table row absent; other source cues remain |
| empty-carry-no-reread-143 | PASS / FAIL | none | 1 | fixed policy could not recover attribute after reset |

The raw pilot is
`artifacts/rsi-core-v1/r12-otel-siflow-pilot-20260926.json`, SHA256
`f73ce4ea5ea1f617917bc5644ce8e3f4500d5ef5a0032284ce792c439b58bc33`.
It binds clean producer `9778e6d7bbdc7f8f97550df0d00e16c48c0c8335`,
the committed preregistration, profile, source/world/material and request
hashes, token intervals, response hash/id/model/finish/usage, attempts,
receipts, carry, legality and named failures. No credential or Authorization
header appears in the raw OTel artifacts.

## Claim boundary and next experiment

The two authentic variants and source swaps show that this frozen model and
policy produced source-conditioned opposite actions in one independent OTel
lineage. They do **not** show reliance on the nominated table row, long
context reasoning, or a model source-free failure. The 1.43 document has 19
`db.query.text` mentions; after deleting its table row it still has 18,
including normative parameterized-query guidance at pinned
`docs/db/database-spans.md:221-226`. Its PASS/PASS deletion result is thus
compatible with valid reading of other supplied evidence. The 1.24 and 1.43
row positions and total lengths also differ, so position robustness has not
been established. The withheld and empty-carry results follow branches in
the fixed policy, rather than proving model memory or inability to answer
without source.

This inspected eight-case screen cannot establish the preregistered ≥16-item
difficulty panel, two-reader agreement/disagreement, non-saturation, position
balance, or a parent-level effect. The provider revision is unobservable, so
this access window supports development evidence only. Qualified independent
parents remain **zero**; OTel and PostgreSQL are two candidate lineages.
The next development panel should pre-register a model-invoked source-free
arm, table-row transplant or other-cue neutralization, equal-length
irrelevant edits, early/middle/late placements, a second reader family, and
complete project outcomes. Already inspected items cannot serve as unseen
gates. The separate researcher pretest additionally needs a trusted host and
a new jailed-brokered entrypoint; see the
[execution-boundary audit](r12-researcher-execution-boundary-audit-20260926.md).
