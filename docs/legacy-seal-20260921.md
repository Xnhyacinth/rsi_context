# Legacy-conclusion seal and the three world dispositions (2026-09-21)

Status: **decision record** — implements the external review round 4's
deliverable 1 on top of docs/world-audit-20260920.md. Owner decision
pending on nothing here: the dispositions below follow the review's
decision table (round 4 §一), which the audit evidence supports. The next
task-family revision uses the version marker **`research-v3`**;
research-v2 and all its records remain intact as development and
diagnostic material.

## 1. The three world dispositions (final)

Principle (review round 4): a fix restores
question–entity–relation–evidence consistency for the ORIGINAL question;
retargeting the question to whatever the wrong retrieval returned is
authoring a NEW task, not repairing an old one, and the two are booked
separately.

| World | Disposition | Rationale (from the audit) |
| --- | --- | --- |
| 1652383 Holiday | **Withdrawn from the formal pool.** The "survey the rendition" re-semantics proposed in world-audit §4 is NOT adopted as a repair of this item; if that task is wanted it becomes a new derived entry with an explicit rendition-bound question and its own answer set. | The question's semantics ("What genre is Holiday?" for the Green Day song per `s_wiki_title`) is not supported by the retrieved gold (Scuba Dice, the covering band). Retargeting would change what the question asks. |
| 6271105 Dragons | **Withdrawn from the formal pool.** The answer is NOT to be changed to "rugby league" (the wrong team's code). Correct evidence for the Welsh rugby-union Dragons must be found before any re-entry; otherwise it stays as a wrong-entity-binding regression fixture. | Gold describes the Ballarat rugby-league club; asked entity is the Welsh rugby-union side. The current "rugby" alias containment-hits the wrong code — the world measures alias breadth, not evidence binding. |
| 3006731 Killjoy | **Withdrawn from the formal pool** until entity identity is resolved. If the question cannot be disambiguated from visible material, a versioned derived task adds an agent-visible qualifier; the qualifier-vs-alias scoring question follows entity resolution, not before. | Gold passage is the 2012 sequel ("comedy horror film"); the asked entity is the 2000 original. The "normalization gap" sits on top of an entity mismatch. |
| 3026511 Krishna | **Removed** (already executed in the audit record; kept as the alias-co-occurrence ≠ relation-support negative fixture, never for capability ranking). | Jain-cosmology passage where "Vasudeva" is a class name in a triad, not a father assertion. |

Consequence for the pool arithmetic: the stratification record's
"17 pass / 2 span-selection / 1 normalization" over 20 worlds becomes, at
the disposition level, **14 retained-easy / 3 withdrawn / 1 removed /
2 withdrawn** (1650366 and 2120061 stay in with the audit's weak/masked
caveats; 2120061 is flagged as parametric-recall-suspect and must be
relation-checked before any confirmatory use — model-correct does not
certify label-correct).

## 2. Claim corrections (sealed)

The following standing formulations are corrected as of this record; the
underlying artifacts are immutable and their measurements stand:

| Sealed formulation | Corrected status |
| --- | --- |
| "research-v2 qualified, 5/5 gates, family 完全合格" | "research-v2 passed the five standing probe gates on its dev panel; probe-gates-v2 record already amended: fact-following is closed **under an oracle participant**. Family-level task validity is superseded by the world audit's relation-mismatch findings." |
| "pool is 85% easy, hence no arm separation" (stratification §Summary) | "The 20-world probe measured one-call extraction; 6/20 carry relation-level entity mismatch including one in the pass tier. 'Easiness' and 'no headroom' hold for the one-call instrument on the audited set; they are not established for family-level difficulty." |
| "world-boundary discipline validated as a measurement" (arm-comparison §Findings 3) | "The no-reset run showed naive persistence poisons; the reset prevents it. The contract's frozen-snapshot carry (source/time/scope boundary) is **not implemented** — `arm_comparison_v2.py:232` wipes all state; `__carry__` is dead code. 'Reset works' ≠ 'the contract is realized'." |
| "研究-v2 的五阶段生命周期…" lifecycle adds task difficulty | For the audited worlds, per-world outcomes under the lifecycle are identical to the one-call tiers: the lifecycle adds no measurable difficulty over single-call presentation on these worlds (audit §1). The family's demonstrated value is leak closure + staged access discipline. |
| "此前高分主要由状态答案捷径造成" (root-cause §What actually produced 24/24) | Already corrected by that record's own channel-parity diagnostic section; re-confirmed here: the 24/24-vs-0/24 gap was jointly item-label defects × note recycling, not a single shortcut. The "state shortcut saturation" phrasing must not re-enter any narrative. |

Engine-test vs capability results are now separated by rule (review round 4
§二): oracle-participant probe results (lifecycle fact-swap, no-history)
are engine tests — they validate runner/materials/checker plumbing, never
participant capability. All three-arm scores on research-v2 (including the
0.333 tie, the 24/24 n=16 panel, and the 0/12-vs-4/12 no-reset run) are
**development comparison records with task/comparison validity not
established**; they are excluded from any formal effect summary. DS
wiring/retry/billing integrity evidence stands as engineering evidence.

## 3. What any cited number must now carry

Traceability rule adopted (review §二 验收条件): every cited number must be
traceable to task version, world set, presentation condition, participant
type (real reader / oracle), and the conclusion class it can support.
The result-index table in world-audit §1 is the template; artifacts
already record most fields (the probe JSONs carry per-item replies and
conditions).

## 4. Version marker

`research-v3` is the next family revision marker. Its gate is NOT "5/5
probes pass" alone but the three-layer evidence split (review §五):
(i) semantic/label validity — relation-audited worlds, disambiguation
handled by design; (ii) engine validity — oracle participant completes
legal trajectories, checker responds correctly to relevant/irrelevant
changes; (iii) real-system behavior — success and failure explainable
along the evidence–state–action chain. research-v2 material (worlds,
probes, constructors) is the development substrate for v3, not its
qualification.
