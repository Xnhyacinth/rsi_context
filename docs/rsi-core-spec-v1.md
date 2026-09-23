# RSI Core Specification v1 — the environment and evaluation that allow real self-improvement

Status: **frozen v1 for implementation** (2026-09-22). Inputs: the e7ec000
review, the 8013d6f review, the three-agent core review (repo inventory,
external-work survey, code gap analysis), and the post-fix live smoke.
This document decides the minimum that must be TRUE before any claim about
"recursive self-improvement" is measurable. It supersedes the ambiguous
parts of prior docs; where they conflict, this file wins.

Scope discipline: the nine research-v3 worlds remain the CALIBRATION
suite — they verify this spec's machinery, and nothing more. The main
benchmark task distribution (the 3-group A/B/C design from the 8013d6f
review) is OUT of scope here and lands in a separate spec once this core
is implemented. One thing at a time: environment and evaluation first.

---

## Part 0 — The conditions for a system-level strategy-improvement claim

v1.1 (review 2026-09-23): this Part is NOT a definition of "real RSI" —
the benchmark does not get to define the phenomenon by artifact form.
It states the EXPERIMENTAL CONDITIONS under which a claim of system-level
strategy improvement is interpretable on this benchmark. All five hold
for any such claim; the artifact form itself is open (memory content,
skills, call policy, or code — what matters is that behavior, measured
through the same channel, changed for traceable reasons):

1. **Policy surface is open**: the improver can change *behavior*, not
   set one of four config knobs whose combined reachable difference is a
   single boolean (gap report G2). The learned artifact is executable
   decision logic over observations, tools, and the model channel —
   whatever its form (memory, skills, code, or a mix).
2. **Actions have observable consequences**: the environment returns
   responses (verdicts, refusals, tool results) that the participant
   SEES and can act on within the same run (G1). Open-loop acting is not
   an environment.
3. **The control is honest**: the fixed baseline implements the task
   interface competently (verifies when needed, uses memory normally) and
   merely never updates its policy (G3). A strawman control measures the
   harness, not learning.
4. **Improvement is net of cost, under matched feedback and compute**:
   every arm's tokens/calls/wall time are ledgered through the same
   accounting (G9); improved arms are compared against matched-compute
   and matched-feedback alternatives (harness-evolution-eval's two rules).
5. **Evaluation is independent**: held-out tasks whose feedback never
   entered any improvement input (already implemented: dev/eval pool
   split), world identity + material hash recorded per cell.

Anything weaker than these five is calibration, and will be labeled as
such in every artifact and document.

## Part 1 — Environment core (the acting loop)

### 1.1 The turnstile becomes a loop

Current (to replace): `StageView → hook.on_stage → StageResponse →
env.apply → discard`. The seam is one-shot (runner.py:87/247/249 in the
gap report).

**New protocol — every action returns an observation:**

```
StageView(stage material + PENDING RECEIPTS)
  → participant turn (any number of tool calls, then one StageResponse)
  → per-action receipts + per-tool receipts, delivered in the NEXT view
```

Concretely:

- `ProjectState.apply(action)` returns a `Receipt` (record id, kind,
  outcome: applied / refused-with-cause, env-stamped fields for
  verification requests). Refusals are receipts, never crashes: a
  `ProjectStateError` inside the env becomes `Receipt(refused=True,
  cause=...)`. The run records it and continues.
- `StageView` gains `receipts: tuple[Receipt, ...]` — everything the
  environment said since the participant's last turn. This is the ONLY
  new channel; documents/prompts stay StageSpec-owned.
- The hook's `StageResponse.pack_text` stays (provenance/citation
  metrics still need it), and `actions` may now be emitted at ANY stage,
  which already works — what changes is that their results come back.

**Why this shape**: it closes gaps 1, 2-partially, 8-partially, and
10-partially with ONE structural change, and it is exactly the seam
Recuris exploits (working memory tracks what happened; skills gate what
to do next). Nothing else in the contract (freeze, branches, ledger)
needs to move.

### 1.2 The metered tool surface (the information diet is improvable)

New module `lifecycle/tools.py` — tools are stage-scoped, metered, and
env-answered:

| Tool | Semantics | Cost (ledgered) | Why it exists |
| --- | --- | --- | --- |
| `reread(doc_id, span)` | re-read a survey document the world showed at stage 1 — the cost the s1 prompt already promises | full input tokens + fixed overhead | gap G4: re-reading policy is a prime improvement target |
| `query_sandbox(filter)` | read back the participant's own records (incl. receipts) | output tokens of the answer | memory USE must be possible before memory POLICY is improvable |
| `request_verification(check, subject)` | already exists as an action; becomes also callable mid-stage with its receipt returned | one env execution, ledgered | the honest-evidence channel stays |
| `delegate(query, docs)` | a bounded sub-agent over the delegation surface; returns finding/source/applicability or "unusable" | full sub-agent token cost | the delegation stage stops being a document about itself |

