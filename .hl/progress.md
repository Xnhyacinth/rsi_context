# Progress

## 2026-08-18 unique PopQA `-03` finished with zero researcher turns

- Same fingerprint as `-02`. H0 0.625 (8 reader calls). All five Codex turns
  exited status 1 in ~3s with no manifest (`missing-submission-r0`…`r4`).
  Selected remains H0. `cost_accounting_complete=false`.
- Cause: Codex ChatGPT usage limit until **2026-08-21 06:16**. stdout 457 B
  JSON `turn.failed`. This is not a packing or reader score of 0.
- `-02` r0 0.75 is still the only successful researcher turn on this panel.
- Do not relaunch until quota resets. `-01`/`-02`/`-03` kept. Formal A2 refused.

## 2026-08-18 unique PopQA `-02` aborted at researcher r1

- Cell `helmet-rag-popqa-k1000-to-8k`, unique queries, gold rank ≥200, 8 items,
  fingerprint `ef16541bbda4a6101ec15af6fb5701ac9efd183bc46385ebfa980e9ab1839e96`.
- H0 lexical 0.625 (8 calls). Round 0 Codex succeeded: Killjoy 0→1, score 0.75.
  Round 1 Codex exited status 1 in 3.48s with no `manifest.json`. Campaign aborted.
- Artifact kept: `results/autonomous-dynamic/codex-sol-local-qwen-visible-popqa-k1000-20260818-02`.
- Fix: researcher process abort now consumes an invalid slot (no reader call).
  `-03` is the continuation in a new directory; `-01`/`-02` untouched.
  `qualification_only=true`. Formal A2 still refused.

## 2026-08-18 PI: realistic public A2 analog; gold-only diagnostic only

- Homemade 32K and RULER qa_2 (SQuAD/Hotpot needles in Paul Graham essays) are
  the wrong A2 task. Gold-only ≥0.85 is no longer an A2 launch kill; it stays a
  diagnostic on extractive cells. Formal `launch_a2_pilot` is still refused
  (no physical isolation). Visible qualification A2 analog is authorized.
- Offline packing kills unchanged. HELMET RAG k1000 screen
  (`artifacts/public-t0/offline-screen-v3-k1000.json`, n=16, 0 reader calls):
  **passed** `helmet-rag-popqa-k1000-to-8k` (median source 111046 Qwen tokens,
  pack 8192, head 0.1875 / lexical 0.625 / hybrid 0.625, disagreement 0.5625,
  gold from `has_answer`). Hotpot/NQ/Trivia k1000 failed because a non-oracle
  packer already places gold on ≥90% (lexical 1.0 on Hotpot; head 1.0 on
  NQ/Trivia). Repair A/B/C untouched. Official HELMET unlabeled.
- Starting visible Codex analog on unique PopQA k1000→8K, gold rank ≥200, 8
  items, 5 rounds, `extractive_span_match`, H0 lexical `policy/seed.py`.
  `-01` aborted: prefix clones plus short-answer hardcoding false positive.
  `-02` is the corrected panel. `qualification_only=true`.

## 2026-08-18 T0-public reader failed gold-only; A2 not started

- Offline T0-public still stands: `helmet-recall-qa2-128k-to-8k`.
- Reader landscapes on pinned Qwen3.6-27B TP8 vLLM 0.25.1, thinking off, T=0,
  seed 42, `contained_match` then `extractive_span_match`. Thresholds unchanged.
- qa_2 128K→8K n=16: no-context 0, head 0, lexical/hybrid 0.5625, gold-only
  0.5625 (answer-substring gold) then 0.625 (supporting-doc gold). Kill: gold-only
  <0.85. Packer band and disagreement already pass.
- qa_2 n=16 rescore with bidirectional span match: gold-only 0.8125, still <0.85
  (yes/no and INSUFFICIENT misses). n=32 span match: gold-only 0.6875, lexical
  0.656, no-context 0, disagreement 0.656. Same kill.
- qa_1 128K→4K n=16: no-context 0, lexical 0.75 (ceiling of the band), gold-only
  0.00 with empty packs then 0.6875 after answer-window gold. Same kill.
- Formal `launch_a2_pilot` still refused. GPU hold restored. Repair A/B/C and
  decoy-noleak landscapes not overwritten. Official HELMET still unlabeled.

## 2026-08-18 T0-public offline passed on RULER qa_2 128K→8K

- Synthetic Repair A/B/C and decoy-noleak landscapes were not overwritten.
  Homemade 32K T0 is still a failed diagnostic, not an A2 pass.
- Offline screen v1 (NIAH / JSON KV / KILT RAG, 10 cells, 32 items, 0 reader
  calls) failed every cell. NIAH lexical ≥0.97; k50 not binding; NQ/Trivia
  head=lexical; Hotpot range 0.09; JSON KV source coverage 0.875 from UUID
  window splits.
