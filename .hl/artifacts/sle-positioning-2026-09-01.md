# Protocol cousin: Scientist's Last Exam (SLE)

Date: 2026-09-01. Source: the SLE brief (Feishu wiki / intended
`Geniusyingmanji/ScientistsLastExam` repo). This is positioning, not a claim
that SLE results exist in this repository.

## Same isolation grammar

Both protocols freeze a judge, isolate a candidate program, and ask whether
**feedback accumulates**:

```text
searcher edits only the allowed files
    → sandbox / fresh worker (no net, no oracle source)
    → trusted process scores with a frozen judge
    → next round sees a restricted feedback record
    → diagnostics that would let the agent optimize the judge stay sealed
```

Open-loop saturation as an admission test is the same idea as our matched
sampling / sequential-refinement control: if extra independent draws still
raise the score, you measured sampling, not iteration.

## Different object, different oracle, different paper

| | SLE | RSIBench-Context |
| --- | --- | --- |
| Question | After score feedback, does a scientific artifact get better? | After permitted feedback, does compiler `H` beat matched search for a frozen reader? |
| Editable | `solution.py` (+ task-local code) | `policy/*.py` (restricted `PolicySpecV1` or open-S folder) |
| Hidden judge | domain simulator / verifier (`verification/`) | frozen reader `M0` + official scorer + labels |
| Score semantics | Opt may exceed a reference (>1); Disc is three-axis | accuracy/efficiency in `[0,1]` plus tokens/latency/$; no literature-SOTA ceiling by design |
| Next-round `F` | total score and validity only | **visible**: item failures, scores, gold may be shown; **gate/sealed**: aggregate only, never trains the next `H` |
| Domain | registered scientific oracles (7 fields, 43 packs) | long source → packed evidence for a frozen long-context reader |

The frozen LLM is **not** SLE's nature-like oracle. Here it is the capability
substrate being served. The judge of `H` is `E(M0(H(x)))` against labels.
A better pack is not a new physical result.

## Our remaining contribution (do not steal SLE's)

1. Identifiable long-context **interface RSI**: researcher vs matched search at
   locus `H`, with replay, manifests, and visible-select / isolated-gate.
2. Efficiency is first-class: tokens, latency, cost move with accuracy.
3. Two program classes: finite `PolicySpecV1` (fair search) and open-S folder
   harness (invention), never pooled with KV/system tracks.

We do not claim wet-lab discovery, score>1 scientific records, or a 43-pack
science suite. SLE does not claim a frozen-reader context-compiler benchmark.
The papers stay distinct if the locus stays distinct.
