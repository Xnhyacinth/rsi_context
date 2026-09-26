# R19 Iceberg fixed-reader and researcher boundary execution ledger

Status: **in progress; no R19 provider or GPU call admitted**. All R19
branches started from clean `main@9e551f4594c59689eb80dd5a86a192c8d4ef475d`
with `uv.lock` SHA-256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`.
Each isolated worktree used `uv sync --extra dev --frozen --link-mode copy`.
The original untracked `logs/` in main is untouched.

| Worktree branch | Owned work |
| --- | --- |
| `work/r19-reader` | Prospective, guarded Iceberg two-session fixed-reader screen, versioned prompts/launch and offline failure tests; no provider execution by the worker. |
| `work/r19-runtime` | Trusted researcher runtime and B/C opportunity/budget audit; no host mutation, candidate execution or provider call. |
| `work/r19-gemma` | Independently pin a second reader family's tokenizer metadata through registry dry run and selective acquisition; no model weights or provider call. |
| `work/r19-short` | Guarded two-call short Iceberg rule-application feasibility gate with its own versioned launch; no provider execution by the worker. |
| `work/r19-integration` | Reconcile science and code review, admit at most a bounded live reader screen after frozen checks, run project gates, merge/push main and clean worktrees. |

The official Iceberg source checkout has been rechecked clean and detached at
`071d5606bc6199a0be9b3f274ec7fbf111d88821`. Its complete spec and license
SHA-256 remain respectively
`e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb`
and `2c0e4b3b8c7a873194c6517058f9a62c59fa00a37d1e24bf80a538e1c885b9b2`.
The repository registry SHA-256 remains
`16807ab8ae22734f2a90cc64df843587a9b290bdf8b4dba79f154efabc81c934`;
the [R18 source/geometry ledger](r18-iceberg-row-scan-candidate.md) is input
evidence, not a qualified parent or a live launch.

## Predeclared feasibility decision

The short paid KEP rule-projection screen failed even with the decisive rule
provided directly. R19 therefore does **not** spend further on KEP. Iceberg
tests a different, authentic long-form source at the measured 32K-compatible
contiguous excerpt. Before paying for 25K-token source arms, a separate
prospective short-input check should give the Iceberg rule bundle explicitly
for each answer-changing side and test the fixed row request. That check
requires its own registered requests, canaries and usage; it measures task
feasibility only. The fixed reader may then make one target call to classify
four answer-free rule fields in session 1 and one target call in session 2 using
only the validated carry and identical constructed row request. Every
source-full, constructed-rule, source-free and identity-only arm starts fresh.
The coherent all-unknown bundle remains a valid carry and proceeds to S2,
including in withheld controls, so a model prior/default can be observed.
Each arm must also continue S2 with either other accepted coherent bundle
when that is what the model actually returned, even if it is wrong for the
arm; preflight cannot substitute an evaluator-expected carry.
Malformed or mixed session-1 fields must be counted and stop that arm before
session 2; no default legal action may be substituted. The evaluator-only
authentic plan is `suppress-row`; the constructed-rule plan is `emit-row`.
The current fixed row facts discriminate the data-versus-file counter and
unpartitioned-global exception. They do not discriminate strict versus
nonstrict sequence comparison (no equality boundary) or all-versus-any
equality IDs (each delete has one ID). A correct four-field S1 answer is
separate extraction evidence; an S2 pass cannot prove all four clauses were
used. Any stronger multi-clause task needs a new request, world and oracle
version with equal-sequence and multi-ID cases before paid testing.

The long-source paid screen, if admitted, is **one-reader development feasibility**,
not a success-rate estimate, full lifecycle completion, cross-model result or
qualified independent parent. Admission requires a committed exact launch,
source and prompt hashes, full API request registration, final-chat offsets,
clean producer, endpoint/model canary, no auxiliary delegation, a bounded
target/requested-token envelope, private dispatch/response journal and
provider-reported usage. An independent reviewer must verify that session 2
cannot reread session-1 source and that all four arm requests and result
interpretations are honest. A second distinct reader family and full
receipt-bearing project action chain remain separate later gates.
This longitudinal screen budgets up to **two target calls per arm**, one in
each session. It is separate from the one-target-call single-reader
leaderboard; every target and auxiliary attempt is metered as an adaptive
experiment.

The researcher effective-update-rate pretest remains unmeasured while the
host jail rejects UID-1000-owned `/usr/bin` and `/usr/lib` paths. Do not
substitute a fake worker response or an untrusted local namespace for that
pretest. The runtime worker will record any viable trusted admission path and
keep its researcher draw denominator and B/C budget separate from this reader
feasibility spend.

An authenticated, read-only Siflow `GET /model-api/models` returned HTTP 200
and 16 visible model IDs on 2026-09-26 UTC. The sanitized, key-free
[catalog record](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/siflow-model-catalog-sanitized.json)
has SHA-256 `d9d85ad44ea5d98854a1210be9ebb2aa4a961265c6a2be0e8ae999defa3d713e`.
It lists the known `Qwen/Qwen3.6-27B` and a prospective distinct family,
`google/gemma-4-31B-it`, with advertised context windows of 262,144 and
131,072 respectively. This verifies **catalog visibility only**. A Gemma
comparison requires registered pinned tokenizer/source assets, exact
chat-template geometry, a versioned provider profile and an exact-model,
usage-bearing canary before any model result or cost claim.

The Gemma metadata intake has since joined this integration branch. Its
registry SHA-256 is
`7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0`;
the [source audit](r19-gemma-tokenizer-intake-audit-20260927.md) records six
immutable metadata files totaling 32,197,909 bytes, no weights, a matching
tokenizer manifest, and a local-only text `AutoTokenizer` load. The snapshot
is not a Siflow canary or second-reader result. Reader launch registrations
must bind this new registry SHA; historical v1 launches remain immutable and
should refuse the changed registry.

## Offline reader result so far

The [R19 reader preregistration](r19-iceberg-reader-prereg-20260927.md) is
committed with local geometry SHA-256
`53d0669031172f8c05fa70bb95971b7394f891461794aa35b663d0d5d79f6559`
and offline-only launch SHA-256
`c4f7f72ec0f02d3163c2e7b9cabe7c1ec3ada6ed1405fc9afd25e9e2a69982b8`.
It sets `live_enabled=false`; no credentialed transport path is present.
Independent science review found no blocker **within this offline scope**.
Integration focused tests passed 35 with three expected historical R18 skips.

A clean integration checkout ran one sealed synthetic four-arm chain at
`/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/iceberg-reader-synthetic-v1/`:
**8 synthetic task requests, 2 synthetic canaries, zero auxiliary calls**.
Its `task.json` and `final.json` SHA-256 are
`ff2a3b0abc0dc6f3eaee8688eabc36b2e24634d70c18ae6ad2c28e2f0e8eeb0b`
and `90e497035295bad9b2cdb158715792abbe4d34d2e7c28ef63cc260c9082886de`.
Private evidence is mode 0600 under a mode-0700 directory. The synthetic
source-free and identity-only arms both chose `suppress-row` despite an
all-unknown source rule and passed their authentic private action gate. This
demonstrates a **possible default-plan shortcut in the test harness**, not a
model result; real controls must rule it out before source-dependence claims.
