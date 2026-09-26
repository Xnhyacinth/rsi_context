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
contiguous excerpt. The fixed reader may make one target call to classify four
answer-free rule fields in session 1 and one target call in session 2 using
only the validated carry and identical constructed row request. Every
source-full, constructed-rule, source-free and identity-only arm starts fresh.
The coherent all-unknown bundle remains a valid carry and proceeds to S2,
including in withheld controls, so a model prior/default can be observed.
Malformed or mixed session-1 fields must be counted and stop that arm before
session 2; no default legal action may be substituted. The evaluator-only
authentic plan is `suppress-row`; the constructed-rule plan is `emit-row`.

The first paid screen, if admitted, is **one-reader development feasibility**,
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
comparison still needs registered pinned tokenizer/source assets, exact
chat-template geometry, a versioned provider profile and an exact-model,
usage-bearing canary before any model result or cost claim.
