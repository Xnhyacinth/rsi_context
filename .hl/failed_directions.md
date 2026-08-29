# Failed or rejected directions

- Claiming that external context or memory evolution for a frozen model is new
  is rejected after Recuris. RSIBench-Context must remain a researcher benchmark
  with matched search/noise/manifest evidence; a Recuris-like memory method is a
  baseline or transfer arm, not the paper's novelty claim.
- Making a live long-horizon benchmark the primary identification surface is
  rejected. Environment stochasticity and matched-retry effects weaken
  attribution; use static long documents first, then frozen-policy offline and
  live transfer.

- Low-entropy repeated-word 32K canaries produced misleading failures; retained only
  as a test-construction lesson.
- Extending the saturated single-needle profile directly to 128K/256K is rejected as
  the next main experiment; increase evidence topology difficulty first.
- Joint semantic policy, KV, scheduler, and cache optimization is rejected for the
  primary benchmark because it destroys causal attribution.
- Remote `hy3-ioa` is rejected as the primary replay/noise anchor after identical-candidate
  scores varied; it remains a replication/transfer reader.
- Qwen3.6 default thinking mode is rejected for short-answer evaluation: even a trivial
  canary consumed 437 completion tokens, and 32K tasks hit the 512-token cap.
- Treating whitespace words as target-model tokens is rejected. In the hard v2 generator,
  nominal 32,768 words measured 53,517--53,720 Qwen tokens; 128K/256K expansion must be
  calibrated with the pinned tokenizer and final rendered prompt rather than scaled filler.
- The hard v2 compositional profile is rejected as A2 fitness because lexical selection
  scored 1.0. The dense profile is rejected because gold-only, bounded-oracle, lexical, and
  full-context all stopped at 0.75. Adding more filler would repair neither failure.
- Declaration-only namespace/runtime preflight is rejected as a formal isolation proof.
  Formal eligibility must come from the scored launcher for the actual untrusted policy
  worker, with hidden-data and live-endpoint bindings.
- Hard v3 dense global comparison is rejected in its current wording: Qwen scored 0 with
  gold-only and bounded-oracle evidence. Retrieval-policy search cannot repair a task the
  frozen reader cannot solve from complete evidence. The immutable failure remains recorded;
  v3b replaces it rather than overwriting it.
- The first 10-key `PolicySpecV1` is rejected as the formal A2 common grammar. STOP/SKIP are
  identical on equal 512-token chunks, leaving only five behavior classes for five rounds,
  and the space lacks graph expansion and dense coverage allocation.
- Hard v3b compositional is rejected after screening the complete 32-policy grammar: 11
  policies score 1.0 even though simple lexical scores 0. It is not enough to make one static
  baseline non-saturated; difficulty must hold over the actual researcher/search space.
- A three-link unique rare-ID chain is rejected as compositional topology because it is
  isomorphic to `PolicySpecV1` two-hop graph expansion from a BM25 subject seed. Lengthening
  filler or moving to 128K would not repair that isomorphism.
- A five-hop live chain with competing three-hop **retired** paths is rejected as the
  compositional repair. Local status cues keep competitors out of the two-hop cut, and
  hops=0 MMR can still pack the gold terminal against cyclic filler. Repair A uses
  string-isomorphic competing terminals without status labels instead of adding hops=3.
- Treating Repair A as A2-ready after topology tests alone is rejected. The 2026-08-15
  Qwen screen unsaturated the grammar but missed gold-only 0.85 and bounded-oracle 0.80
  on compositional items even with gold recall 1.0. Do not start A2 from that seed.
- Putting `folio` (or `vl-`) into the compositional query to ban folio answers is
  rejected: hops=2 RANK then recovered gold C on 4/4 probe items, the same BM25
  leak that forbade `vl` after Repair A. Output-contract wording must not name
  folio/vl identifiers.
- Asking for “the terminal identifier named by that rule” is rejected. The rule
  statement names a junction/registrar, so pinned Qwen returned `INSUFFICIENT`
  on 8/8 gold-only items (recall 1.0) while full 32K stayed 1.0. Record:
  `artifacts/hard-baseline-gate/qwen-repair-b-query-contract-probe-v1.json`.
- Keeping dense node IDs and accepted scores in one chunk is rejected: the query
  lists all six `nd-` IDs, so hops=0 RANK/lexical can pack every gold figure
  (Repair B landscape max 1.0 on that seed). Repair C splits them.
- Treating n=2 strata as a difficulty pass by relaxing the 0/1 threshold after
  seeing scores is rejected. Use ≥4 items per position (16 items/profile) and
  keep the pre-registered rule.
- Comparing hops=1 RANK source with hops=2 RANK source as “two strongest
  policies” does not measure disagreement on this dense graph: they packed the
  same 8K sets. That is a failed identification check, not permission to pick
  friendlier spec pairs after the fact.
