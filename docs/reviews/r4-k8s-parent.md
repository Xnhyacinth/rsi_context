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
The portable source metadata is declared in
`configs/r4_parent_source_manifest_v1.json` in the integration branch.

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
verification. The deterministic test hook distills the first session's
chosen plan and the KEP readiness proposition into the actual
`run_session_sequence` state `carry` subtree. The runner serializes that subtree
through `SessionStateStore`, records its canonical byte length, and gives a
fresh hook only the flushed carry for session 2. A separate over-cap run
rejects a 65,536-character padding field and starts session 2 with empty
carry. The second prompt
does not name the legal plan. Removing the readiness excerpt leaves the first
rollout executable but breaks the derived second choice. This is a scripted
source-retention counterfactual, not evidence that a model can reliably retain
and use the proposition. The first session's verdict does not change the
identity of the later legal plan; that stronger causal claim would need a
different gate and task design.

## Development checks

`tests/test_k8s_parent.py` checks the full scripted recovery path, actual
two-session carry delivery and byte accounting, cap refusal, absent and late
prior writes, stale readiness evidence, removal of each load-bearing source
document, removal of the readiness excerpt, irrelevant text stability,
source-file hash, and deterministic world serialization. The full two-session
serialized world digest is
`9409175713220777bc7ec70683dd3270cead3ac00afd9b431e0cf98fd4b94de7`
(canonical sorted-key compact JSON, SHA-256). The embedded builder is hermetic;
the test verifies the external pinned source hash when that checkout is present.

Qualification still needs an independent review of source support and rule
alignment, a live reader-difficulty pilot, and admission through the shared
manifest. The builder intentionally makes no changes to existing worlds or the
global builder registry.
