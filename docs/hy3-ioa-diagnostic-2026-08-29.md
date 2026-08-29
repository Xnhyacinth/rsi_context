# `hy3-ioa` qualification diagnosis — 2026-08-29

## Outcome

The Tencent Copilot `hy3-ioa` endpoint can execute the project's
OpenAI-compatible transport and controlled 8K retrieval probes. It cannot be
the sole frozen reader for the formal RSI claim because the provider exposes a
mutable alias rather than an immutable model revision and does not expose the
runtime state needed to attest a fixed local serving stack.

This is not a transport failure. It is an experiment-identification boundary:
an API batch can support debugging or a separately labelled replication block,
but it cannot establish the primary replay noise floor.

## Bounded diagnostic

The diagnostic was bounded at 11 target-model calls and then stopped. Credentials
were read at runtime and were not written to the records; endpoint metadata is
retained for profile attestation.

| Check                       | Calls | Result                                                       |
| --------------------------- | ----: | ------------------------------------------------------------ |
| Exact short replay          |     5 | Same `amber.` response, model alias, and usage in this batch |
| 512-token front/middle/tail |     3 | 3/3 correct, score standard deviation 0                      |
| 8K front/middle/tail        |     3 | 3/3 correct, score standard deviation 0                      |

The strict short canary exited nonzero because it requires the literal answer
`amber`, while the endpoint returned `amber.`. An official normalized exact-
match scorer would treat that punctuation separately from replay instability;
the canary remains strict so protocol drift is not silently normalized away.

Earlier records show why one stable batch is insufficient. Two 2026-08-14
batches returned `amber` consistently, while an earlier 2026-08-29 batch mixed
`amber` and `amber.` and changed completion usage. The requested and returned
alias remained `hy3-ioa` throughout. This is observed cross-batch behavior
drift behind the same unversioned alias, not evidence about a policy change.

## Eligibility decision

| Requirement                                     | Status      | Consequence                                                |
| ----------------------------------------------- | ----------- | ---------------------------------------------------------- |
| OpenAI-compatible/SSE transport                 | pass        | API integration is usable                                  |
| Returned alias and usage present                | pass        | Calls can be attributed to the requested alias             |
| 512/8K controlled retrieval                     | pass        | Suitable for cheap qualification and debugging             |
| Immutable provider revision                     | fail        | Cannot attest the same frozen reader across a campaign     |
| Cross-batch output stability                    | fail        | Cannot estimate a durable near-zero replay floor           |
| KV/HBM/GPU-second/cache/scheduler observability | unavailable | Cannot support the local systems/cost track                |
| 32K/128K hard-panel qualification in this batch | not run     | No long-context quality claim follows from this diagnostic |

Allowed uses are researcher-model calls, public-data debugging, and a
separately reported API replication reader. Disallowed uses are the sole A2/A3
reader, the source of a primary noise-floor claim, or a replacement for local
vLLM runtime attestation. API and pinned-local results must not be pooled.

## What would change the decision

The API track could become a formal secondary block after it passes pre/post
campaign canaries, a repeated 32K/128K hard panel, an auditable quota/cost cap,
and batch-level drift checks. It could replace the primary local reader only if
the provider exposes and honors an immutable model and serving revision; more
successful calls to the same alias do not satisfy that condition.
