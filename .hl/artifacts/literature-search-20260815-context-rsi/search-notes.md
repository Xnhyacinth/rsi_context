# Search Notes

Date: 2026-08-15
Topic slug: context-rsi (public: coding agents compiling budgeted context packs for a frozen LLM)
Folder: `.hl/artifacts/literature-search-20260815-context-rsi/`

No unpublished manuscript sentences were pasted into queries. Queries used only public paper/benchmark/method names and field phrases (long-context benchmark, prompt compression, prompt optimization, coding-agent benchmark, memory compiler, self-improving agent, context engineering survey).

## Safe Queries Used

Web / discovery:

- `RULER HELMET LongBench InfiniteBench ZeroSCROLLS Lost in the Middle long-context benchmark arXiv`
- `LLMLingua LongLLMLingua RECOMP ICAE AutoCompressor SnapKV H2O Quest xRAG retrieval head arXiv`
- `DSPy TextGrad GEPA PromptBreeder OPRO EvoPrompt Agentic Context Engineering ACE arXiv`
- `MLAgentBench RE-Bench SWE-bench PaperBench MLE-bench ScienceAgentBench RSIBench arXiv`
- `MemGPT A-MEM MemoryBank LongMemEval Generative Agents memory compiler arXiv`
- `SICA Voyager ADAS Godel Agent Darwin Godel Machine self-improving agent arXiv`
- `context engineering survey 2024 2025 2026 LLM position paper arXiv`
- `HELMET long context evaluation benchmark Yen arXiv`
- `LongBench v2 Bai arXiv long context`
- `GEPA Genetic-Pareto reflective prompt evolution Agrawal arXiv`
- `PaperBench OpenAI arXiv RSIBench benchmark agent`
- `LongMemEval Wu arXiv LongMemEval-v2 memory benchmark`
- `RSIBench recursive self improvement benchmark arXiv OpenReview`
- `Retrieval Head Wu arXiv SnapKV Li H2O Zhang Quest Tang KV cache`
- `InfiniteBench Zhang ACL LongBench Bai ACL Lost in the Middle Liu TACL ZeroSCROLLS Shaham`
- `ScienceAgentBench Chen ICLR TextGrad Yuksekgonul DSPy Khattab ADAS Automated Design of Agentic Systems`
- `prompt compiler LLM DSPy context packing budgeted context benchmark frozen model`
- `Agentic Context Engineering OpenReview ICLR 2026 TextGrad Nature MemoryBank AAAI RECOMP ICLR Promptbreeder ICML`
- `The Prompt Report Schulhoff LLMLingua-2 Dynamic Cheatsheet Suzgun StreamingLLM Xiao context engineering benchmark arXiv`
- `causal attribution prompt compression evaluation replay frozen language model context selection benchmark`
- `Needle in a Haystack Kamradt GitHub L-Eval An BABILong LOFT Gemini long context`
- `The AI Scientist Lu Sakana arXiv LiveCodeBench ICLR DiscoveryWorld ML-Bench`
- `site:openreview.net Agentic Context Engineering Zhang ICLR 2026 GEPA Agrawal HELMET Yen DSPy Khattab`
- `MemoryBank Zhong AAAI 2024 RECOMP Xu ICLR TextGrad Nature Yuksekgonul Generative Agents UIST H2O NeurIPS Promptbreeder`
- `MLE-bench Chan ICLR 2025 ADAS Hu ICLR 2025 LongBench v2 ACL 2025 Gist Tokens Mu NeurIPS`
- `RECOMP Xu Choi ICLR 2024 OpenReview Promptbreeder Fernando venue Context Folding ICLR arXiv`
- `MLE-bench OpenReview ICLR 2025 MemGPT Packer ICLR COLM venue`

arXiv Atom API (`export.arxiv.org/api/query?id_list=...`) for metadata (title, authors, published date, comment/journal_ref) on IDs including:

`2404.06654, 2410.02694, 2308.14508, 2412.15204, 2402.13718, 2307.03172, 2305.14196, 2310.05736, 2310.06839, 2404.15574, 2310.04408, 2405.13792, 2307.06945, 2305.14788, 2404.14469, 2306.14048, 2406.10774, 2310.03714, 2406.07496, 2309.16797, 2309.03409, 2309.08532, 2510.04618, 2507.19457, 2310.03302, 2411.15114, 2310.06770, 2410.07095, 2410.05080, 2504.01848, 2310.08560, 2502.12110, 2305.10250, 2410.10813, 2304.03442, 2605.12493, 2504.15228, 2305.16291, 2408.08435, 2410.04444, 2505.22954, 2507.13334, 2403.12968, 2504.07952, 2406.06608, 2309.17453, 2406.10149, 2408.06292, 2504.08066, 2607.25886`

