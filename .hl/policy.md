# RSIBench-Context orchestration policy

```yaml
version: "1.0"
owner: "RSIBench-Context contributors"
updated_at: "2026-08-29"

objective:
  primary_goal: "Test whether general coding researchers can autonomously discover, predict, retain, and transfer a better frozen-reader context compiler than matched search under fixed feedback and resource budgets."
  non_goals:
    - "Joint semantic-policy and KV/system optimization"
    - "Unpinned model or dataset claims"
    - "Treating prescribed policies as researcher discovery"
    - "Skipping difficulty gates to report HELMET/LongBench numbers"
    - "Claiming strict RSI or the first evolving context/memory system after Recuris"
    - "Using synthetic tasks as the sole paper headline"

complexity_model:
  dimensions:
    breadth: { weight: 1.0 }
    depth: { weight: 1.2 }
    dependency: { weight: 1.0 }
    uncertainty: { weight: 1.1 }
    validation_burden: { weight: 0.9 }
  scoring_range: [0, 10]
  thresholds:
    low: [0, 3]
    medium: [4, 6]
    high: [7, 10]

routing:
  default_mode: "mixed"
  complexity_to_workflow: { low: "express", medium: "standard", high: "deep" }
  max_subagents: { low: 1, medium: 2, high: 3 }
  critical_path_policy: { delegate_immediate_blocker: false }

agent_roles:
  research: ["research_analyst"]
  code: ["worker"]
  debug: ["debugger"]
  review: ["reviewer", "security_reviewer"]
  writing: ["scientific_writer", "research_reviewer"]

quality_gates:
  research:
    require_primary_sources_for_technical_claims: true
    require_claim_evidence_matrix: true
    forbid_fabricated_results: true
  code:
    require_tests_first_for_behavior_changes: true
    require_branch_coverage_at_least: 80
    require_ruff_mypy_bandit: true
  experiment:
    require_replay_noise_gate: true
    require_matched_budget_controls: true
    require_hard_researcher_turn_timeout: true
    require_network_disabled_primary_researcher: true
    require_immutable_artifacts: true
    require_sealed_isolation_for_paper_claims: true
    require_real_public_primary_profile: true

validation:
  preferred_order:
    - "focused pytest"
    - "full pytest with branch coverage"
    - "Ruff"
    - "strict mypy"
    - "Bandit"
  fallback:
    - "Disclose unavailable external or GPU validation and do not upgrade the claim."

artifact_contract:
  study_contract: "docs/study-contract.md"
  trial_log: ".hl/trials.jsonl"
  summary: ".hl/summary.md"
  regressions: ".hl/regressions.md"
  failed_directions: ".hl/failed_directions.md"
  artifact_dirs:
    - ".hl/artifacts/logs"
    - ".hl/artifacts/traces"
    - ".hl/artifacts/replays"
    - ".hl/artifacts/golden"

safety:
  destructive_ops_require_confirmation: true
  network_research_allowed: true
  secrets_handling:
    - "Never print or persist API credentials."
    - "Never send private sealed data to an unapproved remote API."
  acquisition:
    - "Review registry dry-run before any large download."
    - "Use only pinned artifacts for reported experiments."

review_loop:
  enable_critical_major_block: true
  max_rework_rounds: 1
```