- Treating “only compress the input” as the RSI object is rejected. The editable
  object is compiler `H` (select/hops/allocate/order/abstain/evaluator notes).
  Policy-authored unbound summaries, tools, KV joint opt, and answering are out.
- Cloning HELMET or scoring official RAG/Recall before reviewing the dry-run plan
  is rejected. Pin `af609c4d51b97fc35012099380aa889da961c42d`; adapter fixtures
  are not public-bench results.
- Wiring `substitute_extractive_notes` into `PolicySpecV1.assemble` in this slice
  is rejected: it would change the interpreter hash while default packs stay
  identical at `max_free_text_tokens=0`. Keep substitution opt-in until T0.
- Attributing full=1.0 vs gold-only=0.75 only to the decoy naming the answer is
  rejected as a sufficient T0 repair. After quoting a distractor `vl-`, full
  stays 1.0 and n=16 gold-only is 0.8125. Do not start A2 from an 8-item probe.
- Pooling PolicySpecV1 method scores, unofficial HELMET exact-match, and the
  Codex `-04` RSI curve onto one table is rejected. They are three scoreboards.
- Treating `re.compile` as builtin `compile` in `PolicyAuditor.visit_Call` is
  rejected. Forbid the unqualified call and aliases; keep `re.compile` inside
  functions. Do not abort a bounded RSI factorial when H is illegal: consume the
  slot, keep the last valid parent, and continue. TOCTOU after a safe tree audit
  remains a campaign abort, not an invalid-H slot.
- Treating RULER NIAH or JSON KV as A2 fitness is rejected: the query contains
  the lookup key, so lexical/hand-hybrid already place the answer on ≥90% of
  items at 32K and 128K. Changing pack size to 32K does not unsaturate them.
- HELMET `rag_short` k50 and KILT NQ/Trivia k220 are rejected as packing-T0
  cells: k50 is not binding, and on answerable NQ items head already matches
  lexical (disagreement 0). Hotpot k220 range is 0.09. Do not drop the 0.90
  saturation kill or the 0.20 disagreement kill to force a pass.
- LongBench-v2 multiple-choice is rejected as an extractive packing screen:
  the gold letter is not a source span (choice text in context on 18/300 QA
  items). Keep it for later reader transfer.
- Completing a five-round visible Codex factorial is not discovery. `-02` kept
  H0 at 0.50; r0 regressed to 0.00 and r1–r4 tied H0, so historical-best never
  promoted. The protocol fix is confirmed; the 4-item visible panel still did
  not yield a better compiler than lexical H0. Do not start A2 from this curve.
- Treating RULER qa_2/qa_1 gold-only as answer-substring windows is rejected:
  `yes`/`no`/`France`/`9th century` match the haystack, so the oracle pack is
  not the supporting documents. Supporting-doc gold plus span match still left
  gold-only at 0.69–0.81 < 0.85. Do not start A2 from qa_2 by dropping that
  kill; the PI 2026-08-18 decision was to abandon qa_2 as the task, not to
  relabel it as passed.
- Starting A2 from an offline-only T0-public pass **on RULER qa_2** is
  rejected. That cell is the wrong task (needle-in-essay). A2 fitness moved to
  a realistic public RAG cell that still has to pass packing binding and
  unsaturated kills.
- HELMET RAG NQ/Trivia k1000 is rejected as packing fitness: head already
  places gold on 100% of the 16-item prefix (ranked retrieval prefix ≈ 8K).
  Hotpot k1000 is rejected because lexical/hand-hybrid already place gold on
  100%. Do not shuffle ranked `ctxs` to manufacture disagreement.
- Using the first N lines of HELMET `*_k1000_dep6.jsonl` as a visible panel is
  rejected: each question is cloned at gold ranks 0/200/400/600/800/999. The
  first 8 PopQA lines were two questions. Sample unique queries with planted
  gold off the retrieval head (`min_gold_rank=200`). Do not shuffle `ctxs`.
- Treating a short PopQA answer such as `poet` as a hardcoded lookup because it
  appears in a general occupation cue list is rejected. Hardcoding still forbids
  item ids, queries, chunk ids, and long reference strings.
- Aborting a bounded RSI factorial when the researcher CLI exits nonzero is
  rejected. Consume the slot like illegal H: keep the last valid parent, skip
  the frozen reader, and continue. `-02` H0 0.625 / r0 0.75 then Codex r1 exit 1
  in 3.5s with no manifest is a process failure, not a packing or reader result.
- Reporting `-03` round_scores 0/0/0/0/0 as researcher discovery is rejected.
  All five turns were Codex usage-limit errors (retry after 2026-08-21 06:16)
  with no H submitted. Quota failure is an incomplete experiment, not five
  invalid compilers. Do not relaunch until quota resets.
