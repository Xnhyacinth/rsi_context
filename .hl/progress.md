# Progress

## 2026-09-01 autonomous open-S explore

- De-prescribed the method catalog. Prompt now states goal, legal/illegal
  operators, score/token feedback, remaining slots, and frozen library
  signatures. H0 is source-order full-as-fits.
- Offset-72 explore finished: H0 0.500, 5/5 invalid TypeError slots, 8 reader
  calls. Worker had returned only `TypeError`. Locked that artifact. Worker now
  surfaces a one-line exception message.
- Offset-80 explore-b finished: H0 0.500; r0–r3 valid at 0.500; r4 process
  exit 1; `discovery_gain=0`; 40 reader calls. Locked. No mid-run steering.

## 2026-09-01 window-envelope open-S repair

- Dropped pack-8K as the open-S evolution envelope. Full-as-fits, RAG,
  truncation, and hybrid pack share the frozen reader window (hy3: 114624).
  The first window launch failed at pack 128960 (`reader reported usage above
  the model length` on H0 call 4); keep that artifact and relaunch.
- Window-b campaign completed: 5/5 valid rounds, each changed `policy.py`.
  H0 0.375; r0–r1 0.375; r2 0.25; r3–r4 0.375; `discovery_gain=0`. 48 reader
  calls. Qualification only; not researcher advantage.
- Fixed failed self-evolution: identical parent trees are invalid; API
  `policy_source` objects merge onto the parent; Markdown fences are stripped;
  researcher output cap is 32768. Prompt no longer invites a hold copy.
- Frozen the live task in `docs/open-s-visible-scenario.md` (PopQA unique,
  min-rank 200, offset 64, 8 items, 5 rounds). Historical 8K landscape and the
  failed offset-56 campaign stay locked.

## 2026-09-01 hy3 visible open-S analysis

- Reviewed fairness/determinism in `docs/hy3-visible-open-s-preregistration.md`.
  Skipped the locked 40-item diagnostic panel. Verifier is `extractive_span_match`.
  hy3 reader and researcher stay on separate API profiles.
- Frozen landscape (`results/hy3-popqa-frozen-open-s-20260901/`): 16 unseen
  PopQA k1000 items, 64 interleaved reader calls. Scores: open-S H0 0.500,
  head 0.3125, head-tail 0.375, hand-hybrid 0.625. Gold recall 0.4375 / 0 / 0 /
  0.4375. Not official HELMET; `rsi_launch_eligible=false`.
- Dual-role campaign (`results/open-s-hy3-popqa-visible-20260901/`): 8 further
  items, 2 rounds. H0 0.375; r0 resubmitted identical seed (hold); r1 process
  exit 1, no reader calls. `discovery_gain=0`. Do not claim researcher advantage.
- LongMemEval-V2 small pack (`results/lme-v2-small-pack-20260901/`, 0 reader
  calls): 422 text items. Deterministic 294 answer-string rates last-k/lexical/
  random = 0.112 / 0.408 / 0.361. Weak 128 all 0.0. Not official LongMemEval.

## 2026-09-01 open-S harness seed

- Locked a separate open-S track (`open-s-harness-v1`): each trajectory copies a
  byte-identical `seeds/open_s_v1/` tree into an isolated workspace. Restricted
  `policy/seed.py` A2 is unchanged and remains a different leaderboard.
- Auditor now allows sibling modules present in the same tree and submodules of
  allowlisted packages (`rsicontext.policy.open_s`, `collections.abc`). The
  fresh worker appends the audited tree to `sys.path` without stdlib shadowing.
- Frozen operators: retrieve, map_shards, merge_ranked, route_skill,
  record_working_set, pack_spans. H0 wires them with identity sharding.
- Local tests cover digest isolation, H0 fresh-process scoring, campaign
  snapshot, and a hy3 script skip path. No 2×2×2×5 launch.
