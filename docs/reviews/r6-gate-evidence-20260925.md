# R6 offline integration gate, 2026-09-25

R6 started from `main@73157e800197c8116a34cd35db63d603265755cd`.
The grader, broker, jail, and integration worktrees used the same `uv.lock`
SHA256 `5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and ran `uv sync --extra dev --frozen --link-mode copy` before editing.
The R4 parent manifest, B/C budget, and two Siflow profiles retained their R5
hashes. The legacy PopQA test corpus retained SHA256
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`;
the detached OTel checkout remained at
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d` and was clean.

## What this gate establishes

- The common evaluator can opt a later B commit into a session-entry check of
  a prior finalized award and an earlier environment-issued, plan-matching
  PASS verification. It rejects after-the-fact verification and policy-written
  PASS records. The versioned OTel B v2 pair has canonical ordered-pair SHA256
  `b6c165629868d89295e16ece0e3f4e635fd90d4937c3d7c6e0b647b38a1b0bbd`.
  It is a development candidate and reuses the OTel source lineage.
- The trusted broker validates framed child messages, exposes only the visible
  stage, routes tools and model requests through parent budgets, preserves
  state across turns, and fails closed on protocol, deadline, and trusted
  callback errors. The deterministic fake-child tests pass. Provider-reported
  usage remains an adapter assertion, and local estimates are kept distinct.
- The policy jail stages exact audited source and hashes, applies OS isolation
  before candidate execution, and refuses replaceable source or launcher
  paths. Independent security review accepted the refusal fix for offline
  merge. On this host `/usr/bin` and `/usr/lib` are UID-1000-owned, so the
  corrected launcher refuses admission. Earlier kernel isolation observations
  under replaceable paths are historical and do not qualify this host.

The broker and jail are separate offline components. The paired jailed-broker
test covers two direct survey turns only; it skips under the current host
trust refusal. The broker has no `run_session_sequence` integration yet. Any
such integration must bind its tool environment to the runner's per-session
`ProjectState`, then test B cross-session action and verification behavior.
Synchronous model/delegate callbacks also need interruptible deadlines and
usage-bearing auxiliary adapters before paid live use. Neither the live
isolation gate nor the scored A/B/C or sealed gate has opened. No Siflow API
request or GPU job was made during R6; R4's three canary attempts remain a
separate historical usage ledger.

The proposed PEP and PostgreSQL independent-source parents have no registry
entry, acquisition, file-byte/span audit, or qualified task. A read-only
source proposal is in `r3-next-execution-plan.md`; it does not change the
independent-parent count. The old R3 v3 preflight still reports
`live_ready=false` by design.

## Quality gate

Full `pytest` with branch coverage and the pinned OTel source completed:
**1,310 passed, 16 skipped**, 80.39% total coverage (80% required). Fifteen
skips are the named `/usr/bin` host trust refusal in jail and jailed-broker
tests; one is the live Siflow smoke because credentials were not loaded into
the test shell. The ignored raw log is
`artifacts/rsi-core-v1/r6-final-pytest-20260925.log`, SHA256
`73f09cd0fc49f766c32b258045694da55d69ac06d37abb78ef4a9d89b1f502dc`.
The new `_policy_child.py` has 0% in-process coverage and `policy_jail.py`
has 28% because the corrected host admission prevents their launch paths;
the repository-wide figure should not be read as jail coverage.

Repository-wide Ruff lint passed, strict mypy found no issues in 320 source
files, and Ruff formatting passed for all 11 Python files changed in R6.
Bandit emitted 81 LOW findings and two pre-existing MEDIUM B102 findings in
`scripts/arm_comparison_v2.py:119` and `scripts/trajectory_v3.py:375`.
Its JSON artifact is `artifacts/rsi-core-v1/r6-final-bandit-20260925.json`,
SHA256 `5669d0518839c3f1128a4c1b7cde0d57e0024d71916f1b0a6defbad1fb2de5e3`.
`git diff --check` passed. Independent security and integration reviews found
no remaining high-confidence P0/P1 issue in the offline merge scope; both
explicitly kept the live gate closed.
