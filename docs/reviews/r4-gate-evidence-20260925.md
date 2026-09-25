# R4 development gate evidence, 2026-09-25

R4 outputs are development-only. The code and frozen inputs used for the
latest local run were at Git `045311b69232e46dc2a0766815c54caf5f8c5f8a`.
All raw JSON and logs below live under ignored `artifacts/rsi-core-v1/` and
must be copied by SHA256 when moving workspaces. Portable source pins,
visible A-dev feedback and B/C scripted-call projection are tracked in Git.

| Local artifact | SHA256 | Result |
| --- | --- | --- |
| `r4-portable-r3-preflight-20260925.json` | `1aaafdf68b74bac2813214df7f97988a44385d3e1954ac915cfb652308da4895` | Committed A-dev bytes pass the R3 v3 preflight |
| `r4-rebuilt-r3-bc-offline-v1.json` | `dfa81983af4551693924ac00fbd706960d8b66cad18348c54691707ee8687b43` | Rebuilt B/C scripted calls match 31/35 and 18/20, zero API calls |
| `r4-bc-budget-qualification-v2-20260925.json` | `d1fb4f9da2c51a7410567ce811dcbc5503c68ff4ae669b6802ddc30b4eb98716` | 40-call scripted cap fits the old B/C development worlds; live ready false |
| `r4-parent-candidates-v1-20260925.json` | `eb8f7b0f432259936ed8ac69ab5bfa727773a4d51693d5224da6044ba99c8505` | Two new source lineages, **zero qualified parents**, zero model calls |
| `r4-worker-profile-canary-v1.json` | `b5e03beeb60c746fffd715ebb03bc88c17220d9bf5d97a703ca94f23e427d799` | One Qwen call, exact model echo, 80 input / 2 output provider tokens |
| `r4-researcher-profile-echo-diagnostic-v1.json` | `6bda50d8215a96695f579f1e9c80f0c5f327c400a796559c1f27ad0ebab1450f` | One DeepSeek diagnostic call, mismatched model echo, 56 input / 1 output provider tokens |
| `r4-siflow-profile-canary-ledger-v1.json` | `db765868cf788897cc466377d7e96cd16f5b6dd36930c488b0236f092b996a0d` | Three inference attempts total; one earlier strict DeepSeek rejection has unknown usage |
| `r4-final-pytest-20260925.log` | `da18f43a8ed51865ff33dcfd719a27029317174655ea9238a67208843dc07ed2` | 1,230 passed, one live-credential skip, 82.25% branch coverage |
| `r4-final-bandit-20260925.json` | `5c61fd6e3b4f8905a04bdab55a55183b7245e2f185559937f2b531807b12ffac` | 78 low and two pre-existing B102 medium findings |

Ruff and strict mypy passed across the repository. The test worktree used a
temporary link to the existing PopQA corpus (SHA256
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`)
for legacy tests, then removed that link. No candidate policy ran against
Siflow; the canaries used trusted, fixed prompts and did not consume a
researcher draw. The worker canary used a 1,024-token request ceiling, so it
does not prove acceptance of the planned 2,048-token ceiling. The DeepSeek
strict profile remains rejected by the exact response-model check. Neither
profile identifies an immutable service-side model revision.

R4's new OTel A and KEP-753 C worlds are compact construction witnesses, not
long-context qualified or scored parents. Their sources are disjoint from the
supplier dossier; the current qualified independent-parent count remains zero.
The security report confirms useful host jail primitives but no implemented
bounded broker or staged runtime. Live model-authored policy execution stays
closed.
