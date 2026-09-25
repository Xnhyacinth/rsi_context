# R4 B/C development budget qualification

This is a **versioned, offline capacity contract**. It consumes the completed
R3 B/C scripted admission by exact SHA256 and makes no model call. Its scope is
the existing B/C development worlds; the new OTel and KEP-753 parent candidates
must be measured separately before they can enter any call budget.

The R3 scripted baseline/candidate call counts were B 31/35 and C 18/20.
`configs/r4_bc_dev_budget_v1.json` sets one common 40-call cap per complete
development run: the observed maximum candidate run (35) plus five calls.
One fixed baseline and two researcher candidate evaluations per group imply
a maximum of `2 groups × 3 runs × 40 = 240` worker requests. The researcher
opportunity is two planned draws per group, one HTTP attempt per draw, at most
four researcher requests in all. Failed, invalid and missing-usage attempts
must remain in that denominator when a live pilot is later authorized.

The separate `configs/r4_siflow_qwen_worker_profile_v1.json` binds
`Qwen/Qwen3.6-27B`, thinking disabled, 2,048 output tokens, seed 42 and
temperature zero. The existing `siflow-qwen3.6-27b-t2` profile and
`configs/budget_v1.json` remain as historical v1 inputs; neither is silently
changed. The provider revision is unobservable from this profile. An actual
provider canary must confirm that the 2,048-token request is accepted before
the profile is used for model evidence.

After committing the contract and profile, run from a clean project-local
`uv` worktree:

```bash
uv run --no-sync python scripts/qualify_r4_bc_budget.py \
  --source-admission /volume/pt-dev/qjiu/rsi_context/artifacts/rsi-core-v1/r3-bc-gate1-offline-admission-v3-20260925.json \
  --output artifacts/rsi-core-v1/r4-bc-budget-qualification-v1-20260925.json
```

The output records start/end Git and input SHA identities, aggregate call
counts, profile hashes, and `live_ready=false`. It excludes source item
feedback, evaluator labels, and model transcripts. The cap is only a scripted
feasibility bound; real worker usage may exceed it. No live researcher policy
execution is allowed until jailed execution, a successful worker-profile
canary, and a qualified independent-parent manifest exist.

The first committed-input qualification ran at `803b7b1` and produced
`r4-bc-budget-qualification-v1-20260925.json` (SHA256
`84b31950f37e093c2e1aec84295a319391d44ca1c55d8c45a2ec6980c6a42f55`).
The input identity matched at start/end, B/C scripted runs fit the 40-call
cap, and zero provider calls were made. The current shell did not expose
`SIFLOW_API_KEY` or `SIFLOW_BASE_URL`, so the provider canary remains unrun;
no token count or service-side version is inferred from the offline artifact.
