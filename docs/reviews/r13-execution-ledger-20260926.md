# R13 distinct-card and jailed-broker execution ledger

Status: **R13 development slice verified**; no R13 API or GPU call was made.
All four R13 worktrees started clean at
`main@add0a6387d374d78eeb840f552189e88cc693cb6` with `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
Each synced the project-local dev environment using frozen `uv` resolution and
copy link mode. The original main checkout's untracked `logs/` is unrelated
work and stays untouched.

## Parallel work and success condition

| Owner | Frozen input | Deliverable and acceptance |
| --- | --- | --- |
| PG task-card worker | detached clean PG16/17 CREATE SUBSCRIPTION source and existing R11 pair | independently source-adjudicate connect/binary/origin candidates; implement one matched distinct card only if legal action is unambiguous, or publish a source-span-hashed rejection ledger |
| OTel task-card worker | detached clean OTel 1.24/1.43 database convention source and existing R12 pair | adjudicate DBMS/operation/namespace candidates; implement one matched distinct card only if same semantic question and opposite legal keys are supported, or reject with source-span hashes |
| Broker worker | unchanged jail, typed broker, old R3 refusal and R12 boundary audit | add a separate offline prospective admission path that keeps model-authored code out of the evaluator; fail on this host before researcher API, preserve old guard, report `live_ready=false` |
| Integration | all branches and pinned artifacts | reconcile evidence, review code and science claims, run proportionate checks and full required gates, merge/push `main`, then remove R13 worktrees/branches |

No card is counted merely because a field exists in a document. Its
two-session task, source span, private legal action, source-only intervention,
receipt chain, and distinguishability from the already measured card must be
verified. A source/version pair is one parent lineage. The 16-card difficulty
panel in [the feasibility plan](r13-difficulty-panel-feasibility-20260926.md)
remains unimplemented and unqualified until eight distinct cards and two
reader families are frozen. The broker path is a security engineering step;
without unskipped jail tests on a trusted host and a strict researcher model
canary, it is not a paid valid-update-rate pretest.

## Integrated result

Two PostgreSQL cards and one OTel DBMS-system card were admitted as **inspected
development material only**. The PG connect and binary cards have the same
legal action in both pinned revisions; `origin=none` was rejected for lack of
project/data acceptance criteria. The OTel DBMS key changes from `db.system`
to `db.system.name`, but an independent adjudicator still needs to confirm the
old connection-level and new span-definition scopes. OTel operation-name and
namespace/name candidates were deferred. The qualified independent-parent
count remains zero; PG and OTel are only two source lineages, and these new
cards have no model reader measurement. See the card intake records and the
updated difficulty-panel feasibility plan for exact spans, request hashes,
oracles, and experiment controls.

The separate researcher path records an immutable plan, verifies exact
baseline/source/visible-feedback bytes before any draw, audits private
candidate snapshots, and counts failures in the predeclared denominator.
It is **offline admission only**: `live_ready=false`, no candidate exercise,
researcher draw, worker call, or measured effective-update rate. An unchanged
trusted probe CLI refused this host at `non-root-owned path ancestor: /usr/bin`
before credentials/API. The legacy in-process pilot guard remains unchanged.

Independent security review found and verified fixes for a policy-boundary
exception that aborted later draws and for unbound material hashes. Codex
branch review found three P2 issues: invisible PG target record, ambiguous
PG binary publisher version, and a deeply nested candidate AST aborting the
planned draw loop. Each has a behavioral regression. A final
`codex review --base origin/main` found no further actionable issue; its
focused run passed 39 tests against the pinned PG/OTel roots.

The final integration test used detached, clean PEP, PG16/17 and OTel
1.24/1.43 checkouts, the same local PopQA corpus (SHA256
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`),
and a dummy Siflow key without a live endpoint. `pytest --cov=rsicontext
--cov-branch` finished with **1455 passed, 16 skipped, 80.72% branch
coverage** (floor 80%). Fifteen skips reflect the unchanged `/usr/bin` jail
trust refusal; the other is the live researcher smoke with no endpoint.
Repository-wide `ruff check .` passed, strict mypy found zero issues in 361
files, and all eight new Python files pass `ruff format --check`. The five
pre-existing whole-repository formatting differences were left outside this
slice. Bandit reported the unchanged **81 LOW, 2 MEDIUM, 0 HIGH** baseline,
with no finding in the new R13 files.

Raw ignored evidence is in `artifacts/rsi-core-v1/r13-gates/` in the main
checkout. `full-pytest.log` SHA256 is
`a21a13bff9529591a15cc5a9233a7dd10201072368af735f026ede2c02f14397`;
`bandit.json` SHA256 is
`3ab18e02f1ff1af3644938270f7f032436339de06dcedeb0429279423a4ebbe3`.
