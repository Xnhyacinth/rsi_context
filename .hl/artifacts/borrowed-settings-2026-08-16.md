# Borrowed settings from related work (2026-08-16)

Payoff target: a coding researcher improves a frozen reader's **accuracy and
efficiency** on long-context tasks (tokens, latency, cost), the same three
axes LongLLMLingua reports. Identification still requires the matched-grammar
protocol. Do not impersonate these methods; copy their **evaluation settings**.

## LongLLMLingua (Jiang et al., ACL 2024; arXiv:2310.06839)

Primary pages: https://arxiv.org/abs/2310.06839 ,
https://github.com/microsoft/LLMLingua (DOCUMENT.md, issues #7/#12/#76).

| Setting             | Upstream value                                                                        | Adopt here                                                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Compression ratio   | Headline ~4× on NaturalQuestions (GPT-3.5-Turbo); 2×–6× latency study on ~10k prompts | Keep **32,768 → 8,192** as the 4× cell; later 128K source still packs 8K                                                             |
| Decoding            | Greedy, temperature 0                                                                 | Already frozen: T=0, seed 42, thinking off                                                                                           |
| Question-aware rank | `rank_method="longllmlingua"`, `condition_in_question="after_condition"`              | PolicySpecV1 `QUERY_BM25` is the matched analog; a true LongLLMLingua H is a **later baseline**, not a grammar key                   |
| Reorder             | `reorder_context="sort"`; used on NQ multi-doc, not all LongBench tasks               | `OrderV1.RELEVANCE` / `EDGE_INTERLEAVE`; Lost-in-the-Middle strata already exist                                                     |
| Dynamic ratio δτ    | Paper 0.25; authors use **0.3 or 0.4** on multi-document QA                           | If/when LongLLMLingua is run: `dynamic_context_compression_ratio=0.3`                                                                |
| Coarse budget       | `context_budget="+100"` (README) or `"+200"` (author issues); granular k=2            | Record as compressor hyperparams; do not put them in PolicySpecV1                                                                    |
| Iterative segment   | 200 tokens; τ_ins=0.85, τ_que=0.9                                                     | Same                                                                                                                                 |
| Small LM            | LLaMA-2-7B-Chat                                                                       | Registry-gated; do not download until the method baseline is scheduled                                                               |
| Metrics             | EM/F1 **and** API cost **and** end-to-end latency                                     | Every landscape JSON already has reader input/output tokens and wall seconds; report them as first-class columns, not appendix noise |
| Tasks               | NQ-multi (Lost-in-the-Middle), LongBench English, ZeroSCROLLS, MuSiQue, LooGLE        | Transfer **after** a valid 32K landscape                                                                                             |

Do not start a LongLLMLingua GPU job in Repair B. It needs a second model and
would confound the query-contract repair.

## HELMET (Yen et al., ICLR 2025; arXiv:2410.02694)

Configs from https://github.com/princeton-nlp/HELMET :

| Setting       | Upstream value                                                                                         | Adopt here                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| Categories    | RAG, Recall, LongQA, Re-rank, Cite, Summ, ICL                                                          | Synthetic 32K panel is **not** HELMET; HELMET is transfer                                      |
| RAG yaml      | KILT NQ/TriviaQA/HotpotQA/PopQA; `generation_max_length=20`; 2-shot; 100 samples; `stop_new_line=true` | Future transfer cell; keep our exact-ID scorer on the synthetic panel                          |
| Recall yaml   | RULER NIAH mk2/mk3/mv + JSON KV; gen 50–100; 2-shot                                                    | NIAH is a weak proxy (HELMET's claim); do not unsaturate 32K by adding needles                 |
| Length        | Controllable 8k–128k via retrieved-passage count or document length                                    | Length cells hold the 8K pack fixed                                                            |
| Output format | Task-specific post_process; few-shot for base models                                                   | Repair B: put the **output contract in the query**, because the reader system prompt is frozen |
| Fast loop     | Authors recommend Recall + RAG for iteration                                                           | Our cheap loop is gold-only / bounded-oracle / no-context / full, not a HELMET subset          |

## RECOMP (Xu, Shi, Choi, ICLR 2024; arXiv:2310.04408)

| Setting     | Upstream value                                                                         | Adopt here                                                                   |
| ----------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Object      | Compress retrieved docs **before** a frozen LM                                         | Same slot as H; trained compressor vs coding researcher                      |
| Compressors | Extractive sentence selection; abstractive distillation; **empty string** if unhelpful | Abstention sentinel `INSUFFICIENT` is the selective-augmentation analog      |
| Rate        | As low as 6% with small loss on LM + ODQA                                              | 8K/32K = 25%; 8K/128K = 6.25% later                                          |
| Tasks       | WikiText LM; NQ, TriviaQA, HotpotQA                                                    | Overlaps HELMET RAG; share those transfer sets                               |
| Transfer    | Compressor trained on one LM, tested on another                                        | Frozen Qwen is the reproducibility anchor; API readers stay a separate block |

## ACE / GEPA / DSPy

Evolving playbooks or prompts without weight updates. The identifiable analog
here is iterative search over the **finite** `PolicySpecV1` grammar with
byte-identical `RoundFeedback`. Do not give the researcher ACE's unbounded
playbook editor in the matched primary estimand.

## LongMemEval / v2

Official LME-V2: 451 questions, ~25M/115M-token haystacks, **200k reader
truncation**, accuracy–latency Pareto. That is transfer after A2, not a
difficulty repair. Lightweight 12×2 / 12×16 `answer_string_present` already
ran at $0 and cannot rank packers.

## What this changes in the current loop

1. Repair B query contract (HELMET-style output format; dense-profile analog).
2. Landscape tables must show accuracy **and** pack tokens / reader tokens /
   wall seconds (LongLLMLingua axes).
3. LongLLMLingua / RECOMP become method baselines on the same 32K→8K budget
   after the landscape is valid.
4. HELMET RAG/Recall and official LME stay **transfer**, after isolation.
