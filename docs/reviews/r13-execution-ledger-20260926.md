# R13 distinct-card and jailed-broker execution ledger

Status: in progress; no R13 API or GPU call authorized by this ledger.
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
| Broker worker | unchanged jail, typed broker, old R3 refusal and R12 boundary audit | add a separate offline prospective admission/execution path that keeps model-authored code out of the evaluator; fail on this host before researcher API, preserve old guard, report `live_ready=false` |
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
