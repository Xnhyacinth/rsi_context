# R20 Iceberg short S2 feasibility result

The frozen live v2 block ran once on 2026-09-27 UTC. The provider protocol
block passed, but the simplified task did not: the Qwen reader returned
`plan=suppress-row` for all four arms. The independent private oracle requires
`suppress-row` for A and `emit-row` for both B and C. D has no unique oracle
and records the default response. Thus `provider_block_valid=true`,
`task_feasible=false`, and `qualified_parent=false`. This result does not
admit a long-source Iceberg spend. Do not rerun or reinterpret this v2 block.

| Arm | One changed condition | Observed | Private result | Provider input/output |
| --- | --- | --- | --- | ---: |
| A, data-counter-match | Base: data sequence 7, delete 8, same partition, value 42 | `suppress-row` | correct | 197 / 5 |
| B, file-counter-match | Only counter changes; file sequence 12 | `suppress-row` | wrong; expected emit | 197 / 5 |
| C, data-counter-mismatch | Only delete value changes to 99 | `suppress-row` | wrong; expected emit | 197 / 5 |
| D, unknown-diagnostic | All retained-rule fields unknown | `suppress-row` | diagnostic; no oracle | 193 / 5 |

The [private paid artifact](/volume/pt-dev/qjiu/rsi_context_external/r20-paid-runs/iceberg-short-v2-once/)
contains the reserved journal, identity, pre/post canaries, task, and final
records. `final.json` SHA-256 is
`abc924bba6988e9c81c4f1b4ff8634c74583fa3684fabbb67a88b9b57024f082`;
`task.json` SHA-256 is
`a43525db3a95fc8355d5208f2883f9696667d196f9fac1f98df4d395030dd3a3`;
`identity.json` SHA-256 is
`3914b2ce97fc96b9dfc790d6f9b009ab22963fb1ec12ac48a622e23d7690b09b`.
The directory is mode 0700 and files mode 0600. The exact v2 launch SHA-256
is `26a62e88611d8e26d7e17bd28529913651a7ac7d0c65ccf3c43f776c4aed2241`;
the model-visible registration stayed at SHA-256
`a528a02fd8b90d9a69ed0a1bb68c0a0ee89bb854026c459e2e5b7a65d4936e58`.

The sequence was one pre-canary, four target calls, one post-canary, with
zero auxiliary calls and no retries. Both canaries passed. All target
responses echoed `Qwen/Qwen3.6-27B`, stopped normally, matched registered
request hashes, and reported input usage equal to local final-chat geometry.
Provider totals were **908 input / 24 output tokens**, including 784 / 20
for targets and 124 / 4 for canaries, with zero unknown-usage attempts. The
13,196-token local-input-plus-requested-output ceiling was a dispatch bound,
not observed usage.

The all-suppress pattern on both wrong-oracle controls and the no-rule
diagnostic is consistent with a fixed answer shortcut on this task format.
It does not identify whether the cause is model prior, prompt wording, or
failure to apply the retained rule. R19's harder short fixture separately
failed on its `file` counter arm; neither block justifies a long-context
dependency or independent-parent claim. A next version should change the
task/reader design with separately frozen controls and should not treat these
two Iceberg variants as independent benchmark worlds.

## Combined integration gate

After merging the R19 integration fixes into the R20 branch, the full suite
with pinned local source/tokenizer fixtures and no Siflow credentials passed
**1,625 tests, 27 skipped, zero failed**. Branch coverage was **80.48%**,
above the configured 80% threshold. The
[full log](/volume/pt-dev/qjiu/rsi_context_external/r20-preflight/full-pytest-combined.log)
has SHA-256 `40d1c679d2eff236c2af32bbb69a5ca3c9614e8c4a47d0e3bb5dc8fb5f333480`.
Ruff passed; strict mypy passed **410 source files**. Bandit over `src scripts`
reported the unchanged **81 LOW, 2 MEDIUM, zero HIGH** findings, with no R20
finding; the [JSON report](/volume/pt-dev/qjiu/rsi_context_external/r20-preflight/bandit-combined.json)
has SHA-256 `fcf057302a6f6165c31bdb2ba543cfdc751f545e9cbf3828900bc456ecc2a648`.
The host jail tests remain skipped at the separately documented trust boundary.
