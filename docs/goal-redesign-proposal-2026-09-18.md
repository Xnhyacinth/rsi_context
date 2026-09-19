# Goal redesign proposal: unified long-horizon intelligence

Status: **proposal — pending owner ratification**. This document does not amend
`docs/study-contract.md`; it proposes the amendment. Date: 2026-09-18. Inputs:
protocol deep-reads of MGM, Recuris, Dream-RSI, SoL-Pi, ModularRSI,
2607.12227, 2607.14004; two landscape scans (RSI, long-context/memory/horizon
evaluation); full repo synthesis at commit `08ba26d`; fresh environment and
data qualification on 2026-09-18.

## 1. Why this document exists

Two months of build-out produced a hardened harness and zero paper-scale
trajectories. Meanwhile the 2026 RSI wave published: Recuris (2608.24876, Aug
25), MGM (2608.07645, Aug 7), ModularRSI (2609.14857, Sep 14), Dream-RSI
(2609.14858, Sep 14), SoL-Pi (2609.20519, Sep 17). The owner's directive:
re-derive the goal first — unified long-horizon intelligence (long-context
comprehension + memory + long horizon), any-API/model readers — and state
plainly whether the current project still has value.

## 2. What the 2026 wave actually does (verified protocols)

| Work | Improvement object | Frozen | Controls | Efficiency | Domain | Does NOT do |
| --- | --- | --- | --- | --- | --- | --- |
| MGM (2608.07645) | agent scaffold code; archive + contrastive operators (reaction-norm, cross-lineage) | base model (Qwen3.6-35B-A3B) | matched budget vs DGM/HGM; surrogate MC; no matched sampling arms | evals/expansions/wall-hours; per-operator tokens | SWE/Polyglot coding | no matched-search control; no long-context/memory tasks; no replay variance floors |
| Recuris (2608.24876) | memory-control layer (skills E, working-memory W, invocation ρ, checkers C); validation gate = in-loop regression control | base LLM, Meta-Agent, harness | layer-alone inside noise (−2.3, p=.824); mechanism ablations; noise floor; NO matched-search arms; own TTA headline attributed by its own authors to attempt budget, not learning | inference tokens/success; evolution-loop cost unreported | τ²-bench, SkillFlow, TB2.1 | no matched search; no long-context routing; single-source evolution |
| Dream-RSI (2609.14858) | exploration-policy code (branch/parallel/stop) over frozen coding agent; replay simulator over discovery history = zero-execution evaluation | models, evaluator, interfaces | Recursive-Fixed-Exploration matched baseline; prefix-observability constraint (≈ our selection-blind); NO seeds/statistics | cumulative discovery-agent calls (no tokens/$/wall) | Lasso paths, math, kernels | no statistical replication; no public reusable benchmark; no memory surface |
| ModularRSI (2609.14857) | five modules incl. **Context Management**, module-scoped edits | foundation models | 2,000 benchmark-disjoint evolution tasks; contrastive pooling; cross-model transfer | partial | TB2.0/SWE coding | no long-context/memory routing tasks; no replay protocol |
| SoL-Pi (2609.20519) | harness-layer RSI | base model | token-efficiency headline (44.7–49.0% traffic cut, ~1/3 cost) | first-class | coding | no matched-search identification |
| 2607.12227 | (evaluation study) harness evolution | — | **the control protocol**: matched-K direct/parallel/sequential/scaling; sealed 45/10/34; 2-run floor; infra-fail= fail | full | Terminal-Bench 2.1 | finds evolution ≤ parallel sampling; +0.6 held-out transfer |
| 2607.14004 | (evaluation study) optimizer compounding | — | in-loop regression control is the only compounding design (RELAI-VCL 76.4 vs GEPA 66.0, which transfers below baseline) | cost columns | Terminal-Bench 2 | — |

