# R3 Gate 2 parent qualification: offline inventory (2026-09-25)

Status: **Gate 2 not admitted**. This is a development-material audit whose
starting baseline was `main@7052c06494c37bed22fe14bdf929c20b3c9c6e29`,
not a scored model run. The current v4 artifact records the integrated source
commit and material hashes after B/C causal-gate repairs.
The executable entrypoint is
[`scripts/qualify_r3_parent_projects.py`](../../scripts/qualify_r3_parent_projects.py).
It builds worlds from tracked constructors and the M2 scripted reference. It
does not read R3 live results, external resources, or model APIs.

Run from the project root:

```bash
uv run --no-sync python scripts/qualify_r3_parent_projects.py \
  --output artifacts/rsi-core-v1/r3-gate2-parent-qualification-v4-20260925.json
```

The output is created only if absent; the script refuses to replace an
existing artifact. The earlier v1/v2/v3 files are retained as historical output.
The current schema records UTC start/completion times and matching start/end identities:
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

The integrated C runner snapshots finalized record IDs **before** the later
session. The later reaward gate requires the first session's finalized record
in that snapshot; a new finalization in the later session cannot satisfy it.
The direct fresh-state probe now rejects the later finalization in c1,
c1-mirror and c2 even after a valid current verification. Removing the early
verification or entire early action makes the scripted second session fail in
all three worlds. This establishes dependence on the earlier **finalize
write** for the later available legal action. It does not establish that the
earlier verification verdict itself changes the later plan identity. In
particular, an illegal but finalized first-session plan can leave the second
session individually passable while the full project still fails its first
session.

B's first-award verification intervention changes a later scripted decision
flag across its three cases, and the later award now requires a prior
finalized record. The audit has not shown a changed state-conditioned later
**legal answer** across the real reset. The artifact reports this missing
proof separately from the observed action dependency. The A worlds are
single-project lifecycles, so the cross-session probe is inapplicable there.

## Admission work

1. Author at least one genuinely disjoint, reviewed source project per group;
   keep variants/mirrors under the same parent ID. Record document provenance,
   acquisition hash and source segment exclusions before pilot observations.
2. Complete a reviewer-readable ledger for every decision: proposition, exact
   public evidence or verification, action preconditions, and resulting state.
   Keep evaluator-only oracle and expected values in evaluator-side review
   material, never in visible worker input or public case summaries.
3. Preserve the B/C prior-finalization gate and test it on new source parents.
   For B, demonstrate a specific state-conditioned later legal answer across
   the reset, beyond a worker pass/fail difference. For C, keep the write
   dependency distinct from any unproven verification-verdict dependency.
4. Re-run the full probe matrix on each new parent, plus a fixed-policy real
   model difficulty pilot. Reject worlds with failed causal checks before
   freezing an evaluation manifest; archive rejection reasons.

The current artifact makes these gaps explicit. It does not select or replace
worlds based on observed scores.
