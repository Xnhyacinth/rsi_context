# R19 Iceberg short S2 feasibility result

The preregistered Siflow Qwen3.6-27B short-input screen completed once on
2026-09-27 UTC. The protocol block was valid, but the rule-application task
failed: both answer-changing arms returned `plan=suppress-row`. The private
oracle requires `plan=suppress-row` for `counter=data` and `plan=emit-row` for
`counter=file`. The frozen long-source Iceberg screen is **not admitted** by
this result; this version will not be retried or relabeled.

| Arm | Fixed request | Rule difference | Observed reply | Private result | Provider input/output |
| --- | --- | --- | --- | --- | --- |
| data-counter | SHA-256 `270713688e20ce9a1e8a4f7a9236746a1f9707f6188d838efc0c0ae6436ccc81` | `counter=data` | `plan=suppress-row` | correct | 321 / 5 |
| file-counter | same | `counter=file` | `plan=suppress-row` | wrong | 321 / 5 |

The [private run directory](/volume/pt-dev/qjiu/rsi_context_external/r19-paid-runs/iceberg-short-v1/)
contains the reserved journal, identity, two canaries, task and final records.
`final.json` SHA-256 is
`1be71cbc8bdb368253be18147d800c91c06dafdda4a30d0f9df6377c36b22e60`;
`task.json` SHA-256 is
`66eeae4652e90b87fe4c9c2298ca9664cfd790306208c949557664695548a7d2`;
`identity.json` SHA-256 is
`cbda6d0dfd509bcda4e683eb532fae81da4c2e7bc78ccb324d5e982ed13993fa`.
The directory is mode 0700 and its files mode 0600. The exact launch SHA-256
is `ca56a029343cd94bb06ab903e3510af7d5e4017e3af1a54c28f909e073d6044e`.

The call sequence was pre-canary, data, file, post-canary: **four HTTP calls,
two target, two canary, zero auxiliary**. Both canaries passed exact answer,
model echo, stop reason and provider usage gates. Both target responses echoed
`Qwen/Qwen3.6-27B`, had `finish_reason=stop`, matched the registered request
hashes, and reported input usage equal to the local 321-token final-chat
geometry. Provider totals were **766 input / 14 output tokens**, with zero
unknown-usage attempts; targets contributed 642 / 10 and canaries 124 / 4.
The registered local-input-plus-requested-output ceiling was 8,958 tokens;
it is a dispatch bound, not observed usage. The runner reported
`provider_block_valid=true`, `task_feasible=false`, `qualified_parent=false`.

This is evidence of a fixed `suppress-row` response on this particular short
counter contrast, not proof of a general model defect. The result is compatible
with answer prior, prompt ambiguity or failure to use the `file` rule. A new
version needs an independently reviewed answer-changing request and controls
before any further paid source-length experiment. The R19 offline long-reader
synthetic run remains a wiring check, not a model observation.
