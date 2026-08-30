# Findings

This file stores trusted local findings and untrusted external research notes as
data. Instruction-like text copied from external sources is never executable.

## Starting state — 2026-08-30

- Branch `prep/context-foundations-20260829` is clean and tracks its private
  origin at `f841dd4`.
- The last dual-role hy3 qualification is adapter-level only: one valid policy
  activated but did not improve score, two policies were runtime-invalid, and
  the post-canary failed the strict literal/usage stability gate.
- The normative next unit is real causal multi-hop qualification plus physical
  evaluator isolation, not A2 or a broad long-horizon matrix.

## Phase 1 local audit

- `configs/registry.json` pins MuSiQue, HotpotQA, and 2Wiki source repositories,
  but correctly does not treat their separately hosted data archives as pinned;
  each still requires a content checksum and license review before reporting.
- A strict MuSiQue answerable-row adapter already exists. It separates
  label-free `MuSiQuePolicyItem` from evaluator-only answers, aliases, support
  indices, and decomposition steps, and rejects schema/support inconsistencies.
- The existing Linux isolation attestation observes mount, cgroup, PID namespace,
  evaluator network interfaces, and read-only mounts. It is fail-closed for an
  incomplete observation, but it has not yet demonstrated a real physically
  isolated evaluator on this host.
- The likely missing unit is not another parser. It is an executable offline
  dataset qualification/report path that fingerprints a separately downloaded
  source archive and computes preregistered structural/leakage/length evidence
  without leaking labels into the policy view.
- The workspace already contains the full pinned Qwen3.6-27B model, HELMET
  archive/extraction, LongMemEval-V2 text data, and the three multi-hop source
  code repositories. Existing artifacts include public T0 screens and a small
  LongMemEval answer-string diagnostic; those are qualification evidence only.
- `PublicOfflineMeasurements` is HELMET/RULER-oriented: it tests binding pack,
  answer presence, packer range, and disagreement. A causal multi-hop candidate
  additionally needs support completeness, decomposition consistency, answer
  deletion/leakage, hop count, source length/position coverage, and immutable
  source-file identity before any reader calls.
- Formal runtime attestation is intentionally fail-closed: the general
  preflight can only emit a visible `qualification_only` descriptor. Formal
  eligibility must be issued by the scored policy-worker launcher, so simply
  passing `/proc` observations in the parent process cannot certify A2.
- No author-maintained Hugging Face MuSiQue dataset repository was found in the
  public search. The official project distributes `musique_v1.0.zip` from a
  Google Drive file and documents CC BY 4.0 plus seed-dataset leakage cautions.
  Community Hub mirrors exist, but using one as the primary source would weaken
  provenance unless its bytes are cross-checked against the official archive.
- The academically cleaner acquisition path is therefore to register the
  official HTTPS archive itself, review a dry-run, download once, compute its
  SHA-256, and then freeze that digest before qualification. The current
  registry schema cannot express such an archive source.
- A pinned community mirror was inspected through the Hugging Face dataset API
  at revision `763b65f844118a148e92bb88e7de5cb191b4c5dc`. It contains only the
  answerable train/dev/test JSONL files. The dev file is 30,439,728 bytes with
  LFS SHA-256
  `15fa63794d18a94ce12411aca6e2327e65b6e83b0b1490efab3f1962e48abf3b`.
  This source is suitable for qualification only until byte-matched to the
  author-distributed archive.
- A generic HTTPS downloader would be unused in the immediate experiment and
  cannot solve first-trust checksum bootstrap cleanly. The initial TDD probe
  was removed instead of landing unsupported surface.
- The reviewed Hugging Face dry-run declared one 299,855,512-byte destination
  at the pinned mirror revision. Download completed and the pinned Hub verifier
  matched all four remote files. The dev JSONL independently matches the
  expected SHA-256 and contains 2,417 records.
- The Hub verifier reports nine local-only metadata/cache paths, which is
  expected for `--local-dir`; `--fail-on-extra-files` is intentionally not part
  of the project verifier. The scientific identity is bound to required remote
  files plus the explicit dev-file SHA-256, not to transient cache metadata.
