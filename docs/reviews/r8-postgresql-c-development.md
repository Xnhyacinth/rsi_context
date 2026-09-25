# R8 PostgreSQL 17 C development candidate

Status: **offline construction witness; Gate 2 source dependence rejected**.
This is one proposed parent lineage, `postgresql17-failover-slot-readiness`,
with three recorded versions of the current environment outcome. It is not a
qualified, scored, or sealed task.
No PostgreSQL server, Siflow API, or GPU was used.

## Source and constructed state

`material_postgresql_c.py` verifies the complete pinned `REL_17_0` logical
replication SGML, CREATE SUBSCRIPTION SGML, and COPYRIGHT bytes before it
builds either session. The commit and selected file/span SHA256 values are in
`configs/r7_postgresql_source_manifest_v1.json`. The full COPYRIGHT notice
is included beside the source documents. The source supports the facts that
the named slot's failover property can differ from the subscription option,
slot synchronization is asynchronous, the standby must be ahead of the
subscriber, and every required subscription and **finished** table-copy slot
must be present and ready before promotion. An unfinished table-copy slot is
not automatically part of that required set.

The subscription names, publisher-slot inventory, standby inspection,
verification oracle, and `promote-*`/`hold-*` actions are explicitly labelled
**constructed benchmark sandbox state**. The project has one active
subscription with two **mutually exclusive** candidate slot configurations
and one invalid decoy. Only the chosen configuration's subscription and
finished-table-copy slots are required for the proposed standby; an extra
unfinished copy is a distractor. A policy can finalize either aligned
candidate after an environment-issued `slot-selection` PASS. A fresh policy
process receives
only bounded carry in session 2, but it can reread already revealed source
and query the persistent sandbox record. The second-session `act_verify` gate
requires that the current action map to the *actual prior finalized plan* and
cites current environment checks. Promotion requires both the subscription
and table-copy readiness checks and a standby-ahead check to PASS; a hold
requires a PASS `standby-not-ready` check. The visible constructed action
interface gives the exact plan and check names for A and B without declaring
which source-defined slot states are required or revealing current verdicts.
The earlier inspection is only a prior snapshot,
so the current oracle can reveal an asynchronous failure without changing
that visible report.

Canonical JSON SHA256 (`to_dict()`, sorted keys, compact separators,
UTF-8, `ensure_ascii=False`):

| Variant | Session 1 | Session 2 | Ordered pair |
| --- | --- | --- | --- |
| Chosen candidate's required checks ready | `21f1b9801f8b93fa74c2f22c794be5d25746926e227fad61cec168694f11cf2e` | `26e6eb79bdf22b01312df3599d7e7ec5b9cc1719a8be10d0579c17885df17edc` | `4efd7ec6fe5d473619f9630cfeb9c4e7efb3d0c0a25183c53d97e1727c6ab8eb` |
| A finished table-copy check now fails | `21f1b9801f8b93fa74c2f22c794be5d25746926e227fad61cec168694f11cf2e` | `c4570c973e9a2250d7cb92eae3c84ca2b095b3f0464dbf7ded0e099b7b3a7d2b` | `2c5226437c1c5daf92b4cc9c35d59dcd894d1b4bdd3755a46a2456b040f5812a` |
| Standby is now behind the subscriber | `21f1b9801f8b93fa74c2f22c794be5d25746926e227fad61cec168694f11cf2e` | `d861e723ffcbcd0a2ca4d7b484667cb7f5fbc64e321a4038992f9a576354fd32` | `42781a48acbca8dd14a1fe115d64311aef5a1991572b9a366b6353e68c7dbd4e` |

The session-1 source document strings contain 78,714, 25,113, and 1,256
UTF-8 bytes including their marker/title wrappers. These are **bytes**, not
worker tokenizer counts or final request lengths.

## Offline intervention results

The trusted scripted witness runs through real `run_session_sequence` with
one `ProjectState`, shared budget and document registry, and a new policy hook
per session. `tests/test_postgresql_c.py` passed 15 focused cases:

| Controlled factor | Observed legal path |
| --- | --- |
| Same world and readiness oracle; prior verified/finalized `slot-a` versus `slot-b` | Both sessions pass; later plan changes `promote-a` to `promote-b`. Each path receives subject-bound receipts; source and later report stay fixed. |
| Same visible stages and prior `slot-a`; fresh table-copy A receipt changes PASS to FAIL | Later `promote-a` changes to `hold-a` after a current `standby-not-ready` PASS; both paths pass. The inactive B path still promotes. |
| Same visible stages; fresh standby-ahead receipt changes PASS to FAIL | Both A and B hold after a current `standby-not-ready` PASS. |
| In-progress copy check FAIL while all required active checks PASS | Promotion remains legal; a source-blind rule demanding every visible slot would hold incorrectly. |
| Remove the constructed action/check interface | The scripted witness cannot choose a later plan; exact API strings and subject semantics are visible before the commit. |
| Prior `slot-a`, later forced `promote-b` | Later gate rejects the prior-to-later plan mismatch. |
| Missing, late, or participant-forged first verification/finalization | Both session checks fail; a later action cannot repair a missing prior PASS. |
| Remove an exact alignment, asynchronous-sync, or finished-copy source phrase | The scripted witness cannot commit; adding an irrelevant note preserves both passes. |
| Withhold both SGML source documents, then use a hardcoded source-free action map | Both sessions still pass, exposing a source-dependence qualification gap. |
| Change a selected SGML byte before building | The builder rejects the source before exposing a world. |

The source-ablation paths are **scripted structural checks**: the witness looks
for exact source phrases. A separate source-free hardcoded policy still passes
with both SGML documents withheld. Thus the task **does not pass Gate 2 source
dependence**; this cannot establish that a real fixed reader needs the long
document. The policy rereads the source and queries the sandbox after
reset, so these tests do not prove that carry memory is necessary. The
grader permits an immediate hold after a current `standby-not-ready` PASS;
the scripted witness happens to check positive readiness first, but the gate
does not require that order. A direct verified hold is a legal safe strategy.
The versioned metadata uses a whitespace scale estimate; final rendered chat
tokens, source-to-query offsets, position robustness, reader errors, and
hardness against simple filters remain unmeasured. All variants inherit the
same parent lineage and add **zero qualified independent parents** today.
