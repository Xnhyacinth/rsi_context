# Findings

- The completed API policy pilot is a prescribed-policy qualification, not
  researcher discovery.
- Single-needle 8K/32K is saturated and should remain a replay/null calibration.
- The next decisive evidence is a dynamic 32K panel where different task families
  reward different selection/compression/verification mechanisms.
- `hy3-ioa` is suitable for public API replication and pilots but exposes no
  immutable revision; pinned open weights remain the paper reproducibility anchor.
- Formal gate/sealed evaluation still requires process or worker isolation.
- The unversioned remote reader is not a valid noise-floor anchor: a `0 -> 0.25 -> 0`
  trajectory collapsed under replay to candidate mean 0.05 with standard deviation 0.10.
- Pinned local Qwen non-thinking decoding gave zero observed score and item-output variance.
  On corrected-protocol autonomous run `-04`, H0/round-0/round-1 scored
  0.25/0.00/0.50; round-0 and round-1 replayed exactly five times each.
- The successful policy did not merely retrieve more evidence. It replaced broad expansion
  with a governing-statement filter, query-entity binding, bounded one-hop traversal, and
  evidence ordering; reader input fell from about 35.7K to 28.5K tokens.
- Discovery and reliability co-exist in one trajectory: round 0 regressed below H0, while
  round 1 recovered and exceeded it. Historical-best preserves the result but does not make
  the researcher process monotonic.
- Manifest calibration was poor even when discovery succeeded: round-0/round-1 Brier scores
  were 1.5717/1.2972 and ECE 0.8725/0.6525 on four visible items.
- Full context is not an oracle on the dynamic task: with 100% gold recall it scored 0.50,
  while head-8K scored 0.75 at 56.25% mean gold recall on the fixed panel.
- Target-tokenized hard-panel calibration falsified the old length assumption: nominal
  32,768 semantic words were 53,517--53,720 Qwen tokens. The qualification runner now
  replaces chunk declarations with evaluator-owned tokenizer counts and enforces a true
  8,192-token policy pack, but the generator itself still needs native 32K calibration.
- On the disposable hard panel, head/head-tail/lexical scored 0.250/0.375/0.875;
  no-context scored 0; gold-only/bounded-oracle/full-context each scored 0.875.
  Compositional retrieval is lexically saturated (1.0), while dense comparison remains
  0.75 with complete evidence. The former is a search-task failure and the latter a
  reader/task-formulation floor, so neither profile is currently valid A2 fitness.
- The measured dynamic range proves that context composition can change a frozen reader's
  score beyond local replay noise. It does not yet prove researcher discovery beyond matched
  search, transfer to hidden grammar, or long-horizon improvement.
- Runtime and namespace preflight cannot prove confidentiality of the untrusted policy
  worker. Formal eligibility is fail-closed until the scored launcher binds the actual
  worker, hidden mounts, endpoint-serving process, model bytes, and pre/post runtime state.
- A finite random/sequential search is not matched to arbitrary researcher-written Python.
  A2 primary must restrict all controllers to the same canonical `PolicySpecV1`; open Python
  is a separate operator-invention arm. Otherwise a researcher win is confounded by a larger
  hypothesis space.
- Hard v3 generated 32,730--32,750 target tokens natively. Compositional now has the desired
  fixed-policy range and a perfect complete-evidence oracle, but dense comparison scores 0
  under gold-only and bounded-oracle and 0.25 under full context. The next task repair is a
  reader/task formulation change, not additional retrieval or filler.
- Hard v3b replaced dense arithmetic with a seven-evidence authority comparison. On pinned
  Qwen, head/head-tail/lexical scored 0.25/0.50/0.375 overall; no-context scored 0 and
  gold-only/bounded-oracle/full-context each scored 1.0 on both profiles. The reader/task
  floor is repaired and the strongest fixed policies disagree on 3/8 items, but causal,
  counterfactual, replay, stratum, runner, and isolation gates remain open.
- The initial 10-key `PolicySpecV1` collapses to five behavior classes on equal-size hard
  chunks because STOP and SKIP are equivalent. It is a valid scaffold, not an A2 grammar;
  A2 requires at least 20 frozen-panel behavior classes with graph expansion and coverage/
  diversity allocation.
- After correcting the analysis unit, the revised 32-config `PolicySpecV1` has 32
  compositional and 22 dense behavior classes on the repaired panel with the pinned Qwen
  tokenizer. This clears structural non-degeneracy per profile; it does not clear the pending
  real-reader saturation screen across the full grammar.
- Random-5 and fixed sequential search are insufficient controls when the researcher sees
  visible gold evidence and can enumerate the public finite grammar offline. A gold-aware
  exhaustive evidence-recall selector is required as an additional strong non-agent control.