- hy3-ioa H0 canary (`results/open-s-h0-hy3-20260901/summary.json`): prediction
  `amber`, score 1.0, 67 input / 2 output tokens, `qualification_only`,
  `rsi_launch_eligible=false`. This is not researcher discovery.
- Cleaned regenerable caches and moved superseded hy3 researcher v1–v3 plus
  MuSiQue offline v1–v3 into `artifacts/_superseded/`. Locked cells stayed put.
- Wired `policy_track="open-s"` into the autonomous prompt and allowed API
  researchers to return a multi-file `policy_source` object.

## 2026-08-29 unified local/API reader preparation

- Audited the existing zero-dependency OpenAI-compatible reader, strict API
  profiles, Tencent canary, vLLM serving profiles, runtime attestation, and two
  autonomous visible-pilot scripts.
- Added focused tests first for keyless local vLLM, remote-key fail-closed
  resolution, shared profile reader construction, and explicit API
  observability. The required red state was observed: test collection fails
  because `build_profile_reader` is not implemented yet.
- Implemented the minimum shared runtime seam in `experiment/api.py`, added an
  explicit `api_key_required=false` to the local vLLM profile and generated
  local profiles, and kept Tencent key-required by default.
- Focused verification is green: 24 tests passed; focused Ruff, strict mypy,
  and Bandit passed. The helpers are not exported or wired into scripts yet.
- Bumped the canary schema to v3, added a tested API-profile identity factory,
  exported the runtime helpers, and wired them into `api_canary.py` plus both
  autonomous visible-pilot scripts. The duplicate environment lookup, reader
  construction, and identity assembly were removed.
- Post-wiring focused verification is green: 27 tests passed; Ruff, strict mypy,
  and Bandit passed on all touched Python files.
- Executed a real three-replay `hy3-ioa` canary through the shared runtime path.
  Connectivity/model identity passed, but exact answer and output-usage
  stability failed (`amber.`/3 tokens versus `amber`/2 tokens). Artifact:
  `artifacts/api-canary/hy3-ioa-20260829-provider-preflight.json`. No campaign
  was launched after the failed gate.
- Generated the registered local Qwen serve dry-run successfully; it is TP8/DP1,
  BF16 model/KV, 131072 max length, prefix cache off, seed 42, and wrapped by
  `hold.sh`. A one-call local canary then failed with connection refused because
  no server is currently listening on port 8017. No GPU process was started.
- Registered the three official multi-hop code/evaluation repositories at
  verified immutable commits: MuSiQue, HotpotQA, and 2WikiMultiHopQA. Registry
  tests are green (26 passed), and the acquisition dry-run was reviewed. The
  entries explicitly do not claim checksums for separately hosted data bytes.
- After reviewing the dry-run, cloned all three repositories under organized,
  ignored `data/{musique,hotpotqa,2wikimultihopqa}` directories and checked out
  the registered commits detached. No separately hosted dataset archive was
  downloaded.

## 2026-08-29 Recuris-aligned execution roadmap

- Replaced the stale qualification-run task plan with a gated P0--P7 project
  plan. The immediate unit is offline selection of one real supporting-fact
  multi-hop dataset; no A2 researcher trajectory is authorized yet.
- Added `docs/execution-roadmap.md` with a claim-to-evidence matrix, task and
  baseline roles, resource stages, falsifiable expected patterns, and an
  explicit go/no-go ledger. Numerical expectations are labelled hypotheses.
- Borrowed Recuris's component-scoped patches, arithmetic held-out checks,
  file-based state, and mechanism fingerprint as audit ideas. Its evolving
  memory/checkers and progressive hidden gate remain outside static A2.
- Added a planned evaluator-owned policy activation fingerprint. It records
  whether claimed changes actually affect selection, expansion, allocation,
  order, verification, or abstention; it is attribution evidence, not fitness.
- Clarified that `hy3-ioa` may be a researcher treatment or labelled reader
  replication. It cannot silently replace the primary frozen reader without
  snapshot/runtime attestation, deterministic replay, and fresh task gates.