- Offline screen v2 (RULER SQuAD-in-haystack): **passed**
  `helmet-recall-qa2-128k-to-8k` (median source 114415 Qwen tokens, pack 8192,
  head 0.156 / lexical 0.812 / hybrid 0.812, disagreement 0.656, answer-in-source
  1.0). Also passed: qa_2 128K→4K, qa_2 256K→8K, qa_1 128K→4K.
- Primary A2-fitness candidate: qa_2 128K→8K. Reader landscape and isolation
  still open. A2 not started. Official HELMET scorer still unwired.
- Records: `artifacts/public-t0/offline-screen-v1.json`,
  `artifacts/public-t0/offline-screen-v2-qa.json`.

## 2026-08-17 visible Codex `-02` completed five rounds

- New dir `codex-sol-local-qwen-visible-rsi-20260817-02`; `-01` untouched.
- Seed `autonomous-dynamic-visible-rsi-20260817-v2`, fingerprint
  `10290749a2527df0902c1d796ec5c62ec01f130d5e88325539733db370d21620`.
- H0 0.50 → r0 0.00 → r1–r4 0.50; all five rounds `valid`; none promoted;
  selected remains H0. 24 reader calls, 212073/79 in/out tokens, ~8.8 min,
  qualification_only. A2 not started.

## 2026-08-17 invalid-H campaign no longer aborts the factorial

- Visible Codex run `codex-sol-local-qwen-visible-rsi-20260817-01` remains an
  aborted artifact (H0 0.50, r0/r1 0.00, r2 0.50, r3 `PolicySecurityError`).
  Re-audit of that r3 tree is now **safe** (`re.compile` is not builtin
  `compile`). Campaign loop consumes an illegal tree-audit as a non-promoting
  slot, keeps the last valid parent, and continues. TOCTOU re-audit still
  fail-closes. A2 not started. Repair A/B/C landscapes not overwritten.

## 2026-08-17 visible RSI 5-round Codex campaign started

- Formal A2 still refused. Visible coding-researcher loop
  `codex-sol-local-qwen-visible-rsi-20260817-01` ran H0 0.50 → r0 0.00 → r1 0.00
  → r2 0.50, then **aborted at r3**: `re.compile` failed `PolicyAuditor`
  (`compile` forbidden). Invalid H currently crashes the campaign instead of
  consuming a slot. Artifact kept; A2 not started.

## 2026-08-17 decoy-fix probe + landscape + RSI process trace

- 8-item compositional probe after decoy no-leak, seed
  `hard-t0-decoy-noleak-visible-probe-v1`, fingerprint
  `1be0e10bdd9967f2ff78feafa69167b1f37b0cb9f674dc8463dd13892f084824`:
  gold-only=oracle=0.875, lexical=0, full=1.0, 56 calls. Kill list passed.
  One gold-only miss was `INSUFFICIENT`.
- 16-item landscape on `hard-t0-decoy-noleak-visible-causal-v1`,
  `artifacts/hard-causal-gate/qwen-t0-decoy-noleak-causal-v1.json`, fingerprint
  `672f4dfda4b61265de0753db5e06d71ef61292acf28a32223d608065ec72cc46`, 1472 calls,
  14.49M in tokens, 444.7s, `$0`. Difficulty **failed**. Compositional
  gold-only/oracle 0.8125 (max policy 0.3125). Dense gold-only/oracle 1.0
  (max 0.375). Strongest-policy disagreement 0. A2 not started. Repair A/B/C
  not overwritten.
- `campaign_process_trace` records H0+round scores, selected vs last, and
  per-round `policy/` diffs. Reconstructed `-04`: 0.25 → 0.00 → 0.50, selected
  r1, BM25 expansion then evidence-chain. Formal A2 still refused.

## 2026-08-17 T0 oracle fill + landscape + unofficial HELMET packs

- Bounded oracle keeps gold hops contiguous and appends identifier-free haystack.
  Competing-ID skip alone still interleaved fill and dropped probe oracle to 0.5.
  Same-seed re-probe after the change: gold-only=oracle=0.875, lexical=0, full=1.0.
  Repair A/B/C JSON not overwritten.
- Clone-aware disagreement is wired into `_assess_difficulty`. Thresholds unchanged.
- Landscape `qwen-t0-idfree-oracle-causal-v1.json`, seed
  `hard-t0-idfree-oracle-visible-causal-v1`, fingerprint
  `c61bd42b58532867d9f4bf4e211a965d08ccefd862b0d18b21794ed5669deb87`, 1472 calls,
  14.49M in tokens, 444.6s, `$0`. Difficulty **failed**. Compositional gold-only
  0.75 (full 32K is 1.0). Dense gold-only/oracle 1.0, max 0.25, clone-aware
  disagree 0.25. A2 not started.
- T2: NQ k50 already fits in 8K. k220→8K fills the budget; answer-in-pack 14/20
  is retrieval-capped. Unofficial reader exact-match is not a HELMET score.

