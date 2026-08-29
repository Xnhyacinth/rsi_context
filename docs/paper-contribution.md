# Paper contribution: RSI for long-context performance and efficiency

RSIBench-Context asks whether a coding researcher can expand an agent's
capability at one frozen locus — the source-to-context compiler `H` — so a
frozen reader gets **better long-context benchmark accuracy at lower token,
latency, and dollar cost**. That is the same payoff LongLLMLingua claimed for a
human-designed compressor. The NeurIPS D&B object is the protocol that makes
that payoff **identifiable**.

The editable object is `H`: source artifact + query → 8K `ContextPack`. Reader
weights, decoding, prompt, evaluator, and labels stay frozen. Policy code must
not answer, serve, decode, score, or see labels.

The normative research question, terminology, resource budget, task ladder,
and post-Recuris novelty boundary are defined in
[`study-contract.md`](study-contract.md). This is bounded externalized
self-improvement of `H`, not strict self-modification of the researcher.

## Payoff vs identification

| Layer          | Question                                                                                                              | Evidence                                                                                       |
| -------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Payoff         | Does a better `H` raise frozen-reader accuracy while cutting tokens/latency/cost on long-context benches?             | qualified long-source→8K landscape, then HELMET RAG/Recall, LongBench, RULER, LongMemEval-V2   |
| Identification | Did a coding researcher discover that `H`, or was it matched search / a published compressor / label leakage / noise? | Three-way isolation, finite `PolicySpecV1`, replay/causal/manifest, visible-select / gate-eval |

Skipping identification and “just beating HELMET” collapses into a crowded
compressor-methods paper. Skipping the payoff and reporting only protocol
diagnostics will not convince a D&B reviewer that agents matter for long
context. Both layers are required. Transfer benches are not a substitute for a
non-saturated, complete-evidence-solvable fitness landscape.

## Claim the paper can support

The contribution is the **conjunction**:

1. three-way isolation (researcher / editable policy / frozen reader-evaluator);
2. a finite matched `PolicySpecV1` grammar shared by researchers and non-agent
   search, with gold-aware exhaustive recall reported separately;
3. replay, gold-drop, counterfactual following, and item-level manifests;
4. visible-select / isolated-gate evaluation so gate outcomes never train the
   next candidate;
5. first-class efficiency columns (pack tokens, reader tokens, wall seconds,
   later API $) on every landscape, following LongLLMLingua.

Closest prior art covers the pieces, not the conjunction:

| Lineage                       | What it evaluates                 | What it does not freeze                         |
| ----------------------------- | --------------------------------- | ----------------------------------------------- |
| RULER, HELMET, LongBench-v2   | frozen readers on long inputs     | researcher process; matched policy grammar      |
| LongLLMLingua, RECOMP         | human-designed compressors `H`    | researcher discovery vs matched search          |
| GEPA, DSPy, ACE               | prompt/playbook optimization      | frozen reader + causal/replay protocol          |
| Recuris                       | external memory-control evolution | multi-researcher matched-search/noise benchmark |
| RSIBench-Data, PostTrainBench | coding researchers                | inference-time information interface            |

Settings copied from those papers (4× budget, T=0, HELMET output contracts,
RECOMP selective abstention, HELMET RAG transfer) live in
`.hl/artifacts/borrowed-settings-2026-08-16.md`. Do not cite rsibench.com. Do
not claim a new SOTA compressor, the first evolving context/memory system,
strict RSI, or sealed isolation on this host.

## Evidence currently in hand

- Toy and local-Qwen autonomous qualification show discovery and regression
  beyond a zero observed replay-noise floor on a small visible panel. Reader
  input fell from about 35.7K to 28.5K tokens on the winning round — an
  efficiency movement, not only an accuracy movement.
- v3b dense comparison is complete-evidence solvable; compositional v3b
  saturates 11/32 policies at 1.0. That screen is immutable. A2 did not start.
- Repair A unsaturated the 32-policy grammar on pinned Qwen (736 calls, $0,
  fingerprint `a3b319550c8c6673409082263983710436198ad07413c5341c02c43820a9dabe`)
  but failed difficulty: compositional gold-only 0.75 and bounded-oracle 0.375
  with gold recall 1.0. Two gold-only misses were a competing folio `fx-` and
  `INSUFFICIENT`. Dense gold-only/oracle remain 1.0. Do not overwrite that
  artifact.
- Repair B (seal-match query, no `folio`/`vl-`) repaired the compositional
  complete-evidence floor on a new seed: gold-only 1.0, bounded-oracle 0.875,
  max PolicySpecV1 0.375, hops=0 RANK 0. 736 calls, $0, fingerprint
  `740a1b6f77c38e3050a92f8c7d329f5342c6724b4f4ccabb58e390aa2bf6edb0`. Difficulty
  still failed: dense lexical/BM25 hit 1.0 on that seed, and n=2 strata plus
  pooled strongest-policy disagreement are 0. A2 stays stopped.
- Repair C (node/score split; 16 items/profile) unsaturated dense: lexical and
  hops=0 RANK 0, gold-only/oracle 1.0, max 0.3125. 1472 calls, $0, fingerprint
  `b40c5ae1d5ce2fd7838c38afaba52d5567cff55559abb3285095dc7e16c3e3ea`. Difficulty
  still failed: compositional oracle 0.75 on this seed; hops=1/2 RANK source
  clones; head/distributed strata 0. A2 stays stopped.

A2 is a **screen** (2 researchers × 2 profiles × 2 seeds × 5 rounds; 10,720
nominal reader calls). Each researcher turn has a hard 1,800-second timeout,
for a 72,000-second aggregate ceiling over 40 turns. It is not powered to rank
researchers. Formal gate scoring still requires physical isolation that this
host cannot attest.

## Transfer and length

HELMET RAG/Recall, LongBench, RULER, and LongMemEval-V2 are frozen-policy
transfer after valid difficulty qualification and A2, not a way to rescue a
saturated fitness task. Recuris-style state-grounded invocation and verified
working state are long-horizon reference baselines, not static-document matched
controls.
Official LME-V2 uses 451 questions, 25M/115M token haystacks, and a 200k-token
reader truncation. Lightweight first passes in this project keep the 8K pack
and report `answer_string_present` only. Length cells (32K vs 128K, later
256K) hold the 8K pack fixed.
