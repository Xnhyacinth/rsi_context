# R7 source and broker gate, 2026-09-26

R7 started from `main@186cc4f9c331f1db9ca008f23c8650902026bd64`.
The broker, PEP, PostgreSQL, and integration worktrees shared `uv.lock`
SHA256 `5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and each ran `uv sync --extra dev --frozen --link-mode copy`.
The legacy PopQA test corpus retained SHA256
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`.

## Reviewed advances

- `python-pep-process` and `postgresql-rel-17-0` now have exact Git revisions
  registered, reviewed dry-run acquisition plans, detached clean checkouts,
  selected-file Git blobs and SHA256 values, per-file or pinned-license review,
  and complete decisive source-span byte hashes. A read-only independent
  review found two truncated span endings; both were extended through the
  complete sentence and rechecked. The portable manifests and raw acquisition
  ledger are indexed in `r7-source-acquisition-20260926.md`.
- The trusted parent broker now binds the same per-session `ProjectState`,
  shared `ToolBudget`, and `DocumentRegistry` used by `run_session_sequence`,
  then closes pipe descriptors and its owned worker on normal and exceptional
  exits. Before the change, an actual two-session fake-child B path was
  **FAIL/FAIL** because verification used a placeholder environment; afterward
  the legal path is **PASS/PASS**. Failed, late, and forged first-session
  verification paths are **FAIL/FAIL**. The fake-child sequence tests also
  cover carry-only reset, shared budget and registry, and cleanup. Independent
  code review found no P0/P1/P2 merge blocker. Details are in
  `r7-broker-b-sequence.md`.

The B test uses a trusted fake child, not the jail. The corrected jail still
refuses this host's UID-1000-owned `/usr/bin` and `/usr/lib` ancestors. The
new source checkouts are **candidate parent lineages**, with no PEP B or
PostgreSQL C task world qualified by intervention and fixed-reader evidence.
There is no source-specific final rendered prompt token/offset audit, scored
comparison, researcher update-rate estimate, or sealed result from R7.
Provider usage has not been measured in this phase; no Siflow API or GPU job
was used. The R4 canary ledger remains separate historical evidence.
Independent targeted review confirmed the two older Bandit B102 MEDIUM
findings in `scripts/arm_comparison_v2.py` and `scripts/trajectory_v3.py` are
real host `exec` sinks, not scanner false positives. Their normal live CLI
paths currently stop at the unconditional isolation gate before reaching the
sink. Keep those warnings and the gate; an auditor alone or a suppression
comment would not make legacy strategy execution safe.

The changed registry invalidates the R3 v3 preflight's pinned registry hash.
Keep v3 as a historical snapshot; issue a new preflight version with the final
registry, source manifests, budgets, reader profiles, and experiment assets
before any reported R7-world run.

## Next admission gates

1. On a host with trustworthy runtime paths, rerun the jailed-child and
   jailed-broker adverse tests without host-trust skips. For this host, only an
   independently pinned runtime bundle copied without executing replaceable
   `/usr` paths can address that blocker. Keep the live gate closed until the
   actual broker and jail execute B/C paths together.
2. Build a PEP B development world with two coherent prior-status paths and
   later actions, and a PostgreSQL C world whose legal action changes with
   source rule, prior finalized slot, and current receipt. Test deletion,
   reversal, late repair, irrelevant material, carry removal, and source
   lineage before counting either as an independent parent.
3. Measure exact final-chat worker tokens, evidence/query offsets, fixed-reader
   success and failure, and all target and auxiliary calls. Give synchronous
   model/delegate callbacks hard deadlines and usage-bearing adapters before
   any paid pilot; then freeze a versioned preflight and use the configured
   Siflow endpoint for a bounded development run.

## Quality gate

Full pytest with branch coverage and both pinned R7 source roots completed:
**1,321 passed, 16 skipped**, 80.40% total coverage (80% required).
Fifteen skips are the named `/usr/bin` host trust refusal in jail and
jailed-broker tests; one is the live Siflow smoke because credentials were not
loaded into the test shell. The raw log is
`artifacts/rsi-core-v1/r7-final-pytest-20260926.log`, SHA256
`42076d2e0c77ca122f8453fd7db6e550f71c4c77cafa85b41f1fc46cdd075b63`.
The source tests ran against detached PEP/PostgreSQL checkouts rather than
counting absent-source skips. Broker and sequence module coverage reached 80%
and 95%, respectively. `_policy_child.py` remains at 0% and `policy_jail.py`
at 28% on this host because the corrected admission prevents their launch
paths; total coverage is not evidence of live jail coverage.

Repository-wide Ruff lint passed; strict mypy found no issues in 322 source
files; changed Python files passed Ruff formatting. Bandit reported 81 LOW and
the two genuine legacy B102 MEDIUM findings described above, with no new
medium/high finding. Its JSON artifact is
`artifacts/rsi-core-v1/r7-final-bandit-20260926.json`, SHA256
`197c5aa9bb433e9fda767ff8da450c8e6f63a58f3f84f62221f3d559b5366c8e`.
`git diff --check` passed. Independent source, broker, and security reviews
have been reconciled; both identified source-span boundary corrections are in
the final manifests.
