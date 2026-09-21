# Scan: how adjacent benchmarks build INDEPENDENT task worlds (2026-09-21)

Scope: PAST-Bench, AgentStream, FinEvo-Bench, Evo-Memory, MemoryArena (per
task list) + statistical-power and anti-cloning literature. All claims below
verified against arXiv abstract/HTML pages fetched today (WebSearch was
malformed; every citation was fetched directly). Unverifiable items marked **[unverified]**.

## (i) Generation method per benchmark

| Benchmark | Generation | Scale | Repeats/stats |
| --- | --- | --- | --- |
| PAST-Bench (2608.04003) | Synthetic, human-curated "task families": "we curate a diverse set of carefully designed task families… The current task families are synthetically constructed" | 26 scenarios, 204 episodes; family = "ordered sequence of fresh-session episodes" (cold/evaluation/control roles) | "Results are reported in average across 3 runs"; example gap "0.13±0.04 for Hermes and 0.15±0.06 for Hermes+"; paired conditions "share the same prompt, grader, tool stack, and seed" |
| AgentStream (2608.00155) | Re-uses existing suites (AppWorld test-challenge, BFCL multi-turn, BrowseComp-Plus, HLE, SWE-bench Verified, Tau2): "We sample N=50 tasks from each benchmark"; provenance = whatever the source suite is (mixed real/synthetic) | 6 suites × 50 tasks in Isolated/Sequential/Interleaved streams | "three random seeds that shuffle task order while keeping the task set fixed"; per-seed tables have ± columns whose meaning is never defined **[unverified: ± semantics]** |
| FinEvo-Bench (2608.06144) | Real-case-grounded, expert-curated: "Eligible institution-provided and publicly documented cases supply the task facts"; "Institution-provided professional procedures define the required operations and constraints"; identifiers scrubbed; "Domain experts review the final tasks in two stages" | 20 business scenes × 6 cases = 120 tasks across 6 financial domains | "We independently shuffle the 120 tasks three times"; paired non-evolving control; "run each full-benchmark configuration three times and report the mean"; judge 95% CI [0.93, 0.97] |
| Evo-Memory (2511.20857) | Restructures static datasets (MMLU-Pro, GPQA-Diamond, AIME-24/25, ToolBench, AlfWorld, BabyAI, ScienceWorld, Jericho, PDDL) into ordered streams: "Evo-Memory restructures conventional static datasets into streaming task sequences" | 10 datasets, 10+ memory modules | No independence/repeats/variance discussion in fetched sections; only "Sequence robustness tests whether performance stays stable under different task orders" |
| MemoryArena (2602.16313) | Human-crafted, partly real-data: shopping (150 tasks: "annotators compose multi-session shopping instructions" over hand-crafted compatibility maps, manually verified); search (256 BrowseComp-Plus tasks, "strict causal ordering among subqueries"); travel (270 TravelPlanner-based instances, JOIN/RELATION constraints, "dependency chains of up to depth four"); formal reasoning (senior PhD experts decompose claims "extracted from real research papers"; 40 math + 20 physics) | 766 claimed; per-section counts sum to 736 **[unverified: discrepancy unexplained in fetched text]** | No repeats/variance/CI discussion found |

## (ii) What each counts as the independent unit

