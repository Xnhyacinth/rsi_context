# Local artifact inventory

This file is the on-disk map. Locked experiment records were not deleted.
Superseded intermediates were moved, not overwritten.

## Keep in place (locked or current)

| Location | What it is | Do not treat as |
| -------- | ---------- | --------------- |
| `results/autonomous-dynamic/codex-sol-local-qwen-visible-popqa-k1000-20260818-0{1,2,3}` | Visible PopQA analog; `-01` invalid H, `-02` H0 0.625 r0 0.75 then Codex abort, `-03` quota | Discovery / A2 |
| `results/autonomous-dynamic/hy3-locked-popqa-20260830/pre-canary.json` | hy3 locked-gate stop: 5 canary calls, no researcher | Frozen reader |
| `results/hy3-paired-signal-cf19dff-20260831/` | 40-item lexical vs head diagnostic | Researcher discovery |
| `results/hy3-popqa-replay-e23f845-20260831/` | Lexical replay 0.600 ×5 | Discovery |
| `results/hy3-popqa-frozen-open-s-20260901/` | 16-item frozen open-S/head/hybrid landscape | Researcher advantage / official HELMET |
| `docs/open-s-visible-scenario.md` | Frozen live open-S PopQA window cell | 8K HELMET instrument / A2 |
| `results/open-s-hy3-popqa-visible-20260901/` | Dual-role open-S 8K campaign, discovery_gain=0 | Researcher advantage |
| `results/lme-v2-small-pack-20260901/` | Zero-reader last-k/lexical/random pack rates | Official LongMemEval / researcher |
| `artifacts/hy3_api_researcher_qualification_v4_20260829/` | Valid hy3 researcher slot; H0=H1=0 | Advantage |
| `artifacts/hy3_reader_{pre,post}_rsi_canary_20260829.json` | Dual-role canaries | Freeze proof |
| `artifacts/public-t0/*-v4*` and PopQA/RULER screens | Current public-T0 cells | Official HELMET |
| `artifacts/hard-baseline-gate`, `hard-causal-gate` | Repair A/B/C landscapes | A2 pass |
| `artifacts/api-*`, `local-dynamic-gate`, `p2-offline` | Earlier API/local qualification | Paper A2 |

## Moved to `artifacts/_superseded/` (redundant intermediates)

| Path | Why superseded |
| ---- | -------------- |
| `hy3-researcher/v1` | Launcher/import failure before a scorable H |
| `hy3-researcher/v2` | Runtime-invalid policy; `failure.json` |
| `hy3-researcher/v3` | Runtime-invalid policy; zero candidate reader calls |
| `musique-offline/*` except current v4 | Docs record v1/v2/v3 as diagnostic; v4 reproduced the numbers on a clean commit |

Do not pool these directories, do not overwrite Repair A/B/C or PopQA `-01/-02/-03`.

## Deleted (regenerable caches)

`.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.coverage`, `src|tests|scripts/**/__pycache__`.
