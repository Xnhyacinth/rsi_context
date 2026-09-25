# R5 development gate evidence, 2026-09-25

R5 starts from `main@9942398ffc78ae9b98cf949b2dcc97dd3994efe5`.
The metering, protocol, long-task, and integration worktrees have that commit
as their merge base. Their `uv.lock` SHA256 is
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`;
the R4 source manifest, B/C v2 budget, and Siflow profile files did not change.
The external OTel checkout is clean at detached
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`; the builder verifies both
selected source files by exact SHA256. The local legacy PopQA corpus used for
the full test run has SHA256
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`.

| Frozen input | SHA256 |
| --- | --- |
| `configs/r4_parent_source_manifest_v1.json` | `2c180841fc50bc49813829a8183045360fb182e7263af0a0ec853c6567609360` |
| `configs/r4_bc_dev_budget_v2.json` | `4a2d62dc3b85271305a03747f9fab4775884580168d8320a0111624ddd2ac975` |
| `configs/r4_siflow_qwen_worker_profile_v1.json` | `82d5915b807abff306d662d93140f3e9964111f0441f8d2dd00fa4d8f04f8547` |
| `configs/r4_siflow_researcher_profile_v1.json` | `9a108303b35b120ca3302ac4bfd1b50ed0d4c912de717c5fab051fc9197e46da` |

The OTel review records the exact source-file/span hashes and canonical hashes
for both session worlds. These settings identify an offline development
phase; they do not assert a pinned provider-side model revision.

## Reviewed changes

- Common `ToolBudget` and policy/tool callbacks now count dispatched failures,
  malformed delegation requests, and refused attempts. Known local input
  estimates are checked before model/delegate dispatch. `tool_calls` is an
  attempt count; `model_calls` is a dispatched-model count. Provider token
  usage is never inferred from whitespace estimates. Output can still exceed
  a local token cap after a callback; the future broker must constrain the
  provider request/response to make that a hard spending cap.
- The new versioned policy IPC codec bounds frames/state and validates
  schema, action, and message order. Independent review found a mismatch with
  legal multi-check actions; the codec now round-trips a real M2 vector
  `Action.to_dict()`. It is not a child executor or live authorization.
- The OTel B two-session task uses complete pinned sources and a real reset.
  Source deletion, receipt flips, late repair, irrelevant material, and byte
  drift were tested. A forced invalid first-session finalization can still
  satisfy the isolated second-session gate, so Gate 2 is **rejected**. It
  reuses the OTel source lineage and adds no qualified independent parent.
  The pinned Qwen tokenizer counted 12,708 tokens for direct source document
  strings; final policy/API prompt length and fixed-reader difficulty are
  unmeasured. Source-dependent tests require an explicit pinned checkout;
  absent-source skips do not count as qualification evidence.

No Siflow API request or GPU job was made during R5. R4's three Siflow canary
attempts remain a separate historical ledger, including one failed attempt
with unknown provider usage. The strict DeepSeek response-model mismatch and
the unconditional live policy isolation gate remain unresolved. R5 does not
admit a scored comparison, researcher update-rate estimate, or sealed run.

## Quality gate

Full pytest with branch coverage and the pinned OTel source root passed:
**1,279 passed, 1 skipped**, 82.63% total coverage (80% required). The one
skip is the live Siflow smoke, because credentials were deliberately not
loaded into the test shell. The ignored raw log is
`artifacts/rsi-core-v1/r5-final-pytest-20260925.log`, SHA256
`84358be090692c7ad0ecfd37d84174cfea566b2cb7da94aa1e8b8d4fcd6040d6`.

Ruff passed across the repository; strict mypy reported no issues in 311
source files. Ruff formatting passed on all seven changed Python files. A
repository-wide format check reports four unchanged, pre-existing files;
they were left outside this phase. Bandit reports 78 LOW and two pre-existing
B102 MEDIUM findings, the same counts and locations as R4. Its JSON artifact
is `artifacts/rsi-core-v1/r5-final-bandit-20260925.json`, SHA256
`3fef0c44cf4ad78cc59ae44521da9b655bbb52dc1d9c45d505b0f598c05b41a0`.
