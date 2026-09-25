# R3 Gate 2 parent qualification: offline inventory (2026-09-25)

Status: **Gate 2 not admitted**. This is a development-material audit at
`main@7052c06494c37bed22fe14bdf929c20b3c9c6e29`, not a scored model run.
The executable entrypoint is
[`scripts/qualify_r3_parent_projects.py`](../../scripts/qualify_r3_parent_projects.py).
It builds worlds from tracked constructors and the M2 scripted reference. It
does not read R3 live results, external resources, or model APIs.

Run from the project root:

```bash
uv run --no-sync python scripts/qualify_r3_parent_projects.py \
  --output artifacts/rsi-core-v1/r3-gate2-parent-qualification-v2.json
```

The output is created only if absent; the script refuses to replace an
existing artifact. The earlier v1 file is retained as historical output.
Version 2 records UTC start/completion times and matching start/end identities:
Git HEAD plus dirty patch/untracked digests, complete `src`/`scripts` Python
source hash, hashes of the qualifier, M2 builder/reference and evaluator
modules, `uv.lock`, budget and registry configurations, world material and
full-world digests, and the offline execution parameters. A changed identity
aborts before output. This identifies the local materials and code; it does
not prove any service-side model version because this run makes no model call.

The output is an ignored, hash-only inventory. It contains neither source
text nor evaluator fields or item-level scores. `material_sha256` hashes the
ordered document serialization, including document ID, title, text and
provenance; `evaluator_world_sha256` hashes the full serialized instances so
a changed gate is visible without publishing it. Both use canonical sorted-key
UTF-8 JSON with compact separators. The structural ledger records only hashes
of each decision's proposition/precondition, source document when located,
verification oracle, legal action and expected later state. These hashes are
**not** a human-reviewed proposition-to-evidence argument.

## Inventory and independence

| Group | World IDs | Distinct parent IDs | Present qualification |
| --- | --- | ---: | --- |
| A | a-mother, a-mirror, a-aurora-swap, a-vector | 1 shared across all groups | 0/4 |
| B | b-b1, b-b1-reverse, b-b2 | same parent | 0/3 |
| C | c-c1, c-c1-mirror, c-c2 | same parent | 0/3 |

All ten cases descend from the synthetic `supplier-dossier-v4` source corpus.
The mirror/reverse cases permute facts; aurora-swap changes which card supplies
the qualification; vector adds a cumulative check; B2 adds a second scoped
mutation; C2 adds double-switch recovery. Those changes matter to task
structure, but they reuse the source project and do not make ten independent
project samples. Document `source_url` fields are internal `v4:`/`v5:`
identifiers, not externally acquired source provenance. No per-parent author
review is recorded. A new parent must carry disjoint source material, its own
provenance, a reviewed decision ledger and a distinct parent ID before this
inventory can count it.

## Executed interventions and limits

The M2 reference passes each original world (10/10). The script then removes
the first award's named candidate card, changes the evaluator-issued passing
verification to fail, combines those removals, swaps the first non-empty rule
scope, and adds an administrative document with no supplier fact. It reruns
the same scripted worker. The card-removal check proves loss of that named
candidate source before the award; an environment verification can remain an
alternative. A changed scripted pass flag is a **reference-policy outcome**,
not proof that the legal answer changed. The administrative perturbation left
all original reference decision vectors stable. This is only one benign
perturbation, not a robustness distribution.

The strongest C probe starts the second session with a fresh `ProjectState`
containing **no first-session commit or verification record**. It applies the
second-session rule revision, requests a current verification, finalizes the
second-session record and calls the actual `_commit_gate_failures` and
`ObjectiveChecker`. The later gate accepts this legal action in c1,
c1-mirror and c2. In the ordinary shared-state reference, flipping the first
session's winning verification from pass to fail makes the first session fail,
yet the second session still passes in all three worlds. The flipped receipt
changes the environment-issued verification and prevents the first final
commit; the second-session gate still accepts a separate current verification
and `corridor_reaward` record.

A further no-action first-session run leaves `migration_commit` absent. C2's
scripted second session still passes. C1 and c1-mirror's scripted second
sessions fail because their baseline lacks carried notes and creates no
`corridor_reaward`; this is a **worker-policy dependence on carry**, not an
evaluator-side legal-answer dependence. The direct gate probe above separates
the two. Their session-2 legal sets and required current verification are
fixed by session-2 material/oracle and are not conditioned on the first
commit's record or receipt. Gate 2's C requirement that an early receipt or
write changes a later available action or legal answer is therefore unmet in
these current worlds.

B's first-award verification intervention changes a later scripted decision
flag across its three cases, but the audit has not shown a changed
state-conditioned later **legal answer** across the real reset. B remains
unqualified on that claim. The artifact reports this missing proof separately
from the observed reference-policy effect. The A worlds are single-project
lifecycles, so the cross-session probe is inapplicable there.

## Admission work

1. Author at least one genuinely disjoint, reviewed source project per group;
   keep variants/mirrors under the same parent ID. Record document provenance,
   acquisition hash and source segment exclusions before pilot observations.
2. Complete a reviewer-readable ledger for every decision: proposition, exact
   public evidence or verification, action preconditions, and resulting state.
   Keep evaluator-only oracle and expected values in evaluator-side review
   material, never in visible worker input or public case summaries.
3. Redesign C's second-session gate so a specific prior receipt or write
   changes a later available action or legal answer, then rerun both the
   no-action and oracle-flip interventions. For B, demonstrate a specific
   state-conditioned later legal answer across the reset, beyond a worker
   pass/fail difference.
4. Re-run the full probe matrix on each new parent, plus a fixed-policy real
   model difficulty pilot. Reject worlds with failed causal checks before
   freezing an evaluation manifest; archive rejection reasons.

The current artifact makes these gaps explicit. It does not select or replace
worlds based on observed scores.
