# Literature Search: Benchmarking coding agents on a frozen LLM's inference-time information interface

Date: 2026-08-15
Search purpose: Related-work map and novelty/gap diagnosis for a NeurIPS Datasets & Benchmarks positioning (not a new compression method). Public topic: whether coding agents can compile a long source into a budgeted context pack (select / expand / allocate / order / compress / verify) while weights, decoding, and evaluator stay frozen.
Target venue/family: NeurIPS Datasets & Benchmarks
Source-quality policy: applied (MDPI excluded; prefer arXiv abs, proceedings, OpenReview, ACL Anthology)

Evidence status labels used below:

- `verified`: title/authors/year/URL checked on a primary page in this search.
- `venue-comment`: venue taken from arXiv comment, GitHub citation block, or proceedings PDF, not always from a live OpenReview HTML page (OpenReview bot-check blocked several fetches).
- `artifact-not-paper`: GitHub / project page, not a peer-reviewed article.
- `existence-uncertain`: named in the query list but no inspectable paper was found.

Do not treat this folder as a claim that any unpublished protocol already exists in the literature.

## Summary

- Closest-work clusters: (1) long-context _model_ eval; (2) prompt/KV/RAG compression for a frozen or lightly adapted reader; (3) prompt/program search (DSPy/GEPA/ACE); (4) coding / AI-scientist researcher benches; (5) memory compilers; (6) self-modifying coding agents with frozen foundation models; (7) context-engineering surveys.
- Opportunity map: crowded methods and model-eval benches; **protocol gap** for three-way isolation (researcher vs editable context policy vs frozen reader/evaluator) plus matched search grammar plus replay/causal/manifest calibration.
- Strongest baselines to cite, not to impersonate: HELMET, RULER, LongLLMLingua, RECOMP, ACE, DSPy/GEPA, LongMemEval / LongMemEval-V2, RSIBench-Data, DGM.
- Benchmark/dataset candidates for _tasks_ (not for the estimand): LongBench / v2, HELMET, RULER, InfiniteBench, LongMemEval, SWE-bench (agent process only).
- Novelty risks: reviewers saying “this is just ACE / LongLLMLingua / HELMET+compression / DSPy / RSIBench-Data with a different slot.”
- Recommended next action: treat ACE + RSIBench-Data + LongLLMLingua + LongMemEval-V2 as mandatory related work; make the D&B object the _isolated researcher process and calibration protocol_, not a new compressor.

## Paper Table

Quality scores are 1–5 for insight / completeness; numeric evidence is 1–5 or `N/A benchmark`. Overall: A = high-priority close work, B = supporting/baseline, C = background, Risk = may undercut novelty.

