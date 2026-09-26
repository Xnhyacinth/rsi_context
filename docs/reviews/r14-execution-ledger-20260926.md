# R14 independent-parent and broker continuation

Status: in progress. Four isolated worktrees started clean at
`main@7cade65484896fce5185a8ec554d939bdae11697`; each used
`uv sync --extra dev --frozen --link-mode copy`. The common `uv.lock` SHA256 is
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256 is
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
The original main checkout's `logs/` remains untouched.

| Worktree | Ownership | Evidence target |
| --- | --- | --- |
| `r14-pep` | PEP 1 source-dependent B intake | Pinned source spans, visible/project/oracle distinction, source-free shortcut audit; admit a development card only with a defensible action, otherwise reject |
| `r14-kep` | KEP-753 C parent intake | Pinned source and constructed rollout split, multi-session action/receipt chain, causal controls; admit a development card only if adjudicated |
| `r14-broker` | Candidate exercise integration | Exact audited `policy/seed.py` staged in unchanged jail, typed broker B/C exercise and usage accounting; current host must fail before candidate execution |
| `r14-integration` | Experiment contract and merge | Reconcile scientific/security review, run full gates, report effective evidence and limits, merge/push main and clean branches |

The qualified independent-parent count is still zero. Scripted tests may
validate wiring, not model difficulty. The current host jail refuses
`/usr/bin` as a non-root-owned ancestor; no researcher-authored code or paid
researcher call may cross that boundary. A fixed benchmark-owned reader
control is separate from researcher execution and needs its own frozen
materials, profile, canaries, provider usage, and bounded stop rules.

The local credential loader documented by earlier runs is
`/volume/pt-dev/qjiu/wynckeliao-env/ops/env/local-env.sh`. A presence-only
check found `SIFLOW_API_KEY`; that file does not set `SIFLOW_BASE_URL`.
No credential value was printed or copied into this project.
