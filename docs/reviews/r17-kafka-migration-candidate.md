# R17 Kafka migration lifecycle candidate

**Status: offline construction witness only; no qualified parent, model run, or
long-context result.** The builder is
`src/rsicontext/lifecycle/material_kafka_migration.py`. It reads the clean,
detached Apache-owned `apache/kafka-site` checkout registered as
`apache-kafka-site-kip848-intake` at
`379dba2230101f7ca1b73658808d67e6e48bf909`; it refuses a changed
protocol file or top-level license. The complete authentic source is
`content/en/40/operations/consumer-rebalance-protocol.md`, 5,375 bytes,
SHA-256 `82259d8ac257fc5e575f3b44afe270c88db1bb1b85f98410f56c3710d67fc9af`.
The [pinned source](https://github.com/apache/kafka-site/blob/379dba2230101f7ca1b73658808d67e6e48bf909/content/en/40/operations/consumer-rebalance-protocol.md)
is preserved byte for byte in the full-source arm. The top-level `LICENSE`
SHA-256 is `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.

## Semantic rule audit

The protocol source's Offline section (line 71) permits a group-empty
shutdown/restart route. Its Online paragraph (line 75, bytes `[4298, 4762)`,
SHA-256 `53887fc7ebc09cd59265589bf6e7ac57c589a6d58b0721a8ab5dd39e38e69df8`)
permits a rolling Classic-to-Consumer migration only when the Classic
assignor does not embed custom metadata. The Limitations section (line 83)
separately says client-side assignors are unsupported by the new protocol.
These are the only upgrade or assignor compatibility statements in the
5,375-byte selected file. A targeted scan of the 38,264-byte
`basic-kafka-operations.md` companion found group management, permissions,
and offset-reset instructions but no online/offline rebalance migration rule
or `group.protocol` guidance. The 26,076-byte `getting-started/upgrade.md`
mentions KIP-848 at line 64 only to link to this protocol page, without
restating the custom-metadata condition. The 108,775-byte
`operations/monitoring.md` lists Classic group metrics; the 19,196-byte
`design/protocol.md` concerns a different protocol layer. A phrase scan over
the pinned `content/en/40` tree and inspection of these likely longer files
found no longer source with the decisive condition or a relevant dispersed
upgrade rule. This is an intake screen, not a proof about every Kafka page.
These documents are
excluded because this decision does not need them; including one would add
unrelated length.

The constructed group currently has a legacy assignor that embeds custom
member metadata. Its **target** uses a supported built-in server-side
assignor, so the line-83 limitation does not independently rule out the
target. The source-dependent question is whether the *transition* may occur
while the group is active. The same constructed request permits a maintenance
window but prefers the least disruptive supported route. The authentic rule
therefore selects `drain-then-migrate`. A separately labelled constructed
counterfactual replaces exactly the line-75 paragraph with a rule saying
that the transition also works with custom legacy metadata; then
`rolling-migration` is the private legal choice. This is a diagnostic rule
transplant, **not an upstream Kafka revision**. Its full-source SHA-256 is
`25b236938ac65cdca5490bd8d7ba2ef0409b55fb28adcef70817d9d5da7e06de`;
the replacement span SHA-256 is
`825e15603a74b0228b6a723841f91030595ac19662ea251b8f3ffbb22cf250c6`.
All prefix and suffix bytes outside the registered paragraph remain exact.

## World and controls

Session 1 presents the source before the migration request, requires an
environment-issued `review-complete` receipt, and finalizes `source_review`.
After a process reset, session 2 presents the fixed request and requires a
fresh `plan-reviewed` receipt before finalizing `migration_plan`. The
procedural oracle returns PASS for both route names; only the private commit
gate adjudicates technical legality. The earlier finalized record is also a
private prerequisite for the later gate. The frozen participant sees no
legal-plan list, verification oracle, or answer norm.

The matched authentic and constructed arms have identical non-source
prompts, documents, document metadata, stage order, axes, record interface,
and predecision receipts. Their source document text differs only in the
registered paragraph. The deidentified source-free control contains a
withholding marker and no Kafka, KIP-848, Classic, or configuration identity
in its visible stage fields. The identity-only control retains Kafka 4.0,
KIP-848, path, and URL but no substantive compatibility rule. Both controls
use the authentic private oracle and the identical later request. Domain
terms such as “consumer group” and “assignor” remain in the request, so a
model might still infer the project from world knowledge; that shortcut
must be measured, not assumed absent.

| Arm | Session 1 world SHA-256 | Session 2 world SHA-256 | Private later plan |
| --- | --- | --- | --- |
| Authentic full source | `2ef9ae136cd1e67db057f45124667615b884a3cb9a177effd519468593e41820` | `30056c03bb65aa0c54d9769c30aa435988f5f7309308990ab853d9b57dd3f2a8` | drain |
| Deidentified source-free | `3f7fa775b3d20d118a8419dc0512f929ad9de6bcc76afba2f84ea9bedbaac8f3` | `30056c03bb65aa0c54d9769c30aa435988f5f7309308990ab853d9b57dd3f2a8` | drain |
| Identity-only | `f8d92772d2fa1c665381e510c521349d8f8df3c8ab097b4fe806a8922d842517` | `30056c03bb65aa0c54d9769c30aa435988f5f7309308990ab853d9b57dd3f2a8` | drain |
| Constructed online rule | `a7c02f0e94fa92e8ac1c705d5dd8f4e9319333a44738771088ae17defb371534` | `508aa818faaffcb34e4e6e231a0f4564d01a632a252569b81f43d76ecb282b3d` | rolling |

These hashes are SHA-256 of `canonical_instance_json` and include private
evaluator fields; they are not model-visible hashes. The builder's
`kafka_source_ledger()` returns the exact source and intervention hashes.

## Executed offline gate and next decision

Five focused tests passed. They check immutable source and license bytes,
the exact edit interval, matched non-source fields, answer-free controls,
source/license drift rejection, and two-session action/receipt behavior. An
in-memory scripted reference passes both sessions in each source-rule arm;
the same fixed drain choice fails the constructed arm, and the same fixed
rolling choice fails the authentic arm. This proves only the **structural**
action flip and that the environment enforces it. The script's phrase tests
are not a model reading result. Scoped Ruff, strict mypy, and source-file
Bandit pass.

**Defer as a long-context parent.** The authentic source is short (5.4 KB),
and the relevant rule is near its end. There is no exact final-chat geometry, fixed-reader two-family result,
model-invoked source-free/identity-only result, position test, or researcher
pretest. Do not count this as a qualified long-context parent or dispatch
paid calls yet. The next scientifically useful step is an independently
reviewed fixed-reader design and a genuine related long-form source if the
goal is long-context dependency; the unrelated 38 KB companion is not an
acceptable length substitute. Freeze a versioned profile, final-chat
geometry, two reader families, stop rules, and provider-token ceiling before
any real Siflow screen.
