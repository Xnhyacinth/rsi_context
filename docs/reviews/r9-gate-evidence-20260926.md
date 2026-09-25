# R9 integration and admission record, 2026-09-26

R9 began from `main@2727c5d233f19a8bbbfa713e6011cd7be8d3d221` in two
isolated worktrees. Both synced the frozen project environment with
`uv sync --extra dev --frozen --link-mode copy`; `uv.lock` SHA256 was
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and the initial registry SHA256 was
`5d9f26873e0a677be2475e60ec877f964752c7436f20c01c8d1377612c0e0862`.
The R9 protocol was committed before integration as `e1dcf68`; the source
pair was independently developed at `01091a9`, then integrated with review
fixes at `63e3a59`. This record reports the merged candidate's evidence.

## Outcome and scientific boundary

The PostgreSQL 16.0/17.0 matched B development pair passed its **offline
structural source contrast**. Apart from the two pinned upstream documents,
the initial policy-visible stage views are identical. The private legal later
action changes from `defer-native` to `configure-native`. One unchanged
scripted source parser passes both two-session paths; either unchanged
constant source-free policy fails one version. The source-free action
transcript and prior/current review receipts are identical across versions.
Withholding **both** upstream document texts makes the scripted parser choose
the same action in both worlds, failing the 17.0 later gate. Omitting the
earlier finalized, verified record fails both stages as expected. The
private legality check occurs after the `act_verify` stage, while the review
oracle returns PASS for either subject, so the policy cannot probe the answer
from predecision receipts.

This is one PostgreSQL parent lineage, shared with the R8 C proposal. It
adds **zero qualified independent parents**: the parser witness is not a
fixed reader, the task names the decisive SQL option, the source text is
roughly 23–25 KB per variant, and final rendered chat token positions,
reader difficulty, and long-evidence dependence remain unmeasured. The
current benchmark data, task qualification, and full experiment loop are not
complete. No scored or sealed evaluation claim follows from R9.

## Source and run identity

- `REL_16_0` checkout: detached, clean
  `c372fbbd8e911f2412b80a8c39d7079366565d67`; portable selected-file
  manifest SHA256
  `f0aba9fa45716e693c3dbfa32378a7c009767b60f882765a9eacb83b5621c490`.
- `REL_17_0` checkout: detached, clean
  `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`; preexisting manifest
  SHA256 `d859392cab01769f4d5b56cdf0850a94ac565f15b90b127bcbf08ac169453b72`.
- Updated `configs/registry.json` SHA256:
  `d49881da452d7fb4bde311e374c66fcb78cd5b1a3b03eca28ed010d3b95442b6`.
  The registry dry run is retained in the ignored raw artifact
  `artifacts/rsi-core-v1/r9-postgresql16-dry-run-20260926.json`, SHA256
  `c1093c2709a3467e3d2fc5c6bc97d1f4b5484955b59942052343d10cb22e5ec4`.
- The shared PopQA test corpus was accessed through a temporary worktree
  symlink, read only by the tests; SHA256 before and after was
  `ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`.
  The symlink is removed during worktree cleanup.

The complete source/constructed-state separation, official PostgreSQL
documentation links, world hashes, policy vectors, and remaining limitations
are in [the source-pair report](r9-postgresql-source-contrast.md). The
prospective experiment order and denominator are in
[the R9 protocol](r9-experiment-protocol-20260926.md).

## Review and quality gate

`codex review --base origin/main` found one actionable P1: the new registry
ID was absent from the exact-ID test. Independent human review found that
the first source-withheld test left the version-different COPYRIGHT visible.
Both were fixed in `63e3a59`; 16 focused registry/source tests passed after
the fixes. A later `codex review --commit HEAD` attempt did not produce a
valid report because its nested review process recursively launched itself;
it is not counted as a clean automated review. The changed scope was then
manually inspected and its focused tests passed. No further actionable
finding remained.

The full pre-merge test run used both pinned PostgreSQL roots, the pinned
PEP and OTel roots, and the shared PopQA corpus: **1,363 passed, 16 skipped**
in 573.69 seconds; total branch coverage **80.49%**, meeting the configured
80% floor. Fifteen skips are the expected fail-closed `/usr/bin` ownership
gate in jail/broker tests; one live Siflow smoke skip saw no
`SIFLOW_BASE_URL` in the test shell. Raw log:
`artifacts/rsi-core-v1/r9-integrated-pytest-20260926.log`, SHA256
`bb41d9b28c257a16a77a8fd9f275c2de7d6fdd01ff141bf909c04d03cd169266`.

Repository-wide Ruff passed; strict mypy found no issues in 328 source
files; changed Python files passed Ruff format; `git diff --check` passed.
Bandit over `src scripts` reported 81 LOW, two preexisting genuine B102
MEDIUM in `scripts/arm_comparison_v2.py:119` and
`scripts/trajectory_v3.py:375`, and no HIGH or new MEDIUM findings. Raw
JSON: `artifacts/rsi-core-v1/r9-integrated-bandit-20260926.json`, SHA256
`ab816b532e71c893be10cfb4696b35b9bdee59c0a3580f3ce2ae0944038ed1d9`.

No Siflow API token or GPU resource was consumed in R9. The adjacent
root-owned `local-env.sh` exposes `SIFLOW_API_KEY` when sourced but did not
set `SIFLOW_BASE_URL`; the project has a separately fixed Siflow endpoint.
Credential presence does not admit live model-authored policy execution.
The current host still has UID-1000-owned `/usr` ancestors and the jail
correctly refuses. Run unskipped adverse and paired B/C jail tests on a
trusted immutable runtime before any prospective paid researcher update-rate
pretest. A fixed-reader development pilot also needs exact final worker-chat
rendering, tokenizer offsets, model/profile checks, source-free controls,
and a frozen call budget first.