- Formal A2 remains blocked on both qualified task identities, host spend caps,
  physical evaluator isolation, and endpoint identity attestation.
- Documentation consistency verification: `git diff --check` clean and
  `uv run pytest tests/test_project_assets.py -q` passed (2 tests). No model,
  dataset download, reader call, or formal experiment was launched in this step.

## 2026-08-29 study contract and Recuris boundary

- Added `docs/study-contract.md` as the normative project charter: bounded
  externalized RSI terminology, frozen/editable/evaluator-only surfaces,
  matched allocation versus accounting resources, A0--A5 task ladder, gates,
  and falsifiable paper branches. Formal A2 remains blocked.
- A2 now hashes a 1,800-second hard timeout per researcher turn and a
  72,000-second aggregate ceiling over 40 turns. This is an allocation budget;
  GPU/HBM/KV/runtime remain measured conditions, not semantic-policy knobs.
- Registered and pinned Recuris at commit
  `a0479b27a2d08b7fbf2607acf1841a06b121ee91`; cloned it detached under
  `external/recuris`. It is a long-horizon reference adapter, not a matched
  static-document controller.
- Formal A2 task identities remain unfrozen. At least one must be a real public
  long-document distribution; current PopQA k1000 is only a promising routing
  cell, and the causal multi-hop/global role still needs qualification.

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

## 2026-08-29 provider unification + MuSiQue preparation

- Unified all API-backed qualification, hard-gate, autonomous, and replay entry
  points on one OpenAI-compatible profile resolver/reader factory. Remote
  credentials remain runtime-only; keyless local vLLM is explicit.
- The current `hy3-ioa` three-replay canary reached the provider but failed the
  exact answer/output-usage stability gate (`amber.` vs `amber`). It remains a
  debug/replication reader, not the primary frozen backbone.
- Serving profiles now hash `127.0.0.1:8017`; generated vLLM commands explicitly
  bind loopback/port under `hold.sh wrap`. Formal reader construction and runtime
  attestation reject endpoint drift; local launchers expose no override.
- Pinned official MuSiQue, HotpotQA, and 2Wiki code repositories under ignored
  `data/` paths. Their separate archives were not downloaded because upstream
  manifests provide no content checksums.
- Added a fixture-first strict MuSiQue-Answerable adapter. Policy input is
  label-free; answers, aliases, support paragraphs, and hop decomposition stay
  evaluator-side. No generic evaluator conversion is exposed before the
  official scorer is integrated.
- Review found and fixed four defects: boolean/nonpositive reader output caps,
  unauthenticated all-interface vLLM defaults, lossy MuSiQue alias scoring, and
  endpoint/profile provenance drift. Final independent review has no must-fix
  findings.
- Final gates: 433 tests passed, 84.12% branch coverage; Ruff, strict mypy,
  Bandit `-ll`, and diff check passed. No GPU service or A2 trajectory was run.

## 2026-08-29 private publication + `hy3-ioa` diagnosis started

- Activated the file-based planning and Git workflow runbooks.
- Split work into GitHub privacy/release audit, HF prepared-data audit, and a
  bounded `hy3-ioa` diagnosis. No external repository was created or pushed
  before privacy, provenance, and secret checks.
- Completed the bounded `hy3-ioa` diagnostic: 5-call exact replay plus 6
  length/position calls. The endpoint was stable in this batch and passed every
  512/8K position cell, but exact answer compliance failed on a terminal period
  and the alias remains unversioned. No RSI campaign was started.

## 2026-08-29 private publication checkpoint

- Re-read the repository-local `AGENTS.md`; the three-way isolation boundary,
  registry-only acquisition, local `uv`, and full validation gates remain in
  force for this release.
- GitHub audit confirmed `Xnhyacinth/rsi_context` is private and credentials
  are clean, but `main` is unprotected and raw `results/` paths are not safely
  excluded. Publication will therefore use a private feature branch and an
  allowlisted HF payload rather than `git add -A` or a direct main push.
