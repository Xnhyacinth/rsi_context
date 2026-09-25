# Independent parent source candidates for R3 Gate 2

Status: two pinned sources acquired and verified 2026-09-25. No task world was
authored from these sources, and none has passed
Gate 2 or a real-model difficulty screen. These are candidate **new parent
lineages**, not extra variants of the current supplier dossier.

| Candidate lineage | Immutable source and selected material | Distinct dependency to build and test |
| --- | --- | --- |
| `otel-db-migration` | OpenTelemetry semantic-conventions `v1.43.0`, commit `89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`; [database span conventions](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/database-spans.md), [SQL conventions](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/docs/db/sql.md), [Apache-2.0 license](https://github.com/open-telemetry/semantic-conventions/blob/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d/LICENSE). | Version-specific migration choices and the documented `database` versus `database/dup` stability options; a sandbox validation receipt would change which transition can be committed. |
| `k8s-sidecar-rollout` | Kubernetes enhancements commit `13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`; [KEP-753 design/test plan](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/README.md), [KEP metadata](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/kep.yaml), [Apache-2.0 license](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/LICENSE). | Feature gate, test evidence, production-readiness and local rollout state jointly constrain a release decision. The benchmark's write/receipt actions must be explicitly fictional sandbox actions, not claims of upstream approval. |
| `python-pep-process` (reserve) | Python PEPs commit `6822259db9c95f02da739b3e2830a4aa1ae35134`; [PEP 1](https://github.com/python/peps/blob/6822259db9c95f02da739b3e2830a4aa1ae35134/peps/pep-0001.rst), [PEP 621](https://github.com/python/peps/blob/6822259db9c95f02da739b3e2830a4aa1ae35134/peps/pep-0621.rst), [PEP 639](https://github.com/python/peps/blob/6822259db9c95f02da739b3e2830a4aa1ae35134/peps/pep-0639.rst). Selected PEP files carry public-domain/CC0 notices that require per-file confirmation after acquisition. | Proposal-state prerequisites and implementation evidence. PEP 621/639 point to separately maintained current PyPA specifications, so historical PEP text alone must not grade current packaging compliance. |

The pinned repositories occupy 13,414,994 and 98,641,116 bytes locally.
Both detached HEADs and clean working trees were verified. Selected files'
Git blob IDs and SHA256 values, including licenses, are in the local
[`r3-gate2-source-acquisition-20260925.json`](../../artifacts/rsi-core-v1/r3-gate2-source-acquisition-20260925.json)
artifact (SHA256 `57a43b42822904f52ac529048dfd1e36b15a04b463d9d2e4bd0c62c2af87961c`).
The reserve PEP source remains unacquired.

## Acquisition and authoring sequence

1. The two Apache-2.0 entries are now in `configs/registry.json` with `kind: dataset`,
   `integration: adapter`, `source_type: git`, `access: public`, the upstream
   HTTPS repository URL, the complete commit above as `revision` and
   `checksum.value`, `checksum.algorithm: git-revision`, and `size_bytes:
   null`. Use the two Apache-2.0 entries first. Do not add PEPs before the
   selected-file notices and current-PyPA-reference boundary are checked.
2. The repository downloader's **dry-run plan** was inspected, followed by
   `git clone --filter=blob:none --no-checkout` and checkout of the exact
   registered commits into `/volume/pt-dev/qjiu/rsi_context_external/data/`.
   Never follow an upstream branch in a reported experiment.
3. Detached HEAD, clean status, selected-file Git blob IDs and SHA256 were
   verified against the registry and acquisition artifact. Every later
   rendered excerpt still needs its own SHA256 and source-span mapping. Label any
   project version, receipt, legal action or outcome authored for the sandbox
   as constructed material; the official documents support the conditions,
   not a real write to an upstream project.
4. Give each upstream project a distinct `parent_lineage_id`. Mirrors,
   positional variants and seeds inherit it. Split by parent across
   development, gate and sealed pools; never split rows or documents from
   one parent across those pools. These two prioritized lineages are useful
   development candidates but still too few for a population effect claim.
5. Before qualification, draw a decision → proposition → source evidence or
   environment verification → action → later state ledger. Remove decisive
   text, verification, and both; mutate the earlier action/receipt; change
   rule scope; perturb irrelevant material. A B case must cross a session
   reset and a C case must have a later available legal action or answer that
   differs after the earlier action. A legal scripted path is construction
   proof, not model difficulty. Record tokenized evidence/query positions and
   resist simple title/name filters before freezing any evaluation parent.

The dry-run had no warnings; its unknown size fields were resolved by the
local acquisition above. Author review and task construction remain open.
