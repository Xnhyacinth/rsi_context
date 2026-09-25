# R7 PostgreSQL 17 source intake and C-parent design

Status: **read-only source review**. No PostgreSQL checkout, source-byte hash,
benchmark world, model call, or scored result exists for this candidate. Do not
acquire the repository until its entry is merged into `configs/registry.json`
and the resulting dry-run plan has been reviewed.

## Identity, terms, and selected material

On 2026-09-26, read-only `git ls-remote --tags` against both the
[PostgreSQL source repository](https://git.postgresql.org/git/postgresql.git)
and its [GitHub mirror](https://github.com/postgres/postgres) resolved the
lightweight `REL_17_0` tag to the same complete commit,
`d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`. The PostgreSQL
[source instructions](https://www.postgresql.org/docs/17/git.html) name the
first URL as the official clone source. The pinned
[`COPYRIGHT`](https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/COPYRIGHT)
and the project's [license page](https://www.postgresql.org/about/licence/)
identify the PostgreSQL License. Its notice must accompany reproduced source
or documentation. The pinned notice is the relevant one for this release;
the mutable license page has since updated its copyright year.

Selected source files at this exact commit:

| File | Source-supported proposition for a constructed task |
| --- | --- |
| [`doc/src/sgml/logical-replication.sgml`](https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/logical-replication.sgml), section `logical-replication-failover` | Slot sync is asynchronous; identify all required subscription and finished-table-copy slots, then check that *each* is present and ready on the standby before promotion. At this pin, the sample readiness expression is `synced AND NOT temporary AND NOT conflicting`; `synchronized_standby_slots` helps keep the standby ahead of the subscriber. |
| [`doc/src/sgml/ref/create_subscription.sgml`](https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/ref/create_subscription.sgml), parameters `slot_name`, `create_slot`, `failover` | `failover` defaults to false. If an existing named slot is used with `create_slot=false`, its actual failover property can differ from the subscription option; the two must be checked together. `slot_name=NONE` does not create an active slot. |

The current mutable [PostgreSQL 17 HTML documentation](https://www.postgresql.org/docs/17/logical-replication-failover.html)
now expresses the sample standby test with `invalidation_reason IS NULL` in
place of the pinned source's `NOT conflicting`. Do not splice this later text
into an `REL_17_0` world. Neither wording alone establishes that a real
deployment is safe to promote; this benchmark would have no PostgreSQL
cluster or measured failover outcome.

## Registry proposal, not an edit to the registry

```json
{
  "id": "postgresql-rel-17-0",
  "name": "PostgreSQL 17.0 logical replication source",
  "kind": "dataset",
  "integration": "adapter",
  "source_type": "git",
  "url": "https://git.postgresql.org/git/postgresql.git",
  "revision": "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e",
  "license": "PostgreSQL License; retain pinned COPYRIGHT notice",
  "size_bytes": null,
  "access": "public",
  "checksum": {
    "algorithm": "git-revision",
    "value": "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e",
    "verified": true
  },
  "notes": "REL_17_0 tag verified on canonical Git remote and GitHub mirror 2026-09-26. Selected SGML and COPYRIGHT bytes, blob IDs, and license notice require verification after reviewed dry-run acquisition. Constructed failover receipts are not PostgreSQL observations."
}
```

After integration adds that entry, run the **read-only** planner from the
project root and inspect its `dry_run`, destination, exact checkout revision,
warnings, and unknown size before executing any command it prints:

```bash
uv run --no-sync python scripts/registry_download.py postgresql-rel-17-0 \
  --destination /volume/pt-dev/qjiu/rsi_context_external
```

The expected destination is `rsi_context_external/data/postgresql-rel-17-0`.
An in-memory check of the proposal with `RegistryEntry.from_dict` and
`build_download_plan` passed: `dry_run=true`, no warnings,
`unknown_size_count=1`, and the emitted command checks out the exact commit
above. This check did not read or change the live registry and did not acquire
source material.
Only after plan review, acquire the fixed commit into an isolated checkout,
prove detached clean `HEAD`, and record SHA-256 and Git blob IDs for `COPYRIGHT`
and both SGML files. Record exact byte offsets and SHA-256 for every extracted
source span; preserve the notice in any redistribution. If a third source file
is needed, revise the selected-file manifest before world construction. A
registry revision is a commit pin, not a selected-file byte inventory.

## One falsifiable C development parent

Proposed `parent_lineage_id`: `postgresql17-failover-slot-readiness`. Every
variant, reversal, and position shuffle inherits this one ID. Use full pinned
SGML prose or a lossless excerpt ledger; do not fill to a target length with
repeated text. Keep all case-specific subscription names, standby rows,
actions, and receipts visibly labelled as **constructed sandbox state**.

1. In session 1, the participant reads the two source documents and a
   constructed project request. It must choose the subscription's actual slot,
   check `failover` alignment, request an environment-owned verification, and
   finalize a `subscription_prepared` action naming the selected slot. A mere
   participant-authored `status=final` field does not count. Include a plausible
   old slot and a table-copy slot so neither the title nor a single slot name
   suffices to decide.
2. Reset the participant process and deliver only bounded persisted carry.
   The evaluator preserves a snapshot of actions finalized **before** the
   reset. A constructed standby notice and a fresh, subject-bound verification
   receipt describe the readiness of the relevant slot set. The later prompt
   asks for the next legal rollout decision without stating its identity.
3. The sandbox's later legal actions are `promote_selected_standby` only when
   the earlier finalized slot selection and current PASS for **every** required
   slot match, or `hold_and_recheck` otherwise. A later repair cannot create
   the missing earlier finalization. If the earlier legal selection changes to
   a different named slot, the receipt subject and eligible promotion target
   change too. These are benchmark rules informed by PostgreSQL guidance, not
   claims that either SQL command ran on an upstream server.

Required paired interventions, changing only the named source, receipt, or
earlier-action factor while keeping the other world fields fixed:

| Intervention | Falsifiable outcome |
| --- | --- |
| Remove each load-bearing source span separately, and all occurrences of the readiness rule together | The fixed reference can no longer justify the same slot choice or readiness decision from visible material; evaluator legality itself stays fixed. Reject the item if the final prompt or a duplicated note gives the answer anyway. |
| Change one environment-issued PASS to FAIL, use a stale revision, omit one required slot, or mismatch receipt subject | Promotion becomes illegal and hold remains legal; a policy-generated verification claim cannot substitute for the receipt. A fresh verified repair can restore promotion if the earlier action was valid. |
| Remove or change the session-1 finalize action while keeping the later source and receipt unchanged | The previously eligible promotion is refused. A same-session finalize cannot satisfy the pre-reset snapshot. Switching the prior chosen slot changes which later receipt and promotion target are relevant. |
| Add equal-length irrelevant SGML material or rename distractor slots | The legal decision and a robust reference path remain unchanged. |

Measure final rendered chat tokens with the pinned worker tokenizer, evidence
offsets and distance to the later question, carry bytes, legal-action vectors,
source/receipt/action intervention results, fixed-reader success, and all
worker/auxiliary calls under a freshly projected budget. Test actual
`run_session_sequence`, not just a builder function. With no world, byte pins,
or model pilot yet, this is **one candidate parent**, not a qualified C
sample or a population effect estimate.