| #   | Title                                                                                                 | Year | Venue/source                                              | Link                                                  | Type             | Insight | Completeness | Numeric       | Overall | Notes                                                     |
| --- | ----------------------------------------------------------------------------------------------------- | ---- | --------------------------------------------------------- | ----------------------------------------------------- | ---------------- | ------- | ------------ | ------------- | ------- | --------------------------------------------------------- |
| 1   | RULER: What's the Real Context Size of Your Long-Context Language Models?                             | 2024 | COLM 2024 (`venue-comment`)                               | https://arxiv.org/abs/2404.06654                      | pure benchmark   | 4       | 4            | N/A benchmark | A       | Synthetic NIAH+/tracing; evaluates the **reader**         |
| 2   | HELMET: How to Evaluate Long-Context Language Models Effectively and Thoroughly                       | 2025 | ICLR 2025 (`venue-comment`)                               | https://arxiv.org/abs/2410.02694                      | pure benchmark   | 5       | 5            | N/A benchmark | A       | Application-centric; NIAH poorly predicts downstream      |
| 3   | LongBench: A Bilingual, Multitask Benchmark for Long Context Understanding                            | 2024 | ACL 2024                                                  | https://aclanthology.org/2024.acl-long.172/           | pure benchmark   | 4       | 4            | N/A benchmark | A       | Realistic multitask long-context                          |
| 4   | LongBench v2: Towards Deeper Understanding and Reasoning on Realistic Long-context Multitasks         | 2025 | ACL 2025                                                  | https://aclanthology.org/2025.acl-long.183/           | pure benchmark   | 4       | 4            | N/A benchmark | A       | Deep reasoning, 8k–2M words                               |
| 5   | ∞Bench: Extending Long Context Evaluation Beyond 100K Tokens                                          | 2024 | ACL 2024                                                  | https://aclanthology.org/2024.acl-long.814/           | pure benchmark   | 4       | 4            | N/A benchmark | B       | Same family as InfiniteBench                              |
| 6   | Lost in the Middle: How Language Models Use Long Contexts                                             | 2024 | TACL 2024                                                 | https://aclanthology.org/2024.tacl-1.9/               | method+benchmark | 5       | 5            | 5             | A       | Order/position is a first-class failure mode              |
| 7   | ZeroSCROLLS: A Zero-Shot Benchmark for Long Text Understanding                                        | 2023 | Findings of EMNLP 2023 (`venue-comment`)                  | https://arxiv.org/abs/2305.14196                      | pure benchmark   | 4       | 4            | N/A benchmark | B       | Realistic zero-shot long text                             |
| 8   | BABILong: Testing the Limits of LLMs with Long Context Reasoning-in-a-Haystack                        | 2024 | NeurIPS 2024 D&B (`venue-comment`)                        | https://arxiv.org/abs/2406.10149                      | pure benchmark   | 4       | 4            | N/A benchmark | B       | Same track as intended venue; still model-eval            |
| 9   | LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models                     | 2023 | EMNLP 2023 (`venue-comment`)                              | https://arxiv.org/abs/2310.05736                      | pure method      | 4       | 4            | 4             | A       | Token-level prompt compression; frozen target LLM         |
| 10  | LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression       | 2024 | ACL 2024 (`venue-comment`)                                | https://arxiv.org/abs/2310.06839                      | pure method      | 5       | 4            | 4             | Risk    | Select + reorder + compress for frozen LLM                |
| 11  | LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression            | 2024 | Findings of ACL 2024 (`venue-comment`)                    | https://arxiv.org/abs/2403.12968                      | pure method      | 4       | 4            | 4             | B       | Classifier compressor; still a method                     |
| 12  | RECOMP: Improving Retrieval-Augmented LMs with Compression and Selective Augmentation                 | 2024 | ICLR 2024                                                 | https://arxiv.org/abs/2310.04408                      | method+benchmark | 5       | 4            | 4             | Risk    | Compress retrieved docs for frozen LMs                    |
| 13  | In-context Autoencoder for Context Compression in a Large Language Model                              | 2024 | ICLR 2024 (`venue-comment`)                               | https://arxiv.org/abs/2307.06945                      | pure method      | 4       | 4            | 4             | B       | Soft memory slots; **not** frozen encoder                 |
| 14  | Adapting Language Models to Compress Contexts (AutoCompressor)                                        | 2023 | EMNLP 2023 (`venue-comment`)                              | https://arxiv.org/abs/2305.14788                      | pure method      | 4       | 4            | 4             | B       | Recursive summary vectors; fine-tunes                     |
| 15  | xRAG: Extreme Context Compression for Retrieval-augmented Generation with One Token                   | 2024 | NeurIPS 2024 (`venue-comment`)                            | https://arxiv.org/abs/2405.13792                      | pure method      | 4       | 4            | 4             | B       | One-token RAG compression; not frozen-only                |
| 16  | H2O: Heavy-Hitter Oracle for Efficient Generative Inference of Large Language Models                  | 2023 | NeurIPS 2023 (proceedings citation in later work)         | https://arxiv.org/abs/2306.14048                      | pure method      | 4       | 4            | 4             | B       | KV eviction, not a text pack                              |
| 17  | SnapKV: LLM Knows What You are Looking for Before Generation                                          | 2024 | NeurIPS 2024                                              | https://arxiv.org/abs/2404.14469                      | pure method      | 4       | 4            | 4             | B       | Prompt-KV selection before decode                         |
| 18  | Quest: Query-Aware Sparsity for Efficient Long-Context LLM Inference                                  | 2024 | ICML 2024 (`venue-comment`)                               | https://arxiv.org/abs/2406.10774                      | pure method      | 4       | 4            | 4             | B       | Page selection; keeps full cache                          |
| 19  | Retrieval Head Mechanistically Explains Long-Context Factuality                                       | 2024 | arXiv preprint                                            | https://arxiv.org/abs/2404.15574                      | pure method      | 4       | 3            | 3             | B       | Why selection/KV policy matters                           |
| 20  | Efficient Streaming Language Models with Attention Sinks                                              | 2024 | ICLR 2024 (`venue-comment`)                               | https://arxiv.org/abs/2309.17453                      | pure method      | 4       | 4            | 4             | C       | Streaming window + sink; not a compiler bench             |
| 21  | Learning to Compress Prompts with Gist Tokens                                                         | 2023 | NeurIPS 2023                                              | https://arxiv.org/abs/2304.08467                      | pure method      | 4       | 4            | 4             | B       | Soft gist tokens; trains the LM                           |
| 22  | DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines                        | 2024 | ICLR 2024 (Nature/TextGrad cites ICLR 2024)               | https://arxiv.org/abs/2310.03714                      | system/tool      | 5       | 4            | 4             | Risk    | Prompt/program compiler for (often) frozen LMs            |
| 23  | Optimizing generative AI by backpropagating language model feedback (TextGrad)                        | 2025 | Nature 639, 609–616                                       | https://www.nature.com/articles/s41586-025-08661-4    | pure method      | 5       | 4            | 4             | A       | Textual “gradients”; not a D&B isolation protocol         |
| 24  | GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning                               | 2026 | ICLR 2026 Oral (`venue-comment`)                          | https://arxiv.org/abs/2507.19457                      | pure method      | 5       | 4            | 4             | Risk    | Reflective prompt search; DSPy-adjacent                   |
| 25  | Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution                                 | 2023 | arXiv (conference venue not confirmed here)               | https://arxiv.org/abs/2309.16797                      | pure method      | 4       | 3            | 3             | B       | Evolves prompts; method not bench                         |
| 26  | Large Language Models as Optimizers (OPRO)                                                            | 2024 | ICLR 2024 (`venue-comment`)                               | https://arxiv.org/abs/2309.03409                      | pure method      | 4       | 4            | 4             | B       | LLM-as-optimizer for prompts                              |
| 27  | EvoPrompt: Connecting LLMs with Evolutionary Algorithms Yields Powerful Prompt Optimizers             | 2024 | ICLR 2024 (`venue-comment`)                               | https://arxiv.org/abs/2309.08532                      | pure method      | 4       | 4            | 4             | B       | Evolutionary prompt search                                |
| 28  | Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models                     | 2026 | ICLR 2026 (`venue-comment`; OpenReview forum also exists) | https://arxiv.org/abs/2510.04618                      | method+benchmark | 5       | 4            | 4             | Risk    | Strongest “this is just X” for evolving context           |
| 29  | Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory                                           | 2025 | arXiv                                                     | https://arxiv.org/abs/2504.07952                      | method+benchmark | 4       | 4            | 4             | A       | ACE cites this; evolving inference memory                 |
| 30  | MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation                          | 2024 | ICML 2024 (PMLR v235)                                     | https://proceedings.mlr.press/v235/huang24y.html      | pure benchmark   | 4       | 4            | N/A benchmark | A       | Coding researcher on ML experiments                       |
| 31  | RE-Bench: Evaluating frontier AI R&D capabilities of language model agents against human experts      | 2024 | arXiv (METR)                                              | https://arxiv.org/abs/2411.15114                      | pure benchmark   | 5       | 4            | N/A benchmark | A       | Open-ended research engineering vs humans                 |
| 32  | SWE-bench: Can Language Models Resolve Real-World GitHub Issues?                                      | 2024 | ICLR 2024 (`venue-comment`)                               | https://arxiv.org/abs/2310.06770                      | pure benchmark   | 5       | 5            | N/A benchmark | B       | Coding agents; not context packs                          |
| 33  | PaperBench: Evaluating AI's Ability to Replicate AI Research                                          | 2025 | arXiv / OpenAI                                            | https://arxiv.org/abs/2504.01848                      | pure benchmark   | 5       | 4            | N/A benchmark | B       | Replicate papers; not frozen reader interface             |
| 34  | MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering                         | 2025 | ICLR 2025 Oral                                            | https://arxiv.org/abs/2410.07095                      | pure benchmark   | 4       | 5            | N/A benchmark | A       | Kaggle ML engineering                                     |
| 35  | ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery | 2025 | ICLR 2025 (`venue-comment`)                               | https://arxiv.org/abs/2410.05080                      | pure benchmark   | 4       | 4            | N/A benchmark | B       | Science coding tasks                                      |
| 36  | RSIBench-Data: Benchmarking Data-Centric Research for Recursive Self-Improvement                      | 2026 | arXiv preprint                                            | https://arxiv.org/abs/2607.25886                      | pure benchmark   | 5       | 4            | N/A benchmark | Risk    | Isolation analog, **data** slot not context slot          |
| 37  | MemGPT: Towards LLMs as Operating Systems                                                             | 2023 | arXiv                                                     | https://arxiv.org/abs/2310.08560                      | system/tool      | 5       | 4            | 3             | A       | Agent pages context for a fixed window                    |
| 38  | A-MEM: Agentic Memory for LLM Agents                                                                  | 2025 | NeurIPS 2025 (`venue-comment`)                            | https://arxiv.org/abs/2502.12110                      | method+benchmark | 4       | 4            | 4             | B       | Zettelkasten-style agent memory                           |
| 39  | MemoryBank: Enhancing Large Language Models with Long-Term Memory                                     | 2024 | AAAI 2024                                                 | https://doi.org/10.1609/aaai.v38i17.29946             | method+benchmark | 3       | 3            | 3             | C       | Companion memory / forgetting curve                       |
| 40  | LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory                             | 2025 | ICLR 2025 (`venue-comment`)                               | https://arxiv.org/abs/2410.10813                      | pure benchmark   | 4       | 4            | N/A benchmark | A       | Long-horizon conversational memory                        |
| 41  | LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues                       | 2026 | arXiv (comment: work in progress)                         | https://arxiv.org/abs/2605.12493                      | method+benchmark | 5       | 4            | 4             | Risk    | Compact evidence for downstream QA; coding-agent baseline |
| 42  | Generative Agents: Interactive Simulacra of Human Behavior                                            | 2023 | UIST 2023 (widely cited; ACM page not re-fetched here)    | https://arxiv.org/abs/2304.03442                      | system/tool      | 5       | 4            | 3             | B       | Retrieve/reflect/plan memory loop                         |
| 43  | A Self-Improving Coding Agent (SICA)                                                                  | 2025 | arXiv (comment: submitted as preprint to NeurIPS 2025)    | https://arxiv.org/abs/2504.15228                      | method+benchmark | 4       | 3            | 3             | B       | Self-edits codebase; frozen FM implied                    |
| 44  | Voyager: An Open-Ended Embodied Agent with Large Language Models                                      | 2023 | arXiv                                                     | https://arxiv.org/abs/2305.16291                      | system/tool      | 4       | 4            | 4             | C       | Skill library in Minecraft; not context D&B               |
| 45  | Automated Design of Agentic Systems (ADAS)                                                            | 2025 | ICLR 2025 (`venue-comment` via project page)              | https://arxiv.org/abs/2408.08435                      | method+benchmark | 5       | 4            | 4             | A       | Meta-agent programs target agents                         |
| 46  | Gödel Agent: A Self-Referential Agent Framework for Recursive Self-Improvement                        | 2025 | ACL 2025 main (`venue-comment`)                           | https://arxiv.org/abs/2410.04444                      | method+benchmark | 4       | 3            | 3             | B       | Self-referential agent code search                        |
| 47  | Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents                                   | 2025 | arXiv                                                     | https://arxiv.org/abs/2505.22954                      | method+benchmark | 5       | 4            | 4             | A       | Coding agents self-modify; frozen FMs                     |
| 48  | A Survey of Context Engineering for Large Language Models                                             | 2025 | arXiv (comment: ongoing work)                             | https://arxiv.org/abs/2507.13334                      | survey           | 4       | 4            | N/A benchmark | A       | Taxonomy; not a protocol paper                            |
| 49  | The Prompt Report: A Systematic Survey of Prompt Engineering Techniques                               | 2024 | arXiv                                                     | https://arxiv.org/abs/2406.06608                      | survey           | 4       | 5            | 3             | B       | Prompting taxonomy, not context packs                     |
| 50  | The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery                             | 2024 | arXiv                                                     | https://arxiv.org/abs/2408.06292                      | system/tool      | 4       | 3            | 2             | C       | End-to-end paper mill; entangled stack                    |
| 51  | Needle In A Haystack                                                                                  | 2023 | GitHub artifact                                           | https://github.com/gkamradt/LLMTest_NeedleInAHaystack | system/tool      | 3       | 3            | N/A benchmark | B       | Foundational eval _tool_, not a paper                     |

