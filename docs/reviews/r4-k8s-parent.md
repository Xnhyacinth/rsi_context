# R4 Kubernetes sidecar parent: development candidate

This is one candidate parent, separate from the supplier dossier lineage. It is
not yet an admitted benchmark item or a measured model-difficulty result.
The upstream KEP supplies container semantics; the batch rollout, record names,
verification outcomes, and second-session operational amendment are benchmark
constructions. No upstream approval of that rollout is asserted.

## Fixed source and proposition ledger

Source: Kubernetes enhancements, KEP-753, detached commit
`13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`,
`keps/sig-node/753-sidecar-containers/README.md`, SHA-256
`ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21`.
The source and its Apache-2.0 license were acquired through the pinned registry
plan recorded in `artifacts/rsi-core-v1/r3-gate2-source-acquisition-20260925.json`.

| Proposition in visible material | KEP span at the pinned commit | Benchmark use |
| --- | --- | --- |
| `restartPolicy: Always` identifies a sidecar in `initContainers`; startup ordering waits for Started, not exit | [README lines 368–383](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/README.md#L368-L383) | Distinguishes native sidecar from an ordinary companion |
| A continuously running ordinary companion can hold Job completion; native sidecars do not block Pod completion | [README lines 249–263](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/README.md#L249-L263), [lines 391–397](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/README.md#L391-L397) | Session 1 source-based plan decision |
| A native sidecar may have readiness probes that contribute to Pod readiness | [README lines 407–411](https://github.com/kubernetes/enhancements/blob/13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/keps/sig-node/753-sidecar-containers/README.md#L407-L411) | Session 2 uses a constructed readiness-policy amendment |

The constructed first policy requires an environment-issued `job-completion`
verification. Its evaluator oracle fails `regular-companion` and passes
`native-sidecar`, so a reference path observes a fail receipt, switches, verifies,
and finalizes `sidecar_rollout`. The second session advances only the
`readiness-contract` check to revision 2. It permits a new
`readiness_rollout` only when `sidecar_rollout` was finalized *before* that
session began and a current readiness verification passes. The mutation leaves
`job-completion` at revision 1. A same-session repair cannot satisfy the prior
finalization condition.

These are typed sandbox actions, not an actual Kubernetes deployment. The
second gate proves dependence on a prior finalized write and current scoped
verification. It does not prove that the first session's verdict changes the
identity of the later legal plan; that stronger causal claim would need a
different gate and task design.

## Development checks

`tests/test_k8s_parent.py` checks the full scripted recovery path, absent and
late prior writes, stale readiness evidence, removal of either load-bearing
source document, irrelevant text stability, source-file hash, and deterministic
world serialization. The full two-session serialized world digest is
`e92ecb570fb8debe678a2feec601946fda9e0e4b38020bff7b5e96277b004152`
(canonical sorted-key compact JSON, SHA-256). The embedded builder is hermetic;
the test verifies the external pinned source hash when that checkout is present.

Qualification still needs an independent review of source support and rule
alignment, a live reader-difficulty pilot, and admission through the shared
manifest. The builder intentionally makes no changes to existing worlds or the
global builder registry.
