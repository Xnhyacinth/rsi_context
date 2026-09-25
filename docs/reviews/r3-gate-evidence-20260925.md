# R3 offline gate evidence, 2026-09-25

The final integrated offline run used code commit
`e68249d` and the committed Gate 1 v3 manifest. Artifacts below are local,
ignored JSON files under `artifacts/rsi-core-v1/`; copy them by hash when
moving workspaces. They are not model efficacy results.

| Artifact | SHA256 | Result |
| --- | --- | --- |
| `r3-gate1-preflight-v3-20260925.json` | `6e539777598c4b4c1da415b6bf89a8517e225b95b26739f0922f8be5c5a669cd` | Exact tracked, visible and B/C material hashes match; live ready false |
| `r3-bc-gate1-offline-admission-v3-20260925.json` | `a5bc9cb17802f74021babda70432f196e4cb41361888ddd04fb16da16a155ecb` | Complete offline wiring; B baseline/candidate 31/35 calls, C 18/20; zero provider calls |
| `r3-gate2-parent-qualification-v4-20260925.json` | `241ed167893bc7d4dbeaca6c252d655bca1dc56619acae6b39b4099a8bb0a9c2` | 10 worlds, one shared lineage, zero qualified independent parents |
| `r3-gate2-source-registry-dry-run-20260925.json` | `a4f94bf298390130605423cc0b20960f5e47d988f061aab248d1003043a56255` | Two pinned Apache-2.0 source repositories planned; sizes unknown; no download |

The v3 manifest SHA256 is
`3efde837780e047a0c66afccb8b840357bf15312ee8c0b6690a27cda8fd14158`.
The earlier v2 preflight and B/C/Gate 2 runs were made before the source
registry update; they remain historical artifacts tied to commit `cd5b7ae`.
No old artifact is reused as v3 input.

The final project-local check ran with the existing PopQA corpus exposed to
this isolated worktree by a local symlink; the corpus file SHA256 was
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`.
`pytest --cov=rsicontext --cov-branch` finished with 1,197 passed, one live
credential skip and 82.21% total coverage. Its log is
`r3-final-pytest-20260925.log` (SHA256
`4eacdf3c7a619b0fbcd66095bdb7f0f29293e63512c6c04a5c3f08d5e8080b0f`).
Ruff and strict mypy passed. Bandit (`src scripts policy`) reported 64 low and
two medium findings; the medium B102 dynamic-policy execution sites in
`arm_comparison_v2.py` and `trajectory_v3.py` are pre-existing and their live
entry paths now fail closed without an isolated executor. The Bandit JSON
SHA256 is `0945639af3d1877892475f248c53b86a0f24959e7e88883b13629f3f34f19922`.

The next admission steps are an actual low-privilege candidate executor,
versioned B/C worker-call and output-token profiles, independently sourced
and reviewed parent projects, and a development-only real-reader difficulty
screen. Until these pass, the B/C live entry remains closed and no scored
comparison or retained-improvement claim is supported.
