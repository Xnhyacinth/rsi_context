# R20 Iceberg short S2 feasibility preregistration

This is a four-request development screen for the frozen non-thinking Qwen
reader. It tests whether a short, already retained rule can control one row
decision. It contains no S1 source pack or researcher policy. It cannot qualify
an Iceberg parent or establish long-source dependence. The `file` counter is a
constructed counterfactual, not the official Iceberg rule.

## Fixed input and private truth table

The source is the detached Apache Iceberg commit
`071d5606bc6199a0be9b3f274ec7fbf111d88821`, with complete
`format/spec.md` SHA-256
`e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb`.
The [pinned specification](https://github.com/apache/iceberg/blob/071d5606bc6199a0be9b3f274ec7fbf111d88821/format/spec.md)
states that equality delete pruning uses the data sequence number (line 688),
requires a strict earlier sequence (line 848), treats unpartitioned equality
deletes as global (line 853), and deletes a row when every equality column
matches (line 1136). The local source and tokenizer are rechecked through the
R19 source audit before any request. R19 material and launch files are not
modified.

The constructed facts are one data row with field-id 1 value 42, data
sequence 7, file sequence 12, and one unpartitioned equality delete with
sequence 8 and `equality_ids=[1]`. No other delete exists. The query and
output format are identical across arms. This table is evaluator-side; no
correct plan is present in the model-visible registration.

| Arm | Only changed input | Private oracle | Role |
| --- | --- | --- | --- |
| A, data counter, delete value 42 | Base | suppress-row | Required |
| B, file counter, delete value 42 | Counter only | emit-row | Required counter contrast |
| C, data counter, delete value 99 | Delete value only | emit-row | Required row-match control |
| D, all rule fields unknown, delete value 42 | Rule only | No unique oracle | Diagnostic of rule-free shortcut |

The pure private evaluator is
[`iceberg_short_private_r20.py`](../../src/rsicontext/analysis/iceberg_short_private_r20.py),
truth-table SHA-256
`2597ec91086c07304288eb624fdd61c5bc60a9c1bfd015de8d022b7c0c1a86fb`.
All four replies must pass exact format and provider gates; A/B/C must match
their private oracle for `task_feasible=true`. D is recorded with
`correct=null` and cannot become an accuracy claim. A format-valid wrong
answer still allows all remaining arms and the post-canary to run. A malformed
reply or unknown usage stops further dispatch.

## Frozen geometry and budget

The offline [`registration`](../../configs/r20_iceberg_short_registration_v1.json)
SHA-256 is `df17a2c7939eab743129d94aca60fb02777ed26b8608e882549c8bb912649dc2`.
The A/B/C final chat is 185 tokens each; D is 181, all measured by the pinned
Qwen tokenizer and template. Every prompt has a unique retained-rule evidence
span before a later query; the rule-to-query separation is 109 tokens. The
prompt/request SHA-256 per arm, exact chat geometry, source identity, registry,
profile, and tokenizer manifest are in the registration. The separate
[`launch`](../../configs/r20_iceberg_short_paid_launch_v1.json) binds all
producer bytes, the registration, canaries, private oracle, and budgets. Its
SHA-256 is `27d8acf046e39e60f855263fac809e9d52dfaa2647b69531d44eb6aef3278692`.

Maximum requests: **4 target + 2 canary, zero auxiliary**. Target local input
totals 736 tokens; requested target output totals 8,192, giving an 8,928
target planning ceiling. Two canaries add 62 local input and 4,096 requested
output, giving **13,148 local input plus requested output** for the entire
block. This is a request ceiling, not observed Siflow usage. Every target
still permits exactly one target-model call; provider usage and identity must
be returned and reconciled in the private fsynced journal.

The launch has `live_enabled=false`. A live attempt is refused before
credential resolution. Activation requires a reviewed new committed launch
and clean committed producer; the current branch makes **no Siflow or GPU
request**. Offline regeneration:

```sh
uv run --frozen --no-sync --with transformers==5.15.0 \
  --with tokenizers==0.22.2 --with jinja2==3.1.6 \
  python scripts/r20_iceberg_short_offline.py \
  --source-root /volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake \
  --tokenizer-path /volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b
```

Successful offline or synthetic wiring does not satisfy the task. If a later
reviewed paid block is valid but A/B/C fail, the long-source Iceberg screen
remains disallowed by this preregistration.

## Clean-commit synthetic check

At clean producer commit `e87c08c799ade4d17ed867600650282bce6b5b9f`, an
injected-SSE run exercised the committed launch, source/tokenizer checks,
both canaries, four target requests, fsynced journal, and final attestation.
The [private synthetic artifact](/volume/pt-dev/qjiu/rsi_context_external/r20-preflight/iceberg-short-synthetic-e87c08c-v1/)
has identity SHA-256
`c89aaa23b497c4b702cfb3a6d0b70174764549687bfaa707a8f1b24906038002`
and final SHA-256
`472c4a7293ec7fca7f6d1e5faec61fd67fca7afaedadee32a281e3613fbbda34`.
It records six injected requests, zero unknown usage, 13,148 planned tokens,
private 0700/0600 permissions, and `provider_block_valid=false`. Its
`task_feasible=true` verifies the synthetic wiring only; no model result was
observed. The focused suite passed 9 tests, with scoped Ruff, strict mypy,
and Bandit clean.
