# R8 PEP process B development world

Status: **constructed action/receipt development candidate; source-dependence
Gate 2 is rejected**. This is not a qualified benchmark item or model result. Builder:
`src/rsicontext/lifecycle/material_pep_process_b.py`. It is a separate
source lineage from the OTel B candidate; no scored split or policy
answer is registered here.

## Pinned source and construction boundary

The only upstream task document is the complete historical
[PEP 1 process text](https://github.com/python/peps/blob/6822259db9c95f02da739b3e2830a4aa1ae35134/peps/pep-0001.rst)
at detached commit `6822259db9c95f02da739b3e2830a4aa1ae35134`.
The builder rejects any source byte drift before constructing either
session. `peps/pep-0001.rst` is 41,682 bytes, SHA256
`c2bc2ce666758fa82ee2592926218d710e6fdddc674d78314bd6b56c392c46f6`;
the visible `DocumentRef` contains the full file and its header, about
6,322 whitespace words. The decisive
[status passage, lines 409–420](https://github.com/python/peps/blob/6822259db9c95f02da739b3e2830a4aa1ae35134/peps/pep-0001.rst#L409-L420)
starts at source byte 19,817 and has span SHA256
`959c470a75f3da5d841880ca5a204af5ae75abe352cbc7928aacea9a8b5d8657`
per `configs/r7_pep_source_manifest_v1.json`. The Accepted implementation
rule is also stated later in the full file around lines 547–557.
Provisional feedback is mentioned again around lines 477–480. Deletion
probes remove the full equivalent paragraphs/section for the chosen
route rather than a single detector phrase. The file's
public-domain/CC0 notice is pinned in the manifest as well. PEP 621
and 639 were acquired in
R7 but are not used as current PyPA compliance rules in this task.

The board, proposal, receipts, record names, and action codes are
**fictional sandbox material**. Neither status path is an assertion
about a real PEP or a claim that authors can choose actual PEP status.
The mock board reviews one fictional Standards Track language-feature/
standard-library-API proposal and authorizes either status for this
exercise. Its **symmetric** case facts leave both implementation and
interface feedback unfinished under either route. A constructed board
rule funds only one immediate work package: the status-defining
prerequisite described in PEP 1. This rule does not claim that PEP 1
forbids other work under either status. In fact, PEP 1 also permits
feedback changes while Accepted with Steering Council approval and
implementation work while Provisional. The local rule narrows this
mock project's priority, not the general PEP process.

## Decision → evidence → action ledger

| Prior authorized status | Earlier action and evidence | Mock board's single immediate priority after real reset | Constructed evaluator transition |
| --- | --- | --- | --- |
| `accepted` | Environment-issued PASS `status-clearance` for `accepted`, cited before `status_decision` finalization | `complete-reference-implementation`, backed by a new PASS `next-step-clearance` | `accepted → complete-reference-implementation` |
| `provisional` | Environment-issued PASS `status-clearance` for `provisional`, cited before `status_decision` finalization | `collect-interface-feedback`, backed by a new PASS `next-step-clearance` | `provisional → collect-interface-feedback` |

The first session's evaluator accepts **both** statuses. The second
session's static legal set also contains **both** next actions; the
shared `prior_verification.allowed_later_plans` gate selects the legal
priority from the actual previously finalized status under the
constructed board rule. Thus changing only the earlier legitimate
status changes which later action passes in this same sandbox world.
The second-session worker receives no source attachment:
only bounded `carry` survives, while a metered registry reread and
sandbox query remain legitimate recovery routes.

## Controlled probes

The offline scripted witness uses only stage views, delivered receipts,
carry, and, in the explicit recovery test, metered tools. It does not
read evaluator fields. PEP-specific reference decision keys are
`s1_status_valid` and `s2_next_step_valid`; their values and failure
details follow the two actual session outcomes, without legacy B/C
labels. With full source, both vectors above pass.

| Intervention | Chosen first status | Session outcomes | What changes |
| --- | --- | --- | --- |
| Delete the full Accepted status/implementation paragraph and later reference-implementation section | `accepted` | PASS, FAIL | The scripted witness loses both direct supporting passages; `provisional` still passes. Deleting only one phrase leaves other support and does not break its path. |
| Delete both Provisional feedback passages | `provisional` | PASS, FAIL | The scripted witness loses both direct supporting passages; `accepted` still passes. |
| Delete any symmetric pending-work or single-priority local fact | Either | PASS, FAIL | The scripted witness requires the visible constructed project facts in addition to its source extraction. |
| Choose the opposite later action after a valid prior decision | Either | PASS, FAIL | Even a fresh passing next-step receipt cannot override the prior-status map. |
| Flip first status receipt to FAIL and force finalization | Either | FAIL, FAIL | A finalized record without prior PASS evidence cannot legalize the second action. |
| Lose carry, do not reread | `accepted` | PASS, FAIL | The fresh second-session hook has no private working state or source rule. |
| Lose carry, then metered reread plus sandbox query | `accepted` | PASS, PASS | The alternative recovery path costs two tool calls. |
| Add irrelevant office note | Either | PASS, PASS | Legal vectors remain unchanged. |
| Withhold PEP 1 text; use a source-free semantic answer map | Either | PASS, PASS | The evaluator still accepts the shortcut, exposing a source-dependence failure. |

These are reference-execution probes, not measured model difficulty.
Removing source text leaves the evaluator oracle and legal map frozen.
The source-free baseline's success shows that this candidate does **not**
establish a necessary long-context source dependency. The source deletion
tests demonstrate only the scripted witness's reliance on those passages.
Keep this as an action/receipt/reset construction witness; redesign the
source-to-action question before counting it as a qualified B parent.

Canonical UTF-8 JSON (`to_dict()`, sorted keys, compact separators,
`ensure_ascii=False`) SHA256: session 1
`52163666476f0e52ba967dc6f0ba0c301faab7d50e7efbd37908c22d0991b488`,
session 2
`1f57163c3f0602da39d89c0db783675551d05805b8e1cca165268f6de089ebc0`,
ordered pair
`8c55c82262825160f12a11e242d9a58f4727f90ebe2cdf195373bcea31c69e66`.
Builder byte SHA256:
`1477e7f9e8352fbd04524454e4866402a240c9cbdba9660596e8a89f2363a076`.

Replay the construction tests with
`RSICONTEXT_PEP_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/python-pep-process
uv run --no-sync pytest -q tests/test_pep_process_b.py`. A missing
configured checkout skips the source-dependent tests with a named
reason. Final rendered worker-chat token lengths and evidence/query
token offsets, fresh model difficulty, and larger independent-parent
coverage remain unmeasured; this world must not enter a formal manifest
until those checks are completed.
