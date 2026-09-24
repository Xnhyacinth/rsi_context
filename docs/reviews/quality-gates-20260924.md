# Quality-gate triage (2026-09-24)

This is a working-tree audit, not a merge certificate. Full machine-readable
diagnostics are in `artifacts/quality-gates/20260924/` (ignored by Git).
Reproduce from the project root with:

```sh
.venv/bin/ruff check .
uv run --no-sync python -m mypy src tests scripts --show-error-codes --no-incremental
uv run --no-sync python -m bandit -r src scripts -f json
```

The `.venv/bin/mypy` and `.venv/bin/bandit` launchers currently have stale
shebangs pointing to a deleted worktree. `uv run --no-sync python -m ...`
uses the project interpreter and installed packages without changing the lock.

| Gate | Baseline | 2026-09-25 snapshot | Main causes |
| --- | ---: | ---: | --- |
| Ruff | 75 | 0 | Import order, unused bindings, small style defects; some were in concurrently edited R3 files. |
| strict mypy | 423 in 52 files | 0 in 288 files | Untyped test helpers, JSON-shaped `object` values, missing generic arguments, and a few real type mismatches. |
| Bandit (`src scripts`) | 51 findings, 14 medium | 52 findings: 50 low, 2 medium | Fixed-HTTPS `urlopen` sites were reviewed; intentional strategy execution remains a live-run restriction. The low findings remain open. |

Several agents were editing concurrently; rerun all three commands before
merging. The full baseline, intermediate, and 2026-09-25 diagnostics are
archived, including low-severity Bandit findings that have not been
individually resolved. A zero in this table is an observed working-tree
result, not a claim about later edits.

## Medium-severity Bandit findings

The B310 calls suppressed in fixed-endpoint scripts use literal HTTPS Siflow
URLs. `APIResearcherConfig` already rejects non-HTTPS endpoints before its
`urlopen` call, so that site has a source-backed local B310 suppression.
The R2a/R3 B310 sites were also reviewed against their fixed HTTPS endpoint
source; none remain in the 2026-09-25 Bandit report.

Two B102 findings are **real live-run boundaries**:

- `scripts/arm_comparison_v2.py` executes the API researcher's
  `strategy.py` in the benchmark process.
- `scripts/trajectory_v3.py` executes researcher-proposed `strategy_text`
  in the benchmark process.

Neither path uses `PolicyAuditor` before the `exec`. The existing
`FreshProcessPolicyFactory` is not a drop-in remedy: it implements a
different `ContextPolicy.assemble` protocol and explicitly does not provide
filesystem or network confidentiality. The project spec likewise says the
restricted Python namespace is a hygiene filter, not a sandbox. Treat both
legacy scripts as **blocked for live machine-authored strategy execution on
a host containing secrets or evaluator-only data** until a container/node
boundary and matching strategy protocol are implemented and tested. The
current R3 pilot path does not call either script.

`src/rsicontext/lifecycle/policy.py` retains its intentional internal
calibration-policy `exec`; its inline B102 suppression now states the
required external isolation instead of implying the namespace is secure.

## Verification on the quality-gate edits

The selected behavioral suite (`test_phase1_entry`, `test_rsi_core_policy`,
`test_world_v4_dossier`, `test_c_group`, `test_r2b`, `test_api_researcher`)
passed 78 tests; one live API smoke was skipped because no credentials were
present. The second batch passed trajectory/snapshot (24), Zephyr (10),
campaign bridge plus trajectory wiring (15), review acceptance (16),
R2b (13), C group (9), and dependency probes (36) tests. A local no-API
hook check exercised the legacy pilot's fixed/stateful action and note
behavior. `qualification_panel` parsed the existing n=16 artifacts and
returned its expected failed qualification status. The `next` builtin
regression first failed with the observed `NameError`, then passed after
adding only `next` to the calibration policy's builtin list. The full
pytest branch-coverage gate is tracked separately by the integration owner.

## R3 identity and pilot artifact cross-check

The new R3 identity hashes complete `world.to_dict()` material (including
evaluator-only content, represented only by a digest), the strategy and
Recuris seed, all runtime Python source, `uv.lock`, and budget/API profile
configuration. It recomputes identity at the end. The old corrected
offline-v2 and researcher-pilot-v2 artifacts predate this feature and do
not contain a `run_identity`; a fresh numbered run is required for artifact
evidence. Both Siflow profiles currently have `provider_revision: null`,
so the identity fixes the model ID/profile but cannot prove the service's
weight revision.

The researcher-pilot-v2 artifact itself declares a 24,576 researcher output
token cap. Its two reported completion counts (24,576 and 18,883) are
within that cap. Its outcomes are `truncated` and `runtime-failed`, hence
0/2 valid updates. The second draw logged 11 worker requests with provider
usage, including seven `finish_reason=length` responses; its primary
`runtime-failed` label reflects the `next` NameError, and the response
details retain the additional truncation signal. The v3 pilot uses a
different declared cap and needs its own artifact-level check.
