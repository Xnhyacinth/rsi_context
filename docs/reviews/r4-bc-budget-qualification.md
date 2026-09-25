# R4 B/C development budget qualification

This is a **versioned, offline capacity contract**. The active v2 consumes a
committed, label-free projection of the completed R3 B/C admission, pinned by
SHA256 and carrying the original artifact's SHA256. It makes no model call. Its scope is
the existing B/C development worlds; the new OTel and KEP-753 parent candidates
must be measured separately before they can enter any call budget.

The R3 scripted baseline/candidate call counts were B 31/35 and C 18/20.
`configs/r4_bc_dev_budget_v2.json` sets one common 40-call cap per complete
development run: the observed maximum candidate run (35) plus five calls.
One fixed baseline and two researcher candidate evaluations per group imply
a maximum of `2 groups × 3 runs × 40 = 240` worker requests. The researcher
opportunity is two planned draws per group, one HTTP attempt per draw, at most
four researcher requests in all. Failed, invalid and missing-usage attempts
must remain in that denominator when a live pilot is later authorized.

The separate `configs/r4_siflow_qwen_worker_profile_v1.json` binds
`Qwen/Qwen3.6-27B`, thinking disabled, 2,048 output tokens, seed 42 and
temperature zero. `configs/r4_siflow_researcher_profile_v1.json` separately
binds `deepseek-ai/deepseek-v4.1-flash`, thinking disabled, exactly 8,192
output tokens, seed 42 and temperature zero. The contract pins both profile
files by SHA256 and validates their complete loaded identities. The existing
`siflow-qwen3.6-27b-t2` profile and
`configs/budget_v1.json` remain as historical v1 inputs; neither is silently
changed. The provider revision is unobservable from this profile. An actual
provider canary must confirm both new request profiles before either is used
for model evidence. The future live caller must enforce these caps at each
request; this offline qualifier does not send requests.

After committing the contract and profile, run from a clean project-local
`uv` worktree:

```bash
uv run --no-sync python scripts/qualify_r4_bc_budget.py \
  --source-admission resources/r4_bc_scripted_calls_v1.json \
  --output artifacts/rsi-core-v1/r4-bc-budget-qualification-v2-20260925.json
```

The output records start/end Git and input SHA identities, aggregate call
counts, profile hashes, and `live_ready=false`. It excludes source item
feedback, evaluator labels, and model transcripts. The cap is only a scripted
feasibility bound; real worker usage may exceed it. No live researcher policy
execution is allowed until jailed execution, a successful worker-profile
canary, and a qualified independent-parent manifest exist.

The first committed-input v1 qualification ran at `803b7b1` and produced
`r4-bc-budget-qualification-v1-20260925.json` (SHA256
`84b31950f37e093c2e1aec84295a319391d44ca1c55d8c45a2ec6980c6a42f55`).
The input identity matched at start/end, B/C scripted runs fit the 40-call
cap, and zero provider calls were made. The current shell did not expose
`SIFLOW_API_KEY` or `SIFLOW_BASE_URL`, so the provider canary remains unrun;
no token count or service-side version is inferred from the offline artifact.
That v1 artifact is historical: it read an ignored local R3 admission JSON
and its researcher profile allowed 16,384 output tokens without an explicit
thinking flag. The active v2 input projection is committed under `resources/`.
The exact visible A-development feedback bytes needed to rerun the R3
admission are also committed at
`resources/r3_visible_dev_7052c06/a-dev-feedback.json` (SHA256
`ff941ba94062a37d681993db28073fe871b412e0cd3b60847b4563f006241640`).
To regenerate aggregate call evidence, run the R3 preflight with that
resource directory, then run `scripts/r3_bc_researcher_pilot.py` with the
committed v3 manifest and a new output path. The historical R3 artifact's
timestamps and Git head are not expected to reproduce byte-identically.

The active v2 qualification ran at `babbf606` and produced
`r4-bc-budget-qualification-v2-20260925.json` (SHA256
`d1fb4f9da2c51a7410567ce811dcbc5503c68ff4ae669b6802ddc30b4eb98716`).
Its start/end identity matched; the contract SHA256 was
`4a2d62dc3b85271305a03747f9fab4775884580168d8320a0111624ddd2ac975`.
The portable projection, rather than the ignored R3 JSON, supplied the exact
31/35 and 18/20 call counts. The v2 output still reports `live_ready=false`
and zero model API calls.