Semantic Scholar batch API: attempted; **HTTP 429**, not used for venue confirmation.

OpenReview HTML: several forum URLs exist but browser-check blocked full HTML (ACE `id=9EPY8DDQYv`, others). Venue claims that rest only on OpenReview HTML are marked `venue-comment` or uncertain.

ACL Anthology / proceedings used as primary when found:

- LongBench https://aclanthology.org/2024.acl-long.172/
- LongBench v2 https://aclanthology.org/2025.acl-long.183/
- ∞Bench https://aclanthology.org/2024.acl-long.814/
- Lost in the Middle https://aclanthology.org/2024.tacl-1.9/
- RECOMP ICLR 2024 proceedings hash `bda88ed2892f5e61c9a9bf215c566913`
- SnapKV NeurIPS 2024 proceedings PDF
- MLE-bench ICLR 2025 proceedings PDF
- MLAgentBench PMLR https://proceedings.mlr.press/v235/huang24y.html
- MemoryBank AAAI https://doi.org/10.1609/aaai.v38i17.29946
- TextGrad Nature https://www.nature.com/articles/s41586-025-08661-4
- Gist Tokens NeurIPS 2023 proceedings PDF

## Sources Checked

| Source                                       | Role                                                          | Result                                                              |
| -------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------- |
| WebSearch                                    | Discovery across clusters A–G                                 | High recall of named papers                                         |
| arXiv Atom API                               | Author lists, dates, comments                                 | Primary metadata                                                    |
| arXiv abs/html                               | Abstracts and venue comments                                  | Claim grounding                                                     |
| ACL Anthology                                | LongBench, LongBench v2, ∞Bench, Lost in the Middle           | Proceedings URLs                                                    |
| ICLR / NeurIPS / ICML / PMLR / AAAI / Nature | Venue confirmation                                            | RECOMP, SnapKV, MLE-bench, MLAgentBench, MemoryBank, TextGrad, Gist |
| GitHub / project pages                       | HELMET, NIAH, ACE unofficial reimplementations, RSIBench-Data | Artifacts vs papers distinguished                                   |
| OpenReview                                   | ACE, MLE-bench, SWE-bench ids                                 | Partial (bot wall)                                                  |
| Semantic Scholar                             | Venue batch                                                   | Failed (429)                                                        |
| MDPI                                         | —                                                             | Not searched (policy exclude)                                       |

## Inclusion / Exclusion Criteria

Include if:

- Named in the public query list, or a high-signal neighbor found while resolving those names (e.g., LLMLingua-2, Dynamic Cheatsheet, BABILong, Gist, StreamingLLM, The AI Scientist, RSIBench-Data).
- Stable URL on arXiv abs, proceedings, OpenReview, ACL Anthology, DOI, or official org page.
- Enough metadata to list title and authors without invention.

Exclude if:

- MDPI journal/proceeding/PDF.
- Blog/medium/industry roundups as primary citations (Transactional, Medium, iwoszapar used only as discovery pointers).
- Untraceable PDFs or snippet-only claims.
- Marketing pages without a paper (`rsibench.com` “coming soon”).
- Unofficial GitHub reimplementations presented as the ACE paper.

## Excluded Sources

- Policy-excluded: MDPI (none needed to drop from the final table; none were used).
- `https://rsibench.com/` — “Public Release Coming Soon”; not a paper.
- `sunghunkwag/rsi-bench` (and mirror github.laiyagushi.com) — software README, not a verified conference paper.
- Third-party ACE reimplementation `rrahimi-uci/agentic-context-engineering` — not the primary paper.
- ResearchGate copies used only when arXiv/proceedings existed.
- Informal arXiv `2603.09619` (corporate multi-agent “context engineering”) not treated as a primary survey.

## Screening Counts (approximate, not PRISMA-grade)

- Named targets in the user list: ~45.
- Verified as papers or official artifacts: 51 catalog rows in `papers.md`.
- Existence-uncertain / not independently verified: see Unknowns.
- Duplicates merged: InfiniteBench = ∞-Bench; AutoCompressor = “Adapting Language Models to Compress Contexts”; TextGrad Nature vs arXiv preprint.

## Unknowns

### Papers / venues not fully verified

