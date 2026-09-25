# R8 B/C development-world audit, 2026-09-26

All R8 worktrees started from `main@ca9fe87e2821a72dbc0acd039d3b22d483c8885c`
with identical `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`5d9f26873e0a677be2475e60ec877f964752c7436f20c01c8d1377612c0e0862`.
Each ran `uv sync --extra dev --frozen --link-mode copy` before editing.
The PEP and PostgreSQL checkouts remained at the detached, clean R7 commits
and their selected bytes are checked by the new builders. The shared PopQA
test corpus SHA256 remained
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`.

## Findings and admission decision

- The PEP B builder produces two actual-session paths for one fictional
  Standards Track proposal. Either prior status can be finalized with an
  environment-issued PASS; the later constructed single-priority task changes
  with that prior status after reset. Its focused tests reject a failed prior
  receipt and a wrong later action; common runner tests cover forged, late,
  and missing prior evidence. The PEP-specific decision vector reports actual
  session outcomes. Pair material SHA256 is
  `8c55c82262825160f12a11e242d9a58f4727f90ebe2cdf195373bcea31c69e66`.
  Its 19 focused tests passed. See `r8-pep-process-b.md`.
- The PostgreSQL C builder uses complete pinned SGML and COPYRIGHT, one
  constructed subscription with two mutually exclusive slot configurations,
  current environment verification, and an older standby report. The same
  world accepts two distinct prior finalized slots and maps them to different
  later actions. A failed finished-copy or standby-ahead check makes a verified
  hold legal; an unready in-progress copy alone does not block promotion.
  The pinned source supports the conditions; the exact action/check API names
  and constructed project state are visible before the action. Ready-world pair SHA256 is
  `4efd7ec6fe5d473619f9630cfeb9c4e7efb3d0c0a25183c53d97e1727c6ab8eb`;
  other version hashes are in `r8-postgresql-c-development.md`. Its 15
  focused tests passed.

Independent scientific and security reviews found and corrected material
issues before merge: PEP status alone did not justify exclusive real-world
actions; PG's first draft hid the action API and treated two simultaneously
active subscriptions as one required slot set. The final worlds disclose
their fictional rules, keep evaluator gates private, and label the remaining
scientific limitation.

**Gate 2 source-dependence is rejected for both new candidates.** For each,
a scripted fixed map still obtains PASS/PASS when the original source text is
withheld. Phrase-deletion tests prove only that one scripted witness checked
those phrases. They do not prove a fixed reader needs long source material.
Neither candidate increases the qualified independent-parent count or enters
a scored or sealed split. The benchmark's data, tasks, setup, and experiment
loop are therefore not complete. Final rendered worker-chat token lengths,
evidence/query offsets, fixed-reader errors, source-free baselines over more
independent parents, and a frozen R8 preflight remain open.

No Siflow API or GPU job was made during R8. The prior R4 canary ledger is
separate. The current host's policy jail still refuses replaceable `/usr`
ancestors, so the paid researcher update-rate pretest is not admissible yet.
Its denominator must include **every planned researcher attempt**. Report
both (a) valid-submitted rate: prospectively audited, changed, submitted
policy snapshots divided by all planned attempts; and (b) audited-and-exercised
rate: those accepted snapshots that reach a metered worker decision without a
policy error, again divided by all planned attempts. Report provider usage
and task success separately. Existing R3 executable-update observations are
not a prospective candidate-admission rate.

## Next work

1. Revise source-specific questions so the source-free strategy fails under
   a fixed reader and source/receipt/action interventions remain separable.
   Test at least two independent qualified parent lineages before using a
   transfer or population-effect claim. The present variants all share their
   respective one-parent lineage.
2. Measure final rendered prompt tokens, source spans and distance to the
   later query using the pinned worker tokenizer/chat template. Freeze a new
   preflight version for final source/world/profile/budget bytes; do not
   overwrite the R3 v3 snapshot.
3. Keep legacy host-`exec` scripts and live model-authored policy execution
   fail-closed until an actual trusted-runtime jailed broker passes unskipped
   adverse and B/C paired tests. Then add interruptible provider callbacks,
   use Siflow's provider-reported target/auxiliary usage, and run a bounded
   prospective development pretest.

## Quality gate

Full pytest with branch coverage and the pinned PEP, PostgreSQL, and OTel
source roots completed: **1,355 passed, 16 skipped**, 80.46% total coverage
(80% required). Fifteen skips are named `/usr/bin` host trust refusals in the
jail and jailed-broker tests; one is the live Siflow smoke because credentials
were not loaded into the test shell. The ignored raw log is
`artifacts/rsi-core-v1/r8-final-pytest-20260926.log`, SHA256
`0d149c5fc0a41936c0f3533c35e8094e7ac8c61a542184a15233d99299e33fc1`.
`_policy_child.py` remains 0% and `policy_jail.py` 28% on this host, so the
repository-wide coverage figure is not evidence of current jail admission.

Repository-wide Ruff lint passed; strict mypy found no issues in 326 source
files; all four R8 Python files passed Ruff formatting. Bandit reported 81
LOW and the two previously reviewed, genuine legacy B102 MEDIUM findings,
with no new medium/high finding. Its JSON artifact is
`artifacts/rsi-core-v1/r8-final-bandit-20260926.json`, SHA256
`cf04a07767cf731bc32a14d5755026ecef760860019ce75c5e9406a57070b258`.
`git diff --check` passed. Independent source, scientific, and code/security
review findings were reconciled before merge; both worlds retain explicit
Gate 2 rejection.
