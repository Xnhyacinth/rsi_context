# RSIBench-Context project rules

- Preserve the three-way boundary: researcher, editable context policy, frozen
  reader/evaluator. Do not let policy code answer questions or modify serving,
  decoding, metrics, or labels.
- Researcher-editable files live only under top-level `policy/`. Candidate
  policy directories contain Python files only and must pass `PolicyAuditor`.
- Visible data may expose item failures and gold evidence. Gate and sealed
  questions, labels, seeds, and item-level scores are evaluator-only.
- Large models, datasets, and upstream repositories are acquired only from
  `configs/registry.json` after reviewing the dry-run plan. Never follow an
  unpinned upstream branch in a reported experiment.
- Keep the semantic-policy and KV tracks separate. Single-reader runs permit
  exactly one target-model call; adaptive runs must account for every target
  and auxiliary call.
- Use the project-local `uv` environment. Wrap every GPU command with
  `/workspace/wynckeliao/ops/gpu/hold.sh wrap ...`.
- Run pytest with branch coverage, Ruff, strict mypy, and Bandit before merging.