- **Promptbreeder conference venue:** arXiv 2309.16797 exists; ICLR/NeurIPS proceedings page not confirmed in this pass.
- **MemGPT conference venue:** arXiv 2310.08560 exists; ICLR/other camera-ready not confirmed.
- **Generative Agents UIST 2023:** standard citation; ACM HTML not re-fetched (arXiv 2304.03442 verified).
- **ACE ICLR 2026 main vs workshop:** arXiv comment and Microsoft Research page say ICLR 2026; OpenReview forum `9EPY8DDQYv` exists but HTML was bot-blocked; a search snippet also mentioned MemAgents workshop oral. **Do not over-claim track.**
- **RE-Bench later venue:** arXiv 2411.15114 verified; ICML 2025 (mentioned in some secondary text) **not independently confirmed**.
- **H2O NeurIPS year:** arXiv 2306.14048 verified; NeurIPS 2023 inferred from later papers’ citations, not from a proceedings HTML fetch of H2O itself.
- **Voyager venue:** remains arXiv on the record used here.
- **SICA:** not an accepted NeurIPS 2025 paper on the evidence used (comment: submitted as preprint).
- **Context Folding / FoldPO:** an ICLR 2026 “under review” PDF snippet was retrieved via OpenReview CDN; **authors/arXiv ID not confirmed** — not included in the scored table.
- **ProCut** (EMNLP 2025 industry, attribution-based compression): anthology PDF seen; not fully extracted into the main catalog (supporting, not closest work).
- **ContextBench (arXiv 2602.05892), SWE Context Bench (2602.08316), Evaluating AGENTS.md (2602.11988):** appeared only in a blog roundup; **not independently fetched** — do not cite until arXiv abs is opened.
- **L-Eval, LOFT, LongProc, DuoAttention, Selective Context:** mentioned in related work of included papers; not fully catalogued.
- **ZeroSCROLLS anthology ID:** Findings EMNLP 2023 from arXiv comment; anthology landing page not fetched (arXiv used as stable URL).
- **LongLLMLingua anthology:** ACL 2024 from arXiv comment; anthology ID not fetched in this pass (arXiv used).
- **Semantic Scholar citation counts:** unavailable (API 429). Influence ranking is qualitative.

### Missing benchmark details

- Matched PolicySpec / replay / causal / manifest: **no public paper was found that uses this combination of names as a released protocol.** Absence in search ≠ proof of nonexistence, but no hit on public keywords + named neighbors.
- Frozen reader + coding-agent compiler + matched search: no single verified D&B paper.

### RSIBench naming collision

Public hits for the string `RSIBench`:

1. **RSIBench-Data** — arXiv 2607.25886 — include.
2. **rsibench.com** — coming soon — do not cite as a paper.
3. **rsi-bench GitHub (Kwag)** — unverified software — do not cite as a paper.

Do not conflate these with any unpublished local project name.

## Handoff Notes

- **For writing:** Closest-work groups are in `papers.md`. Mandatory citations: ACE, LongLLMLingua/RECOMP, HELMET/RULER/Lost-in-the-Middle, DSPy/GEPA, RSIBench-Data, LongMemEval-V2, DGM/ADAS. Position as D&B protocol, not a compressor.
- **For idea optimization:** Strongest rescue if novelty feels thin: keep isolation + matched grammar + replay/causal/manifest as the _object_; put LongLLMLingua/ACE in the baseline table on day one.
- **For direction scouting:** Direction is crowded on methods, open on protocol. Kill conditions listed in `papers.md`.
- **For experiment design:** Task families can be borrowed from HELMET/LongBench/RULER; estimand must remain compiler/agent under frozen reader. Include LongLLMLingua, RECOMP, BM25/RAG, ACE/GEPA-style adapters, and a matched-search control.
- **For review:** Reviewer “this is just ACE / LongLLMLingua / HELMET / DSPy / RSIBench-Data / MemGPT” is the main prior-art risk list.

## Checklist Status (ccf-literature-searcher standard mode)

1. Public queries only: done.
2. MDPI excluded: done.
3. Primary/high-confidence sources preferred: done, with `venue-comment` flags.
4. Deduplicated by title: done.
5. Venue/year/type/relevance: done in `papers.md`.
6. Quality scores: done in paper table; pure benches use N/A numeric + notes.
7. Paper-type taxonomy: applied.
8. Claims traceable or marked inferred/uncertain: applied.
9. Clusters with covered/gap/differentiation: done.
10. Folder written: `papers.md` + `search-notes.md`.
11. Next module: idea review / experiment design (baselines + isolation tests), then writing.

Recommended next CCFA module: **idea review** (novelty confidence vs ACE/RSIBench-Data) then **experiment designer** (matched-search + frozen-reader protocol), not manuscript drafting first.
