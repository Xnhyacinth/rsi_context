# R3 next execution plan and common workspace contract

Status: active **offline preflight**. This plan does not authorize live
model-authored policy execution or a scored A/B/C comparison. Its common
source baseline is Git commit `7052c06494c37bed22fe14bdf929c20b3c9c6e29`.
The machine-readable settings and byte hashes are in
`configs/r3_gate1_offline_preflight_v3.json`; run
`uv run --no-sync python scripts/verify_r3_gate1_preflight.py --resource-root
<snapshot-directory> --require-clean` from a committed worktree before an
experiment. The verifier checks the exact lock/config/resource bytes, Python
interpreter, Git ancestry, and clean runtime source. It always reports
`live_ready=false` for this version. The earlier v1 and v2 manifests remain
in Git as historical preflight snapshots; v3 also pins the newly registered,
independent-source candidates. Both pinned source repositories were acquired
and verified after the v3 preflight; neither has yet become a qualified task.

## R4 active goal, starting 2026-09-25

Success for this phase is a reviewed development-only candidate from each new
source, a versioned B/C budget that no longer fails its own scripted demand,
an evidence-backed decision on whether this host can jail untrusted policy
code, and a clean integration into `main`. These are admissions to later
experiments, not a scored researcher comparison.

All R4 worktrees start from `d7cd47771b76775e23b93fc84cde4bace5ec39f6`,
use `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and `uv sync --extra dev --frozen --link-mode copy`, and read the same detached
source checkouts recorded in
`artifacts/rsi-core-v1/r3-gate2-source-acquisition-20260925.json`.

| Branch / worktree | Ownership | Admission evidence |
| --- | --- | --- |
| `work/r4-otel-parent` / `r4-otel-parent` | One independent OTel A development world and source ledger | Reference path, source and verification interventions, selected-file hashes |
| `work/r4-k8s-parent` / `r4-k8s-parent` | One independent KEP-753 C development world and source ledger | Prior-write dependency, scoped revision, source and verification interventions |
| `work/r4-isolation` / `r4-isolation` | Host jail feasibility and security tests | Malicious policy cannot read secrets/evaluator files or use direct network; otherwise live remains closed |
| `work/r4-budget-integration` / `r4-budget-integration` | Versioned B/C budget/profile and integration review | Same identity, frozen settings, cap feasibility, usage accounting, all required checks |

R4 budget/profile capacity qualification completed offline at `803b7b1`:
40 scripted worker requests per full development run fit the old B/C calls,
with a separate 2,048-output-token Siflow worker profile. A tracked portable
manifest now pins both source repositories and selected files. No provider
canary or model call has been made. The host jail feasibility report found
useful primitives but no typed broker or staged low-privilege runtime; live
policy execution remains closed.

The reviewed OTel/K8s task/score mismatches were corrected. A versioned
candidate-only inventory now records two new source lineages, 114 and 102
source whitespace words, zero qualified independent parents, and zero model
calls. The active B/C budget v2 pins separate Siflow worker/researcher
profiles and a portable call-count projection; scripted capacity passes, but
provider canaries, policy isolation, and new-parent call demand remain open.

The next action is to design longer source-grounded development tasks and
measure fixed-reader difficulty, while implementing the jailed runtime and
typed broker. Admit no parent or scored run from a scripted reference alone.

## Initial state and workspaces

| Responsibility | Branch/worktree | Owned output | Shared starting state |
| --- | --- | --- | --- |
| Candidate execution boundary | `work/gate1-isolation` / `gate1-isolation` | isolation gate, tests, broker feasibility | commit `7052c06`, frozen lock |
| B/C researcher usability | `work/gate1-bc-pilot` / `gate1-bc-pilot` | B/C offline admission and bounded pilot entry | same commit and lock |
| Parent task qualification | `work/gate2-qualification` / `gate2-qualification` | parent inventory, intervention checks, rejection reasons | same commit and lock |
| Protocol and integration | `work/experiment-coordination` / `experiment-coordination` | manifest, evidence schema, merge checks | same commit and lock |

Every worktree was created from that commit and ran
`uv sync --extra dev --frozen --link-mode copy`. The shared development
snapshot is read-only at
`/volume/pt-dev/qjiu/rsi_context_worktrees/resources/r3_visible_dev_7052c06/`.
It holds one minimal `a-dev-feedback.json` with A baseline development
instance ID, decision outcomes, and failure strings; it contains no eval
records or model transcripts. Its SHA256 is in the manifest. The original
full R3 live artifact was removed from the shared resource path after an
audit found evaluator-side rows in it. Gate/sealed questions, labels, seeds,
and item-level scores do not enter this replacement snapshot. Each branch
writes its own ignored artifacts and must
record their hashes; no agent writes to the snapshot or another branch.

The effective development model setting proposed for B/C is two planned
researcher draws per group, one request per draw to
`deepseek-ai/deepseek-v4.1-flash` with thinking disabled and an 8,192-token
output cap, followed by `Qwen/Qwen3.6-27B` worker calls with thinking disabled
and a 2,048-token output cap. Temperature is 0 and seed is 42. Candidate
submission requires exact-byte `PolicyAuditor` approval before loading. Every
attempt, invalid output, API error, cap refusal, and missing usage stays in
the planned denominator. No development or evaluation score selects a
candidate. The provider profiles still have `provider_revision=null`, so
requested model ID and model echo do not establish a fixed weight revision.

These values are **recorded development settings**, not a feasible live B/C
budget. The current 16-worker-call per-draw cap is below scripted full B and
C development baseline demand (31 and 18 calls). The reader profile declares
1,024 output tokens while `configs/budget_v1.json` and existing R3 runs use
2,048. A new versioned cap/profile contract is required before any B/C live
qualification; changing v1 in place would erase this admission failure.

## Claim–evidence map

| Claim to test | Required evidence | Independent unit and endpoint | Current status |
| --- | --- | --- | --- |
| The task needs earlier evidence, verification, and actions | Complete legal reference path plus decisive-text, verification, early-action, rule-scope, and irrelevant-text interventions | Parent project; later legal action/answer changes under the named intervention | B/C scripted action dependence now passes; 0 independent parents qualified |
| A researcher can deliver executable policy updates | Every planned draw counted; exact candidate audit; at least one correctly metered worker decision; no policy error | Development attempt; audited-and-exercised update rate, separate from task success | A v3: 2/2 executable under a narrower predeclared gate; prospective audit and isolation remain open |
| Experience improves an agent beyond fixed strategy and equal-budget search | Same parent, frozen reader/profile, task order, feedback and opportunity; distinct improvement and deployment costs | Paired parent-project completion difference, by A/B/C group | No valid efficacy estimate yet; old R3 B/C live values are invalid |
| Improvement retains and transfers | Frozen snapshots on unused parents and changed rule/source strata; replay of earlier parents | Independent parent lineage, not session/decision/mirror | No qualified held-out parent panel yet |

## Execution queue and admission decisions

1. **Execution boundary:** keep live model-authored Python fail-closed until
   a separate low-privilege candidate process has no credential, sealed file,
   or direct network access. The evaluator owns `ProjectState`, grading,
   `ToolBudget`, and API credentials; typed, length-bounded RPC brokers only
   visible observations and declared tool/model actions. A malicious policy
   must fail to read host secrets or evaluator-only material in behavioral
   tests. A static audit or user-supplied attestation string is insufficient.
2. **B/C offline admission:** prove session state continuity, arm-level
   Recuris delivery, named B failure feedback, complete decision vectors,
   candidate rejection before execution, and actual worker-call demand. Keep
   old flawed live B/C scores out of the input. Report the first infeasible
   cap and a prospective versioned replacement with matched opportunity.
3. **Independent parents:** inventory lineage IDs and material hashes. A
   mirror or parameter twin inherits its parent's ID. Reject a parent unless
   full evidence permits a legal solution, decisive removal changes the
   intended justification, an early action changes a later available legal action or answer,
   scoped revision distinguishes current from stale evidence, and irrelevant
   perturbation leaves the legal answer stable. B must cross a real session
   reset; C must depend on a receipt or write.
4. **Difficulty screen:** on *development-only* qualified parents, run a
   fixed strong policy and another reader family under the same budget. Inspect
   decision traces and wrong answers. Record saturation and top-two
   disagreement against the existing benchmark diagnostics; any inspected or
   revised parent remains development material.
5. **Formal freeze:** only after the above gates, version a statistical
   contract and immutable run manifest. Pair all arms on each independent
   parent; predeclare group-specific project completion, order seeds, retry
   and failure rules, the primary paired effect and clustered uncertainty,
   multiple-group interpretation, and the cost horizons for
   `C_improve + N·C_deploy`. Score no unregistered replacements or reruns.

## Row-level evidence required for a scored run

One row per parent × group × arm × phase × order seed must carry: lineage ID,
material SHA, code/lock/config SHA, exact delivered policy/package SHA,
requested and echoed model/profile plus available provider version, start/end
identity check, feedback visibility, candidate audit and selection outcome,
planned/attempted researcher and worker calls, provider prompt/completion
tokens including failed calls, tool ledger, per-decision outcome, project
completion, error class, and improvement/deployment cost. Session and
decision rows link to that parent row; they never inflate the independent
sample count. Unknown usage or model revision remains explicitly unknown.

Each branch is reviewed against its owned files and focused behavioral tests.
Before integration, run the repository pytest branch-coverage gate, Ruff,
strict mypy, Bandit, and `git diff --check`; preserve the existing two legacy
Bandit B102 live-run blockers in the disposition. Merge reviewed branches into
main only after dependencies align, push main, then remove merged branches and
their worktrees. Preserve ignored run artifacts by SHA, and do not delete the
root checkout's pre-existing `logs/r3-live.out`.
