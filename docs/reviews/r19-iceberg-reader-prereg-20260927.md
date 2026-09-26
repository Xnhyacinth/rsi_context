# R19 Iceberg fixed-reader prospective screen (offline freeze)

This is a **synthetic wiring screen**, not an observed reader result or a qualified
long-context parent. The runner has no credential or live transport path. A separate
two-call, short-input S2 feasibility gate must pass before considering any paid
24–25K-token S1 run. A new versioned launch and review are required for live use.

## Frozen material and comparisons

The R18 builder supplies an authentic contiguous Iceberg 1.9.2 spec excerpt
(source lines 90–1179), a four-span **constructed** file-sequence rule rewrite,
source-free and identity-only controls. The pinned upstream spec is 184,975 bytes;
the authentic pack is 118,725 bytes (SHA-256
`51863fe50379b9fe460206cf0ecb58d9c238239058604f87e209497de548dc45`).
The constructed pack SHA-256 is
`a4d0e6a0a3f1e7097d42e1cee3f3ebb83fb9c081e10eebe9ae3c2e10c4925493`.
The source checkout must be clean, detached at
`071d5606bc6199a0be9b3f274ec7fbf111d88821`. The source and constructed
bytes, edited spans, complete four S1 prompts, three possible S2 prompts,
their API request SHA-256 hashes and measured chat-template tokens are frozen in
[`configs/r19_iceberg_reader_geometry_v1.json`](../../configs/r19_iceberg_reader_geometry_v1.json).
The final post-Gemma registry SHA-256 is
`7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0`.

Order is authentic, constructed, source-free, identity-only. Each arm starts
from a fresh two-session world. S1 receives its own source view and must answer
with exactly one coherent four-field bundle: data/strict/same-or-global/all-IDs,
file/strict/same-or-global/all-IDs, or all-unknown. Outer whitespace is ignored;
mixed fields or extra prose stop that arm before S2 and end the block. **Any**
accepted bundle, including an incorrect source-bearing bundle or all-unknown
from a withheld control, reaches S2. No observed carry is replaced with oracle
data. S2 receives only that validated bundle and an identical fixed non-source
row-scan request. Its document registry rejects rereads. The private evaluator
records extraction match for source-bearing arms, prior-rule match and shortcut
completion for withheld controls, S2 plan correctness, and lifecycle completion
separately. Model-visible prompts and feedback contain no oracle.

The fixed request distinguishes data versus file sequence and the unpartitioned
global exception. It has no equal-sequence or multi-ID mismatch; S2 success
cannot establish dependence on the strict-bound or all-ID clauses. The four-field
S1 answer is an extraction diagnostic. A stronger task requires a new request,
oracle, hashes, geometry and preregistration.

## Calls, stopping and evidence

One target call occurs per session, at most eight task calls for four arms;
there are two exact-profile canaries, so at most ten calls and zero auxiliary
calls. S1 measured input tokens are 24,883 / 24,894 / 126 / 261; S2 has
321 for either known bundle and 317 for all-unknown. The conservative task
input cap is 51,448 tokens; input plus eight requested 2,048-token outputs is
67,832. Including two 62-input-token canaries gives a global ceiling of
72,052. The 32K per-call context check is inherited from the frozen R18
geometry. The launch manifest binds these ceilings, endpoint/profile/canary,
registry, geometry and committed producer bytes. It explicitly sets
`live_enabled=false`.

Pre-canary failure prevents task calls. Transport, protocol, missing provider
usage, malformed S1, cap excess or registered-request mismatch stops further
calls. A wrong but coherent answer does **not** censor remaining controls.
Exactly executed arms and calls are recorded. Private directory mode is 0700;
all artifacts are 0600, with fsynced dispatch-before-response journal records.
Private task evidence retains raw replies, observed carries/plans, model echo,
finish reason, prompt/request/response hashes and usage. Provider usage is
unknown for this synthetic screen; synthetic token totals are labeled as such.
No secret or Authorization header is persisted.

The runner requires clean committed producer bytes, launch and geometry before
any synthetic call, then recomputes source, tokenizer, profile, all prompts and
requests. The frozen geometry SHA-256 is
`53d0669031172f8c05fa70bb95971b7394f891461794aa35b663d0d5d79f6559`.
The versioned launch is
[`configs/r19_iceberg_reader_launch_v1.json`](../../configs/r19_iceberg_reader_launch_v1.json).
Neither a passing synthetic chain nor this freeze admits a paid or leaderboard
claim. The separate short S2 feasibility gate and subsequent observed four-arm
reader traces determine whether long-source spending has scientific value.
