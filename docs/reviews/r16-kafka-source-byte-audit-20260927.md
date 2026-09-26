# R16 Apache Kafka-site source intake: pinned byte audit

Status: source acquired and audited for **candidate intake only**. No
benchmark world, model call, legal-plan oracle, dependency result or qualified
parent is claimed. The acquisition used the committed registry entry on
`work/r16-kafka@bf6ac2c`; the dry-run plan at
`/volume/pt-dev/qjiu/rsi_context/artifacts/rsi-core-v1/r16-preflight/kafka-registry-plan.json`
has SHA256 `0f4d818a42bb43db69f702135f83889c4b17d6dfca1bf5e9f21d7bc935a55220`,
reported one unknown-size artifact and no warnings. After reviewing that
plan, `git clone --filter=blob:none --no-checkout` acquired the official
`https://github.com/apache/kafka-site.git` repository and a detached checkout
selected **only** commit `379dba2230101f7ca1b73658808d67e6e48bf909`.
The checkout at
`/volume/pt-dev/qjiu/rsi_context_external/data/apache-kafka-site-kip848-intake`
is clean and detached at that commit. The committed registry SHA256 is
`e063e0c4291de8e560d5928ce2c847b003ede8c0b2bd69a85265df0707a1a6a7`.

| Selected source | Bytes | Git blob | SHA256 |
| --- | ---: | --- | --- |
| `content/en/40/operations/consumer-rebalance-protocol.md` | 5,375 | `c68d7f5a5b8b47df0db6e618ce7d2d1389dd4e56` | `82259d8ac257fc5e575f3b44afe270c88db1bb1b85f98410f56c3710d67fc9af` |
| `content/en/40/operations/basic-kafka-operations.md` | 38,264 | `3f228afe1087715e3f301405bf83be8d860ae4e5` | `74e4e7acd82a1e240a188d4925adb7b7b432e3a39d2a2cbe8011d7a3d2ab5f1d` |
| Top-level `LICENSE` | 11,357 | `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

The protocol Markdown has an Apache Software Foundation license notice in
its header. The decisive authentic Online-migration paragraph is inclusive
line **75**, raw byte interval **[4298, 4762)**, 464 bytes, SHA256
`53887fc7ebc09cd59265589bf6e7ac57c589a6d58b0721a8ab5dd39e38e69df8`.
It permits rolling migration without downtime only when the Classic group's
assignor does not embed custom metadata. The same file's Offline section at
line 71 gives a shutdown/restart route when the group is empty. A search of
the pinned `content/en/40` tree for the exact custom-metadata and rolling
condition found this paragraph only; the 38,264-byte companion has no match
for those phrases. That search is an **exact phrase scan**, not proof that
all semantically equivalent cues have been excluded. The official
[versioned page](https://kafka.apache.org/40/operations/consumer-rebalance-protocol/)
and [pinned Markdown](https://github.com/apache/kafka-site/blob/379dba2230101f7ca1b73658808d67e6e48bf909/content/en/40/operations/consumer-rebalance-protocol.md)
support the source-level condition. The site commit dates after the 4.0
release, so the claim is about this documentation snapshot, not release-day
behavior.

An offline builder must preserve the authentic source bytes and mark any
constructed rule transplant separately. A fixed S2 request with an assignor
embedding custom metadata and identical non-source metadata across arms can
make `drain-then-migrate` legal under the authentic paragraph; an explicitly
constructed contrary rule would make `rolling-migration` legal under the
*same* request. Both plans should obtain the same procedural receipt, with
legality checked only at finalization. A truly deidentified source-free arm,
an identity-only arm retaining Kafka 4.0 cues, a complete-authentic-source
arm, and the constructed same-identity rule arm must all invoke the same
fixed reader. Keep the two session worlds, source document hashes, model
visible metadata, private oracle, prompt tokens and evidence offsets in a
versioned ledger. A full-source success without those controls is not a
dependency result; a constructed arm is not another independent upstream
project. The 38 KB companion must serve an actual dependency role; including
it merely to increase prompt length would not qualify task depth.

Next gate: implement and independently review the lifecycle world and
answer-free controls, then run a no-API geometry/rejection exercise. Only
after full-source feasibility and a prospective token/call budget should a
small Siflow development screen be considered. The current qualified
independent-parent count remains zero.