---

## Included papers (clustered)

For each paper: authors as listed on the primary page used; 1–2 sentence RSIBench-Context relevance; covered vs not covered relative to **frozen reader + researcher vs matched search + replay/causal/manifest calibration**.

### A. Long-context evaluation benchmarks

#### A1. RULER: What's the Real Context Size of Your Long-Context Language Models?

- **Authors:** Cheng-Ping Hsieh, Simeng Sun, Samuel Kriman, Shantanu Acharya, Dima Rekesh, Fei Jia, Yang Zhang, Boris Ginsburg
- **Year / venue:** 2024; COLM 2024 (`venue-comment` on arXiv); **not** NeurIPS D&B
- **URL:** https://arxiv.org/abs/2404.06654
- **Type:** pure benchmark
- **Relevance:** Configurable synthetic long-context tasks (NIAH variants, multi-hop tracing, aggregation) that a budgeted context pack would still have to serve.
- **Covers:** Effective context length of _models_; length and complexity knobs.
- **Does not cover:** A researcher agent compiling packs; matched search over a policy grammar; replay/causal/manifest; frozen-reader isolation as the object of study.

#### A2. HELMET: How to Evaluate Long-Context Language Models Effectively and Thoroughly

- **Authors:** Howard Yen, Tianyu Gao, Minmin Hou, Ke Ding, Daniel Fleischer, Peter Izsak, Moshe Wasserblat, Danqi Chen
- **Year / venue:** 2025; ICLR 2025 (`venue-comment`; project page https://princeton-nlp.github.io/HELMET/)
- **URL:** https://arxiv.org/abs/2410.02694
- **Type:** pure benchmark
- **Relevance:** Best current argument that NIAH/RULER-style retrieval is a weak proxy for application long-context; seven categories, lengths to 128k.
- **Covers:** Thorough _model_ ranking; metric reliability; base vs instruction-tuned eval.
- **Does not cover:** Who assembled the prompt; coding-agent compilers; causal ablations of pack operators; matched finite search.

#### A3. LongBench: A Bilingual, Multitask Benchmark for Long Context Understanding

- **Authors:** Yushi Bai, Xin Lv, Jiajie Zhang, Hongchang Lyu, Jiankai Tang, Zhidian Huang, Zhengxiao Du, Xiao Liu, Aohan Zeng, Lei Hou, Yuxiao Dong, Jie Tang, Juanzi Li
- **Year / venue:** 2024; ACL 2024
- **URL:** https://aclanthology.org/2024.acl-long.172/
- **Type:** pure benchmark
- **Relevance:** Standard realistic long-context suite often used as a downstream testbed by compression papers.
- **Covers:** Multitask bilingual long-context understanding of models (and truncation/retrieval baselines).
- **Does not cover:** Isolated researcher vs frozen reader; replay of compiled packs; manifest calibration.

#### A4. LongBench v2: Towards Deeper Understanding and Reasoning on Realistic Long-context Multitasks

- **Authors:** Yushi Bai, Shangqing Tu, Jiajie Zhang, Hao Peng, Xiaozhi Wang, Xin Lv, Shulin Cao, Jiazheng Xu, Lei Hou, Yuxiao Dong, Jie Tang, Juanzi Li
- **Year / venue:** 2025; ACL 2025
- **URL:** https://aclanthology.org/2025.acl-long.183/ (also https://arxiv.org/abs/2412.15204)
- **Type:** pure benchmark
- **Relevance:** Harder realistic long-context reasoning, including code-repo understanding; human-under-time-limit baseline.
- **Covers:** Deep long-context _model_ (and o1-style reasoning) performance.
- **Does not cover:** Budgeted compilation as the intervention; matched search; three-way isolation.

#### A5. ∞Bench / InfiniteBench: Extending Long Context Evaluation Beyond 100K Tokens

- **Authors:** Xinrong Zhang, Yingfa Chen, Shengding Hu, Zihang Xu, Junhao Chen, Moo Khai Hao, Xu Han, Zhen Leng Thai, Shuo Wang, Zhiyuan Liu, Maosong Sun
- **Year / venue:** 2024; ACL 2024
- **URL:** https://aclanthology.org/2024.acl-long.814/ (arXiv https://arxiv.org/abs/2402.13718)
- **Type:** pure benchmark
- **Relevance:** 100k+ hybrid synthetic/realistic tasks; same “reader under long input” family.
- **Covers:** Extreme-length model eval.
- **Does not cover:** Compiler agents; frozen-eval isolation of a policy.

#### A6. Needle In A Haystack (`artifact-not-paper`)

- **Authors:** Greg Kamradt (repository owner)
- **Year / venue:** 2023–; GitHub tool, widely reused in papers
- **URL:** https://github.com/gkamradt/LLMTest_NeedleInAHaystack
- **Type:** system/tool
- **Relevance:** The retrieval stress test that RULER/HELMET argue is insufficient.
- **Covers:** Depth × length retrieval heatmaps for a model.
- **Does not cover:** Any researcher/policy/evaluator split. Cite as an artifact, not as a D&B paper.

#### A7. Lost in the Middle: How Language Models Use Long Contexts

- **Authors:** Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang
- **Year / venue:** 2024; TACL
- **URL:** https://aclanthology.org/2024.tacl-1.9/
- **Type:** method+benchmark (analysis + eval protocol)
- **Relevance:** Direct evidence that **order/position** of evidence changes a frozen reader’s accuracy; justifies order/allocate operators.
- **Covers:** Positional robustness of readers given a constructed multi-document context.
- **Does not cover:** Who selected those documents under a byte budget; causal credit of compiler ops; matched search.

#### A8. ZeroSCROLLS: A Zero-Shot Benchmark for Long Text Understanding

- **Authors:** Uri Shaham, Maor Ivgi, Avia Efrat, Jonathan Berant, Omer Levy
- **Year / venue:** 2023; Findings of EMNLP 2023 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2305.14196
- **Type:** pure benchmark
- **Relevance:** Realistic long-document QA/summarization without fine-tuning the reader.
- **Covers:** Zero-shot long-text _model_ eval.
- **Does not cover:** Context-pack compilers or isolation protocols.

#### A9. BABILong: Testing the Limits of LLMs with Long Context Reasoning-in-a-Haystack

- **Authors:** Yuri Kuratov, Aydar Bulatov, Petr Anokhin, Ivan Rodkin, Dmitry Sorokin, Artyom Sorokin, Mikhail Burtsev
- **Year / venue:** 2024; NeurIPS 2024 Datasets & Benchmarks (`venue-comment`)
- **URL:** https://arxiv.org/abs/2406.10149
- **Type:** pure benchmark
- **Relevance:** Same _venue track_ as the intended paper; facts distributed in very long haystacks.
- **Covers:** Reasoning-in-haystack for models, extensible length.
- **Does not cover:** Coding-agent compilation; three-way isolation.

### B. Prompt / context compression and retrieval compilers

#### B1. LLMLingua

- **Authors:** Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, Lili Qiu
- **Year / venue:** 2023; EMNLP 2023 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2310.05736
- **Type:** pure method
- **Relevance:** Hard prompt compression for accelerated inference of a (typically frozen) LLM.
- **Covers:** Token pruning via small-LM perplexity; latency/cost vs quality.
- **Does not cover:** Researcher search over a grammar; replay/causal/manifest; D&B isolation.

#### B2. LongLLMLingua

- **Authors:** Huiqiang Jiang, Qianhui Wu, Xufang Luo, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, Lili Qiu
- **Year / venue:** 2024; ACL 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2310.06839
- **Type:** pure method
- **Relevance:** Closest _method_ cousin: question-aware compression, document reordering, subsequence recovery — select/order/compress for a frozen LLM on LongBench/ZeroSCROLLS-style tasks.
- **Covers:** A human-designed H: long source → budgeted prompt; lost-in-the-middle mitigation.
- **Does not cover:** Coding-agent researchers; matched finite search vs agent; replay of packs; causal operator credit; sealed evaluator.

#### B3. LLMLingua-2

- **Authors:** Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang, Menglin Xia, Xufang Luo, Jue Zhang, Qingwei Lin, Victor Rühle, Yuqing Yang, Chin-Yew Lin, H. Vicky Zhao, Lili Qiu, et al.
- **Year / venue:** 2024; Findings of ACL 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2403.12968
- **Type:** pure method
- **Relevance:** Faster task-agnostic hard compression via token classification.
- **Covers:** Distilled compressor; LongBench/ZeroSCROLLS transfer.
- **Does not cover:** Agent discovery protocol.

#### B4. RECOMP

- **Authors:** Fangyuan Xu, Weijia Shi, Eunsol Choi
- **Year / venue:** 2024; ICLR 2024 (proceedings PDF)
- **URL:** https://arxiv.org/abs/2310.04408 — proceedings https://proceedings.iclr.cc/paper_files/paper/2024/hash/bda88ed2892f5e61c9a9bf215c566913-Abstract-Conference.html
- **Type:** method+benchmark (compressors + RAG/LM eval)
- **Relevance:** Explicitly compresses retrieved text **before** a frozen LM sees it; extractive/abstractive/selective empty-string.
- **Covers:** Frozen-LM RAG with a trained compressor; transfer across LMs on LM task.
- **Does not cover:** Open coding-agent search; matched grammar; replay/causal/manifest of compiler decisions.

#### B5. ICAE

- **Authors:** Tao Ge, Jing Hu, Lei Wang, Xun Wang, Si-Qing Chen, Furu Wei
- **Year / venue:** 2024; ICLR 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2307.06945
- **Type:** pure method
- **Relevance:** Soft in-context autoencoding into memory slots.
- **Covers:** Learned compression into activations the target LM can condition on.
- **Does not cover:** Frozen encoder (fine-tunes); text-pack grammar; researcher isolation.

#### B6. AutoCompressor (Adapting Language Models to Compress Contexts)

- **Authors:** Alexis Chevalier, Alexander Wettig, Anirudh Ajith, Danqi Chen
- **Year / venue:** 2023; EMNLP 2023 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2305.14788
- **Type:** pure method
- **Relevance:** Recursive summary-vector compression.
- **Covers:** Soft compression with adapted LMs.
- **Does not cover:** Frozen weights throughout; agent compilers.

#### B7. xRAG

- **Authors:** Xin Cheng, Xun Wang, Xingxing Zhang, Tao Ge, Si-Qing Chen, Furu Wei, Huishuai Zhang, Dongyan Zhao
- **Year / venue:** 2024; NeurIPS 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2405.13792
- **Type:** pure method
- **Relevance:** Extreme RAG compression to one token using retriever embeddings.
- **Covers:** Soft one-token RAG.
- **Does not cover:** Inspectable text packs; coding-agent search; frozen-only pipeline (uses modality adapters).

#### B8. H2O

- **Authors:** Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong Chen, Lianmin Zheng, Ruisi Cai, Zhao Song, Yuandong Tian, Christopher Ré, Clark Barrett, Zhangyang Wang, Beidi Chen
- **Year / venue:** 2023; NeurIPS 2023 (cited as NeurIPS in later SnapKV/proceedings text)
- **URL:** https://arxiv.org/abs/2306.14048
- **Type:** pure method
- **Relevance:** KV “heavy hitters” eviction — a _serving_ compression, not a researcher-editable text pack.
- **Covers:** Decode-time KV budget.
- **Does not cover:** Text-level policy grammar; agent vs matched search; replay of a pack artifact.

#### B9. SnapKV

- **Authors:** Yuhong Li, Yingbing Huang, Bowen Yang, Bharat Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle Cai, Patrick Lewis, Deming Chen
- **Year / venue:** 2024; NeurIPS 2024 (proceedings PDF)
- **URL:** https://arxiv.org/abs/2404.14469
- **Type:** pure method
- **Relevance:** Selects prompt KV before generation using an observation window.
- **Covers:** Training-free prompt-KV selection.
- **Does not cover:** An inspectable context pack; researcher isolation.

#### B10. Quest

- **Authors:** Jiaming Tang, Yilong Zhao, Kan Zhu, Guangxuan Xiao, Baris Kasikci, Song Han
- **Year / venue:** 2024; ICML 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2406.10774
- **Type:** pure method
- **Relevance:** Query-aware KV page selection without deleting the cache.
- **Covers:** Inference efficiency with approximate attention.
- **Does not cover:** Text compilation; D&B protocol.

#### B11. Retrieval Head Mechanistically Explains Long-Context Factuality

- **Authors:** Wenhao Wu, Yizhong Wang, Guangxuan Xiao, Hao Peng, Yao Fu
- **Year / venue:** 2024; arXiv preprint
- **URL:** https://arxiv.org/abs/2404.15574
- **Type:** pure method (mechanistic)
- **Relevance:** Explains why naive KV/context dropping can destroy factual retrieval (retrieval heads).
- **Covers:** Head-level retrieval mechanism; implications for compression.
- **Does not cover:** Benchmarking researchers; matched search.

#### B12. Gist Tokens

- **Authors:** Jesse Mu, Xiang Lisa Li, Noah Goodman (from NeurIPS 2023 paper page; arXiv 2304.08467)
- **Year / venue:** 2023; NeurIPS 2023
- **URL:** https://arxiv.org/abs/2304.08467
- **Type:** pure method
- **Relevance:** Compress prompts into gist tokens by training the LM.
- **Covers:** Learned prompt compression with attention-mask trick.
- **Does not cover:** Frozen reader; agent compilers.

**Cluster B gap (shared):** many papers implement select/compress/reorder _as methods_. None found that freeze reader+decoding+evaluator and then score _coding agents_ against a **matched** search over a shared policy grammar with replay/causal/manifest checks.

### C. Agent self-improvement / prompt and program search

#### C1. DSPy

- **Authors:** Omar Khattab, Arnav Singhvi, Paridhi Maheshwari, Zhiyuan Zhang, Keshav Santhanam, Sri Vardhamanan, Saiful Haq, Ashutosh Sharma, Thomas T. Joshi, Hanna Moazam, Heather Miller, Matei Zaharia, Christopher Potts
- **Year / venue:** 2024; ICLR 2024 (confirmed via later Nature TextGrad citation of the ICLR 2024 paper)
- **URL:** https://arxiv.org/abs/2310.03714
- **Type:** system/tool
- **Relevance:** Literally a “compiler” from declarative LM programs to optimized prompts/demos, often with frozen LMs.
- **Covers:** Metric-driven prompt/program search (BootstrapFewShot, later MIPROv2/GEPA in the ecosystem).
- **Does not cover:** Long-source → budgeted evidence pack as the estimand; three-way isolation with sealed labels; replay/causal/manifest of pack operators.

#### C2. TextGrad (Nature title: Optimizing generative AI by backpropagating language model feedback)

- **Authors:** Mert Yuksekgonul, Federico Bianchi, Joseph Boen, Sheng Liu, Zhi Huang, Carlos Guestrin, James Zou
- **Year / venue:** 2025; Nature 639, 609–616
- **URL:** https://www.nature.com/articles/s41586-025-08661-4 (preprint https://arxiv.org/abs/2406.07496)
- **Type:** pure method
- **Relevance:** Optimizes prompts/code in a compound system via textual feedback; black-box LLM components can stay frozen.
- **Covers:** General text-space optimization of compound AI.
- **Does not cover:** A D&B isolation protocol; matched context-pack grammar; causal pack calibration.

#### C3. GEPA

- **Authors:** Lakshya A Agrawal, Shangyin Tan, Dilara Soylu, Noah Ziems, Rishi Khare, Krista Opsahl-Ong, Arnav Singhvi, Herumb Shandilya, Michael J Ryan, Meng Jiang, Christopher Potts, Koushik Sen, Alexandros G. Dimakis, Ion Stoica, Dan Klein, Matei Zaharia, Omar Khattab
- **Year / venue:** 2026; ICLR 2026 Oral (`venue-comment`; ICLR virtual page listed)
- **URL:** https://arxiv.org/abs/2507.19457
- **Type:** pure method
- **Relevance:** Reflective, Pareto prompt evolution from execution traces; natural baseline _adapter_, not the estimand.
- **Covers:** Sample-efficient prompt search beating GRPO/MIPROv2 on several tasks.
- **Does not cover:** Frozen long-source compiler with sealed eval; matched operator grammar; replay/causal/manifest of evidence packs.

#### C4. Promptbreeder

- **Authors:** Chrisantha Fernando, Dylan Banarse, Henryk Michalewski, Simon Osindero, Tim Rocktäschel
- **Year / venue:** 2023; arXiv (conference venue **not confirmed** in this search)
- **URL:** https://arxiv.org/abs/2309.16797
- **Type:** pure method
- **Relevance:** Self-referential prompt evolution.
- **Covers:** Evolutionary prompt self-improvement.
- **Does not cover:** Context-pack D&B protocol.

#### C5. OPRO

- **Authors:** Chengrun Yang, Xuezhi Wang, Yifeng Lu, Hanxiao Liu, Quoc V. Le, Denny Zhou, Xinyun Chen
- **Year / venue:** 2024; ICLR 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2309.03409
- **Type:** pure method
- **Relevance:** LLMs as prompt optimizers.
- **Covers:** Iterative prompt optimization with an LLM optimizer.
- **Does not cover:** Isolated researcher vs frozen reader on long sources.

#### C6. EvoPrompt

- **Authors:** Qingyan Guo, Rui Wang, Junliang Guo, Bei Li, Kaitao Song, Xu Tan, Guoqing Liu, Jiang Bian, Yujiu Yang
- **Year / venue:** 2024; ICLR 2024 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2309.08532
- **Type:** pure method
- **Relevance:** EA + LLM prompt search.
- **Covers:** Evolutionary prompt optimization.
- **Does not cover:** Budgeted evidence compilation protocol.

#### C7. ACE — Agentic Context Engineering (`exists`)

- **Authors:** Qizheng Zhang, Changran Hu, Shubhangi Upasani, Boyuan Ma, Fenglu Hong, Vamsidhar Kamanuru, Jay Rainton, Chen Wu, Mengmeng Ji, Hanchen Li, Urmish Thakker, James Zou, Kunle Olukotun
- **Year / venue:** 2026; arXiv comment “ICLR 2026”; Microsoft Research publication page also says ICLR 2026; OpenReview forum https://openreview.net/forum?id=9EPY8DDQYv exists but HTML was bot-blocked here — **do not over-claim main vs workshop**
- **URL:** https://arxiv.org/abs/2510.04618
- **Type:** method+benchmark
- **Relevance:** Highest reviewer-risk neighbor: evolving contexts (playbooks) for self-improving LMs **without weight updates**; Generator/Reflector/Curator; compares to GEPA, MIPROv2, Dynamic Cheatsheet.
- **Covers:** Offline prompt and online memory adaptation; execution-feedback without labels; agent/finance tasks.
- **Does not cover (from abstract/related-work text inspected):** A frozen long-source → budgeted _evidence pack_ compiler as D&B estimand; matched finite operator grammar vs coding researchers; replay of packs through a sealed reader; causal operator ablations; manifest calibration of claimed vs executed context.

#### C8. Dynamic Cheatsheet

- **Authors:** Mirac Suzgun, Mert Yuksekgonul, Federico Bianchi, Dan Jurafsky, James Zou
- **Year / venue:** 2025; arXiv
- **URL:** https://arxiv.org/abs/2504.07952
- **Type:** method+benchmark
- **Relevance:** Persistent evolving memory at test time for a black-box LM; ACE builds on this.
- **Covers:** Test-time strategy/code memory without weight updates.
- **Does not cover:** Matched search over a context-pack grammar; sealed long-source compilation.

### D. AI-scientist / coding-researcher benchmarks

#### D1. MLAgentBench

- **Authors:** Qian Huang, Jian Vora, Percy Liang, Jure Leskovec
- **Year / venue:** 2024; ICML 2024 (PMLR)
- **URL:** https://proceedings.mlr.press/v235/huang24y.html (arXiv https://arxiv.org/abs/2310.03302)
- **Type:** pure benchmark
- **Relevance:** Closest _process_ cousin: agents read/write/execute to improve an ML outcome.
- **Covers:** 13 ML experimentation tasks; success vs baseline improvement.
- **Does not cover:** Frozen inference-time information interface; matched context grammar; replay/causal of packs.

#### D2. RE-Bench

- **Authors:** Hjalmar Wijk, Tao Lin, Joel Becker, Sami Jawhar, Neev Parikh, Thomas Broadley, Lawrence Chan, Michael Chen, Josh Clymer, Jai Dhyani, Elena Ericheva, Katharyn Garcia, Brian Goodrich, Nikola Jurkovic, Holden Karnofsky, et al.
- **Year / venue:** 2024; arXiv (METR); later venue not independently confirmed here
- **URL:** https://arxiv.org/abs/2411.15114
- **Type:** pure benchmark
- **Relevance:** Frontier agents vs human experts on AI R&D engineering under time budgets.
- **Covers:** Open-ended research engineering; human comparison.
- **Does not cover:** Frozen reader/decoding/eval; a finite context-policy search space.

#### D3. SWE-bench

- **Authors:** Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, Karthik Narasimhan
- **Year / venue:** 2024; ICLR 2024 (`venue-comment`; OpenReview id VTF8yNQM66 cited on arXiv)
- **URL:** https://arxiv.org/abs/2310.06770
- **Type:** pure benchmark
- **Relevance:** Standard coding-agent eval; DGM/SICA report SWE-bench numbers.
- **Covers:** Issue resolution in real repos.
- **Does not cover:** Compiling long sources into reader context packs.

#### D4. PaperBench

- **Authors:** Giulio Starace, Oliver Jaffe, Dane Sherburn, James Aung, Jun Shern Chan, Leon Maksin, Rachel Dias, Evan Mays, Benjamin Kinsella, Wyatt Thompson, Johannes Heidecke, Amelia Glaese, Tejal Patwardhan
- **Year / venue:** 2025; arXiv / OpenAI (https://openai.com/index/paperbench/)
- **URL:** https://arxiv.org/abs/2504.01848
- **Type:** pure benchmark
- **Relevance:** Agents replicate ICML papers from scratch; rubric isolation is a D&B-quality idea.
- **Covers:** Research replication with hierarchical rubrics and a judge eval.
- **Does not cover:** Frozen LLM information interface; context-pack grammar.

#### D5. MLE-bench

- **Authors:** Jun Shern Chan, Neil Chowdhury, Oliver Jaffe, James Aung, Dane Sherburn, Evan Mays, Giulio Starace, Kevin Liu, Leon Maksin, Tejal Patwardhan, Lilian Weng, Aleksander Mądry
- **Year / venue:** 2025; ICLR 2025 Oral (OpenReview https://openreview.net/forum?id=6s5uXNWGIh)
- **URL:** https://arxiv.org/abs/2410.07095
- **Type:** pure benchmark
- **Relevance:** Coding/ML-engineering agents under Kaggle-like constraints.
- **Covers:** End-to-end ML engineering from scratch.
- **Does not cover:** Inference-time context compilation for a frozen reader.

#### D6. ScienceAgentBench

- **Authors:** Ziru Chen, Shijie Chen, Yuting Ning, Qianheng Zhang, Boshi Wang, Botao Yu, Yifei Li, Zeyi Liao, Chen Wei, Zitong Lu, Vishal Dey, Mingyi Xue, Frazier N. Baker, Benjamin Burns, Daniel Adu-Ampratwum, et al.
- **Year / venue:** 2025; ICLR 2025 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2410.05080
- **Type:** pure benchmark
- **Relevance:** Scientific data-analysis coding agents with contamination controls.
- **Covers:** 102 publication-derived coding tasks.
- **Does not cover:** Frozen reader context packs.

#### D7. RSIBench-Data (`public paper exists`; distinct from unpublished names)

- **Authors:** Fanqing Meng, Lingxiao Du, Qiguang Chen, Ziqi Zhao, Haocheng Lu, Mengkang Hu, Michael Qizhe Shieh
- **Year / venue:** 2026; arXiv preprint
- **URL:** https://arxiv.org/abs/2607.25886
- **Type:** pure benchmark
- **Relevance:** Closest _isolation-protocol_ cousin: researcher agent vs **fixed** train/serve/eval stack; iterative strategy revision; auditable trajectories. Locus is **training-data synthesis + LoRA SFT**, i.e. the target model’s _weights change_.
- **Covers:** Three-way-like isolation for data-centric post-training; feedback-driven revision; discovery–reliability gap.
- **Does not cover:** Inference-time information interface with **frozen weights and decoding**; context-pack grammar; replay of packs through a frozen reader; causal credit of select/order/compress operators.

#### D8. The AI Scientist

- **Authors:** Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, David Ha
- **Year / venue:** 2024; arXiv
- **URL:** https://arxiv.org/abs/2408.06292
- **Type:** system/tool
- **Relevance:** End-to-end automated ML “papers”; shows why entangled stacks are a bad D&B object.
- **Covers:** Ideation–code–experiment–write–review loop.
- **Does not cover:** Isolated frozen reader; matched search.

**RSIBench as a generic name:** `https://rsibench.com/` says “Public Release Coming Soon” — **not a paper**. A GitHub `rsi-bench` by Sunghun Kwag is software, not a verified conference paper. Do not cite those as D&B priors.

### E. Long-horizon memory compilers

#### E1. MemGPT

- **Authors:** Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, Joseph E. Gonzalez
- **Year / venue:** 2023; arXiv (conference venue not confirmed here)
- **URL:** https://arxiv.org/abs/2310.08560
- **Type:** system/tool
- **Relevance:** OS paging: the _agent_ chooses what sits in the frozen LLM’s window.
- **Covers:** Hierarchical memory + function-call paging; document analysis and multi-session chat.
- **Does not cover:** Matched grammar search; sealed evaluator; causal/replay/manifest of a compiled pack as D&B metrics.

#### E2. A-MEM

- **Authors:** Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang
- **Year / venue:** 2025; NeurIPS 2025 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2502.12110
- **Type:** method+benchmark
- **Relevance:** Agentic, evolving notes vs MemGPT/MemoryBank/LoCoMo.
- **Covers:** Dynamic memory graphs; token-efficiency vs full-history baselines.
- **Does not cover:** Frozen long-source compilation protocol.

#### E3. MemoryBank

- **Authors:** Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, Yanlin Wang
- **Year / venue:** 2024; AAAI 2024
- **URL:** https://doi.org/10.1609/aaai.v38i17.29946
- **Type:** method+benchmark
- **Relevance:** Retrieve/update/forget for companions.
- **Covers:** Ebbinghaus-style memory for chat.
- **Does not cover:** Budgeted source compilation; matched search.

#### E4. LongMemEval

- **Authors:** Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu
- **Year / venue:** 2025; ICLR 2025 (`venue-comment`)
- **URL:** https://arxiv.org/abs/2410.10813
- **Type:** pure benchmark
- **Relevance:** Evaluates _memory systems_ on long interactive histories rather than the raw context window.
- **Covers:** Chat-assistant long-term memory abilities.
- **Does not cover:** Coding-agent compilers of a long _source document_ under a byte budget with sealed reader.

#### E5. LongMemEval-V2

- **Authors:** Di Wu, Zixiang Ji, Asmi Kawatkar, Bryan Kwan, Jia-Chen Gu, Nanyun Peng, Kai-Wei Chang
- **Year / venue:** 2026; arXiv (comment: work in progress)
- **URL:** https://arxiv.org/abs/2605.12493
- **Type:** method+benchmark
- **Relevance:** Explicit **context-gathering** formulation: memory consumes huge histories and returns **compact evidence** for downstream QA; includes a **coding-agent** baseline (AgentRunbook-C). Very close transfer story.
- **Covers:** Accuracy–latency Pareto of memory compilers; RAG vs coding-agent evidence gathering.
- **Does not cover:** Three-way isolation with a sealed frozen reader/evaluator; matched finite policy grammar vs researchers; replay/causal/manifest calibration as first-class D&B metrics.

#### E6. Generative Agents

- **Authors:** Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein
- **Year / venue:** 2023; UIST 2023 (standard citation; ACM HTML not re-fetched)
- **URL:** https://arxiv.org/abs/2304.03442
- **Type:** system/tool
- **Relevance:** Retrieve–reflect–plan memory architecture that later memory papers cite.
- **Covers:** Interactive simulacra with streaming memory.
- **Does not cover:** Frozen LLM information-interface D&B.

### F. Recursive / self-improving agents (verified papers only)

#### F1. SICA — A Self-Improving Coding Agent

- **Authors:** Maxime Robeyns, Martin Szummer, Laurence Aitchison
- **Year / venue:** 2025; arXiv (comment: submitted as a preprint to NeurIPS 2025 — **not treated as accepted NeurIPS**)
- **URL:** https://arxiv.org/abs/2504.15228
- **Type:** method+benchmark
- **Relevance:** Coding agent edits its own codebase; distinguishes itself from ADAS (meta vs target).
- **Covers:** Self-referential code improvement on a SWE-bench subset.
- **Does not cover:** Frozen reader context packs; matched pack grammar.

#### F2. Voyager

- **Authors:** Guanzhi Wang, Yuqi Xie, Yunfan Jiang, Ajay Mandlekar, Chaowei Xiao, Yuke Zhu, Linxi Fan, Anima Anandkumar
- **Year / venue:** 2023; arXiv
- **URL:** https://arxiv.org/abs/2305.16291
- **Type:** system/tool
- **Relevance:** Open-ended skill library; often cited in self-improving-agent related work.
- **Covers:** Embodied lifelong skill acquisition in Minecraft.
- **Does not cover:** Inference-time context compilation D&B.

#### F3. ADAS

- **Authors:** Shengran Hu, Cong Lu, Jeff Clune
- **Year / venue:** 2025; ICLR 2025 (`venue-comment` via https://www.shengranhu.com/ADAS/)
- **URL:** https://arxiv.org/abs/2408.08435
- **Type:** method+benchmark
- **Relevance:** Meta-agent _programs_ new agents in code; frozen FMs implied.
- **Covers:** Search over agent designs; archive of discovered agents.
- **Does not cover:** A frozen reader’s information interface; pack replay/causal protocol.

#### F4. Gödel Agent

- **Authors:** Xunjian Yin, Xinyi Wang, Liangming Pan, Li Lin, Xiaojun Wan, William Yang Wang
- **Year / venue:** 2025; ACL 2025 main (`venue-comment`)
- **URL:** https://arxiv.org/abs/2410.04444
- **Type:** method+benchmark
- **Relevance:** Self-referential recursive self-improvement of agent code (Gödel-machine inspiration).
- **Covers:** Agents that rewrite their own routines.
- **Does not cover:** Context-pack D&B isolation.

#### F5. Darwin Gödel Machine

- **Authors:** Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, Jeff Clune
- **Year / venue:** 2025; arXiv
- **URL:** https://arxiv.org/abs/2505.22954
- **Type:** method+benchmark
- **Relevance:** Open-ended evolution of coding agents that self-modify; empirically validates on SWE-bench/Polyglot; **frozen foundation models** power the agents. Mentions long-context window management as a discovered capability.
- **Covers:** Archive-based self-improvement of _agent code_.
- **Does not cover:** Compiling a long source into a budgeted pack for a frozen _reader_; matched pack grammar; replay/causal/manifest of that pack.

**Not invented:** all five named Cluster F systems have primary arXiv pages. Original Schmidhuber Gödel machine is a 2003 theoretical proposal, not an LLM agent paper.

### G. Context-engineering surveys / position-adjacent work (2024–2026)

#### G1. A Survey of Context Engineering for Large Language Models

- **Authors:** Lingrui Mei, Jiayu Yao, Yuyao Ge, Yiwei Wang, Baolong Bi, Yujun Cai, Jiazhi Liu, Mingyu Li, Zhong-Zhi Li, Duzhen Zhang, Chenlin Zhou, Jiayi Mao, Tianze Xia, Jiafeng Guo, Shenghua Liu (arXiv lists 15 names in the Atom feed; HTML lists additional affiliations)
- **Year / venue:** 2025; arXiv (comment: ongoing work; 166 pages)
- **URL:** https://arxiv.org/abs/2507.13334
- **Type:** survey
- **Relevance:** Formalizes context engineering as retrieval/generation, processing, and management, plus RAG/memory/tools/multi-agent implementations. Useful taxonomy; cites LongMemEval/GAIA-style eval as future work, not a compiler-agent D&B.
- **Covers:** Broad map of methods.
- **Does not cover:** The three-way isolation + matched grammar + replay/causal/manifest protocol.

#### G2. The Prompt Report

- **Authors:** Sander Schulhoff, Michael Ilie, Nishant Balepur, Konstantine Kahadze, Amanda Liu, Chenglei Si, Yinheng Li, Aayush Gupta, HyoJung Han, Sevien Schulhoff, et al. (31+ authors)
- **Year / venue:** 2024; arXiv
- **URL:** https://arxiv.org/abs/2406.06608
- **Type:** survey
- **Relevance:** Prompt-engineering ontology; background, not closest work.
- **Covers:** Technique taxonomy and a small MMLU prompting meta-eval.
- **Does not cover:** Long-source compilation; isolation protocols.

**Excluded from scored table:** blog/industry pieces (Transactional, Medium, iwoszapar); `Context Engineering: From Prompts to Corporate Multi-Agent Architecture` (arXiv 2603.09619) looks like an informal position/preprint with vendor surveys — not used as a primary prior. MDPI outlets were not searched or cited.

**Seen but not fully verified (see Blockers):** “Context Folding” / FoldPO ICLR 2026 PDF snippet; ProCut (EMNLP 2025 industry, attribution-based prompt compression); ContextBench / SWE Context Bench / Evaluating AGENTS.md arXiv IDs mentioned only on a blog.

---

## Clusters

### Cluster 1: Long-context _model_ evaluation (RULER, HELMET, LongBench/v2, ∞-Bench, NIAH, Lost in the Middle, ZeroSCROLLS, BABILong)

- **Representative papers:** HELMET, RULER, LongBench, LongBench v2, Lost in the Middle, BABILong
- **Already solves:** How well a _reader_ uses long inputs; positional failures; synthetic vs realistic tasks; NeurIPS D&B already has BABILong.
- **Remaining gap:** The intervention is almost never “a coding agent compiled this pack.” Benchmarks score models, not compilers.
- **Differentiation:** Keep these as _task families_ and reader diagnostics; do not claim a new long-context model bench.
- **Effect on a D&B paper:** Necessary background. If the paper only reports reader accuracy after a new compressor, it collapses into this cluster.

### Cluster 2: Frozen (or black-box) prompt/KV/RAG compression methods (LLMLingua family, RECOMP, ICAE/AutoCompressor/xRAG, SnapKV/H2O/Quest)

- **Representative papers:** LongLLMLingua, RECOMP, SnapKV, LLMLingua
- **Already solves:** Select/compress/reorder (and KV analogs) to fit a budget while a target LM answers.
- **Remaining gap:** Methods are human-designed or trained compressors, not evaluated as _researchers_ under a matched search space; KV methods do not emit an inspectable pack; several soft methods unfreeze encoders.
- **Differentiation:** Use them as **baselines inside a frozen-reader protocol**, not as the contribution. D&B value is the protocol + agent vs matched control.
- **Effect:** Highest “this is just LongLLMLingua” risk if operator set looks like compress+reorder.

### Cluster 3: Prompt/program/context search without weight updates (DSPy, TextGrad, GEPA, OPRO, EvoPrompt, ACE, Dynamic Cheatsheet)

- **Representative papers:** ACE, DSPy, GEPA, TextGrad
- **Already solves:** Optimizing prompts, demos, or evolving playbooks/memories for frozen LMs; ACE is explicitly “context engineering.”
- **Remaining gap:** Search object is usually a _prompt/playbook_, not a budgeted compilation of a long sealed source with replay/causal/manifest of evidence operators. No matched finite grammar vs coding researchers as the D&B estimand.
- **Differentiation:** ACE/GEPA/DSPy are **adapters/baselines**. The paper must show a different object (source→pack), different isolation (researcher cannot touch reader/eval), and calibration (replay/causal/manifest).
- **Effect:** ACE is the single most dangerous novelty neighbor.

### Cluster 4: Coding / AI-scientist researcher benchmarks (MLAgentBench, RE-Bench, SWE-bench, PaperBench, MLE-bench, ScienceAgentBench, RSIBench-Data)

- **Representative papers:** MLE-bench, MLAgentBench, RE-Bench, RSIBench-Data
- **Already solves:** Whether agents can do ML/science/code research; RSIBench-Data isolates a researcher while freezing the _training_ stack.
- **Remaining gap:** Target is almost always code, experiments, or **training data** (weights change). Not a frozen inference-time information interface.
- **Differentiation:** Cite RSIBench-Data as a **sibling isolation idea** with a different intervention slot (data vs context). Do not imply it already did context packs.
- **Effect:** Reviewers may say “swap SFT data for prompts.” Must show why frozen decoding + pack replay is a different scientific question.

### Cluster 5: Memory compilers (MemGPT, A-MEM, MemoryBank, LongMemEval, LongMemEval-V2, Generative Agents)

- **Representative papers:** MemGPT, LongMemEval, LongMemEval-V2
- **Already solves:** Hierarchical/agentic memory; compact evidence for downstream QA; even a coding-agent memory controller (LME-V2).
- **Remaining gap:** Histories/trajectories, not compiling one long _source_ under a shared operator grammar with sealed labels and causal pack audits.
- **Differentiation:** Memory benches are multi-session; a context-pack D&B is a single-shot (or few-shot) **information interface** with matched search.
- **Effect:** LME-V2 is the closest _formulation_ (“return compact evidence”). Must distinguish source compilation vs trajectory memory.

### Cluster 6: Self-modifying coding agents with frozen FMs (ADAS, SICA, Gödel Agent, DGM; Voyager as ancestor)

- **Representative papers:** ADAS, DGM, SICA
- **Already solves:** Agents that rewrite _agent code_ while FMs stay frozen; SWE-bench-style outcomes.
- **Remaining gap:** The editable artifact is the agent, not a context pack consumed by a frozen reader under sealed eval.
- **Differentiation:** Same outer story (coding agent + frozen model) but different inner object and metrics.
- **Effect:** Useful for “why coding agents” motivation; not a scoop of the D&B protocol.

### Cluster 7: Surveys (Mei et al. 2025; Prompt Report 2024)

- **Already solves:** Vocabulary and taxonomy for context/prompt engineering.
- **Remaining gap:** Surveys flag evaluation as immature; they do not provide the isolation+matched-search+calibration protocol.
- **Differentiation:** Cite for field naming; do not treat as prior art that “already benchmarked context compilers.”

---

## Opportunity Map

| Cluster                               | Status                   | Open gap                                            | Possible direction                                           | Evidence needed                                                  | Risk                               |
| ------------------------------------- | ------------------------ | --------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| Long-context model eval               | crowded but open         | Object of study is the reader                       | Use as tasks/diagnostics only                                | Show agent/pack ablations change conclusions vs raw HELMET/RULER | Looks like HELMET-with-compression |
| Prompt/KV compression methods         | covered central _method_ | No agent-vs-matched-search D&B                      | Protocol paper with LongLLMLingua/RECOMP/SnapKV as baselines | Matched byte budget; frozen decode; agent ≠ tuned compressor     | “Just LongLLMLingua”               |
| Prompt/context search (ACE/DSPy/GEPA) | crowded but open         | Playbooks ≠ source packs; no replay/causal/manifest | Different estimand + isolation                               | Side-by-side vs ACE/GEPA on same tasks                           | “Just ACE”                         |
| Coding-researcher benches             | crowded but open         | Wrong intervention slot (code/data/weights)         | Frozen _inference interface_                                 | Explicit comparison table vs RSIBench-Data / MLE-bench           | “Just RSIBench-Data”               |
| Memory compilers                      | crowded but open         | Trajectory memory ≠ source compilation              | Single-source budgeted pack + matched grammar                | Contrast with LongMemEval-V2 gathering                           | “Just MemGPT/LME-V2”               |
| Self-improving coding agents          | crowded but open         | Editable artifact is the agent                      | Freeze reader; edit only pack/policy                         | Show DGM-style agents fail/succeed _as compilers_                | Unfocused RSI rhetoric             |
| Surveys                               | background               | No protocol                                         | Use taxonomy                                                 | None                                                             | Overciting blogs                   |

---

## Required synthesis

### 1. Closest-work clusters (7)

See Clusters 1–7 above.

### 2. Covered / remaining gap / differentiation (compact)

| Cluster                 | Covered                                       | Remaining gap                                    | Differentiation           |
| ----------------------- | --------------------------------------------- | ------------------------------------------------ | ------------------------- |
| 1 Model eval            | Reader long-context ability                   | Compiler as estimand                             | Tasks not contribution    |
| 2 Compressors           | Select/order/compress methods                 | Agent vs matched search + calibration            | Methods as baselines      |
| 3 Prompt/context search | Frozen-LM prompt/playbook evolution           | Source→pack + isolation + replay/causal/manifest | ACE/DSPy/GEPA as adapters |
| 4 Researcher benches    | Coding/ML/science agents; data-slot isolation | Frozen inference interface                       | Sibling of RSIBench-Data  |
| 5 Memory                | Paging and compact evidence                   | Matched grammar on sealed sources                | Not multi-session memory  |
| 6 Self-modifying agents | Frozen FM + editable code                     | Editable pack not agent                          | Different artifact        |
| 7 Surveys               | Taxonomy                                      | Protocol                                         | Background only           |

### 3. Honest novelty assessment (D&B)

**Judgment:** The _conjunction_ of (i) three-way isolation of researcher vs editable context policy vs frozen reader/decoding/evaluator, (ii) a **matched** policy/spec grammar so agents are not compared to an unbounded heuristic soup, and (iii) replay / causal / manifest calibration of what the pack claims vs what the frozen reader actually used, is **not instantiated as a public D&B protocol** in the papers verified here.

**It is not a greenfield scientific problem.** Pieces exist:

- Frozen reader + compression: RECOMP, LLMLingua/LongLLMLingua.
- Frozen weights + evolving context: ACE, Dynamic Cheatsheet, MemGPT.
- Isolated researcher + frozen surrounding stack: RSIBench-Data (weights still updated via SFT).
- Compact evidence for a downstream model: LongMemEval-V2.
- Coding agents + frozen FMs: ADAS, DGM, SICA.

**Confidence:** **medium-high (about 0.7)** that the _full protocol package_ is a gap; **low** that reviewers will automatically accept that gap as NeurIPS D&B-worthy without (a) a crisp estimand, (b) mandatory ACE/LongLLMLingua/RSIBench-Data/LME-V2 discussion, and (c) results that cannot be restated as “compression helped the reader.”

**What is already done:** evaluating long-context models; proposing compressors; evolving prompts/playbooks; benchmarking coding agents on SWE/ML/science; isolating data-centric researchers.

**What is not already done (on verified public evidence):** a D&B whose _object_ is whether coding agents can improve a **frozen** LLM’s **inference-time information interface** under a **matched search** and **replay/causal/manifest** audit.

### 4. Biggest reviewer-risk prior art (“this is just X”)

1. **ACE (Zhang et al., 2026)** — evolving contexts, no weight updates, agentic generator/reflector/curator. Mitigation: different artifact (evidence pack from a long source vs playbook bullets); isolation and calibration protocol; matched grammar vs coding researchers.
2. **LongLLMLingua / LLMLingua / RECOMP** — select/reorder/compress for frozen LMs. Mitigation: those are baselines; contribution is agent-vs-matched-search + audits, not a new compressor.
3. **HELMET / RULER / LongBench** — “you evaluated long context.” Mitigation: reader is frozen; ranking compilers/agents is the claim.
4. **DSPy / GEPA / TextGrad** — “prompt compiler.” Mitigation: DSPy compiles programs/prompts from labeled metrics, not sealed long-source packs with causal/replay.
5. **RSIBench-Data** — “isolated researcher, frozen stack.” Mitigation: they update weights via data/SFT; this slot is inference-time context with frozen decoding.
6. **LongMemEval-V2 + MemGPT** — “memory compiler / coding agent gathers evidence.” Mitigation: different source type (trajectories vs one long corpus), different protocol (matched grammar, sealed eval, causal/replay).
7. **DGM / ADAS** — “coding agents improve frozen-FM systems.” Mitigation: they edit agent code, not a reader-facing pack.

### 5. Kill conditions (benchmark not worth doing)

The D&B is probably **not worth doing** (or should be killed/reframed) if any of the following hold:

1. **Estimand collapse:** After ACE + LongLLMLingua + HELMET, the only number that moves is reader accuracy under a new compressor, with no matched-search control and no replay/causal/manifest. Then it is a methods paper in a crowded area, not D&B.
2. **Protocol already public:** A paper appears that already (a) freezes reader+decode+eval, (b) lets only a context policy/pack change, (c) compares agents to a matched grammar search, and (d) audits packs with replay/causal/manifest. ACE + RSIBench-Data together are **not** that paper today, but a 2026 preprint could become it.
3. **Un-isolatable leakage:** Researcher can see labels, seeds, item scores, or evaluator internals; then three-way isolation is theater.
4. **Trivial saturated tasks:** Gold extractive packs and BM25/LongLLMLingua already match the frozen reader’s full-context ceiling; agents have nothing to discover.
5. **Unmatched search:** Agent action space is unbounded (arbitrary Python) while “matched search” is a tiny heuristic — reviewers will reject the comparison as unfair either way.
6. **Non-replayable packs:** Packs are stochastic, KV-only, or non-textual so they cannot be hashed, replayed, or causally ablated — the claimed calibration protocol cannot exist.
7. **Sibling scoop on isolation:** If the field treats RSIBench-Data’s isolation story as venue-defining and sees context-vs-data as a thin delta without new measurements, D&B reviewers may desk-reject as incremental.
8. **Negative-only without protocol value:** If agents never beat matched search _and_ the paper does not turn that into a sharp, reusable diagnostic (when/why compilers fail), a negative result may still be publishable but is a weak D&B.

A **non-kill** negative result: agents lose to matched search on a non-saturated, well-isolated protocol with replay/causal/manifest. That can still be a valid D&B (the protocol is the contribution).

---

## Benchmark And Dataset Candidates

| Name             | Link                             | Task                        | Metrics                           | Baselines                 | Fit                    | Risks                                 |
| ---------------- | -------------------------------- | --------------------------- | --------------------------------- | ------------------------- | ---------------------- | ------------------------------------- |
| HELMET           | https://arxiv.org/abs/2410.02694 | Application long-context    | Category scores; model-based eval | Frontier LCLMs            | High as _reader tasks_ | Scoring the reader, not the compiler  |
| RULER            | https://arxiv.org/abs/2404.06654 | Synthetic long-context      | Accuracy vs length                | 17 LMs in original        | High for tracing/NIAH  | Saturated NIAH                        |
| LongBench / v2   | ACL 2024 / ACL 2025              | Realistic long QA/reasoning | EM/accuracy                       | Long-context LMs          | High                   | Contamination; truncation conventions |
| LongMemEval / v2 | ICLR 2025 / arXiv 2605.12493     | Memory / evidence gathering | Accuracy, latency                 | RAG, MemGPT, coding agent | Medium–high            | Wrong source type if used as-is       |
| SWE-bench        | https://arxiv.org/abs/2310.06770 | Coding agents               | Resolve rate                      | Agent scaffolds           | Process only           | Not the estimand                      |

---

## Citation And Positioning Cautions

- Claims that need direct citation: Lost in the Middle (order); HELMET (NIAH ≠ downstream); LongLLMLingua/RECOMP (frozen-LM compression); ACE (evolving context without weights); RSIBench-Data (isolated researcher, different slot); LongMemEval-V2 (compact evidence); DGM/ADAS (coding agents, frozen FMs).
- Papers that may weaken novelty: ACE, LongLLMLingua, RECOMP, DSPy/GEPA, RSIBench-Data, LongMemEval-V2, HELMET.
- Papers that only support background: Voyager, Generative Agents, Prompt Report, Needle-in-a-Haystack GitHub, The AI Scientist.
- Do **not** cite RULER as NeurIPS D&B (it is COLM 2024). BABILong _is_ NeurIPS 2024 D&B.
- Do **not** cite rsibench.com or unaudited GitHub “RSI-Bench” as the public RSIBench paper. The public arXiv paper is **RSIBench-Data**.
- Do **not** claim ACE “ICLR 2026 main” without checking camera-ready/OpenReview; arXiv comment says ICLR 2026, OpenReview forum exists.
- Do **not** treat SICA as NeurIPS 2025 accepted (arXiv comment says submitted as preprint).
- Do **not** overclaim a “context compiler benchmark” already exists; none of the verified papers combine isolation + matched grammar + pack replay/causal/manifest.

## Quality-score rationale (short)

A-tier close work is scored high on insight when it changes the _object of evaluation_ (HELMET vs NIAH; ACE vs prompt brevity; RSIBench-Data vs entangled post-training; Lost in the Middle vs uniform context use). Pure methods that unfreeze encoders (ICAE, Gist, AutoCompressor) are completeness-strong but fit-weaker for a frozen-reader D&B. Numeric scores are N/A for pure benches; compression/agent methods were not re-audited from tables beyond abstracts/proceedings text.