Rules: tools are the participant's ONLY mid-stage channels; all tool
costs enter the arm's budget; the env answers from world data only (the
oracle stays evaluator-side, never serialized into views).

**The strategy file becomes the POLICY over this surface** (see Part 2):
when to reread, what to store, when to verify, when to delegate, how to
cite — these are no longer harness constants.

### 1.3 Strategy surface v2 (replace the 4-knob namespace)

The executable policy is a strategy module the harness imports per turn:

```python
# strategy.py — the researcher-authored policy (carried by snapshot)
def on_turn(turn: Turn) -> TurnDecision
```

`Turn` carries: stage kind, prompt, documents, receipts since last turn,
budget state, and TOOL HANDLES (callables). `TurnDecision` carries: the
tool calls to make (ordered), the StageResponse (pack_text + actions),
and memory writes. The harness hard-codes NOTHING that the old hook
hard-coded: note truncation/retention (160 chars / last 24) become
policy decisions; check derivation, verification timing, citation
choice, and the commit-time fallback all move into the policy.

**Back-compat**: `TrajectoryHook` and the 4-knob namespace keep running
untouched as the CALIBRATION profile (the 9-world suite). They are the
reference participant for the machinery, not a competitor arm.

### 1.4 Isolation boundary (honest about what it is and is not)

v1 implements a **restricted execution namespace** for strategy code:
no `open`/`__import__`/`os`/network (capability-scan at freeze time +
`exec` with a controlled builtins set; imports resolved from a whitelist
of stdlib modules: json, re, math, statistics).

v1.1 correction (review §3.6): this is a **hygiene filter, NOT a
security boundary** — Python underscore attributes are not access
control, regex scans are not confidentiality, and a policy object
holding a live ToolSurface can reach the env object. It is adequate for
internally-trusted calibration policies only. For open participation
and machine-authored code, a process/container boundary with controlled
RPC between participant and evaluator is REQUIRED (reusing the existing
worker/infra plumbing, not a new platform); the restricted namespace
remains as a first-line lint. Official runs additionally isolate whole
experiments regardless.

### 1.5 Budgets v1 (registry-consistent, one source of truth)

All limits move to `configs/budget_v1.json` and the code reads them from
one loader. Resolved values (deviations from registry now bug-flagged):

- worker (reader): max_output 2048 (registry 1024 → flagged INCONSISTENT,
  v1 uses 2048 for continuity with all live artifacts; reconcile before
  any main-benchmark run), temp 0.0, seed 42, timeout 300s
- researcher: max_output 16384, retry 5@10s, timeout 600s (as live)
- state byte cap 65536; snapshot per-file 1 MiB; feedback failures cap 32
- NEW tool metering: reread/delegate enter `B_serve`; their per-call
  overhead is fixed in this file; budget exhaustion is a NAMED outcome
  (run continues, tools refuse with receipts) — never a silent pass

`B_improve` (researcher+probes) and `B_audit` (re-evaluation) are
reported separately per arm in every artifact — the three-level split
the 8013d6f review specified.

## Part 2 — Evaluation core

### 2.1 Arms (the comparison set, fixed for v1)

| Arm | What it is | What it proves |
| --- | --- | --- |
| **reference** | scripted legal path (exists) | solvability |
| **strong-fixed** | full policy, implemented by us, never updated: verifies on receipt of a rule-change receipt, rereads when uncertain, delegates on demand | the honest control (G3) — S₁ must beat THIS, not a strawman |
| **experience-only** | strong-fixed + memory writes allowed, policy frozen | value of accumulating experience alone |
| **researcher-improved** | strong-fixed as A₀; the researcher (DeepSeek v4.1-flash) rewrites strategy.py from dev feedback across rounds | the RSI arm |
| **matched-compute sampling** | same model+token budget as the researcher arm, spent on independent solution sampling instead of improvement | the harness-evolution-eval control |

The old "fixed = designed-to-fail" arm remains ONLY inside calibration
tests, renamed `weak-fixed`, so the existing 15 red-then-green tests keep
their meaning.

### 2.2 Metrics (three layers, no single number)

1. **Task outcome**: per-task pass/fail + task-specific quality (the
   gate); refusals/unverifiable verdicts are failures, never dropped.
   **Infra failures score ZERO** (Rethinking rule): a crashed cell
   counts 0/1 in every fraction — implemented in `_pass_fraction`
   (regression-pinned); a crash inflating the score by leaving the
   denominator is a measurement bug, not a policy.
2. **Improvement**: paired deltas (S₀→Sₙ, arms matched) with
   uncertainty; report per branch-kind: continuation / same-family
   transfer / structural transfer — never merged into one scalar. The
   primary delta form (AgentStream convention): with-state minus a
   matched no-evolution control on the identical backbone — S₁ minus
   strong-fixed, not S₁ minus weak-fixed.
