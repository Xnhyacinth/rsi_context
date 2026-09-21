# Recuris fidelity correspondence table (2026-09-21)

Status: **review round 4 §七 deliverable** — the 适配对应表 the external
review requested in place of adding more algorithm arms. Scope: what
"Recuris-style" ACTUALLY executes in this repo, at each of the four
mechanisms the review named (工作状态实际影响技能调用 / 环境证据实际控制状态
更新 / 定向修改 / 接纳与回归检查), with the deliberate changes stated.
Sources: `src/rsicontext/participant/recuris_arm.py` (the arm),
`external/recuris/src/recuris/metaagent/` (the pinned method checkout),
and the v3 trajectory surface (frozen-snapshot carry +
evaluator commit gate) the arm would run through.

## The correspondence

| Recuris mechanism (原方法) | Where it actually executes here (本实现执行位置) | Deliberate change (有意改变) |
| --- | --- | --- |
| **工作状态驱动技能调用** — W (working memory) gates which skill E fires per turn; their `ρ` reads state to decide delivery | `InvocationPolicy.delivered()` (recuris_arm.py:352-376): stage match + tracked-field grounding + per-stage cap — the same three-part rule as their `_base` manifest's `need_driven_retrieval`. The v3 TrajectoryHook consults strategy state (`choose_plan` reads STATE + survey text) through the equivalent seam | Their TurnRuntime is in-turn LLM delivery; ours is a deterministic simulation the gate itself checks — no model call inside the policy. State-grounding is tracked fields (the Σ schema), not free text |
| **环境证据控制状态提交** — checkers C decide when a conclusion may enter W | The **evaluator commit gate** (runner.py `_commit_gate_failures` + StageSpec.commit_precondition) and the finalize-lock (env v3): a verification record is only commit-grade if it carries the current protocol revision IN SCOPE; supersession requires a NEW record, never in-place revision. The participant-emitted Action preconditions mirror the same rule at apply time | Their checker is an LLM/user simulator under the method's own control; ours is benchmark-owned and deterministic — the adaptation point the 2026-09-20 integration notes named: the repair predicate's evidence source, not the evaluator itself |
| **定向修改** — the Meta-Agent localizes a failure to ONE component (E/W/ρ/C) and patches only it | `_localize` in recuris_arm.py: stage failures → E, usage anomalies → ρ, state-schema issues → W — deterministic, one component per round, `_apply_patch` replaces exactly that component. The v3 equivalent surface: the DS researcher edits one strategy file through `agent_files_changed` (validated safe-relative paths), and the snapshot carries code + memory EQUALLY | Their Meta-Agent is an LLM reading structured traces `(w_t, E_t, a_t, o_t)`; ours consumes the restricted-F `signals` subset (stage failures, usage anomalies, schema issues) — a documented tolerant subset. Trace-schema depth is the known fidelity gap: our signals carry stage-level attribution, not per-step traces |
| **接纳与回归检查** — a patch is admitted only if it repairs the source failure AND passes regression on the previous round's evidence (held-out paired gate, reg_cap) | `_run_gate` (recuris_arm.py): accept iff the patch repairs its own signal AND replaying the previous round's feedback through the patched package re-fails at most `reg_cap` (default 0) previously-repaired signals; the do-not-repeat ledger blocks (component, action, target) repeats | Their paired held-out split with bootstrap CI is benchmark-scored; under our contract the evaluator is benchmark-owned, so the gate runs over the restricted feedback only — the arm may not run its own hidden comparisons. The **v3 addition**: the S0→S1 trajectory now measures what the gate cannot — unseen-world branches under the evaluator gate, with crash-vs-pass distinguishability (strategy_errors) |

## What this table establishes (and does not)

- The four mechanisms are executable code paths in this repo, each with
  file:line — not component names on a data file. The 2026-09-20
  integration notes' question ("仅同名字段不够") is answered at the
  mechanism level: state-driven invocation, evidence-controlled state
  commit, one-component patches, repair-and-regression admission.
- **Effectiveness remains unclaimed** (the integration notes' standing
  boundary): no Recuris-arm run has scored on any world; the
  fidelity-table claim is interface-level, exactly as the review's
  "现在应做保真检查" asked.
- The nearest-fidelity gap is trace depth: their localization consumes
  `(w_t, E_t, a_t, o_t)` structured trajectories; our F-schema carries
  stage-level signals. Closing it is a feedback-schema extension, not a
  rewrite — the signals layer would carry per-step attribution.
- MGM: per the 2026-09-20 review, ordinary DS JSON-file editing does not
  represent MGM (cross-task, cross-lineage comparative editing) and no
  arm claims it.