Shared grammar across the wave: **frozen base model; the improvement lives in
external code/memory/harness layers; feedback accumulates through a bounded
update loop.** That is exactly this project's core grammar — externally
validated. None of them publishes a reusable, replayable, matched-control
benchmark, and none covers the long-context/memory/horizon routing surface
(all cluster on coding/terminal/math). The wave is also accelerating: 19+
new RSI/harness-evolution titles appeared on arXiv between Sep 1–17 2026
alone (MetaRSI/RSI2 2609.06396 composes Data/Harness/Model-RSI operators on
one loop kernel; Guardrailed Meta-Agent Loops 2609.12216 pins policies and
budget bounds; Fragility of Self-Improving Agents 2608.18066 documents
variance/task-order/underspecification failure modes; Auditing Harness
Tampering 2609.00069). Methods are crowded; the measurement layer is not.

## 3. Honest value verdict

**As a method/system contribution: no value.** Building "a better memory or
context system" is subsumed — Recuris (memory), Dream-RSI (orchestration),
ModularRSI (context module), SoL-Pi (efficiency) own those lanes with more
results. Say this plainly and stop entertaining it.

**As the identification benchmark for the unified long-horizon surface: yes,
the slot is empty and the field needs it.** Five reasons, each verifiable:

1. The central 2026 dispute is measurement, not method: is an "improvement"
   search, noise, or retained capability? (2607.12227: evolution ≤ matched
   parallel sampling; 2607.14004: no compounding without regression control;
   Recuris's own TTA headline is attempt budget per its own authors.)
2. No evolution work evaluates on long-context/memory/horizon routing tasks;
   the LongMemEval-V2 / NoLiMa / MRCR surface has no evolution benchmark.
3. No public replayable benchmark with matched-search controls exists for ANY
   improvement locus; our instrument suite (selection-blind, replay variance
   floors, deterministic manifests, gold-drop/counterfactual instruments) is
   **designed to exceed** the published 2026 protocols. Honesty requires the
   split: executed today are replay-variance floors on qualification
   artifacts and the toy-campaign selector; 2607.12227 *executed* a sealed
   45/10/34 protocol with matched-K arms and a 2-run floor — stronger
   execution than ours so far. Sealed transfer, population regression rates,
   and matched-control arms remain built-but-unrun here. The design leads;
   the execution does not, yet.
4. Adjacent institutional measurement demand exists and is explicit: OpenAI's
   Preparedness Framework v2 maintains a "Critical" AI Self-Improvement
   threshold (visible via METR's Jun 2026 GPT-5.6 Sol predeployment eval);
   Anthropic's Sep 2026 "Measurements for understanding the pace of AI
   development inside frontier labs" post publishes an R&D Automation Index
   (Epoch AL0–AL5 scale; Claude performs 26% of Anthropic's own AI R&D, up
   from <1% in Feb 2026); METR's Aug 2026 funding update (~$71M commitments)
   names "tracking recursive self-improvement" as newly funded work. These
   institutions measure automation *share* and capability *trends* — adjacent
   to, not the same as, locus-level identification of "search vs noise vs
   retained capability". METR has published time-horizon methodology and the
   Sol eval; what none of them publishes is a replayable matched-control
   identification protocol. Adjacent demand, empty exact slot.
5. Our prior negatives (hy3 replay failure, sampling-saturated cells,
   five synthetic-panel qualification failures) are internal protocol
   evidence and a credibility signal that cells are killed when they fail
   gates — not a contribution class comparable to the published systematic
   negative-result studies (2607.12227, 2608.18066).

**Conditions of validity.** (i) The locus must actually widen to memory and
horizon (L2–L4 below) — otherwise "unified" is false advertising. (ii) The
execution bar is non-negotiable: n ≥ 16 items per cell, ≥ 2 research seeds,
replay ≥ 5, in-loop regression control as a named component, two-tier reader
registry. (iii) Speed matters, and the threat is symmetric across two directions: on
the methods side, Recuris's memory-control layer with validation gates is
the nearest collision — extending it from τ²-bench/TB2.1 onto
LongMemEval-style tasks is a smaller step than a ModularRSI pivot; on the
benchmark side, the LongMemEval-V2/NoLiMa/MRCR consortium crowd already owns
the task surface and could bolt on evolution tracking. The moat is
**executed** replay + matched-control identification on that surface; it
decays to zero within months if L2–L4 are not executed.

**Stated failure mode.** If the team cannot execute L2–L4 and the replication
matrix, the honest fallback is publishing the current narrow version as the
L1 cell of the family with the protocol contribution — not inflating the claim
to "unified".

## 4. Redesigned goal and estimand family

Normative question (proposed rewrite of `docs/study-contract.md:11-15`):

> Under a fixed reader family, evaluator, feedback interface, and resource
> envelope, can a general coding researcher discover, retain, and transfer a
> better long-horizon context/memory policy system — routing evidence across
> length, sessions, and horizons — than matched non-agent search?

**Locus ladder** (each cell its own leaderboard; never pooled):

| Locus | Contract | State | Status in repo today |
| --- | --- | --- | --- |
| L1 single-call compiler | one reader call per item, per-item policy; **L1 primary = the open-S track** — the restricted `PolicySpecV1` A2 executable is already launch-invalid pending the 2026-08-31 elastic-envelope rebuild (`study-contract.md:279-294`, `a2-preregistration.md:129-133`), so that track is deferred (not canceled) until the rebuild lands; the elastic rebuild enters Phase 0's work list if the owner wants the restricted track in the paper, otherwise its prereg is amended to superseded | none | current open-S surface; restricted A2 surface exists but its frozen plan hash is invalid |
| L2 session state | bounded persistent memory across items of a session (write/read, byte-capped, part of envelope `B`) | session-scoped | blocked by the per-item pin on `seeds/open_s_v1/memory.py` |
| L3 adaptive multi-call | bounded reread/verify with call ledger (tokens AND calls counted inside `B`); matched control = a fixed-reread orchestrator at the same call budget (Dream-RSI's Recursive-Fixed-Exploration is the reference); must close the repo's own rejected-direction hole ("no extra unlabeled target-model calls") — the ledger closes it or L3 does not launch | cross-item | provisioned as "separately budgeted future track" (`study-contract.md:86`); schema surface exists (`ContextPack.request_reread`, `VerificationDecision`) and is actively rejected by the single-reader enforcement; the 32-byte reread-query cap is a serious constraint to redesign; build is comparable in scale to L2 |
| L4 stratification instrument | a *reporting* instrument, never a standalone claim: per-stratum axis is named per stratum — source-length bins for S1/S2, session position for S3, retention across sessions for the transfer battery; METR time-horizon framing stays in the paper narrative as explicit analogy only (the repo has no agent-duration axis); one frozen precomputed task→bin map per stratum, per-bin deltas with CIs | cross-session | language exists ("transfer by … horizon"); no instrument |

Generalized loop (unchanged shape): `H_(k+1) = R(H_k, F_k; B)`, then
`F_(k+1) = E(M0(H_(k+1)(x)))` — with `F` extended to carry the memory-op
ledger (writes/reads, bytes, ops per session) alongside scores, tokens,
latency, and dollars.

Per-locus estimand (extends `docs/a2-preregistration.md:30-33`): gate score of
the visible-selected researcher policy minus gate score of the visible-selected
**matched control**, paired within task profile, research seed, reader tier,
and resource envelope; plus retention (frozen `H` on new sessions/splits) and
horizon-stratified reporting.

**Two-tier reader registry** (formalizes what the hy3 failure taught):

| Tier | Definition | Eligibility | Role |
| --- | --- | --- | --- |
| Anchor | locally served, hash-pinned open model — full identity tuple required, not an abbreviated example: revision + serving-profile hash + `chat_template_enable_thinking=false` flag + tokenizer manifest (docs/operations.md:30-33 records that default thinking alone invalidated a protocol probe; `experiment-protocol.md:76-79` requires both profile hashes in every artifact) | immutable revision + deterministic serving + replay gate | all primary claims |
| Replication reader | any OpenAI-compatible API, open or closed | **passable eligibility gates, the exact ones hy3 failed** (`docs/hy3-locked-qualification-gate-2026-08-30.md`): (i) pre/post-campaign canaries — answer-form, usage, and returned-model echo — with any drift invalidating the whole batch; (ii) a measured same-policy score-variance floor from ≥5 in-batch repeats, and reported deltas must exceed it; (iii) version string + access date + provider-reported model echo recorded per artifact (`provider_revision: null` ⇒ replication-only); (iv) infra failures count as failures; (v) a pre-registered maximum observed in-batch variance ceiling above which the reader is **rejected** for that block, not flagged. A dated version string is a labeling convention, not a pin — the repo's own record shows a fixed alias with T=0/seed 42 still varied output. | transfer/robustness blocks; never anchors |

This is the "any API, any model, open or closed" requirement made rigorous —
the existing `OpenAICompatibleReader` transport (allowlisted hosts, redirects
rejected, usage enforced) already implements the mechanics; `api_profiles.json`
already carries `provider_revision`. The contract line "a provider without
auditable usage can run only in a replication block" (`study-contract.md:139`)
already states the policy; this proposal promotes it from a sentence to a
registry with eligibility gates.

## 5. Scenario and task family (the unified capability surface)

Four strata over one harness; task-identity rules (complete-evidence
solvable, non-saturated over the actual grammar, position-balanced,
causally gold-dependent — `study-contract.md:153-155`) apply per stratum:

| Stratum | Capability | Tasks (current registry state) |
| --- | --- | --- |
| S1 long-context comprehension | dense/global aggregation, latent association | replace failed synthetic panels with real-data calibrated cells (NoLiMa- and MRCR-style properties; RULER demoted to sanity floor) |
| S2 routing under binding budgets | multi-hop evidence selection when selection binds | HELMET PopQA k1000 gold-rank ≥ 200 (wired and ready, 2026-09-18); MuSiQue (blocked on byte-match, frozen) |
| S3 session memory | state tracking, write/read/forget across a session | **Re-designated by the review: LongMemEval-V2 small is the L2 *transfer/robustness* surface, not primary L2 fitness** — its frozen qualification records only **two** unique history artifacts (`longmemeval-v2-qualification-2026-08-30.md:74-81`; confirmed `unique_artifact_count: 2` on 2026-09-18), so "n ≥ 16 items" is effectively n ≈ 2 clusters and every CI must cluster by shared history and question family. Primary L2 fitness needs a many-independent-session real-data source (new acquisition + qualification — costed before Phase 2). LME-V2's own doc already assigns it the transfer-bridge role (`study-contract.md:164`, A4). |
| S4 horizon stratification | gains by horizon quartile; retention | instrument on top of S2/S3 reporting (Recuris's stratification is the reference; METR time-horizon framing for the paper narrative) |

## 6. Design deltas in the repo (after ratification)

1. `docs/study-contract.md`: rewrite the normative question, add the locus
   ladder and two-tier reader registry, extend `F` with the memory-op ledger.
2. `seeds/open_s_v1/memory.py` / L2 is an **engineering workstream, not an
   unpin**: the per-item no-persistence rule lives in at least five
   load-bearing places (seed docstring, the operator library's
   cross-item-memory prohibition, the per-item fresh-process bridge, the
   single-reader-context enforcement, and the per-item replay loop).
   Deliverables before any L2 cell: (a) a session-scoped persistent policy
   worker (or explicit state-in/state-out protocol per item); (b) a
   canonical deterministic state serialization (sorted-key JSON, byte cap
   enforced inside `B`); (c) `PolicyAuditor` changes treating persisted
   state as untrusted-code-authored data; (d) `ContextPack`/schema
   extensions; (e) a redefined replay gate — "identical state transcript +
   identical packs + identical reader outputs across ≥5 repeats" (state
   makes byte-identical replay harder, not impossible, but the current
   design masks a latent nondeterminism: the worker env does not pin
   `PYTHONHASHSEED` and `hash` is not on the auditor's dangerous-calls
   list — harmless per-item-fresh today, variance-injecting in a stateful
   worker; pin `PYTHONHASHSEED=0` or forbid `hash`). Also fix the
   efficiency cliff before L2: the per-item bridge currently ships the
   entire artifact (~25.6M tokens per LongMemEval-V2 small item) — the
   loader already needed a caching fix after 3 h/30 GB RSS on medium;
   stateful session workers must load once per session, not per item.
   Seed re-hash + freeze only after (a)–(e) land and tests pass.
3. **L2 state-boundary contract** (new named rule; closes the leakage
   channel the per-item pin used to close structurally): (i) state resets
   to empty at every split boundary — visible, gate, replay, and sealed
   runs are separate sessions with fresh state; (ii) gate/replay sessions
   contain only gate items, never visible items; (iii) the full state
   transcript is logged and auditable; (iv) a pre-registered leak probe
   injects visible-gold tokens in a canary session and requires their
   absence from all gate packs. Without this rule, cross-item memory can
   ferry visible-split gold evidence into gate scoring (PopQA/LongMemEval
   entities recur across items) — a new hole in the "gate outcomes never
   select a candidate" architecture.
4. **L2 estimand is conditional on a control family existing** — the L2
   primary estimand as written (researcher policy minus matched non-agent
   control) is unconstructible today: restricted `PolicySpecV1` is
   per-item stateless (Random-5/Sequential-5 cannot "get state"), and
   open-S's only control arm is selection-blind researcher proposals.
   Two options, to be picked at ratification: (a) build a frozen
   enumerable stateful grammar so Random-K/Sequential-K extend naturally
   (non-agent comparison retained, ~weeks of work); or (b) relabel the
   first L2 estimand as researcher-vs-researcher (normal vs
   selection-blind, both stateful) and defer the non-agent comparison
   until (a) exists. Option (b) is the honest cheap start; option (a) is
   required before any "researcher advantage" claim at L2. The fairness
   rule stands: any control arm that exists at L2 gets state and the same
   memory budget, or the comparison is invalid.
5. In-loop regression control: **resolved as a reported/ablated arm, not a
   silent selector swap**. The frozen promotion rule (H0-inclusive visible
   historical-best with lexicographic tie-breaks,
   `a2-preregistration.md:186-196`) stays the promotion mechanism; a
   Recuris-style validation gate ("repair the source failure AND pass
   regression on dev anchor tasks", reference: 2607.14004's finding that
   in-loop regression control is the only compounding design) is added as a
   separately reported arm that is ablated in the analysis. Any change to
   the promotion rule itself would change what "visible-selected" means and
   must be a re-frozen amendment, not a bullet.
6. Cell sizing: n ≥ 16 visible items, ≥ 2 research seeds, replay ≥ 5 — with
   two honesty caveats from the review: n ≥ 16 fixes *sampling noise*, not
   *panel saturation* (the offset-104 blind cell's four independent draws all
   hit 0.75; the difficulty contract's kills — no policy ≥ 0.90, top-two
   disagreement ≥ 20%, `a2-preregistration.md:270-277` — are the actual
   saturation instrument and belong in every cell gate); and at n=16 with
   paired binary-ish items, plausible SEs (~0.05–0.08) make the repo's own
   practical screen (gate advantage ≥ 0.05) roughly 1 SE — cells are
   **screens** for a usable signal, not powered tests. Per-stratum power
   analysis (clustered for S3) is a Phase-1 deliverable.
7. Efficiency columns gain memory-op accounting (writes/reads, bytes, ops per
   session) next to tokens/latency/dollars — following SoL-Pi's ledger
   (input/cache-read/cache-write/output split, dated price sheet, cost per
   solved task) and **extended to the improvement loop's own cost**, which
   none of the 2026 wave reports (Recuris: "evolution is the expensive step";
   Dream-RSI counts LLM calls only). Budget denominates in tokens and
   dollars, never LLM call counts.
8. Citation hygiene: remove "SLE/Scientist's Last Exam" (not in public
   literature; use Humanity's Last Exam 2501.14249 for that reference point);
   add MGM, Dream-RSI, Recuris, ModularRSI, SoL-Pi, 2607.12227, 2607.14004.
9. Loop operators, selection-blind mode, replay gates, manifests:
   **behaviorally unchanged** — they are locus-agnostic and remain the
   protocol's core asset. The SLE naming hygiene in (7) is a docstring/docs
   edit only, behaviorally a no-op, recorded as a superseding commit with
   locked cells and their records left immutable; the mechanism description
   stays (the repo treats SLE as a real private protocol cousin — owner to
   confirm before any external mention).
10. **Adopt from the wave's strongest mechanisms** (each mapped to a concrete
   repo surface):
   - Recuris component-attribution: map packing failures to packer
     components (selection/summarization/ordering/memory) and measure
     localization accuracy from **structured packing traces** (their
     outcome-only 13.0% vs structured-trace 64.8% is the argument for making
     traces first-class benchmark surfaces).
   - Recuris validation gate: accept a revision only if it repairs the source
     failure AND passes regression on dev anchor tasks; ablate the gate as a
     control.
   - Recuris/MGM model-agnostic pairs: with/without-artifact paired deltas
     with task-clustered bootstrap CIs; pre-registered noise floor from
     byte-identical re-runs.
   - Precomputed variant-invariant horizon stratification: one fixed
     task→length-bin map, per-bin deltas with CIs — never abstract-only
     slogans (Recuris's "+32.2 on longest tasks" traces to no table cell).
   - Dream-RSI replay-as-simulator: score candidate packing policies against
     archived reader outcomes — **demoted by the review to a non-primary
     cost instrument**: it is off-policy surrogate evaluation, the exact
     class the control literature flags; if used, it must be validated
     against online exact-replay on a qualification panel and labeled
     non-primary, or it undermines the replay-first identity of the
     benchmark.
   - MGM matched evaluation + expansion counts with shared ancestor; failed-
     pool boosting for informative task overlap.
   - Recuris component-attribution via structured traces: requires a
     per-step trace surface `ContextPack` does not have (final-state only
     today) — new schema work, costed with the L2 workstream or demoted to
     future work.
   - HAL factorization: reader × improvable-locus × benchmark as separate
     axes with released logs.
11. **Enforce minimum detectable effect per comparison** — no CI-over-zero
    deltas presented as gains (Recuris Airline +8.5, TTA +2.3 at p=.774 are
    the cautionary examples); generality is tested by swapping the reader and
    re-running, never asserted (MGM's fixed-60-task-subset weakness).

## 7. Execution order (conditional on ratification)

Cost reality from the review (reader arithmetic from the repo's own ledgers:
~32K input tokens/reader-second on the pinned 27B; one L1 cell ≈ 3.3M input
tokens ≈ **~2 minutes of reader time**; wall-clock is dominated by
researcher turns, up to 2.5 h/trajectory, ~10 h per 4-trajectory L1 cell —
**roughly a day per L1 cell**; quota/rate-limit failures on closed-API
researchers are a named operational risk with the Codex `-03` all-quota-
failure precedent). Engineering-days: Phase 0 ≈ days; the L2 session worker
+ state protocol + auditor + replay redefinition ≈ weeks; the per-item
full-artifact bridge (~25.6M tokens/item on LME) must become a
load-once-per-session worker or L2 is computationally prohibitive.

| Phase | Content | Gate to next |
| --- | --- | --- |
| 0 | Ratify this doc; amend study-contract; **one complete end-to-end L1 cell becomes the phase's centerpiece, not a later phase** (serve the pinned anchor on iquest, canary ×5, one normal-vs-blind cell at n=16 with full replay and gate evaluation — the highest-information action after two months of zero trajectories); elastic A2 rebuild lands here only if the owner keeps the restricted track in the paper | new contract-level tests (state reset, replay-transcript equality, control fairness, saturation kills) enumerated and passing — 628 passing today only proves no regression |
| 1 | L1 real-data cells on the pinned anchor (PopQA n=16, normal vs selection-blind, ≥2 seeds, replay ≥5, saturation-kill gate) | replay gate + dynamic range + difficulty-contract kills |
| 2 | L2: first the many-session primary-fitness source (acquisition + qualification, cluster-aware power analysis), then session-state cells; LME-V2 small as the *transfer* surface | (i) one complete L1 cell executed end-to-end including gate; (ii) L2 control family chosen (§6.4); (iii) state-boundary rule (§6.3) implemented with the leak probe passing |
| 3 | L3 adaptive multi-call (call ledger); replication readers (closed APIs) per registry gates | ledger audit + replay + the rejected-direction hole closed |
| 4 | Replication matrix (2 researchers × 2 profiles × 2 seeds × 5 slots), retention/transfer battery, paper assembly | container isolation procurement resolved in parallel from day one; state-isolation design (per-split state namespaces, byte-cap enforcement point, no filesystem persistence, memory-op ledger inside the run artifact — state bytes are researcher-authored persistent data and a new side channel) |
 | 

## 8. Decision requested

(a) Ratify the wide framing with the L1–L4 ladder, **or** choose the
narrow-L1 route — now a first-class option, not a consolation: after two
months of build-out with zero trajectories, one complete end-to-end L1 cell
is the highest-information next action either way, and the narrow route
publishes that cell plus the protocol contribution as the L1 member of the
family. (b) L2 estimand route: (b) researcher-vs-researcher first (cheap,
honest, defers the non-agent control), or (a) stateful grammar first
(weeks, required for any "researcher advantage" claim at L2). (c) Should
the restricted PolicySpecV1 A2 track stay in the paper (elastic rebuild in
Phase 0) or be superseded? (d) Are closed-API replication readers in the
primary paper or an appendix block? (e) Venue: benchmark/datasets track
(the identification framing) or methods track — §3 supports the former.

## 9. Adversarial review record (2026-09-18)

This proposal was reviewed adversarially after drafting (20 findings:
3 blockers, 12 major, 5 minor; verdict "not ready as written" — all folded
in below). The material changes the review forced: §3 reason 3 downgraded
from "exceeds" to "designed to exceed" with the executed/unrun split;
§3 reason 4 downgraded to *adjacent* institutional demand (title corrected);
threat condition (iii) extended to Recuris-extension and
benchmark-consortium directions; L1 track ambiguity resolved (open-S
primary, restricted A2 deferred pending the elastic rebuild); L2 re-priced
as an engineering workstream (session worker, state protocol, auditor,
replay gate, PYTHONHASHSEED pin, artifact-shipping cliff); the L2
state-boundary contract added (§6.3); the L2 estimand made conditional on a
control family (§6.4); S3/LME-V2 re-designated to the *transfer* role per
its own frozen qualification (two unique histories ⇒ cluster-aware power
only); the selection-rule collision resolved (validation gate = reported
arm, promotion rule unchanged); the replication tier rewritten as passable
gates (canaries, variance floor, echo recording, rejection ceiling) instead
of labeling policies; anchor identity tuple completed (serving-profile
hash, thinking flag, tokenizer manifest); cell sizing annotated with its
real semantics (screens, not powered tests; difficulty-contract kills are
the saturation instrument); state-isolation design added to Phase 4; §6.10's
Dream-RSI replay-as-simulator demoted to a validated non-primary cost
instrument; the Recuris structured-trace adoption flagged as new schema
work. The narrow-L1 option was promoted to a first-class §8(a) choice.