3. **Cost & reliability**: B_improve + B_serve + B_maintain per arm;
   valid-artifact rate; failure taxonomy (endpoint, protocol, budget).
   Failures enter system-level results; quality-vs-cost is reported as
   the frontier, not one "better".

`gate_failure_counts` remains calibration-only (different worlds have
different check counts — not cross-task comparable).

### 2.3 Statistical honesty rules (frozen)

- Measurement noise (T2 floor), minimal-interesting-effect, and service
  validity are three different thresholds — the charter's conflicting
  sentences are superseded by this sentence.
- n = independent worlds/projects per claim; variants of one world and
  repeats of one call never count as n.
- Legal saturation (a legitimate 6/6) is reported as saturation, not
  hidden; difficulty rules like "no policy ≥ 0.90" are retired.
- Four acceptable outcomes for the improvement arm: improves / ties /
  regresses / strong-fixed already optimal. None is a gate to hide.

## Part 3 — Feedback contract (frozen)

Allowed into improvement inputs: stage prompts + documents shown, the
participant's own receipts/tool results, memory contents, run outcome
on DEV tasks (pass/fail + gate cause strings), resource usage.

Forbidden (enforced structurally, not by prompt): held-out task
identity, material, outcomes, or failure text; evaluator internals
(oracle contents, expected_state_delta, aliases); anything from
evaluation branches. The dev/eval pool split (already merged) is the
structural wall; the researcher round's feedback builder is the only
funnel, and it is audited by the same tests.

Assisted vs unassisted: v1 runs the researcher WITH the current
assisted task prompt (it names the failure mode) — reported as
"assisted improvement". The unassisted condition (task interface + dev
experience only, no diagnosis) is REQUIRED for any main-benchmark
claim and is implemented in v1's successor. Both are always labeled.

## Part 4 — What each external work contributed (provenance)

Survey sources (2026-09-22 literature subagent, primary arXiv pages;
abstract-level reads flagged): full multi-work survey now on file.

- **Recuris** (arXiv 2608.24876, abstract-level): the receipts/turn seam
  and "working memory tracks, skills gate, validation-gated localized
  updates" shape of Part 1.3/2.1. NOTE: the repo already carries a
  fidelity adapter (`src/rsicontext/participant/recuris_arm.py`,
  in-process, 22 offline tests, never scored on a world) — integrating
  it as a live arm is Part 5 next-round work, not new construction.
- **Rethinking the Evaluation of Harness Evolution** (2607.12227, full
  read): matched-feedback + matched-compute controls (the
  matched-compute sampling arm), held-out generalization rule, AND
  **infra-failures-scored-zero** — enforced below in Part 2.2 and in
  `_pass_fraction` (crashed cells count as 0, never dropped).
- **Evo-Memory** (2511.20857, full read): streaming test-time-learning
  protocol, order-effect checks, fixed retrieval-budget fairness; we do
  NOT claim "experience reuse across task streams" as novel.
- **MemoryArena** (2602.16313, abstract-level): candidate external
  validation surface for cross-session interdependence, phase after v1.
- **Dream-RSI** (2609.14858, full read — VERIFIED this round, correcting
  the earlier "unverified" label): exploration-policy-only improvement
  surface over a fixed executor; **replay-simulator** (off-policy
  scoring of candidate strategies against recorded execution trees +
  scheduled online revalidation) adopted as the eval-cost amortizer
  direction for later phases; cumulative-calls as a first-class cost
  metric.
- **MGM — Mendel Gödel Machine** (2608.07645, full read — VERIFIED this
  round): scaffold-code lineage with matched 200-eval/24-expansion
  budget contract; **freeze-artifact + zero-shot cross-benchmark/
  cross-model transfer** adopted for the evaluation protocol (the
  improved SNAPSHOT is the shipped artifact; report its zero-shot
  transfer, not the search process); lineage/provenance record.
- **AgentStream** (2608.00155, full read): Isolated/Sequential/
  Interleaved triad; **evolution-gain = with-state minus matched
  no-evolution control** as the primary metric form; mandatory
  cost-multiplier reporting.
- **FinEvo-Bench** (2608.06144, abstract-level): scene structure (N
  related tasks sharing one procedure; within-scene position effects as
  the transfer readout) — input to the main-task spec's A-group design.
- **PROCTOR / GuardrailLoop / ModularRSI / SIFT / RRSI** (Sep-2026,
  abstract-level): canary/cheat-trap tasks, hash-pinned eval contracts,
  named-module improvement-surface registry, two-tier feedback
  economics — noted for the main-benchmark spec, not yet committed.