## 2026-08-17 T1 extractive notes + T2 HELMET adapter dry-run

- Dense gold score sentences now emit six evaluator `CompressedNote`s (fingerprint
  schema v3). Notes cite one source chunk, contain `ds-` not `nd-` or the answer.
  `substitute_extractive_notes` may replace packed spans when `max_free_text_tokens > 0`.
  Default landscape budget remains 0; `PolicySpecV1.assemble` is unchanged so Repair C
  interpreter identity and packs stay comparable.
- HELMET registry dry-run recorded; clone **not** executed. Pin
  `af609c4d51b97fc35012099380aa889da961c42d`. Fixture compiler + unofficial
  head/lexical/hand-hybrid packs: `.hl/artifacts/helmet-dry-run-2026-08-17.md`.
- A2 not started. Repair A/B/C landscapes not overwritten.

## 2026-08-17 Repair C dense split + 16-item landscape

- Dense gold is now 13 chunks: qualification rule + 6 node→dossier bindings + 6
  dossier→score records. Query still lists six `nd-` IDs; `ds-`/`dossier` stay
  out of the query. hops=0 RANK packs bindings and misses scores; lexical is
  incomplete at 32K. Topology test:
  `test_dense_repair_c_locks_dossier_split_and_policy_probes`.
- Causal-gate script default is 16 items/profile (4 per stratum). Function
  default stays 4 for unit tests. Do not silently relax the 0/1 stratum rule.
- Cheap dense probe (56 calls, new seed): gold-only/oracle 1.0, lexical 0,
  head 0.25. Kill-list passed.
- Full landscape 1472 calls on `hard-repair-c-visible-causal-disposable-v1`,
  fingerprint `b40c5ae1d5ce2fd7838c38afaba52d5567cff55559abb3285095dc7e16c3e3ea`,
  `$0`. Dense unsaturated (max 0.3125, hops=0/lexical 0). Difficulty still
  failed: compositional oracle 0.75; clone-spec disagreement 0; head/distributed
  strata 0. A2 not started. Repair A/B artifacts not overwritten.
- Record: `artifacts/hard-causal-gate/qwen-repair-c-causal-replay-disposable-v1.json`.

## 2026-08-15 Repair A controllers + P2 lightweight + E1 launch

- Repair A generator is test-locked (topology + PolicySpecV1 probes). Dense unchanged.
- Matched-controller code: Hamming-1 sequential search, gold-aware, RoundFeedback bytes,
  SpendLedger (including `$0`), restricted V1, invalid slots consume budget, A2 launch
  always refuses.
- Causal gate schema v2 now records no-context / gold-only / bounded-oracle and stamps
  `difficulty_assessment`. Script default `items_per_profile=8`. Function default 4 for tests.
- Verification: 334 passed, 84.19% branch coverage; Ruff, strict mypy, Bandit `-ll` clean.
- P2 unofficial LME: 12×2 all packers 4/12; 12×16 full 6/12 vs 8K packers 5/12; `$0`, 0 reader
  calls. Not an official score. Budget note: `.hl/artifacts/p2-budget-2026-08-15.md`.
- Paper contribution note: `docs/paper-contribution.md`.
- A2 not started. v3/v3b artifacts not overwritten.
- GPU: Repair A E1 finished. 736 calls, `$0`. `difficulty_assessment=failed`.
  Compositional gold-only 0.75 / bounded-oracle 0.375 / max policy 0.375; dense
  gold-only/oracle 1.0 / max 0.625. Search-space saturation kill did **not** fire.
  A2 not started. Record: `artifacts/hard-causal-gate/qwen-repair-a-causal-replay-disposable-v1.json`.

## 2026-08-16 Repair B query + related-work settings

- Re-centered the paper object: payoff = long-context accuracy and efficiency via
  RSI-improved `H`; identification = isolation + matched grammar + replay/causal.
  Borrowed LongLLMLingua 4×/T=0/latency-cost, HELMET output-format and RAG yaml,
  RECOMP selective abstention. Note: `.hl/artifacts/borrowed-settings-2026-08-16.md`.
- Repair B query: seal-match + “return only the exact terminal identifier”, without
  `folio` or `vl-`. Putting `folio` in the query made hops=2 RANK recover C on 4/4
  items; “named by that rule” made gold-only 8/8 `INSUFFICIENT`. Topology tests pass.
- Cheap probes then full landscape: v1 query (“named by that rule”) gold-only 0.0;
  v2 query gold-only/oracle 0.875 on the probe seed. Full 736-call landscape on
  `hard-repair-b-visible-causal-disposable-v1` got compositional gold-only 1.0 /
  oracle 0.875 / max policy 0.375, but dense lexical/BM25 hit 1.0. Difficulty
  failed. A2 not started. Record:
  `artifacts/hard-causal-gate/qwen-repair-b-causal-replay-disposable-v1.json`.
