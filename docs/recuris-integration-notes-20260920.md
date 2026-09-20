# Recuris small-fidelity integration notes (2026-09-20)

Status: **review step 5 executed** — an external-method integration smoke, not
an effectiveness comparison. Implementation:
`src/rsicontext/participant/recuris_arm.py` (arm), `tests/test_recuris_arm.py`
(22 tests, offline, deterministic). Method source: the pinned checkout
`external/recuris` (Apache-2.0, arXiv:2608.24876). Per the external review,
effectiveness claims wait for frozen tasks and protocol; nothing here measures
Recuris, it demonstrates that the participant interface admits it.

## What was built

`RecurisStyleImprover` implements the `ImprovementProcess` protocol
(`participant/registration.py`) as an in-process, validation-gated memory
evolution loop. The improved object is a memory package `M = (E, W, rho, C)`
serialized as the agent data file `memory_package.json` — skills, config, and
workflows are valid state carriers under the participant interface, so agent
strategy code stays byte-frozen while the package evolves. Each round:
parse restricted feedback -> localize the failure to one component -> propose
one component-scoped patch -> run the validation gate -> emit the patched
package only on acceptance, plus ledger state and usage.

## Preserved vs. replaced mechanisms

| Recuris mechanism | Preserved as | Verified at |
| --- | --- | --- |
| Component taxonomy `M = (E, W, rho, C)` | `EEntry` / `WorkingMemory` / `InvocationPolicy` / `CheckerContract`, canonical-JSON package | `external/recuris/docs/architecture.md` §"M = (E, W, rho, C)"; `docs/skill-memory-format.md`; `src/recuris/metaagent/plan_schema.py` (`PATCHABLE_COMPONENTS`, `ACTIONS_BY_COMPONENT`) |
| Failure localization to one component | Deterministic localizer: stage failures -> E, usage anomalies -> rho, state-schema issues -> W | `plan_schema.py` Phase D cluster schema; `driver.py` round workflow |
| One edit per component per round | `_propose` emits at most one `PatchRecord`; `_apply_patch` replaces exactly one component | `plan_schema.py`: "Each cluster owns exactly one component" |
| Validation gate, model-free | `_run_gate`: accept only if the patch repairs its own failure AND replaying the previous round's feedback through the patched package newly fails at most `reg_cap` (default 0) previously repaired signals | `src/recuris/metaagent/gates.py`: "Nothing here consults a model"; `held_out_paired_gate` + `reg_cap` |
| Do-not-repeat ledger | `ParticipantState.ledger_blocks` on (component, action, target) | `gates.Ledger.is_repeat`; `plan_schema.ledger_key` |
| File-based cross-round memory, never model context | Package as agent data file; ledger + replay set as declared Sigma state | `driver.py` docstring: "Memory across rounds = files the driver injects" |
| Neutral deterministic seed | `neutral_seed_package()` (empty E, `reg_cap=0`) | README `--base neutral` |
| State-grounded invocation | `InvocationPolicy.delivered` (stage match + tracked-field grounding + per-stage cap) | README: "Working memory drives skill invocation"; `_base` manifest `need_driven_retrieval` |
| Card discipline (placeholders, provenance, no answers) | Card `source` = trigger signal id; template bodies with placeholder language only | `docs/skill-memory-format.md` §"The one prohibition" |

Replaced: their Meta-Agent (upstream LLM writing `plan.json`) -> deterministic
localizer + patch templates, because the mechanism under test is the loop, not
the diagnosis quality; their Claude-Code/driver campaign harness -> this
participant protocol; their paired held-out split with bootstrap CI ->
repair-plus-regression over the restricted feedback (the benchmark owns
evaluation; an improver may not run its own hidden comparisons); their
TurnRuntime in-turn delivery -> `delivered` as the deterministic simulation the
gate itself checks. No LLM is called; usage reports zero model tokens and real
wall time (honest for this build — a full adaptation carries its LLM tokens in
`usage`).

## What this proves

- The participant interface admits a Recuris-STYLE method with its core
  mechanisms intact — memory package, component-scoped patches, state-grounded
  invocation, validation-gated updates — as ordinary registration + round I/O.
  No benchmark rule, feedback schema, or accounting path changed: the arm runs
  through `qualify_registration` with an audit hook, and snapshot/billing/eval
  apply unchanged.
- Memory evolution travels entirely through the declared channels: the agent
  data file (`agent_files_changed`) and Sigma state (`state_update`), both
  re-validated on load, both under the byte cap.
- Agent strategy code is byte-frozen throughout (tests assert only
  `memory_package.json` is ever emitted).
- The gate's discipline is real: a non-repairing patch is discarded; a
  repairing patch that regresses a previously repaired signal is discarded; a
  rejected patch is never re-proposed (ledger). Each is a passing test.

## What this does NOT prove

- Effectiveness. No task stream, no scores, no comparison against any arm.
  The deterministic localizer is not their Meta-Agent; a fidelity smoke of the
  interface, not a replication of their results.
- That the restricted-feedback subset (`signals` list of stage failures, usage
  anomalies, state-schema issues) is the final F schema — it is a documented,
  tolerant subset; anything unparseable yields no signal and the round admits
  nothing (a valid outcome, per their loop's own semantics).

## Integration-cost notes (a full Recuris adaptation)

- **Their trace format**: `(w_t, E_t, a_t, o_t)` structured trajectories are
  what their localization actually consumes. Our restricted feedback would
  need a signals layer carrying stage-level failure attribution, or the arm's
  localizer stays weaker than theirs by construction.
- **Their checker LLM / user simulator**: their gates run on benchmark scores
  produced under pinned judges. Under our contract the evaluator is
  benchmark-owned, so the adaptation point is the repair predicate's evidence
  source, not the evaluator itself.
- **Their activation probe** (`metaagent/activation_probe.py`): offline
  "can this carrier fire" checks before anything is measured. Our build
  approximates this inside `_repairs` (a card repairs only if rho actually
  delivers it); a full adaptation would add the probe as a qualification gate.
- **Cost**: their evolution loop is LLM-driven (their paper: "evolution is the
  expensive step"); every token must land in `usage` / `C_improve`, which this
  arm's accounting path already carries.