- Added the first fail-closed HF bootstrap specification and release-builder
  tests. The initial red test was the expected missing module; the implemented
  behavior tests pass 7/7. A focused module-coverage run reached 79.27%, just
  below the 80% gate, so malformed-schema and boundary tests are being added
  before any external publication.
- Added a credential-free `hy3-ioa` diagnostic note and ignore rules for future
  raw results, traces, environment files, and common private-key formats.
- Completed the HF bootstrap builder quality loop: 20 focused tests pass, the
  release module reaches 95.12% branch-aware coverage, and focused Ruff,
  strict mypy, and Bandit checks are clean. The extra cases cover malformed
  schemas, nonempty staging, unsafe/reserved paths, duplicate destinations,
  invalid label declarations, and unreadable inputs.
- Independent review blocked publication on provenance and partial-output
  risks. Fixed the builder to require an existing `source_revision` equal to a
  clean repository `HEAD`, validate every entry before staging, write the same
  captured bytes that were hashed, and atomically rename a temporary package.
  Added nonexistent/mismatched/dirty-revision tests; 21 focused tests now pass
  with 90.37% branch-aware release-module coverage and clean focused Ruff,
  strict mypy, and Bandit checks.
- Corrected the `hy3-ioa` note: endpoint metadata is retained while credentials
  are not, and the 11-call diagnostic was bounded rather than preregistered.
- The second provenance review identified ignored and `assume-unchanged` files
  as clean-status bypasses. The builder now loads the committed blob for the
  spec and every payload with `git cat-file` and requires byte identity with
  the captured release input. Regression tests cover both bypasses plus atomic
  rename cleanup. Focused status: 23 tests, 91.67% branch-aware coverage, and
  clean Ruff, strict mypy, and Bandit.
- The first post-builder repository-wide gate completed before this final
  provenance tightening: 454 tests passed in 311.67 seconds with 84.24%
  branch-aware coverage. A final static gate and a targeted/full regression
  rerun are still required after the last fix.
- Final post-review gates passed: 456 repository tests with 84.28%
  branch-aware coverage in 321.05 seconds; repository-wide Ruff; strict mypy
  across 150 source files; Bandit medium/high scan; and `git diff --check`.
  The final independent release review reports no remaining must-fix issue.
- Published four reviewed commits to the private GitHub feature branch
  `prep/context-foundations-20260829`; the HF package source revision is
  `985502664a4457146b928581ee96ba7fff89f118`.
- Created the private HF dataset repository
  `Xnhyacinth/rsibench-context-prepared-visible` and uploaded the validated
  schema-smoke package at revision
  `6c384b2c209f79201a8b3ff9c54bbda2a339c62c`. Authenticated post-upload checks
  confirmed `private=true`, the exact five-file allowlist including Hub
  `.gitattributes`, and byte identity of the remote and local manifests.

## 2026-08-29 `hy3-ioa` dual-role qualification

- Added a stateless API researcher worker, separate 8192-output profile, strict
  policy/manifest parser, parent-policy delivery, and API support in both
  autonomous visible scripts.
- Preserved the virtual-environment launcher path after a local pre-API failure
  and added evaluator preflight so runtime-invalid candidates consume a slot
  while making zero reader calls.
- Used exactly three researcher API calls. Two candidates were runtime invalid;
  the third was valid and scored H0 0.0, H1 0.0. No A2/A3 run started.
- Post-canary punctuation/usage drift invalidated strict operational-freeze
  evidence. See `docs/hy3-dual-role-initial-results-2026-08-29.md`.
- Final repository gates pass: 468 tests, 84.04% branch coverage, repository
  Ruff, strict mypy over 152 files, Bandit medium/high, and diff check. A
  credential-value scan found zero API-key matches; endpoint URL matches are
  expected profile/test metadata.
- Risk-first code review found no must-fix boundary or credential issue. The
  residual risks are the unversioned provider alias, non-formal short-answer
  hardcoding defense in the open-Python arm, and absent physical gate
  isolation; each keeps the result qualification-only.