- Dataset fingerprints must bind query text and each chunk's token count, not only chunk text
  and aggregate source tokens. The generator now uses a versioned canonical payload that
  binds those scored-task fields; old qualification artifacts remain immutable.
- The full 32-policy reader screen falsified the repaired compositional profile: 11 policies
  score 1.0. Dense remains non-saturated with maximum 0.50. Full/gold-drop/counterfactual are
  1.0/0/1.0 and the strongest policy has zero replay variance, so the blocker is task
  saturation rather than evidence causality or reader noise.
- Split-specific decoy bodies now differ beyond Ledger/CARD/Dispatch wrappers for both
  primary profiles. Hidden transfer remains unmeasured and still requires evaluator-secret
  seeds plus physical isolation.
- This host supports rootless namespaces and read-only binds but lacks Podman/bwrap, a Docker
  daemon, cgroup delegation, and a minimal read-only runtime rootfs. It cannot honestly issue
  formal policy-worker isolation. Gate/sealed scoring must move to a container-enabled worker
  with cgroup-owned cleanup; host execution stays visible qualification only.
- Public related work (2026-08-15): RULER/HELMET/LongBench-v2 evaluate frozen readers;
  LongLLMLingua is a human-designed H; GEPA/DSPy/ACE optimize prompts or playbooks; RE-Bench,
  MLAgentBench, MLE-bench, and RSIBench-Data evaluate coding researchers at training/R&D/data
  loci. No sourced paper jointly does frozen-reader + matched finite context-policy grammar +
  replay/causal/manifest + visible-select/gate-eval.
- v3b compositional saturation mechanism: live chain was three unique-ID hops, exactly
  `GraphHopsV1.TWO` from a BM25 subject seed. Repair A keeps five gold statements and
  isomorphic competing two-hop terminals without `retired` cues; structural tests lock
  hops=0/1 RANK missing C and hops=2 RANK a proper subset. Reader-score gates are still open.
- Design critique follow-up: Repair A is test-locked and was Qwen-screened on a
  new disposable seed. The 32-policy space is unsaturated (compositional max 0.375,
  hops=0 RANK/MMR 0). Difficulty still fails: compositional gold-only 0.75 and
  bounded-oracle 0.375 with gold recall 1.0; full 32K context is 1.0. Next repair
  is 8K complete-evidence solvability, not hops=3 or 128K.
- Protocol review follow-up: RoundFeedback bytes, sequential Hamming-one, gold-aware
  exhaustive, restricted V1, spend caps, and A2 launch refusal are now code. Formal
  `formal_eligible=true` still requires a container-enabled isolation node. Difficulty
  instruments now stamp `passed`/`failed` on the causal gate (schema v2).
- Literature: the _conjunction_ (isolation + matched grammar + replay/causal/manifest) is a
  D&B gap; the pieces are not. Mandatory related work is HELMET/RULER, LongLLMLingua/RECOMP,
  ACE/DSPy/GEPA, RSIBench-Data, LongMemEval-V2. Do not cite rsibench.com.
- The scientific core is not “protocol instead of long-context performance.” It is RSI
  expanding agents so a frozen reader gains LongLLMLingua-style accuracy **and**
  token/latency/cost, with the protocol as the identification layer. Borrowed
  settings: 32K→8K as the 4× cell; T=0; HELMET output contracts; RECOMP-style
  abstention; HELMET RAG/Recall and LME as transfer. Details:
  `.hl/artifacts/borrowed-settings-2026-08-16.md`.
- Repair A gold-only misses were format/procedure, not missing evidence: one middle
  item returned competing folio `fx-c5e722b83072`, one returned `INSUFFICIENT`, both
  at gold recall 1.0. Dense already states aggregation and “return only the exact
  node id”; compositional needed the same contract without BM25 type-word leakage.
- Repair B v2 query (seal-match + return-only-terminal, no `folio`) lifted
  compositional gold-only from 0.75 to 1.0 and bounded-oracle from 0.375 to 0.875
  on the 736-call landscape, with no PolicySpecV1 ≥ 0.90. The remaining A2
  blockers are dense lexical/BM25 saturation on that seed (1.0) and n=2 strata /
  pooled strongest-policy disagreement, not the compositional reader floor.
- Repair C: putting node IDs and accepted scores in the same dense chunk lets
  hops=0 BM25 pack the gold figures because the query lists all six `nd-` IDs.
  Splitting node→dossier bindings from dossier→score records (no `nd-` on score
  chunks, no `ds-` in the query) drops dense lexical/hops=0 RANK from 1.0 to 0
  while gold-only/oracle stay 1.0. hops=1 RANK source then sits at 0.3125.