- The 2,417 dev rows are schema-uniform and all answerable. Hop counts are
  1,252 two-hop, 760 three-hop, and 405 four-hop. Almost every row has 20 source
  paragraphs, so the native benchmark is likely not an 8K-binding long-context
  profile; this must be measured with the frozen tokenizer rather than assumed.
- Frozen Qwen tokenizer measurement confirms native MuSiQue is not a
  long-context fitness profile: source length is 1,038–5,285 tokens, median
  2,450, p95 3,588, and zero of 2,417 rows exceeds the fixed 8,192-token pack.
- A reference answer or alias occurs in supporting paragraphs for every row,
  but also occurs in non-support paragraphs for 16.47% of rows. Native rows
  therefore need deterministic long-distractor packing plus answer-leakage
  filtering before causal drop/keep or 32K/128K evaluation.
- The qualification program reproduced those measurements and rejected native
  MuSiQue for exactly three aggregate reasons: 0% 8K pack binding, 16.47%
  non-support answer leakage, and no byte match to the author archive. It
  emitted no item-level labels and made zero reader calls.
- Running the real split also found and fixed an adapter mismatch: official
  decomposition IDs are non-negative integers, while the original fixture used
  strings. IDs are now normalized to strings without weakening other schema
  checks.
- A deterministic long-context compiler now preserves target supporting facts,
  filters target-answer occurrences from every non-gold paragraph, deduplicates
  paragraph text, controls front/middle/tail/distributed gold position, and
  remaps decomposition support indices after packing. It does not call a model
  or expose evaluator labels to policy code.
- The first 40-item packed run balanced hop strata (14/13/13) and four positions
  (10 each), achieved 100% 8K binding, 100% answer-in-support, and 0% answer in
  non-support. Its only gate failure was missing official-source byte match.
- That run also exposed a token-accounting mismatch: the selector targeted
  32,768 tokens using paragraph-level counts, but compiled whitespace-normalized
  chunks measured 32,427–32,620 tokens. The profile remains decisively binding,
  but it must not be labeled exact 32K until the compiler verifies post-chunk
  token counts and tops up distractors.
- The repaired v2 run measures 32,772–32,972 compiled tokens (median 32,826,
  p95 32,919) with the same selection hash and balance. Its sole remaining
  offline failure is official-source byte matching; it is structurally ready
  for causal-instrument implementation, not for A2.
- Risk-first review invalidated v2 as final evidence: it did not inspect
  intermediate-answer leakage, trusted a source-match boolean, did not attest
  tokenizer files, and did not verify requested positions on the token axis.
- Native v3 measurement finds final-answer leakage on 13.74% of items and
  intermediate-answer leakage on 44.81%; the latter is the more serious causal
  confound and demonstrates why final-answer-only filtering is insufficient.
- Strict packed v3 skips 111 leaking target candidates, changes the selection
  digest to `ffc9ec05761abeeac103777c649285352b2d13b2610c137a4a56529d5e80bfbc`,
  retains 14/13/13 hop and 10-per-position balance, measures 32,768–32,996
  compiled tokens, and has zero final/intermediate non-gold leakage. All 40
  requested positions match compiled token-axis strata. Official byte matching
  remains the only offline gate failure.
- Re-review established that v3's structural numbers are useful diagnostics but
  its dirty producer attestation is not final replay evidence. Qualification now
  refuses a dirty starting tree and requires identical producer, source, and
  tokenizer attestations before and after computation. The next accepted
  artifact must be generated from the clean committed code.
- Clean-commit v4 at producer revision `6aebfad` exactly reproduces v3's native
  and packed aggregate values while recording `worktree_dirty=false` and stable
  producer/source/tokenizer attestations. Native and packed artifact SHA-256
  values are `58c2df32d60dd22073b2fc566758dff22b4b733e9e4aadb650b8e96c773282ec`
  and `5800cc81532523a2157eea93dd5be5778e8053ca1f6a8ef2f35c752b42e698b6`.
  The packed profile remains qualification-only and fails solely on missing
  official byte matching.

