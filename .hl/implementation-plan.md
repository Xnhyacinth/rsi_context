# RSIBench-Context implementation state

- Started: 2026-08-14
- Objective: implement the frozen-reader context-policy RSI benchmark skeleton,
  deterministic toy campaign, registries, researcher adapters, and verification.
- Environment: project-local uv environment; all GPU jobs use the workspace hold wrapper.
- Current phase: executable harness and independent-review hardening complete.
- Deliberately deferred: large model/data downloads, private sealed dataset contents,
  official task/optimizer adapters, process-isolated evaluation, and full GPU campaigns.
- Acceptance: unit/integration tests, strict mypy, Ruff, Bandit, >=80% branch coverage,
  and an end-to-end toy research trajectory producing immutable artifacts.
- Implemented checks: 8xH200/disk/HF/hold preflight; toy RSI `0 -> 1 -> 0` with
  zero replay variance; content-addressed lineage; strict manifest/security audit;
  Qwen/Llama vLLM dry-run profiles; private counterfactual generator.
- Pinned local code checkouts: RULER, HELMET, LongMemEval-V2, and GEPA. GEPA import
  and LongMemEval validator CLI pass. RULER and HELMET require isolated optional
  dependencies (`nltk` and `rouge_score` were the first missing imports).
- Review hardening completed: exact policy-import allowlisting; trusted compressed-note
  provenance; calibration class-order fix; researcher prompts moved to stdin; Codex
  user rules and Claude settings disabled; usage/cost parsing now fails closed.
- Independent review found no remaining must-fix within the explicitly declared harness scope.
- Reader network boundary now uses an opener with an empty proxy map, a redirect-rejecting
  handler, and a 1 MiB response cap; focused tests and static checks pass.
- Run and serving specs now reject coercive/unknown inputs, boolean numeric fields,
  non-finite budgets, and mutable model revisions; focused suites and static checks pass.
- Evaluations now require fresh evaluator-owned policy instances, reject empty/duplicate
  item sets and invalid scorer domains, and bind manifest predictions to the complete item set.
- The counterfactual fixture now uses opaque policy-facing IDs, three genuinely distinct
  template families, natural two-hop facts with multiple competing values, and no literal
  answer marker. Its Python container is explicitly evaluator-side, not a sealed-data sandbox.
- Reader responses now carry endpoint-reported input/output usage; toy manifests record measured
  usage rather than constants. Run identity includes a serving-profile hash and every policy
  budget field, with canonical reader/policy budget derivation.
- Finite grid search consumes only the budgeted Cartesian prefix; random search samples product
  indices without materializing the full grid. The integration suite passes 165 tests at 83.32%
  branch coverage; Ruff, strict mypy, full Bandit, lock, and environment checks pass.
- Documentation now separates completed harness capabilities from unimplemented official task,
  optimizer, model-weight, long-horizon, and independently hosted sealed-data work.
- Independent review narrowed the executable contract to `single_reader`: adaptive/KV and reread
  now fail explicitly. Endpoint-reported usage enforces output and full model-length limits.
- Boundary collections are normalized to immutable tuples/frozensets; direct reader/serving
  constructors validate booleans, finite values, callability, and immutable host allowlists.
- Policy audit rejects obvious cross-item state (global/nonlocal, module/class mutable values,
  shared attribute mutations, stateful decorators, and mutable defaults). Formal sealed runs
  still require process isolation because AST checks cannot prove arbitrary Python purity.
- Serving-bound readers now cross-check the run specification against the exact registered
  profile and model revision. Formal state isolation still requires the planned per-item/replay
  process runner; fresh in-process object identity is only a smoke-test guard.
- The canonical single-call reader caps its request timeout at the run wall-time budget;
  aggregate runner timing and a complete call ledger remain explicit paper-scale work.
- Tencent `hy3-ioa` strict SSE support, an unversioned API profile, and a credential-free
  repeated canary record are implemented. It is an API replication reader; pinned Qwen
  remains the reproducibility anchor until the provider exposes an immutable revision.
- The first real API gates are complete: the controlled 8K/32K position matrix is 18/18
  correct with zero score/usage replay variance, and the prescribed 8K policy trajectory
  scores `1/3 -> 3/3 -> 1/3` with zero lexical replay variance. These qualify the dynamic
  locus but are explicitly not researcher-agent discovery results.
