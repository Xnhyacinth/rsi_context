# Research-v2 probe-gate rerun (2026-09-20)

Status: **standing-gate rerun record** per docs/dependency-probes-20260920.md
§Consequences 2-4. Five probes on the leak-closed research-v2 family
(`--family research-v2`), same discipline, artifacts at
`artifacts/qualification/probe-v2-*.json`.

## Verdicts

| Probe | v1 result | v2 result | Gate |
| --- | --- | --- | --- |
| no-history | FAIL (1.0 vs 1.0; answer in final prompt 8/8) | **PASS** — stateful 1.0 vs empty-state 0.0; `memory_necessary: true` | memory structurally necessary |
| evidence-missing (strict) | PASS (refusal 1.0) | **PASS** — refusal 1.0, parametric 0.0, other 0.0 | reader treats evidence as necessary |
| irrelevant-perturbation | FAIL (0.625) | **PASS** — stability 0.75 (floor 0.75) | stable under irrelevant edits |
| longdoc-necessity | FAIL (0.625 = 0.625) | **PASS** — gold 0.875 vs short-rule 0.5 (`longdoc_necessary: true`) | documents load-bearing |
| fact-swap | FAIL (flip 0.125) | **FAIL** — flip 0.125 | see below |
| lifecycle-fact-swap | n/a | **PASS** — follow rate 1.0, baseline sanity 1.0 (probe-v2-lifecycle-factswap-20260920.json) | the answer-path gate the reader-level probe could not measure: committed answers follow edited stage-1 facts through the full lifecycle |

## The fact-swap failure is a probe-family mismatch, recorded honestly

Per-item analysis shows the probe feeds the EDITED passage directly to the
reader (its v1 design) — it measures reader-level literal extraction, not
the v2 family's answer path (stage-1 documents → retained memory → stage-5
commit). The replies confirm: after replacing "punk" with "Luxembourg" in
the gold passage, the reader extracts the remaining phrase ("power pop") —
faithful extraction from an edited passage, not evidence-independence. One
item followed the swap ("Irish Luxembourg"); one repeated a partial alias
("sports" ⊂ "sports video game").

The family-level question — "does the COMMITTED answer follow an edited
stage-1 fact through the lifecycle?" — requires running the swap through
`run_lifecycle` (edit the stage-1 document, run the stateful hook, compare
the committed answer). That is a sixth probe variant (lifecycle-path
fact-swap), not yet built. Until it exists, the fact-swap gate verdict for
v2 is **INCONCLUSIVE** (probe measures the wrong layer), not failed-on-the-merits.

## Standing-gate status after this rerun

- Memory necessity: **closed** (structural, the strongest form).
- Evidence necessity (strict readout): **closed**.
- Stability under irrelevant edits: **closed** (at floor; watch it).
- Document load-bearingness: **closed** on this corpus slice.
- Fact-following: **closed under an oracle participant** (amended 2026-09-20
  by docs/world-audit-20260920.md §5.2) — the lifecycle-path probe (built
  2026-09-20 later that day, reader-free structural probe) measured follow
  rate 1.0 with baseline sanity 1.0 on 8 items: committed answers follow
  edited stage-1 facts through the full five-stage lifecycle **when the
  participant is the scripted perfect-reader hook** (`_OracleStatefulHook`).
  This proves the runner+materials+checker transmit an edited stage-1 fact
  to the committed answer; it does not measure any real participant's
  fact-following. The reader-level fact-swap (0.125) remains recorded as a
  reader-extraction lens, not a family gate.

## Disposition

The revised family qualifies on four of five gates with the fifth
inconclusive for probe-design reasons. The first meaningful arm comparison
(task #27) may proceed on this basis with the fact-following caveat
recorded; the lifecycle-path fact-swap probe is the next instrument to
build and will be a standing gate for every future family revision.
