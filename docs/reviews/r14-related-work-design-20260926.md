# R14 related-work check and benchmark consequences

Status: primary-source literature check for experiment design, not a novelty
or performance claim. Checked on 2026-09-26; the task and result facts below
come from the cited papers' author abstracts. The proposed RSIBench changes
are inferences from those facts and from the current R13 gate evidence.

| Work | Author-stated evaluation target | Consequence for this benchmark |
| --- | --- | --- |
| [HANDBOOK.md](https://arxiv.org/abs/2607.25398) | 65 agentic tasks governed by long policy documents; task-specific alterations to decisive rules, with programmatic required/prohibited-action criteria | **Inference:** keep the R13 authentic-source pairs, but add separately labeled constructed rule counterfactuals whose exact changed clause and unchanged other cues are hashed. Score complete action chains, including prohibited actions, rather than key recall alone. Do not call a source swap a new independent parent. |
| [MemoryAgentBench](https://arxiv.org/abs/2507.05257) | Incremental multi-turn memory evaluation spanning retrieval, test-time learning, long-range understanding, and selective forgetting | **Inference:** require a reset and bounded carry in B/C, plus no-carry and stale-carry controls. A one-shot source-key question cannot establish an improvement in a persistent context policy. |
| [LongMemEval-V2](https://arxiv.org/abs/2605.12493) | Context gathering from long experience trajectories for downstream questions about state, workflows, failures, and premise awareness | **Inference:** report retrieval/reader performance and researcher update effectiveness separately. Its context-gathering scores do not validate RSIBench's policy-edit loop, and RSIBench's constructed project receipts do not validate web-agent experience memory. |
| [Memory as Action](https://arxiv.org/abs/2510.12635) | A learnable memory-editing policy for long-horizon agent tasks | **Inference:** compare an editable context policy against fixed and retrieval-based context baselines under the same reader, call, token, and tool budgets; do not credit changed reader weights or serving settings to the policy. |

## Immediate evidence priorities

1. **Independent sources and real dependency.** PEP and KEP-753 intake should
   add parent lineages only after source, constructed request, private oracle,
   model-invoked source-free arm, and complete-project outcome are checked.
   More versions or paraphrases inside PG/OTel remain paired observations.
2. **Difficulty before RSI.** Freeze a question-general policy and a second
   reader family. Screen full-source solvability and fixed-choice shortcuts
   before spending on position, counterfactual, or researcher-update arms.
   A correct action after deleting one OTel table row is not row dependence
   while other normative mentions remain in the document.
3. **Update-rate denominator.** Register every researcher draw before any
   paid call. Report changed-and-audited submission, jail-exercised validity,
   and task success as different outcomes, with provider-reported target and
   auxiliary usage. A host trust refusal has no effective-update-rate estimate.
4. **Claim unit.** Summarize task results by source lineage and trajectory.
   A 16-row panel drawn from two repositories is not 16 independent sources;
   reserve aggregate uncertainty claims until additional parents and readers
   are measured.

This note does not change the frozen R12 experiment. The R14 PEP/KEP task
cards, if admitted, are inspected development material and cannot later serve
as an unseen sealed gate.
