# R16 independent-parent intake and rejection ledger

**Decision: no new qualified parent.** This read-only intake began from clean
`main@93e7773`; `configs/registry.json` SHA256 remains
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`
and `uv.lock` SHA256 remains
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`.
No source was downloaded, no model or GPU was called, and no researcher policy
ran. The PEP 621/639 R15 paid screen showed both identity-only controls
complete the project; it is a measured shortcut, not an independent parent.
This intake does not turn an older PostgreSQL or OpenTelemetry card into a
third lineage by changing the question.

## Pinned-source checks and rejected proposals

The existing PostgreSQL 16.0/17.0 and OpenTelemetry 1.24/1.43 checkouts were
detached, clean, and at their registered commits, respectively:
`c372fbbd8e911f2412b80a8c39d7079366565d67`,
`d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`,
`cafda7127683b7f667e27cdbd3220510b6f998c9`, and
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`.

| Proposal | Exact source and possible two-session decision | Intake result |
| --- | --- | --- |
| PostgreSQL 17 `slot_name` and `failover` consistency | The complete pinned `doc/src/sgml/ref/create_subscription.sgml` is 25,011 bytes, SHA256 `935c1a67d7c013410012b753ca81d75e84ed5ce2f622b195601ce1e688e97340`. Its paragraph at inclusive lines 186–199, bytes `[7045,7959)`, SHA256 `6f6145c337dfed6c0f935a176a28d15ae783e9ddca50f177d92d50a57a798040`, requires an existing named slot's `failover` property to match the subscription parameter when `create_slot=false`. Session 1 could survey the full catalog; session 2 could reveal an existing slot with mismatched flags and ask whether to attach it or reconcile first. | **Reject as a new independent parent.** It is another PostgreSQL decision in the R9/R11 lineage. A reader can choose “reconcile flags” by generic consistency reasoning without using the nominated paragraph. Changing the project request to matching flags would reveal the answer in non-source material. One authentic 17.0 source does not supply a matched opposite-rule pair; a rewritten rule would be a constructed intervention, not a second upstream parent. No model-invoked identity-only or source-free result exists for this decision. |
| OpenTelemetry `db.operation.name` | The older pinned `docs/database/database-spans.md:191–197` conditions `db.operation` on `db.statement` applicability; the newer pinned `docs/db/database-spans.md:119,151–164` conditions `db.operation.name` on readily available single-operation information. A survey session and a later instrumentation request are possible. | **Defer.** These are different semantic conditions, so no single unchanged project request yet has an independently adjudicated opposite legal action. Naming either field in the task would leak the answer. This remains the existing OTel lineage, even if resolved. |
| OpenTelemetry namespace/name | The older `docs/database/database-spans.md:191,195` selects a more specific database-name layer; newer `docs/db/database-spans.md:118,147–149` allows multiple namespace components. | **Defer.** The field's scope changes. Without a fixed same-target request and independent oracle, scoring one key as the only legal answer would manufacture a version contrast. It is also the same OTel lineage. |

These decisions follow the [R9 matched-source protocol](r9-experiment-protocol-20260926.md): the unit is an upstream project, non-source observations must be identical for a legal-action flip, and actual model calls must be made in the source-free and identity-only controls. Prior R11/R12 source swaps and scripted witnesses do not supply those missing controls. The R12 OTel row deletion also left 18 equivalent `db.query.text` cues in the complete file. No new lifecycle builder or oracle was added because none of the three proposed cards meets the present intake bar.

## Next distinct-project acquisition proposal: Apache Kafka documentation

The official [Kafka 4.0 consumer rebalance protocol page](https://kafka.apache.org/40/operations/consumer-rebalance-protocol/) states that online migration from a Classic group to the Consumer protocol is possible only when the classic assignor does not embed custom metadata; it also lists an offline migration path and client-side-assignor limitations. This is an **intake hypothesis**, not a frozen task. A possible two-session B request would survey a complete, pinned operations source in session 1 and, after reset, receive a constructed migration plan for an existing Classic group in session 2. Candidate actions would be `rolling-migration` and `drain-then-migrate`, with a procedural receipt that approves either plan and a private source-adjudicated final legality check. The rule is public and the version marker is strong, so success on the full source alone would be weak evidence. The proposed full source bundle and every equivalent cue need auditing before a legal oracle can be frozen.

For a first authentic-source arm, the later request would say: the Classic
group's current assignor embeds custom member metadata, the application
prefers no downtime but permits a maintenance window if needed, and an
operator proposes rolling out
`group.protocol=consumer`. Under the official page's Online condition, the
private legal choice among `rolling-migration` and `drain-then-migrate` is
`drain-then-migrate`.
A second request could specify an assignor without custom metadata and make
`rolling-migration` legal. Both choices would get the same procedural receipt.
This pair is **not yet a matched source contrast**: its non-source request
changes and may itself suggest the answer. The default rolling action fails
the custom-metadata request but passes the other; a fixed default cannot pass
both, yet a source-free model may infer the condition. An identity-only model
may know the widely published KIP-848 rule. Neither shortcut has been tested.

The versioned official page maps to the Apache-owned
[`apache/kafka-site` Markdown source](https://github.com/apache/kafka-site/blob/379dba2230101f7ca1b73658808d67e6e48bf909/content/en/40/operations/consumer-rebalance-protocol.md), at commit
`379dba2230101f7ca1b73658808d67e6e48bf909`; the candidate decisive
paragraph is under `## Upgrade & Downgrade / ### Online`. The same commit has
[`content/en/40/operations/basic-kafka-operations.md`](https://github.com/apache/kafka-site/blob/379dba2230101f7ca1b73658808d67e6e48bf909/content/en/40/operations/basic-kafka-operations.md)
(GitHub displays 558 lines, 37.4 KB) as a possible authentic long-form
companion; the protocol page itself is only 86 lines, 5.25 KB. A top-level
[`LICENSE`](https://github.com/apache/kafka-site/blob/379dba2230101f7ca1b73658808d67e6e48bf909/LICENSE)
containing Apache-2.0 text. The HTML page is versioned but was updated after
Kafka 4.0's release; the Git commit, not the URL's `40` segment, would be the
experimental byte identity. The candidate paragraph's exact byte interval,
full-file SHA256, blob ID, and equivalence scan remain **unmeasured** until a
registry-approved clean checkout exists. The `40` path and release text must
be hidden from model-visible metadata, and a same-identity constructed
rule transplant would be labelled separately from authentic source. Whether
the authentic bundle gives enough natural dependency distance must be
measured after final chat rendering; no padding would count as task depth.
The decisive Online paragraph must be removed together with any equivalent
material in the operations companion for an answer-free control; that audit
cannot be done from a single web page. Thus this is an **acquisition
candidate only**, with no frozen task, legal oracle, or qualified parent.

Proposed registry entry, **not committed to `configs/registry.json`**, because
that file is part of the frozen R15 producer identity:

```json
{
  "id": "apache-kafka-site-kip848-intake",
  "name": "Apache Kafka 4.0 consumer protocol documentation intake",
  "kind": "dataset",
  "integration": "adapter",
  "source_type": "git",
  "url": "https://github.com/apache/kafka-site.git",
  "revision": "379dba2230101f7ca1b73658808d67e6e48bf909",
  "license": "Apache-2.0; verify selected source notices after acquisition",
  "size_bytes": null,
  "access": "public",
  "checksum": {
    "algorithm": "git-revision",
    "value": "379dba2230101f7ca1b73658808d67e6e48bf909",
    "verified": true
  },
  "notes": "Proposed KIP-848 source intake only; no task qualification or source-byte audit yet."
}
```

The project `RegistryEntry` and `build_download_plan` functions validated
this exact candidate in memory without changing the shipped registry. The
observed planner output had `dry_run=true`, one unknown-size artifact, no
warnings, and the destination/commands described below. A later
versioned registry migration should add it, review the actual dry-run plan,
then acquire the exact commit. The observed destination was
`/volume/pt-dev/qjiu/rsi_context_external/data/apache-kafka-site-kip848-intake`,
and `git clone --filter=blob:none` followed by `git checkout --detach
379dba2230101f7ca1b73658808d67e6e48bf909`. Once the entry is in the
registry, the normal nonexecuting command is:

```sh
uv run --frozen --no-sync python scripts/registry_download.py apache-kafka-site-kip848-intake \
  --destination /volume/pt-dev/qjiu/rsi_context_external
```

Before implementation or paid calls, freeze source/license/blob/span hashes,
identical model-visible metadata across variants, a same-request legal-action
flip under a source-rule intervention, an answer-free source-free arm, an
identity-only arm preserving Kafka/version/path cues but no substantive rule,
and an intervention removing or transplanting **every** equivalent migration
rule. Invoke the same fixed reader on all arms, then require both-session
project completion, independent oracle review, two reader families, exact
final-chat offsets, bounded target/auxiliary attempts and provider usage.
Stop if the identity-only arm succeeds, as in R15 PEP, or if the full-source
arm is not solvable. Count Kafka as one parent only after these controls pass;
all result cells are currently unmeasured.