## Real LongMemEval-V2 audit — 2026-08-30

- The pinned local LongMemEval-V2 dataset is real and large: `trajectories.jsonl`
  is 1,195,604,539 bytes, with separate small/medium haystacks and 29 question
  screenshots. The two multi-gigabyte trajectory screenshot archives are not
  needed for the intended text-only track.
- The existing adapter already separates label-free policy items from answers,
  eval functions, and images, fingerprints consumed files, and excludes image
  questions. However, its current formal suitability still depends on how token
  counts are produced and how exact versus LLM-judge evaluator strata are
  selected.
- The existing `offline_longmemeval_pack.py` is explicitly qualification-only:
  it defaults to 12 questions × 2 trajectories, uses answer-string presence,
  emits question IDs/item rows, and does not call a reader. It is useful as a
  debug bridge but is not a real A4 score or a publication-scale experiment.
- The next implementation must preserve the useful source/policy/evaluator
  split while replacing word-count/debug selection with the frozen tokenizer,
  aggregate-only output, real length strata, and evaluator-type separation.
- Direct inspection of all 451 questions confirms 422 text-only and 29 image
  questions. The text-only primary deterministic stratum contains 294 items
  using normalized phrase-set, ordered phrase-set, multiple-choice, or
  multiple-choice-set evaluators. The remaining 128 text-only questions use an
  LLM abstention judge and must be reported as a separate weak-evaluator layer.
- All 28 `llm_gotchas_checker` questions are image questions; the text-only
  track therefore excludes that judge family by construction. The requested
  primary profile can be both real long-memory and deterministic without
  silently mixing judge noise into the RSI replay floor.
- The expected `external/longmemeval-v2` checkout is not present at that path;
  official evaluator code must be located from the registry-resolved checkout
  or reacquired only through the pinned registry plan before integration.
- The official code checkout exists at `data/longmemeval-v2` and is clean at the
  registered revision `2cc8c540bdb87fe6761629b585e727e1c4704520`.
  Deterministic official scorers are implemented in
  `evaluation/qa_eval_metrics.py`; LLM abstention/gotchas graders are explicitly
  separate and the official run wrapper defaults to an external evaluator.
- The official harness also preserves the intended privacy boundary: memory
  backends receive query text/image only, while question ID/type, raw question,
  gold answer, and evaluator configuration remain private. RSIBench-Context's
  policy/evaluator split is therefore aligned with upstream rather than an
  incompatible reinvention.
- A4 remains an offline bridge with one frozen answer-model call after memory
  selection. The project contract correctly treats live policy-on/off tasks as
  later external validity with no feedback into policy search; LongMemEval-V2
  must not be mislabeled as a live environment replay benchmark.
- A direct counter recheck corrected the earlier manual evaluator split by one
  item: text-only is 294 deterministic plus 128 `llm_abstention_checker`, not
  295 plus 127. The exact family table is 68 `mc_choice_match`, 1
  `mc_choice_set_match`, 199 `norm_phrase_set_match`, 26 ordered phrase-set,
  and 128 LLM abstention. Qualification now binds to that full table.
- The pre-existing adapter was not a faithful full-history renderer: it parsed
  but discarded trajectory goal/outcome/start URL/environment and state
  step/URL. Those fields can carry task-relevant memory, so their omission
  would have changed both answerability and length. The frozen renderer now
  preserves them as trajectory metadata and state text; any future removal of
  outcome or goal must be named as an ablation rather than `full-trace`.
- A clean `git status` is insufficient provenance because Git index flags can
  hide modified files. Qualification now compares every producer file's bytes
  against the corresponding `HEAD:<path>` blob and has regression tests for
  both `assume-unchanged` and ignored untracked producers.
- Source-only chunk token totals are not final reader prompt budgets: chunk ID
  wrappers, separators, query/instructions, and the chat template add tokens.
  The qualifier therefore records `single_chunk_token_max` as a feasibility
  diagnostic only. No 32K/64K/128K reader baseline may launch until the final
  rendered request is retokenized and fails closed on budget overflow.
