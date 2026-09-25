# R8 PEP process B development world

Status: **constructed development candidate, not a qualified benchmark
item or model result**. Builder:
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
rule is also stated later in the full file around lines 547–550.
Provisional feedback is mentioned again around lines 477–480. Deletion
probes remove both supporting occurrences for the chosen route. The file's
public-domain/CC0 notice is pinned in the manifest as well. PEP 621
and 639 were acquired in
R7 but are not used as current PyPA compliance rules in this task.

The board, proposal, receipts, record names, and action codes are
**fictional sandbox material**. Neither status path is an assertion
about a real PEP or a claim that authors can choose actual PEP status.
The mock board authorizes either status for this one exercise. The
pinned PEP 1 text supplies their different process implications; local
material names two possible next-action codes without spelling out
which prior status selects which code.

## Decision → evidence → action ledger

| Prior authorized status | Earlier action and evidence | Later justified action after real reset | Evaluator transition |
| --- | --- | --- | --- |
| `accepted` | Environment-issued PASS `status-clearance` for `accepted`, cited before `status_decision` finalization | `complete-reference-implementation`, backed by a new PASS `next-step-clearance` | `accepted → complete-reference-implementation` |
| `provisional` | Environment-issued PASS `status-clearance` for `provisional`, cited before `status_decision` finalization | `collect-interface-feedback`, backed by a new PASS `next-step-clearance` | `provisional → collect-interface-feedback` |

The first session's evaluator accepts **both** statuses. The second
session's static legal set also contains **both** next actions; the
shared `prior_verification.allowed_later_plans` gate selects the legal
one from the actual previously finalized status. Thus changing only
the earlier legitimate status changes which later action passes in the
same world. The second-session worker receives no source attachment:
only bounded `carry` survives, while a metered registry reread and
sandbox query remain legitimate recovery routes.

## Controlled probes

The offline scripted witness uses only stage views, delivered receipts,
carry, and, in the explicit recovery test, metered tools. It does not
read evaluator fields. With full source, both vectors above pass.

| Intervention | Chosen first status | Session outcomes | What changes |
| --- | --- | --- | --- |
| Delete both Accepted implementation statements | `accepted` | PASS, FAIL | The witness cannot justify that route's later action; `provisional` still passes both sessions. Removing just one statement leaves the other and does not break the path. |
| Delete both Provisional feedback passages | `provisional` | PASS, FAIL | The corresponding later justification disappears; `accepted` still passes both. |
| Choose the opposite later action after a valid prior decision | Either | PASS, FAIL | Even a fresh passing next-step receipt cannot override the prior-status map. |
| Flip first status receipt to FAIL and force finalization | Either | FAIL, FAIL | A finalized record without prior PASS evidence cannot legalize the second action. |
| Lose carry, do not reread | `accepted` | PASS, FAIL | The fresh second-session hook has no private working state or source rule. |
| Lose carry, then metered reread plus sandbox query | `accepted` | PASS, PASS | The alternative recovery path costs two tool calls. |
| Add irrelevant office note | Either | PASS, PASS | Legal vectors remain unchanged. |

These are reference-execution probes, not measured model difficulty.
Removing source text leaves the evaluator oracle and legal map frozen.
The two status meanings may also be partly guessable from their names;
the source-deletion test demonstrates the scripted witness's reliance,
not universal information-theoretic necessity for every model.

Canonical UTF-8 JSON (`to_dict()`, sorted keys, compact separators,
`ensure_ascii=False`) SHA256: session 1
`f3e2cca035eac63c02c33397ae9e0d92a489c15fbb5ac3f0f3eb890a6a3322f7`,
session 2
`5db76833c125db39a099e13b7ff7a4c9c48c5a40ad15ebae9b1a0ef2bca75fba`,
ordered pair
`a8fbe631ad500db24930ceac99812b4a97406a1f8e5b42575eaaeee432bdd6f9`.
Builder byte SHA256:
`f62f82d5549e54ee68688bb60e17bc52ffe1aca55e1f71f37e3133548548852d`.

Replay the construction tests with
`RSICONTEXT_PEP_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/python-pep-process
uv run --no-sync pytest -q tests/test_pep_process_b.py`. A missing
configured checkout skips the source-dependent tests with a named
reason. Final rendered worker-chat token lengths and evidence/query
token offsets, fresh model difficulty, and larger independent-parent
coverage remain unmeasured; this world must not enter a formal manifest
until those checks are completed.
