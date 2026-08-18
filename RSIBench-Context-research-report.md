# RSIBench-Context 调研、碰撞审计与研究建议

**检索截止：2026-08-14**  
**建议 venue：NeurIPS Datasets & Benchmarks**  
**核心结论：值得做，但必须从“再发明一个 context optimizer”改成“测量研究员 agent 能否发现并保住可迁移的长文档 context policy”。**

## 1. 执行摘要

原方案最有价值的部分不是某个新的 `select/compress/order/verify` 算子，而是把以下变量同时控制住：外部 coding researcher、可执行 context-policy 制品、冻结 reader、密封迁移、同一制品回放、逐轮 discovery/retention，以及证据因果审计。到 2026-08-14，我没有找到一项公开工作同时覆盖这整个 protocol bundle。

但一般性表述已经被快速占位：

- [MCE](https://arxiv.org/abs/2601.21557) 已让 agent 在冻结模型上进化可执行 context skill；[Meta-Harness](https://arxiv.org/abs/2603.28052)、[AHE](https://arxiv.org/abs/2604.25850)、[Self-Harness](https://arxiv.org/abs/2606.09498) 和 [HarnessCompass](https://arxiv.org/abs/2608.01918) 已让 agent 修改完整 harness 程序并做验证、迁移或回滚。
- [EvolveMem](https://arxiv.org/abs/2605.13941) 已经采用“逐题失败日志 → LLM 诊断 → 修改完整检索配置 → best-so-far/revert”的 AutoResearch 循环；[SelfMem](https://arxiv.org/abs/2607.03726) 已在 BEAM 100K–1M 上反馈驱动地优化 memory strategy，而且中间 best 高于 final，直接出现 discovery–retention gap。
- [PAST-Bench](https://arxiv.org/abs/2608.04003) 已用 matched persistence-on/off 和 fresh-session tasks 隔离“保留经验是否使后续行为变好”；[SHAPER](https://arxiv.org/abs/2608.11350) 又在 2026-08-11 演化冻结 planner/executor 外部的 skills 与 context-code harness。
- [Context Assembly as the Controlled Variable](https://arxiv.org/abs/2607.25408) 已明确形式化 frozen inner policy 与 outer context-assembly policy。因此不能声称首次把 context policy 当独立控制变量。
- [Rethinking the Evaluation of Harness Evolution](https://arxiv.org/abs/2607.12227) 表明：若不匹配总推理/反馈预算，不分离 train/validation/test，所谓 harness evolution 增益可能被 parallel sampling、sequential refinement 或 task-level scaling 打平；其不相交划分上的平均测试增益只有约 0.6 个百分点。

因此，建议论文只声称两类贡献：

1. **基准与鉴定协议**：研究员—context policy—冻结 reader 的有界接口；可见、promotion gate、一次性 sealed test 三层数据；回放噪声地板；证据因果审计；匹配搜索预算的参考研究员；静态长文档与离线 agent trajectory 两个清晰分轨。
2. **经验规律**：不同 frontier coding researchers 的 discovery、peak regression、选择后悔、预测校准和跨长度/任务/骨干迁移；historical-best 或 stopping/gating 到底能补上多少缺口。

论文不应声称新进化器、长上下文 SOTA、首次冻结模型进化 context、首次角色隔离、首次程序化 policy、首次 manifest/rollback，也不应把 128K 静态 QA 的改善直接解释为广义 long-horizon agent capability。

## 2. 搜索方法与证据边界

本轮按对象而非论文标题检索了四条文献链：

1. 自动 prompt/program/workflow/harness 改进与 RSI；
2. 静态长文档理解、RAG、压缩、递归阅读与 long-context benchmark；
3. 对话/轨迹 memory、长时域 agent、跨 session persistence；
4. KV-cache 预算、位置分配和推理系统可复现性。

优先使用 arXiv/ACL Anthology/PMLR/OpenReview、作者项目页、官方代码、模型卡和 vLLM 文档。博客或二手页面只用于发现候选，不作为关键结论的唯一证据。检索特别覆盖 2026 年 7–8 月的新增工作。由于该领域日更很快，这是一份截至截止日的结构化 novelty audit，而不是对未来提交时新论文的保证；投稿前必须再做一次封闭检索。

## 3. 先校准术语：这是不是严格 RSI

建议把相关系统分成四层：

| 层级 | 被改变的对象                                     | 例子                                   | 是否严格递归                                            |
| ---- | ------------------------------------------------ | -------------------------------------- | ------------------------------------------------------- |
| L0   | 单题内的反思、重读、搜索轨迹                     | Reflexion、ReadAgent、RLM              | 否，只是 test-time computation                          |
| L1   | 可持久化 prompt、memory、context policy          | ACE、SelfMem、EvolveMem                | 通常是有界 artifact improvement                         |
| L2   | 可执行 agent/harness 程序                        | DGM、Meta-Harness、AHE、Self-Harness   | 更接近 system self-modification，但改进者能力未必被改进 |
| L3   | 改进机制自身或模型权重，且改进提升下一轮改进能力 | STOP 的理想化目标、模型—harness 共进化 | 才接近严格 recursive self-improvement                   |

RSIBench-Context 中，研究员 agent 改的是 $H_t$，不是研究员自己的研究能力。冻结的 $M_0$ 也没有变。因此它最准确的定位是：

> **对 RSI 所需“研究与改进外部制品”能力的隔离评测，或 bounded component-level self-improvement；不是已经实现严格 RSI。**

这与 [RSIBench-Data](https://arxiv.org/abs/2607.25886) 的谨慎定位一致：后者固定 post-training stack，评测 coding researchers 是否能通过数据制品改进下游模型。其 4 researcher × 6 benchmark 共 24 个 setting 中，14/24 超过首次有效尝试；在峰值后继续搜索的 23 条轨迹中，18 条最后一次低于峰值。它们是单 trajectory/setting 的描述性统计，不是“总体回退概率”的精确估计。

## 4. 相关工作全景：真正被优化的是什么

### 4.1 只评测长上下文模型，不研究 policy

- [RULER](https://arxiv.org/abs/2404.06654) 用 13 个合成任务测试 retrieval、multi-hop tracing 和 aggregation，适合固定 seed、位置和 gold 的低噪声诊断。
- [HELMET](https://arxiv.org/abs/2410.02694) 覆盖 retrieval、RAG、long-document QA、summarization 和 ICL，显示单一 synthetic NIAH 不能稳定代表所有现实长上下文能力。
- [LongBench v2](https://arxiv.org/abs/2412.15204) 有 503 道 8K–2M **words** 的四选一题；原始论文快照中 direct 最好约 50.1%，但它的答案公开，不能叫 sealed test。
- 2026 的 [LongBench Pro](https://arxiv.org/abs/2601.02872) 扩到 1,500 条、8K–256K tokens 和更细任务分层，同样是公开迁移集，不是密封集。
- [NoLiMa](https://arxiv.org/abs/2502.05167) 降低 query 与 needle 的词面重叠；[BABILong](https://arxiv.org/abs/2406.10149) 把带 supporting facts 的 bAbI 推理嵌入最长百万级背景；[Oolong](https://arxiv.org/abs/2511.02817) 更偏 dense aggregation，而不是找一根针。

这些工作为 task profile 和 gold instrumentation 提供基础，但没有研究员、可编辑政策或过程可靠性问题。

### 4.2 手写或训练出的长文档 reading/context 方法

| 类型                           | 代表工作                                                                                                                                                                | 对本项目的含义                                                                     |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 交互阅读/层次记忆              | [MemWalker](https://arxiv.org/abs/2310.05029)、[ReadAgent](https://openreview.net/forum?id=vRHrqXVTiQ)、[GraphReader](https://arxiv.org/abs/2406.14550)                 | 强手写 scaffold；答题模型在线决定读哪里，不是外部 researcher 研究可复用政策        |
| 多 agent 分解                  | [LongAgent](https://aclanthology.org/2024.emnlp-main.912/)、[Recursive Agent Harnesses](https://arxiv.org/abs/2606.13643)                                               | 多次模型调用与单次 prompt compiler 不能放在同一预算赛道                            |
| 长 RAG/主动压缩                | [LongRAG](https://aclanthology.org/2024.emnlp-main.1259/)、[CompAct](https://aclanthology.org/2024.emnlp-main.1194/)、[LongLLMLingua](https://arxiv.org/abs/2310.06839) | select/compress 的强参考实现；单算子本身没有 novelty                               |
| 递归代码阅读                   | [Recursive Language Models](https://arxiv.org/abs/2512.24601)                                                                                                           | 能处理 10M+ input，但每题可递归调用模型；应成为 adaptive-reread 单独赛道的强基线   |
| 训练出的 memory/context action | [MemAct](https://aclanthology.org/2026.findings-acl.956/)、[Memory-R1](https://aclanthology.org/2026.acl-long.583/)、[Context-Picker](https://arxiv.org/abs/2512.14465) | 改了 selector/model weights，不能与 frozen-policy 主结果混报，但应列概念或性能上界 |

单个 policy operator 也早已是拥挤赛道：selection 有 [Adaptive-k](https://arxiv.org/abs/2506.08479) 与 Context-Picker；compression 有 LongLLMLingua、[Selective Context](https://arxiv.org/abs/2310.06201) 和 [RECOMP](https://arxiv.org/abs/2310.04408)；RAG/full-context routing 有 [Self-Route](https://arxiv.org/abs/2407.16833)；verification/abstention 有 [Self-RAG](https://arxiv.org/abs/2310.11511)、[FLARE](https://arxiv.org/abs/2305.06983)、[CRAG](https://arxiv.org/abs/2401.15884)、[Adaptive-RAG](https://arxiv.org/abs/2403.14403) 和 [Sufficient Context](https://arxiv.org/abs/2411.06037)；ordering 的基础事实来自 [Lost in the Middle](https://arxiv.org/abs/2307.03172)。因此 `verify.py`、fallback 或“把证据放两端”都只能是可编辑面，不能单独作为方法贡献。

面向文档 agent 的后续工作也在扩展 scaffold：例如 [DocAgent](https://aclanthology.org/2025.emnlp-main.893/)、[OkraLong](https://aclanthology.org/2025.findings-emnlp.890/)、[IterCOMP](https://aclanthology.org/2026.acl-long.1559/) 和 [Agentic Context Strategies for Multi-Format Document Understanding](https://aclanthology.org/2026.acl-industry.133/)。它们强化了“routing、分块、工具读取和多轮压缩很重要”的经验前提，但没有把外部 coding researcher 的发现与保持能力作为被测对象。

### 4.3 Context/prompt/program/harness evolution

这一组是新颖性的主要威胁。

| 工作                                                                        | 可编辑面与冻结条件                                                            | 已覆盖的拟议要素                                            | 仍未覆盖的部分                                                                                        |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| [GEPA](https://arxiv.org/abs/2507.19457)                                    | 冻结模型，反射式 Pareto 优化 prompt/程序参数                                  | trajectory feedback、validation selection、低 rollout 优化  | 不是长源文档研究过程 benchmark                                                                        |
| [ACE](https://arxiv.org/abs/2510.04618)                                     | 冻结模型，生成/反思/整理 structured playbook                                  | context evolution、抗 collapse、在线/离线反馈               | context 是领域策略知识，不是固定超长原文的 allocation policy                                          |
| [MCE](https://arxiv.org/abs/2601.21557)                                     | 冻结 LLM，双层进化 CE skill 与文件/代码/context function                      | agent 写可执行 context 程序、parent/offspring validation    | 任务为领域知识/classification；没有低噪声 replay、密封长文迁移、多 researcher 比较                    |
| [Meta-Harness](https://arxiv.org/abs/2603.28052)                            | 冻结模型，proposer 搜索单文件 Python harness                                  | prompt、retrieval、memory、orchestration 的开放程序搜索     | 不隔离静态长文 context locus，也不以研究过程可靠性为被测对象                                          |
| [AHE](https://arxiv.org/abs/2604.25850)                                     | 固定 solver，改七类 harness 文件                                              | researcher/solver 分工、逐题轨迹、manifest、文件级 rollback | broad harness，环境/采样噪声，无同制品 replay floor；其 regression 预测很弱，正好可成为本基准指标动机 |
| [Self-Harness](https://arxiv.org/abs/2606.09498)                            | 冻结模型，自诊断并提 minimal harness diff                                     | failure clustering、regression validation、promotion        | promotion 所用 held-out 仍不是一次性 sealed test                                                      |
| [TTHE](https://arxiv.org/abs/2607.08124)                                    | 冻结 backbone，test-time 进化 executable harness                              | solver/proposer/judge 分工、population、selection regret    | transductive，在同 batch 搜索与计分；不是密封长文档研究                                               |
| [RHI](https://arxiv.org/abs/2607.15524)                                     | 固定 foundation model，优化多 agent harness                                   | 研究任务、communication/context flow、成本下降              | 开放式 ML research，不是长源文档 policy 的因果隔离                                                    |
| [HarnessCompass](https://arxiv.org/abs/2608.01918)                          | 冻结 GPT-5.4，componentwise harness evolution                                 | held-out/model transfer、manifest、回滚                     | 仍是 broad harness；削弱“既有工作无迁移”的说法                                                        |
| [Context Assembly as Controlled Variable](https://arxiv.org/abs/2607.25408) | 冻结 inner policy，bandit/RL 控制 prompt/demo/retrieval/planning/verification | frozen inner/outer context policy 的正式分解                | 小型固定动作空间；无 coding researcher、静态 32K–1M 文档、sealed process benchmark                    |
| [SHAPER](https://arxiv.org/abs/2608.11350)                                  | 冻结 planner/executor，演化 skills/context-code harness                       | 外部制品自改进与具身迁移                                    | broad embodied harness，不隔离长文档 context allocation                                               |

更早的 [STOP](https://arxiv.org/abs/2310.02304)、[OPRO](https://arxiv.org/abs/2309.03409)、[Promptbreeder](https://arxiv.org/abs/2309.16797)、[TextGrad](https://arxiv.org/abs/2406.07496)、[ADAS](https://arxiv.org/abs/2408.08435)、[AFlow](https://arxiv.org/abs/2410.10762) 和 [DGM](https://arxiv.org/abs/2505.22954) 已经占据 prompt、improver、workflow 或 coding-agent program 的一般自动优化位置。

其他 2026 年相邻信号也应在 related work 中交代：[Adaptive Auto-Harness](https://arxiv.org/abs/2606.01770) 处理开放任务流中的 routing/harness tree；[Living-Harness](https://arxiv.org/abs/2607.26598) 让 procedural memory 持续演化；[Co-Harness](https://arxiv.org/abs/2607.22688) 交替优化 harness 与 SFT weights，因 locus 混合而不是主对照；与 `2607.25408` 同作者的[配套系统论文](https://arxiv.org/abs/2607.25415)已在 tool workflows、HumanEval 和 HotpotQA 上实现小动作空间 controller。[ACE-GraphRAG](https://arxiv.org/abs/2608.01269) 虽曾直接声称 inference-time context policy 并覆盖 HotpotQA/2Wiki，但 2026-08-04 已因内部审查与授权问题撤稿，只能视为快速竞争信号，不能作为可靠实验依据。

最接近工作的定量证据也说明，“是否能改进”已经不是唯一有信息量的问题：SelfMem 从 default 0.472 到 final 0.497，但 historical best 为 0.510；EvolveMem 报告 LoCoMo 从 30.5 到 54.3，并内置 regression revert；AHE 在 Terminal-Bench 2 从 69.7% 到 77.0%，但其 regression manifest precision/recall 仅约 11.8%/11.1%。另一方面，[Rethinking Harness Evolution](https://arxiv.org/abs/2607.12227) 在严格不相交设置下只观察到平均约 0.6 个百分点的测试增益。剩余空间因此是**过程可靠性、科学校准、匹配预算和密封泛化**，而不是再次证明某一次 campaign 能涨分。

### 4.4 Memory 与 long-horizon self-improvement

| 工作                                               | 对象                                                                            | 与本项目最关键的关系                                                                                  |
| -------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| [SelfMem](https://arxiv.org/abs/2607.03726)        | BEAM 100K/500K/1M 的 memory operations 与 procedural strategy                   | 最接近直接碰撞：冻结模型、反馈驱动策略优化、held-out、非单调 best-vs-final 都已出现                   |
| [EvolveMem](https://arxiv.org/abs/2605.13941)      | retrieval scoring/fusion/query augmentation/budget/verifier 的完整配置          | “证据→诊断→改策略→外部验证→回滚”叙事已被明确实现                                                      |
| [EvoMemBench](https://arxiv.org/abs/2605.18421)    | in-/cross-episode × knowledge-/execution-oriented memory                        | 已从 self-evolving perspective 标准化比较 15 种 memory method；说明不能把 memory benchmark 本身当空白 |
| [PAST-Bench](https://arxiv.org/abs/2608.04003)     | 跨 fresh sessions 的 memory/skill/workflow persistence                          | matched on/off 与 mechanism evidence 是本项目应借用的鉴定思想                                         |
| [TACO](https://arxiv.org/abs/2604.19572)           | terminal observation compression rules                                          | 冻结 solver 下进化单一轨迹压缩算子，已占位                                                            |
| [SelfCompact](https://arxiv.org/abs/2606.23525)    | 何时、如何摘要 agent trace                                                      | inference-only；展示 compaction 可把 correct 翻为 wrong，支持 verify/retention 的必要性               |
| [BEAM](https://arxiv.org/abs/2510.27246)           | 100 个合成长对话、2,000 问、约 100K–10M                                         | 已被 SelfMem 用作主场，只能作迁移，不能再做论文标题                                                   |
| [MINTEval](https://arxiv.org/abs/2605.18565)       | 15.6K QA、平均 138.8K、最长 1.8M，包含频繁更新与干扰                            | 比静态 needle 更能测试 stale-state rejection 和多目标 aggregation                                     |
| [LongMemEval-V2](https://arxiv.org/abs/2605.12493) | 25M/115M WebArena/WorkArena 历史轨迹，Insert/Query→bounded context→fixed reader | 最适合把同一 context-policy locus 扩展到 agent trajectory，而不把 planner/tool competence 混进来      |

动态长时域还需要区分“上下文持续增长”和“长规则约束行动”。[LOCA-Bench](https://arxiv.org/abs/2602.07962) 让 context 在任务语义不变时持续增长；[VISTA](https://arxiv.org/abs/2606.30005) 用 typed blocks、dashboard 和可恢复 archive 做 training-free 管理；[AgentLongBench](https://arxiv.org/abs/2601.20730) 从环境 rollout 合成 31K–4M histories，并显示静态检索能力不等于 tool-response synthesis；[HANDBOOK.md](https://arxiv.org/abs/2607.25398) 用 20–124 页 SOP、65 个任务和 824 个程序化 criteria 测长规则在工具行动中的持续约束。这些更适合冻结 policy 后的迁移或第二阶段，不宜与静态 source-document 主分混成一个 construct。

### 4.5 KV-cache 与系统预算

[H2O](https://arxiv.org/abs/2306.14048)、[SnapKV](https://arxiv.org/abs/2404.14469)、[PyramidKV](https://arxiv.org/abs/2406.02069)、[Quest](https://arxiv.org/abs/2406.10774)、[KV-Compress](https://arxiv.org/abs/2410.00161)、[DynamicKV](https://arxiv.org/abs/2412.14838) 和 [EvolKV](https://aclanthology.org/2025.findings-emnlp.88/) 已覆盖全局/逐头/逐层/page-level 驱逐与进化式预算分配。[KVPress](https://github.com/NVIDIA/kvpress) 已提供统一实现框架。

必须把两个 construct 分开：

- **Semantic context policy** 决定 reader 真正看到哪些 token、以什么顺序看到；直接影响 prefill 和证据可用性。
- **KV policy** 往往先做完整 prefill，再决定 decode 时保留哪些内部状态；短答案 QA 的 decode 很短，cache ratio 未必转化成相同的端到端收益。

如果让 $H$ 同时改文本和 layer-wise KV，vLLM/platform 就不再是固定变量。建议 v1 只做 semantic policy；KV 另列 track 或后续论文。至少分别报告 TTFT、prefill GPU-seconds、decode TPOT、peak HBM、input/output tokens，并报告 cold-cache 与严格定义的 warm-cache。

## 5. 原方案中需要纠正的六个关键点

### 5.1 LongBench v2 不是 sealed

它的 503 道题和 `answer: A/B/C/D` 公开可下载。最多只能称“evolution loop 未见的一次性 public transfer”。真正 sealed 需要私有标签、私有 procedural seeds、网络隔离和评测服务器；而且公开模型可能已在预训练中见过公开题，单次不反馈也不能消除 contamination。

### 5.2 RULER v1 不应是唯一主适应度

RULER 的固定生成器非常适合 replay/noise、位置和 gold 因果诊断，但现代模型在一部分 8K/32K NIAH 已接近饱和。建议把它降为 P0 空区与校准；主 visible fitness 改为 RULERv2 medium/hard、HELMET exact-RAG、私有反事实 multi-hop，并加入 Oolong/BABILong 一类 dense aggregation，防止最优 policy 退化成 BM25 top-k 或一个压缩比。

### 5.3 `T=0` 不等于零噪声

vLLM 官方[可复现性文档](https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html)明确指出在线 `vllm serve` 不支持严格 reproducibility，调度和 kernel 都可能影响结果。应固定模型与 tokenizer hash、vLLM/CUDA/container、量化、TP/PP、batch order、seed、max tokens，并优先用 offline batched inference 建 noise floor；native-HF 与 vLLM 做一次交叉 replay。

### 5.4 Historical-best 必须区分三种含义

- `dev-best`：用可见 dev 选择候选，再一次性上 sealed test；可部署。
- `gate-selected`：用独立 promotion set 选择；可部署，但 gate 不能反复泄露给 researcher。
- `oracle hidden-best`：事后看所有 $H_t$ 在 hidden 上的最高分；只能诊断 discovery potential，不能称为 selection rule。

如果每轮在同一个 hidden panel 上打分再 keep-best，hidden 就已经成为训练信号。类似地，e-value 早停只有在预注册、sequentially valid 的 fresh audit stream 或合适 reusable-holdout 机制下才成立；不能给重复使用同一 dev set 的任意 adaptive search 直接贴上 e-value 标签。

### 5.5 Prefix cache 是实验变量，不只是工程优化

vLLM 的[Automatic Prefix Caching 文档](https://docs.vllm.ai/en/v0.22.1/features/automatic_prefix_caching/)说明，APC 只在请求共享前缀时减少 prefill，不减少 decode。query-specific selection/order 会破坏共享文档前缀。建议把 API 拆成：

```text
prepare(document) -> immutable artifact          # query-agnostic, 可缓存
assemble(artifact, query, budget) -> ContextPack # query-aware
verify(answer, ContextPack, state) -> Decision
fallback(artifact, query, state, remaining_budget) -> ContextPack
```

预处理成本要按一个文档被查询 $N$ 次摊销；同时报告 cold 与 warm，不能让 cache hit 变成隐藏奖励。

### 5.6 静态长输入不等于 long horizon

长时域行动还包含环境状态变化、延迟信用分配、错误恢复、主动工具调用和跨 session persistence。RULER/Hotpot 改善只支持“long-input context-policy research”。若要验证 long-horizon，必须另加保持同一 locus 的 trajectory track，再以冻结 $H^*$ 做 live transfer；不能把 Terminal-Bench/τ² 直接混进主优化循环。

## 6. 推荐论文：RSIBench-Context

### 6.1 最稳的标题和一句话问题

> **RSIBench-Context: Can Research Agents Discover and Retain Long-Document Context Policies under Frozen Inference?**

中文问题：

> 在冻结 reader 与低回放噪声下，当前 frontier coding researchers 能否研究出超过强手写/自动搜索基线、能迁移到密封任务的长文档 context policy；发现后是否会因继续搜索而退化；选择、停止和因果审计能补上多少缺口？

### 6.2 五个预注册研究问题

1. **Discovery**：researcher 是否超过首次有效 policy、强手写 hybrid、MCE/Meta-Harness/GEPA adapter，以及匹配评测预算的 random/Bayesian search 和 test-time scaling？
2. **Retention**：轮间下降是否显著大于同一 policy replay noise；last、dev-best、gate-selected 和 oracle-hidden-peak 的 gap 各多大？
3. **Scientific calibration**：researcher 对 fix/regression/unchanged 的逐题概率预测是否校准？
4. **Generalization**：收益能否跨长度、evidence topology、文档域和 backbone，而不是记住公开模板？
5. **External validity**：在冻结 policy 后，它能否改善离线 agent-trajectory context construction；是否进一步迁移到小规模 live long-horizon task？

### 6.3 三角色与有界接口

1. **Researcher $R$**：只能读取允许的源代码、可见 dev 轨迹、分数和成本；只能提交 `policy/*.py`、测试及 `manifest.json`。
2. **Context policy $H$**：通过 typed API 选择、压缩、排序、分配预算、验证证据和触发有限重读；只能返回 `ContextPack`，不能返回 final answer。
3. **Frozen reader $M_0$**：模型、tokenizer、chat template、系统提示、vLLM/container、解码、最大输出、metric 都锁定。

建议 `ContextPack` 至少包含：

```text
spans: [{document_id, start, end, text_hash, role}]
compressed_notes: [{source_span_ids, text}]
ordering: [span_or_note_id]
token_count: int
abstain: bool
request_reread: optional bounded query
```

这使 provenance、evidence recall、necessity/sufficiency 和越权审计都可执行。禁止 policy 修改 solver prompt、tools、decoder、metric，禁止网络、子进程和任意 benchmark import；匿名 item ID，并做 AST、文件和 syscall audit。否则 Python policy 可以硬编码标签、hash ID 或直接答题。

### 6.4 两个推理赛道

- **Track A：single-reader context compiler**。每题只允许一次 $M_0$ 调用；核心比较 selection/compression/order/budget。
- **Track B：adaptive reread/recursive**。允许 verify/fallback/RLM，但严格限制 target/auxiliary model calls、总 input/output tokens、GPU-seconds 和 wall time。

不分轨时，一个递归 scaffold 可用十几次模型调用击败一次 prompt compiler，结果没有解释力。

## 7. 任务与数据矩阵

### P0：噪声地板与空区

- RULER v1 8K/32K single-needle、固定和私有 seed。
- 目标不是 discovery，而是 replay variance、位置效应、停止校准和防泄漏。
- 饱和区的正确行为是停止；持续修改造成的下降单独计为 `null-zone harm`。

### P1：可见主适应度

建议三个互补 profile，而非只跑 NIAH：

1. **HELMET exact-RAG slice**：NQ/TQA/PopQA/HotpotQA，控制 gold passage 位置；现实检索与 exact metric 兼顾。
2. **[RULERv2](https://neurips.cc/virtual/2025/122399) medium/hard + Oolong/BABILong**：覆盖 retrieve-then-solve 与 dense aggregation，防止 genotype 塌成 top-k。
3. **私有 multi-hop distractor pack**：以 HotpotQA、2Wiki、MuSiQue 的 evidence graph 为原型，重新生成实体、数值、关系、文档名和 distractors；保留 minimal supporting set。

visible feedback 建议分两臂：black-box score only；instrumented dev（可见 gold evidence）。这样可测 gold instrumentation 是帮助科学诊断，还是鼓励过拟合标注格式。

### P2：证据因果审计

每题锁定五个条件，且不反馈为 fitness：

1. full context；
2. gold-only，测 sufficiency；
3. gold-drop，测 necessity；
4. no-context，筛查 parametric/guessing shortcut；
5. counterfactual，替换实体、日期、数值或关系，要求答案随证据改变。

[How Context Attribution Handles What the Model Already Knows](https://arxiv.org/abs/2607.23804) 指出现有 attribution 在知识同时存在于权重和 context 时难以分清 provenance。因此 gold-drop 后仍答对不能直接等同于“参数记忆”，还可能来自冗余证据、选项偏差或猜测；需要 minimal evidence、冗余审计和 counterfactual 联合判断。

### P3：真正的 sealed migration

不能直接使用公开 LongBench v2/Pro。理想方案是：

- 从新的开放许可长文档或合作方保留文档中构造 300–500 道 private questions；
- 同时含 sparse retrieval、multi-hop、dense aggregation、global comparison 和 insufficient-evidence；
- 人工验证答案与 minimal evidence；
- 按 document/domain family 切分，而不是随机按 question 切；
- researcher 容器无网络、无 test assets；server 只接收冻结 artifact，一次性返回最终分数。

[LongBench v2](https://arxiv.org/abs/2412.15204)/[LongBench Pro](https://arxiv.org/abs/2601.02872)、[InfiniteBench](https://arxiv.org/abs/2402.13718) exact slice、NoLiMa、[LIFBench](https://arxiv.org/abs/2411.07037) 仍可作为公开 one-pass transfer，但与 sealed 分开报告。

### P4：离线 agent-trajectory context policy

优先采用 [LongMemEval-V2](https://arxiv.org/abs/2605.12493) 的 `Insert/Query → bounded context → fixed reader` 构造，而不是再以 BEAM 为主场：

- 输入是不可改的 WebArena/WorkArena 历史轨迹 corpus 和问题；
- $H$ 只能构造带 provenance 的 32K/64K/128K ContextPack；
- 指标包括 reader accuracy、answer-bearing state recall、stale-state rejection、premise abstention、token/GPU-sec/latency；
- 因果仪器包括 answer-bearing state drop/keep、old↔new state swap、failure-trajectory-only 和 random trajectory negative control。

它测的是“从长期 agent experience 编译 bounded context”，仍保持 context locus。BEAM、MINTEval、AgentLongBench 可作补充迁移。

### P5：冻结后的 live external-validity test

只在研究结束后冻结 $H^*$，用 [MemoryArena](https://arxiv.org/abs/2602.16313) 或 PAST-Bench 式 fresh-session family 做小规模 matched `H on/off`：固定 host agent、prompt、tools、environment snapshot、simulator、seed 和 max steps；$H$ 只能选择/压缩/排序 observation-memory messages。结果标为外部有效性，不回流 researcher。

Terminal-Bench、τ²-Bench、OSWorld 可留给后续工作，因为它们把 context、planner、tool、recovery 和环境噪声强耦合，且与 TACO/AHE/Self-Harness 直接竞争。

### KV track：单列，不进主总分

若资源允许，用 EvolKV、SnapKV、PyramidKV、Quest、Expected Attention/KVPress 复现一个单列系统剖面；不要让 researcher 在 v1 同时编辑语义 policy 和 KV kernels/eviction。也不要把 semantic、trajectory、KV 三类结果压成一个总 leaderboard。

## 8. 基线：必须匹配的不只是轮数

### 8.1 固定 policies

- middle/head-tail truncation；BM25、dense、hybrid top-k；adaptive-k；full-context 高成本参考；oracle-gold selector 仅作诊断上界。
- 强手写 hybrid：query-agnostic index + query-aware retrieve/rerank + evidence diversity + deterministic ordering + bounded fallback。
- LongLLMLingua/Selective Context/RECOMP；ReadAgent/MemWalker；Self-Route/full-context retry。

### 8.2 参考研究员/优化器

- GEPA；ACE；MCE；Meta-Harness/AHE/Self-Harness 在同一 typed policy API 上的适配版本。
- SelfMem/EvolveMem 风格的策略优化器，尤其用于 trajectory track。
- random/grid/Bayesian search over 同一参数化 policy，匹配 external evaluation calls 与 GPU-seconds。

### 8.3 匹配 test-time compute 的非进化基线

受 [Rethinking Harness Evolution](https://arxiv.org/abs/2607.12227) 的直接警示，必须加入：

- best-of-$N$ / parallel sampling；
- sequential reread/refinement；
- fail 后 full-context retry；
- 同 verifier 次数的 task-level harness scaling。

若 agent evolution 只比一次 direct inference 强，而被同算力 sampling/read-again 打平，不能声称 discovery 优势。

## 9. 指标与选择协议

### 9.1 主要过程指标

- **Discovery**：在同预算和 sealed transfer 上，候选是否超过首次有效尝试与最强非-agent baseline。
- **Peak regression**：已经到达峰值且继续搜索的轨迹中，last 低于 peak 的比例；同时报告下降幅度，不只报二元比例。
- **Selection regret**：`last - oracle_hidden_peak`、`dev_best - oracle_hidden_peak`、`gate_selected - oracle_hidden_peak`。
- **Replay noise**：固定 $(H, M_0)$ 的 within-policy 方差；与 between-round 方差做 variance decomposition。
- **Generalization gap**：visible/gate/public-transfer/sealed 的差。
- **Cost-normalized gain**：sealed Δ / researcher tokens、target prefill/decode tokens、auxiliary calls、CPU indexing、GPU-seconds、wall time 和 peak HBM。
- **Null-zone harm**：饱和空区中继续研究造成的期望损失和额外成本。

### 9.2 Manifest 不应只是文字清单

要求 researcher 对每个可见 item 提交 `P(improve), P(regress), P(unchanged)`、置信度和声称依赖的 evidence/机制。使用 Brier score、log loss、ECE、fix/regression precision/recall 评分。这样才能避免“把所有题都列为可能改善”的投机写法，并直接承接 AHE 已暴露的 regression prediction blindness。

### 9.3 统计分析

- 每个候选与基线按题做 paired bootstrap/permutation；二元 accuracy 可辅以 McNemar。
- 跨 researcher、research seed、task family、backbone 用 hierarchical bootstrap 或 mixed-effects model，不能把所有题当独立重复。
- LongBench v2 的 503 题在 50% 附近，未配对近似 95% 区间约为 ±4.4 个百分点；小差异必须报告 paired CI，不能只给点估计。
- 若想把 $p≈0.78$ 的回退率估到简单二项 95% ±0.10，约需 66 条符合条件的独立轨迹；±0.08 约需 103 条。原设 4 researcher × 3 profile × 4 seeds = 48 条，而且并非都在峰后继续，精度不足；应增加廉价主骨干上的 research seeds，或把回退率明确标为 exploratory。
- 固定候选轮数和预算，预注册 primary endpoint、多重比较和 stopping。不要把 adaptive 试了很多 $H_t$ 后的最高分当无偏估计。

## 10. 骨干、推理与算力可行性

### 10.1 建议骨干

- **主 pilot：Qwen3.6-27B**。官方[模型卡](https://huggingface.co/Qwen/Qwen3.6-27B)给出 native 262,144 context、Apache-2.0 和 vLLM 支持，27B 适合先完成大规模 research-seed 统计。但它是 Gated DeltaNet + attention 的混合架构，不适合用来做通用 KV eviction 结论。
- **确认骨干：Llama-3.3-70B-Instruct**。官方[模型卡](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)给出 128K context；标准 GQA transformer 更适合做跨架构确认，但许可、显存和 prefill 成本更高。
- **备选：Qwen3-32B**。标准 transformer、开源许可更友好，但官方 native 32K，扩到 128K 依赖 YaRN，会引入 context-extension confound。

应冻结 exact revision、tokenizer/chat template、precision、quantization、vLLM/container 和 kernel。第二骨干只复评 selected policies，而非复跑全部研究循环，是更现实的设计。

### 10.2 分阶段预算，而不是一开始跑大矩阵

一个粗略量级：4 researchers × 3 profiles × 4 seeds × 10 rounds × 200 items × 64K input 已约 6.1B target prefill tokens，尚未算 replay、fallback、auxiliary compression 和 70B 确认。原矩阵在没有 pilot 的情况下风险很高。

建议：

1. **2 周 feasibility pilot**：1 个 27B、2 researchers、2 seeds、2 profiles、6 rounds、每轮 96 items、32K 平均长度，约 1.5×10^8 prefill tokens；测吞吐、OOM、replay、动态区间和 policy 复杂度。
2. **廉价主统计**：一个 27–32B 骨干、2 个主 profile、4 researchers、尽量 8–10 research seeds；固定 8 轮。用较小 dev panel 做迭代，用独立 gate panel promotion。
3. **70B 确认**：只跑 H0、最强手写、每个 researcher 的 dev-best/gate-selected 和 matched-search best；不重跑整个 evolution。
4. **sealed 和 live transfer**：每个冻结 artifact 一次；结果绝不回流。

在已知 GPU 型号、数量、精度、目标并发和文档复用率前，无法给可信美元/GPU-hour 总额。最先做的不是确定 16 周大矩阵，而是用 pilot 测 `tokens/sec、TTFT、peak HBM、APC hit rate、cold/warm delta`，再锁定预算。

## 11. 杀伤条件与 desk-reject 审计

以下任一项成立，都应缩题或停题：

1. fixed-policy replay 的标准差与典型轮间摆动同量级，无法把 regression 归因给研究过程。
2. matched-budget random/Bayesian search、parallel sampling 或 sequential reread 打平或超过最好 researcher，且没有更好的迁移/成本/校准。
3. visible 提升在真正 sealed 文档/domain split 上消失，说明主要是 benchmark/template overfitting。
4. 最优程序实际上只调 `top_k` 或压缩比；多算子交互消融不显著，完整政策研究的必要性不成立。
5. gold-only 太低或 H0/full-context 已饱和，骨干—任务组合没有可研究的动态区间。
6. sandbox/ID/network/file 设计不能排除 hard-code、标签读取或 policy 直接答题。
7. semantic policy 与 KV/cache 状态泄漏无法分离；warm-cache 差异主导成本或分数。
8. 符合 peak-regression 定义的独立轨迹太少，却仍试图复刻“78%”式总体结论。
9. static QA 是唯一证据，却在标题或摘要声称提升 long-horizon agency。
10. 提交前出现同时覆盖“外部 coding researchers + typed long-document policy + frozen reader + sealed process benchmark + replay/causal instruments”的新工作。

## 12. 三个候选研究方向的排序

| 方向                                      |                                           新颖性 |       可鉴定性 |        16 周可行性 | 建议                                                         |
| ----------------------------------------- | -----------------------------------------------: | -------------: | -----------------: | ------------------------------------------------------------ |
| **A. RSIBench-Context 过程基准**          |                               高，但必须窄 claim |             高 |               中高 | **主推**；D&B 论文                                           |
| B. 新 context evolution 算法              | 低，MCE/Meta-Harness/SelfMem/EvolveMem/GEPA 拥挤 |             中 |                 中 | 不做主论文；只有基准发现稳定缺口后再做 stop/gate/verify 方法 |
| C. 泛 long-horizon self-improving harness |   低到中，AHE/Self-Harness/TACO/PAST/SHAPER 拥挤 | 低，环境噪声高 |                 低 | 不与 Paper 1 捆绑；只做冻结后的 external validity            |
| D. Agent 写 KV policy                     |                 低，EvolKV 与大量 KV work 已占位 |             中 | 低到中，系统工程重 | 单列后续工作，不混进 semantic track                          |

## 13. 最小 Good Question Card

- **Question**：frontier coding researchers 能否在冻结 reader 下发现并保住跨任务有效的长文档 context policies？
- **Why now**：长上下文方法和 harness evolution 已爆发，但其优化器、模型、任务、噪声与选择规则彼此耦合，无法比较研究能力本身。
- **Stake**：若会发现但保不住，问题在 research selection/stopping；若完全不回退，RSIBench-Data 的 78.26% 可能主要受训练/环境噪声影响；若 matched search 打平，则“researcher agent”叙事需要降级。
- **Bottleneck**：不是缺少第六个 context 算子，而是缺少低噪声、密封、匹配预算、因果可归因的研究过程测量。
- **Wedge**：静态长文档的 source-to-context compiler，exact metrics 与 known evidence 使归因最干净。
- **Existence proof**：SelfMem、EvolveMem、MCE、Meta-Harness 已证明 agent 能优化相邻制品；RSIBench-Data 已表明 discovery/retention 是现实问题。
- **First experiment**：Qwen3.6-27B，HELMET exact-RAG + 私有 counterfactual multi-hop，2 researchers × 2 seeds × 6 rounds，三次固定-policy offline replay；同时跑 hand hybrid、Bayesian search、parallel/read-again。
- **Decisive control**：fresh sealed generator/domain split；matched total target/auxiliary calls 与 GPU-seconds；gold-only/drop/no-context/counterfactual 只做锁定审计。
- **Useful null**：没有 peak regression 说明训练噪声可能解释 RSIBench-Data 的一部分；agent 被 matched search 打平说明完整 coding researcher 暂无额外价值；两者都可形成 D&B 结论。
- **Stop rule**：replay variance 不可分、无 sealed transfer、policy 塌缩为单参数或发生 leakage，任一成立即停止大矩阵。

## 14. 16 周执行建议

### 第 1–2 周：可行性与噪声

- 实现 typed `prepare/assemble/verify/fallback` API、sandbox 与 provenance。
- 在 H0、手写 hybrid 和 2–3 个扰动 policy 上做 offline vLLM/native-HF replay。
- 找出 gold-only 不太低、H0/full 不饱和的任务—长度—骨干动态区间。
- 测 cold/warm cache、吞吐、HBM 和文档复用摊销。

### 第 3–5 周：私有任务与审计

- 建 RULERv2/HELMET visible panel；生成并人工核验第一批 counterfactual multi-hop。
- 完成 full/gold-only/gold-drop/no-context/counterfactual 管线。
- 冻结 dev/gate/sealed 划分、网络隔离、artifact schema 和预算账本。

### 第 6–10 周：主 research trajectories

- 跑 4 researchers 与 hand/random/Bayesian/GEPA/MCE/Meta-Harness adapters。
- 每轮记录 diff、manifest calibration、per-item flips、成本、replay audit。
- 固定轮数，避免“失败 run 早停、成功 run 多搜”的选择偏差。

### 第 11–13 周：selection 与迁移

- 比较 last、dev-best、gate-selected、oracle-hidden-peak。
- 一次性 sealed 评测；public LongBench v2/Pro/InfiniteBench/LIFBench 只作迁移。
- 选少量 policy 上 70B 骨干确认。

### 第 14–16 周：trajectory 与写作

- LongMemEval-V2 offline trajectory transfer；资源允许时做小规模 MemoryArena paired on/off。
- 完成 hierarchical CI、成本曲线、null-zone 和 causal evidence 报告。
- 投稿前重复最新文献检索；预注册“无 gap、hist-best 全修复、matched search 打平”同样报告。

## 15. 最终建议

应该做，但要把论文的中心从“agent 进化 context”移动到“agent 是否会做可复现、可保持、可迁移的 context-policy 研究”。静态长文档是最干净的第一性实验台；LongMemEval-V2 是把同一 locus 推向 long horizon 的最佳桥梁；live agent 环境只做冻结后的外部有效性。

最强的创新不在某个新算子，而在同时回答四个现有工作没有一起回答的问题：

1. 改进是否超过匹配算力的非研究型搜索/重读？
2. 峰后回退是否超过固定制品的回放噪声？
3. researcher 是否知道自己将修好或弄坏哪些题？
4. 改进是否能通过因果证据审计并迁移到真正密封的新文档、轨迹和骨干？

只要这四个问题被严谨回答，即使结论是“historical-best 已经足够”“agent 被 Bayesian search 打平”或“没有训练噪声后回退消失”，仍然是一篇有用的 Datasets & Benchmarks 论文。反过来，如果继续把 novelty 写成“首次冻结模型进化上下文”，在 SelfMem、EvolveMem、MCE、Meta-Harness、AHE、PAST-Bench 和 2026 年 8 月新工作之后，很容易被审稿人直接否掉。