- **PAST-Bench**: no formal unit stated. Structurally, the *task family* is one
  trajectory — episodes within it share state — so the family maps to our
  "world" and 26 families = 26 parent units; episodes are NOT independent
  samples ("Every task family is an ordered sequence of fresh-session
  episodes"). 3-run averaging is presented without CI/SE definition for the
  aggregate.
- **AgentStream**: the underlying suite task is the unit (N=50/suite). Task
  SET is fixed across seeds; only order varies ("the within-benchmark task
  exposure order is held constant to ensure comparability" across scenarios,
  while seeds shuffle stream order). Independence between tasks is assumed
  from the source suites, never argued.
- **FinEvo-Bench**: closest published analogue to our rule. The *scene* is the
  workflow family; within it, "Each scene contains six related but
  substantively distinct cases" and "cases with only superficial differences
  are excluded from the same scene" — an explicit anti-clone gate. But six
  cases share one procedure + one rubric, so scenes (20), not tasks (120), are
  the conservative independent-material unit. Order is handled by 3 shuffles,
  effects by paired controls.
- **Evo-Memory**: the *source dataset* is the grouping; items keep a "unified
  task sequence ordering within each dataset". No independence treatment at
  all in fetched text.
- **MemoryArena**: the multi-session *task* (avg ~6.9 interdependent subtasks)
  is the unit; subtasks share the task's history. Real-data grounding appears
  only in the formal-reasoning domain (claims from real papers). No
  statistical-independence discussion found.

None of the five names a clustered-at-world statistical model — that remains
our contract's distinguishing rule (contract v2: "CIs and order-effect tests
therefore cluster at the world/trajectory level").
## (iii) Design options for OUR next worlds (independent material, not variants)

1. **Fresh hand-authoring + anti-cloning audit (GSM1k protocol, 2405.00332)**:
   new task cards written against author rules "original creations… cannot be
   paraphrased versions of the examples", "Don't reuse a problem setting";
   3 review layers; independent double-solve of the legal plan set (discard on
   disagreement); distinctness audit via odd-one-out panel (GSM1k's
   crowdworkers identified the source-set item at only 21.83% chance-level —
   the same test applied to our docs vs parent-world docs). Fits the
   hand-audited-card workflow directly.
2. **Different real-document segments per world (MemoryArena formal-reasoning
   / FinEvo model)**: each new world's substrate is a disjoint real corpus
   segment (new PopQA/KILT clusters, or a second/third corpus family), with
   constraint facts authored to be derivable from that segment's named
   documents only; FinEvo's "superficial differences excluded" rule imported
   as a pre-registered distinctness gate between worlds. Maximum structural
   distance from the parent world's material while keeping the
   every-constraint-derivable rule mechanical.
3. **BenchBench-style generated-then-verified drafting (2603.20807)**: LLM
   drafts candidate world material from a "domain card"; every item must pass
   "a multi-model answerer panel using exact/numeric/symbolic verifiers"
   (ours: the four oracle-scripted legal paths + precondition-refusal checks =
   layer-2 engine validity) plus quota control across the five failure-class
   axes. Drafts save author time; the answerer panel + our hand audit is the
   gate. **[caution: never publish un-audited generated worlds — our card rule
   requires the owner audit as the freeze step]**
4. **Incidental-similarity screening as a pre-registration gate
   (2608.24825)**: score candidate worlds for "incidental content
   redundancy" vs every existing world via structured decomposition +
   semantic relatedness; reject above threshold BEFORE the hand audit (cheap
   kill, catches template drift that manual review misses).
5. **Templates are NOT worlds (GSM-Symbolic, 2410.05229 — negative result)**:
   "LLMs exhibit noticeable variance when responding to different
   instantiations of the same question"; "performance of all models declines
   when only the numerical values in the question are altered". Template
   variants measure template sensitivity, not world diversity — keep them
   exactly where they are now (diagnostic counterfactuals within one parent
   world), never in the independent pool. This confirms the existing
   variants-of-one-parent = ONE world rule with published evidence.

## Power guidance for the improvement delta (what n supports a claim)

- Miller, "Adding Error Bars to Evals" (2411.00640): paired per-item
  differences; N = (z_{α/2}+z_β)²(ω²+σ²/K)/δ². Their worked assumptions (80%
  power, 5% sig, ω²=1/9): a 3-point gap needs N≈969 items — "at least 1,000
  questions". Derived from their own formula: δ=5% → ~349; δ=2% → ~2,181;
  δ=1% → ~8,700 independent items. Crucially for us: "clustered SEs can be
  over 3X larger than naive standard errors" (DROP ratio 3.05) — items that
  share a world/cluster do NOT count at face value, so the binding N is the
  number of independent WORLDS × per-world items with clustering, and paired
  designs (same worlds, two arms) are strictly better than unpaired.
- Observed self-improvement effect sizes in the adjacent wave: FinEvo gains
  "+19.37" and "9.33-19.37 points"; PAST-Bench gaps 0.13±0.04 / 0.15±0.06 (≈3×
  their stderr at 3 runs). Fragility critique (2608.18066): "the agent's
  improvement is highly dependent on task order" and self-improvement loops
  "amplify" run noise — multiple runs + shuffles mandatory (already our
  contract's §Protocol semantics).
- Practical read for the next rung: our current 0→1 gate-binary repairs are
  large effects (a handful of independent worlds × seeds suffices to show the
  mechanism fires); FinEvo-sized score deltas (+9–19 pts) at δ≈5–10% would
  need ~O(100–350) clustered independent items ≈ tens of independent worlds at
  6 items each — consistent with matrix-v3's "no CI worth computing at this n".

## (iv) Verdict

**Option 2** — one world per disjoint real-document segment (different
PopQA/KILT clusters or additional corpora), with FinEvo's
superficial-difference exclusion as a pre-registered gate and GSM1k's
double-solve + odd-one-out audit at the card freeze — is the best fit for the
task-card rule, because disjoint real segments make "every constraint
derivable from named documents" mechanical rather than aspirational, and the
audit instruments are published and cheap.