- n=2 strata cannot satisfy “no position entirely right or wrong” (scores only
  0, 0.5, 1.0). The 16-item landscape makes n=4 per stratum; dense head and
  distributed still score 0 under hops=1/2 RANK source because competing high
  figures enter the pack without the qualification rule. Head truncation scores
  4/4 on those same head items. Do not lower the 0/1 threshold after seeing this.
- The difficulty gate’s top-two disagreement compares the two highest-scoring
  specs. On Repair C dense those are hops=1 and hops=2 RANK source with identical
  item scores, so disagreement is 0 even though RANK vs coverage and hops=0 vs
  hops=1 differ. Changing that rule after seeing the landscape would be
  post-hoc. Compositional bounded-oracle 0.75 on the 16-item seed is fill/
  competing-folio confusion (gold recall 1.0), not a dense-generator regression.
- “Only compress input” is the wrong harness slogan. Long-context RSI here is a
  budgeted compiler `H` (select / hops / RANK|MMR|coverage / order / abstain /
  evaluator notes). Policy-authored free-form summaries are a second reader.
  Real benches transfer a frozen `H`; they do not skip the synthetic gate.
- Wiring note substitution into `PolicySpecV1.assemble` was rejected for this
  slice: default `max_free_text_tokens=0` would no-op, but the interpreter source
  hash would still change and mix identities with Repair C. Keep substitution
  opt-in until a pre-registered canonical key is added after T0.
- “RSI研究日记 / Agent 如何积累经验” maps to the **researcher** outer loop
  (`.hl` trials, failed directions, tests), not to `policy/` playbooks. Promoting
  one successful agent run into unbounded skills inside `H` would turn the
  compiler into a second reader and break matched search. Keep experience
  writeback in `.hl` + topology tests; do not start A2 because a diary exists.
- Bounded-oracle poison was hop-splitting, not only competing `fx-` IDs. Filling
  in source order interleaved haystack between gold hops; the reader then emitted
  the gold folio. Contiguous gold + ID-free pad makes oracle match gold-only.
  Remaining T0 miss is gold-only 0.75 vs full 1.0 on a 16-item seed.
- HELMET `rag_short` 8K uses k50; that set already fits ~6K Qwen tokens, so
  frozen-H packers are a no-op. The 4× cell is k220→8K. Answer-string coverage
  there is retrieval-capped (14/20). Do not report chat exact-match as HELMET NQ.
- Decoy quoting the gold terminal was a real confound but not the remaining
  T0 failure: after the leak fix, full context is still 1.0 while 16-item
  compositional gold-only/oracle is 0.8125 (probe n=8 was 0.875). Do not treat
  an 8-item probe as the difficulty denominator. RSI process value is the `-04`
  H0/r0/r1 curve (0.25/0.00/0.50, selected peak, strategy rewrite), not 8K
  compression. Keep methods, HELMET, and RSI-round scoreboards unpooled.
- Visible Codex `-02` completed five audited rounds on a new seed without
  aborting: scores 0.50 / 0.00 / 0.50 / 0.50 / 0.50 / 0.50, selected H0,
  discovery_gain 0. Two items stayed `INSUFFICIENT` under every candidate.
  Protocol completeness ≠ H improvement. `-01` remains the aborted artifact.
- T0-public offline: RULER NIAH/JSON-KV and KILT RAG cannot be the A2 packing
  landscape (key-in-query saturation or head=lexical). RULER `qa_2` 128K→8K
  passed the pre-registered packing screen on 32 items (head 0.156, lexical
  0.812, disagreement 0.656, binding, answer in source). That is identification
  of a public cell, not a reader T0 pass and not A2. Do not pool it with
  homemade 32K scores or Codex round curves.
- T0-public reader: on that same qa_2 cell the frozen Qwen packer landscape is
  already in band (no-context 0, head 0, lexical 0.56–0.66, disagreement ≥0.56).
  Gold-only stays 0.69 (n=32, supporting-doc gold, span match) to 0.81 (n=16
  bidirectional rescore) < 0.85. The kill is complete-evidence solvability, not
  packing saturation. qa_1 128K→4K hits the lexical ceiling 0.75 with gold-only
  0.69. PI 2026-08-18: do not keep hunting gold-only on qa_2; the task is wrong.
- Realistic packing cell: HELMET PopQA k1000→8K (Wikipedia retrieval, ~111k
  source tokens). Head 0.1875 vs lexical/hybrid 0.625, disagreement 0.5625,
  binding 1.0. NQ/Trivia k1000 head-saturate; Hotpot k1000 lexical-saturates.
  Visible A2 analog uses PopQA, not homemade 32K and not RULER haystacks.
