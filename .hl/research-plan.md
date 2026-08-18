# RSIBench-Context research state

- Search cutoff: 2026-08-14 (UTC)
- Review type: systematic scoping review + benchmark/protocol design
- Primary question: Can a frontier researcher agent discover and retain better long-context policies for a frozen target model under a bounded, replayable interface?
- Decisive rivals:
  1. Researcher agents learn transferable policy structure.
  2. Gains are ordinary hyperparameter/task-level search under extra evaluation budget.
  3. Apparent improvement/regression is evaluator, serving, or sampling noise.
  4. Gains overfit visible tasks or exploit parametric knowledge / label leakage.
- Included: frozen-model prompt/program/harness/context/KV/memory evolution; long-context evaluation and causal evidence benchmarks; long-horizon agent context/memory compression.
- Excluded: model context-extension training alone; one-shot prompt engineering without iterative feedback; open-web QA where search-time contamination cannot be sealed.
- Required controls: matched evaluation/inference budget, task-level search baseline, historical-best, fresh held-out tasks, replay variance, causal evidence perturbations, sealed final test.
- Important newly found collisions:
  - Rethinking the Evaluation of Harness Evolution for Agents (2607.12227): matched test-time search and held-out generalization are mandatory.
  - HANDBOOK.md (2607.25398): deterministic long-context instruction-following over long tool horizons is a strong second-stage task.
  - HarnessCompass (2608.01918), Living-Harness (2607.26598): the 2026 harness-evolution frontier is moving beyond AHE.
