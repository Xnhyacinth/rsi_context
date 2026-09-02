# hy3-ioa run ledger

hy3-ioa is an unversioned API alias. It may be a **researcher** or a **labelled
replication reader**. It is not the paper's frozen open-weight reader (pinned
Qwen3.6-27B). Do not pool hy3 curves with local Qwen.

## What hy3 actually did

| Run | Task | Rounds | Policy change | Score / gain | Claim |
| --- | ---- | -----: | ------------- | ------------ | ----- |
| Provider canary 2026-08-29 | 1 public sentence: "What is the canary code?" evidence "amber" | 0 | none | `amber` / `amber.` drift | connectivity only |
| Dual-role researcher v4 | homemade 32K, 2 visible items (sparse hop + dense values) | **1 valid** after 2 invalid slots | rewrote `policy.py` to query-overlap lexical packing | H0 **0.0** → H1 **0.0**, `discovery_gain=0`; sparse gold recall 0.5→1.0, dense 1.0→0.875 | adapter qualification; answers stayed `INSUFFICIENT` |
| Locked PopQA pre-canary 2026-08-30 | canary only, 5× T=0 seed 42 | 0 | none | answer/usage not frozen | **stopped**; no researcher |
| PopQA operational replay | 40 unique PopQA k1000, lexical pack → 8K | 0 | fixed `LexicalPolicy` | 0.600 ×5 | replication, not RSI |
| Paired signal diagnostic | same 40 items, lexical vs head, 3 interleaved reps | 0 | **fixed two policies**, no researcher | lexical 0.600 vs head 0.325, Δ **+0.275** | diagnostic **fail** for item-level researcher feedback (bootstrap lower 0.125 < 0.165) |
| Open-S H0 canary 2026-09-01 | 1 canary item through `seeds/open_s_v1` | 0 | none (H0 only) | 1.0 `amber` | seed+reader path; not discovery |
| PopQA frozen landscape 2026-09-01 | 16 unseen unique k1000 (offset 40), 8K pack, 64 output | 0 | frozen: open-S H0 / head / head-tail / hand-hybrid | 0.500 / 0.3125 / 0.375 / 0.625 | landscape only; not researcher advantage |
| Open-S dual-role visible 2026-09-01 | 8 further unseen items (offset 56), 2 rounds, **8K pack** | 1 valid, 1 invalid | r0 byte-identical H0; r1 process exit 1 | H0 0.375, peak 0.375, `discovery_gain=0` | qualification_only; no advantage claim; **do not rerun** |
| Open-S window-envelope visible | 8 unseen items (offset 64), 5 rounds, pack 128960 | 0; H0 aborted | none | `ReaderProtocolError` usage above model length after 4 reader calls | keep `results/open-s-hy3-popqa-window-20260901/`; do not overwrite |
| Open-S window-envelope visible-b | 8 unseen items (offset 64), 5 rounds, pack 114624 | **5 valid** | each round rewrote `policy/policy.py` (lexical/title/entity rank) | H0 **0.375**, scores 0.375/0.375/**0.25**/0.375/0.375, `discovery_gain=0` | qualification_only; no advantage; 48 reader calls, 5.68M input tokens |
| Open-S autonomous explore | 8 unseen items (offset 72), 5 rounds, pack 114624 | **0 valid** | each round rewrote `policy.py`; all TypeError on `retrieve_by_query(..., top_k=)` | H0 **0.500**, round scores recorded 0/0/0/0/0, `discovery_gain=0` | qualification_only; 8 reader calls (H0 only); keep `results/open-s-hy3-popqa-explore-20260901/`; do not overwrite |
| Open-S autonomous explore-b | 8 unseen items (offset 80), 5 rounds, pack 114624 | **4 valid**, r4 process exit 1 | r0–r3 rewrote `policy.py`; r4 missing | H0 **0.500**, scores 0.5/0.5/0.5/0.5/invalid, `discovery_gain=0` | qualification_only; 40 reader calls, 4.66M input tokens; keep `results/open-s-hy3-popqa-explore-b-20260901/`; do not overwrite |
| Open-S autonomous explore-c | 8 unseen items (offset 88), 5 rounds, pack 114624 | **4 valid**; r0 invalid manifest | r1–r4 rewrote `policy.py` | H0 **0.500**, scores invalid/0.5/0.5/0.5/0.5, `discovery_gain=0` | qualification_only; 40 reader calls, 4.67M input tokens; r0 diagnostic `APIResearcherError: API researcher manifest is invalid`; keep `results/open-s-hy3-popqa-explore-c-20260901/`; do not overwrite |
| Open-S autonomous fresh (post-fix) | 8 unseen items (offset 96), 5 rounds, pack 114624 | **4 valid**; r0 invalid manifest | r1 retrieval-ranked; r2 hybrid rank+source-order fill; r3 shard merge; r4 density reorder | H0 **0.500**, scores invalid/0.625/0.625/0.625/0.5, `discovery_gain=0.125` | qualification_only; 40 reader calls, 4.65M input tokens; keep `results/open-s-hy3-popqa-fresh-20260901/`; do not overwrite; **not** a researcher-advantage claim |
| Open-S selection-blind 8K | 8 unseen items (offset 104), 5 rounds, pack **8192**, `selection-blind` | **4 valid**; r3 invalid promotion.decision | 4 independent from-seed overlap compilers | H0 **0.375**, scores 0.75/0.75/0.75/invalid/0.75, `discovery_gain=0.375` | qualification_only; 40 reader calls, 0.34M input tokens; parents all seed; no gold in prompt; keep `results/open-s-hy3-popqa-blind-8k-20260901/`; do not overwrite; **not** an iteration claim |
| LME-V2 small pack 2026-09-01 | 422 text-only, 8K last-k/lexical/random, 0 reader | 0 | frozen packers | det.294: 0.112 / 0.408 / 0.361; weak.128: 0 | answer-string presence, not official score |

The selection-blind 8K cell is an **open-loop sampling** record: four independent
seed restarts all reached 0.75 by query-overlap ranking. That saturates this
8-item panel for sampling. A matched `normal` arm on offset 104 is required
before claiming that score feedback adds anything. Window-envelope offset 96
remains a separate, looser envelope.

Explore-c (offset 88) recovered after one invalid manifest and tied
source-order H0 at 0.500. The post-fix fresh cell (offset 96) is the first
hy3 open-S panel with `discovery_gain>0` (peak 0.625 vs H0 0.500). That is a
qualification-only 8-item visible score, not a matched-control researcher
advantage. Dual-role v4 remains the first scored researcher rewrite on
homemade items (`discovery_gain=0`).

## Dual-role v4 in one paragraph

Researcher and reader shared the `hy3-ioa` alias with different prompts, output
caps, and call ledgers. Three researcher attempts: two failed at runtime
(invalid `ContextPack` construction); the third produced a valid lexical
overlap packer. Score remained 0 on both items. Post-canary still alternated
`amber`/`amber.`. Keep v1–v3 under `artifacts/_superseded/hy3-researcher/` as
the invalid-slot record; v4 is the scorable artifact.