- **OpenAI harness engineering** (post 403'd; mirror retrieval, date
  unconfirmed): feedback taxonomy (product behavior + telemetry +
  review), numeric perf budgets as acceptance — designs only.

Correction record: Dream-RSI and MGM were earlier marked "NOT
independently verified" when search tooling failed; the literature
subagent's primary-source reads landed after the spec was first
committed, and this section is corrected accordingly. Remaining
verification debt: everything is arXiv-preprint or blog (zero peer
review); Recuris/FinEvo/PROCTOR-family details are abstract-level.

## Part 5 — Implementation order (this worktree)

1. **DONE (2026-09-22)** — `Receipt` + `ProjectState.submit()` +
   `StageView.receipts` + runner drain/wiring; refusals are receipts,
   never crashes. Tests: `tests/test_rsi_core_receipts.py` (5).
2. **DONE** — tools module `lifecycle/tools.py` (reread / query_sandbox /
   request_verification / delegate) with `ToolBudget` metering.
   Tested via `tests/test_rsi_core_policy.py` (tool metering pinned).
3. **DONE** — policy surface `lifecycle/policy.py`: `Turn`/`TurnDecision`/
   `TurnActions` + restricted exec namespace (guarded `__import__`,
   capability scan, safe builtins); `PolicyHook` wiring. The
   STRONG-FIXED baseline policy: `lifecycle/strong_fixed_policy.py`.
   Tests: `tests/test_rsi_core_policy.py` (7).
4. **DONE** — budget pack `configs/budget_v1.json` + loader
   `lifecycle/budget.py` (registry 1024-vs-2048 conflict flagged, not
   silently resolved).
5. **DONE (baseline floor)** — `scripts/rsi_core_demo.py`: the
   strong-fixed arm over the full 9-world calibration pool.
   **Result: 9/9 passed, zero policy errors, zero tool calls** (the
   baseline needs no re-reads on this pool — worlds are solvable from
   the survey alone; the informative arms come with main tasks where
   tools are NECESSARY, not optional). The researcher arm, the
   experience-only arm, and matched-compute sampling land with the
   trajectory entry integration (next round).
6. **v1.1 DONE (2026-09-23, review of ab07c75)** — execution-entry
   completion, one acceptance test per review row (`tests/test_phase1_entry.py`):
   the metered model channel (`turn.ask_model` — policy-owned context and
   timing, harness-owned pool/budget/accounting; failures named), intra-stage
   recovery (`max_turns_per_stage` multi-turn loop; a refused action is read
   as a receipt and repaired within the stage), event-timing correctness
   (rule-change clock advances BEFORE the stage's observations — sync-tool
   and action verifications at the same logical moment now carry the same
   revision), historical reread (DocumentRegistry: everything legally
   revealed stays re-readable; future material unreachable by construction),
   budget ENFORCEMENT (ToolBudget caps refuse calls before execution and
   refused calls still meter; request_verification charged with unique
   sequential ids; note the v1 word-count estimates remain ENVIRONMENT
   UNITS, not model-bill tokens — real model usage is metered by the
   model channel from platform-reported usage).
7. **NEXT** — in the review's corrected order, run in PARALLEL:
   (a) one non-isomorphic MAIN-TASK longitudinal slice (A-group:
   persistent evidence synthesis — early material's conditions and
   exceptions must still drive later decisions; reread-vs-remember is a
   real trade) — its spec is a separate document;
   (b) the four-arm comparison: a strong MODEL fixed agent (same A0 as
   the update arm — reads, verifies, recovers; never updates), the
   UNASSISTED feedback-update arm (no "the failure is X, do Y" prompt;
   assisted stays a labeled diagnostic), non-adaptive strategy search
   (the `stateful_control` slot's first real implementation), and the
   REAL Recuris adaptation — which per the review is NOT today's
   `recuris_arm.py`: that module is a mechanism simulation (deterministic
   localizer replaces their Meta-Agent; delivery simulated; zero model
   calls). Asset maturity ladder now governs naming: interface
   placeholder / mechanism simulation / real implementation / main-entry
   wired / verified participation. `recuris_arm.py` = mechanism
   simulation (reclass: Recuris-style rule control, usable for pipeline
   calibration only); a real Recuris arm needs their Meta-Agent actually
   proposing edits from legal execution traces, memory actually entering
   the worker's context, and acceptance validated on real dev tasks.
   Two reported deltas: Δ_reference = J(S_k) − J(strong-fixed) and
   Δ_update = J(S_k) − J(S0-matched) (AgentStream-style matched
   no-evolution control, same backbone/permissions/budget).
   Deploy-time sampling stays a separate cost-quality control (candidate
   selection without hidden-answer access).
   The inventory's top-5 undecided list (world distribution, main
   metrics/statistics, process isolation, frozen F-schema, control arms)
   is the main-task spec's agenda, now open in parallel.
