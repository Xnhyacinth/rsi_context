# Must-not-break checks

- Researcher code cannot modify reader, evaluator, metrics, labels, or serving.
- Gate/sealed questions, labels, seeds, and item scores never enter researcher workspaces.
- Candidate manifests cover exactly the evaluator-bound item IDs.
- Empty datasets, non-finite scores, usage omissions, redirects, proxies, and budget
  overruns fail closed.
- Prescribed policies are never reported as researcher discovery.
- Semantic-policy and KV/system results remain separate.
- Qwen3.6 local requests explicitly freeze `chat_template_enable_thinking=false`; a missing
  switch is a different, invalid protocol, not a comparable run.
- Reader identity records model revision, API profile hash, serving profile hash, output cap,
  seed, temperature, and chat-template thinking mode.
- Autonomous round feedback may include only prior visible item predictions/scores. Gate and
  sealed per-item outcomes must remain in an evaluator-only store.
- Researcher-invalid submissions (audit failure, dirty workspace, missing manifest,
  or researcher process abort) stay in the reliability denominator and are never
  hand-repaired into valid candidates.
- Public visible research/search seeds must not derive gate or sealed generator seeds.
  Hidden split seeds and grammar families remain evaluator-only.
- A dataset fingerprint binds query, answer, item/chunk IDs, source spans, chunk text hash,
  per-chunk target-token count, gold provenance, tokenizer identity, and generation metadata.
- A semantic-word count may never be reported as a target-token hard cap. Formal length and
  policy-budget claims use the pinned target tokenizer and rendered-request accounting.
- Gate outcomes never select researcher or control artifacts. Visible selects once; gate
  evaluates the selected artifact once for the primary estimand.
- Unbudgeted full context, gold-only, no-context, and bounded-oracle are evaluator instruments,
  not matched 8K policy controls.
- Failure of a pre-registered difficulty or isolation gate stops A2/A3; do not regenerate a
  seed or reinterpret a threshold after seeing researcher outcomes.
- Public T0-public offline kills stay at n≥16, binding pack, answer-in-source ≥0.90,
  strongest packer <0.90, range and disagreement ≥0.20. Do not relax them to pass NIAH
  or KILT NQ/Trivia/Hotpot k1000. A2 packing fitness is a public cell that already
  passed that screen (currently HELMET PopQA k1000→8K).
- Public reader gold-only ≥0.85 remains a diagnostic for extractive homemade/RULER
  cells. PI 2026-08-18 dropped it as an A2 launch kill; do not use that drop to
  relabel qa_2 as passed. Formal sealed isolation is still required for paper A2
  claims. Visible qualification analogs must stay `qualification_only=true`.
- A2 primary controllers share the exact grammar/interpreter/H0, five candidate slots, and
  byte-identical visible feedback. Open Python artifacts never enter the restricted matched-
  search estimand, and additional researcher compute is always costed.
- Count policy-space size by distinct `(selected spans, order, abstain)` behavior on the
  frozen target-tokenized panel, not by config strings or profiles pooled together. Every A2
  task profile must independently retain at least 20 behavior classes; the current reference
  is 32 compositional and 22 dense.
- Failed v2/v3 and repaired v3b qualification records are separate immutable artifacts. A
  complete-evidence pass or 3/8 policy disagreement never substitutes for the still-pending
  causal, replay, stratum, controller, and isolation gates.
- Do not resolve a virtual-environment Python launcher through its symlink
  before invoking `-m rsicontext.researcher.api`; that loses its import context.
- AST-safe, manifest-valid policies can still violate the runtime
  `Artifact`/`Budget`/`ContextPack` protocol. Preflight every candidate item
  before the first reader call and retain runtime failures as invalid slots.
- The 2026-08-29 `hy3-ioa` post-canary alternated `amber`/`amber.` and 2/3 output
  tokens. Do not label that block deterministic or launch A2/A3 from it.
- Two-hop BM25 rank allocation must not recover every compositional gold chunk on a majority
  of a 32K-to-8K panel. Hop depth 1 versus 2 must change the recovered gold set. Do not
  shorten the live chain back to three unique-ID links. The compositional query must not
  contain `vl-` or the token `folio`; those BM25-saturate hops=2 RANK.
- A policy effect may be called larger than replay noise only when its uncertainty
  lower bound, not merely its point estimate, clears the precommitted noise upper
  bound. Both policy arms must report item-level replay instability, and unstable
  items must enter a conservative paired sensitivity analysis.
- A generic self-consistent contract is not a public preregistration. Public
  qualification tiers must lock the exact dataset, compiled panel, profile,
  budget, scorer, policy implementations, source/token axis, and preregistration
  digest. Evaluator-private ledgers never share the public artifact tree, and
  file modes alone never count as formal researcher isolation.
- Ruff excludes immutable experiment results; candidate bytes are checked by PolicyAuditor
  and replay hashes rather than rewritten to satisfy repository style.
- Open-S visible evolution uses the reader-window pack envelope. Do not relaunch
  that track with `--pack-tokens 8192`.
- An open-S researcher turn that resubmits the parent policy tree is invalid,
  even if the manifest says hold.
- New mode-search open-S runs use a new output directory and offset 72.
  Do not overwrite window-b (offset 64) or the 128960 abort cell.

