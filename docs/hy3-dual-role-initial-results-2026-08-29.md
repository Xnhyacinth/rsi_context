# `hy3-ioa` dual-role RSI qualification — 2026-08-29

## Scope and claim level

This run tested whether one OpenAI-compatible model alias can occupy two
operationally separate roles: a stateless context-policy researcher and a
single-call frozen reader. It is a visible, two-item, one-round adapter
qualification. It is not A2, a matched-search comparison, a sealed evaluation,
or evidence about long-memory or long-horizon transfer.

The roles shared only the HTTP/SSE transport and model alias. They used
different system prompts, API profiles, output caps, process environments, call
ledgers, and artifacts. The researcher received the exact parent policy,
visible failures and gold evidence, and a manifest template. It returned strict
JSON containing one Python policy and one manifest. Only the evaluator executed
the audited policy and called the reader once per item.

## Fixed fields

| Field                        | Reader                    | Researcher                           |
| ---------------------------- | ------------------------- | ------------------------------------ |
| profile                      | `tencent-copilot-hy3-ioa` | `tencent-copilot-hy3-ioa-researcher` |
| requested alias              | `hy3-ioa`                 | `hy3-ioa`                            |
| temperature / seed           | `0.0` / `42`              | `0.0` / `42`                         |
| output cap                   | 512                       | 8192                                 |
| target context cap           | 8192 policy tokens        | not applicable                       |
| target calls per scored item | exactly one               | zero                                 |

Both profiles are unversioned (`provider_revision=null`). This is an
operational-freeze qualification, not snapshot-frozen evidence.

## Bounded call ledger

- Reader pre-canary: 3 calls.
- Launcher diagnosis: no researcher API call; 2 H0 reader calls.
- Researcher qualification: 3 actual researcher calls. Two produced audited
  but runtime-invalid policies; the third produced a scorable policy.
- Reader calls inside those attempts: 2 + 2 + 4.
- Reader post-canary: 3 calls.
- Total: 3 researcher calls and 16 reader calls.

The first launcher failure occurred before reaching the API and is not counted
as a researcher call. Resolving a virtual-environment Python symlink destroyed
its import context; the worker now preserves the invocation path.

## Observations

The pre-canary returned `amber.` three times with identical usage. The
post-canary returned `amber`, `amber`, and `amber.`, with output-token counts
2, 2, and 3. The response model remained `hy3-ioa`. Semantic content was
stable, but the literal answer and usage contracts were not. The whole block
fails the strict replay/freeze gate.

The first researcher artifact treated `Artifact`, `Budget`, and `ContextPack`
as dictionaries/strings and failed at runtime. After the runtime interface was
stated precisely, the second imported a nonexistent `Policy` symbol and used a
nonexistent `ContextPack(chunks=...)` constructor. These failures passed
syntax/AST and manifest checks but made zero candidate reader calls. The
campaign now records them as invalid slots rather than aborting.

The third artifact was valid and changed selection behavior:

| profile                | H0 gold recall | hy3 candidate gold recall | H0 answer      | candidate answer |
| ---------------------- | -------------: | ------------------------: | -------------- | ---------------- |
| sparse multi-hop       |          0.500 |                     1.000 | `INSUFFICIENT` | `INSUFFICIENT`   |
| dense competing values |          1.000 |                     0.875 | `INSUFFICIENT` | `INSUFFICIENT`   |

The score stayed 0.0. This is policy activation without reader improvement. It
also exposes a mechanism tradeoff: generic lexical reranking recovered the
missing sparse hop while dropping one dense evidence chunk.

The manifest assigned `(improve, unchanged, regress) = (0.6, 0.2, 0.2)` to
both items and predicted aggregate delta `+0.4`. Both outcomes were unchanged.
Descriptively, over only two items, multiclass Brier was 1.04, log-loss 1.609,
and ECE 0.6; uniform Brier was 0.667 and always-unchanged was 0.0. This is a
calibration failure, not a powered estimate.

## Interpretation and decision

The adapter demonstrates separate roles and a complete artifact path: parent
policy observation, strict JSON, AST audit, manifest/lineage validation,
fresh-process execution, and single-reader evaluation. It does **not**
demonstrate autonomous improvement. The valid candidate tied H0, item-level
predictions were miscalibrated, no matched random/search controller ran, and
the reader failed the post-run strict replay gate.

Do not launch the 2-profile × 2-seed × 5-slot block, A2, 128K/256K transfer,
LongMemEval, or a live long-horizon task from this result. The next valid setup
is `hy3-ioa` as researcher with the pinned local vLLM reader, after real-profile
and physical-gate qualification. A second API-reader replication may be
reported separately only if interleaved canaries establish a stable,
explicitly normalized metric; it must not be pooled with snapshot-frozen local
reader results.
