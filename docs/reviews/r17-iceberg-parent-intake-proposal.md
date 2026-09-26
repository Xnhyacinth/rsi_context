# Apache Iceberg specification as a distinct-parent intake proposal

**Status: source scouting only.** No Iceberg repository or dataset has been
acquired, no registry entry or benchmark world has been added, and no model
call, oracle or parent qualification is claimed. Do not use an unpinned branch
in an experiment. The official Apache Iceberg `apache-iceberg-1.9.2` tag
peeled through `git ls-remote` to commit
`071d5606bc6199a0be9b3f274ec7fbf111d88821`; the proposed file is
[`format/spec.md` at that commit](https://github.com/apache/iceberg/blob/071d5606bc6199a0be9b3f274ec7fbf111d88821/format/spec.md).
File bytes, license notice, blob ID and SHA-256 are **not yet measured**;
acquisition would first require a versioned `configs/registry.json` entry and
reviewed dry-run plan.

This source offers a stronger long-form dependency hypothesis than the short
Kafka migration page. In the pinned specification, the sequence-number
inheritance section distinguishes a file's **data sequence number** from its
file sequence number and explains inherited/null entries and v1 defaults
(rendered lines 714–728). The later scan-planning section makes equality
deletes apply only when the data sequence number is **strictly less** than the
delete's sequence number, plus a partition equality or unpartitioned-delete
condition (lines 829–845). The equality-delete section later explains which
column values identify matching rows, including dropped-column behavior
(lines 1045–1085). A reader task could require combining these sections in
one later scan decision, rather than finding a single local sentence.

An offline candidate would survey the complete authentic spec, then receive
a constructed table/manifest/delete state after a session reset. For example,
an existing data file can have data sequence 7 but file sequence 12; an
unpartitioned equality delete can have sequence 8. The evaluator must use
the **data** sequence and global partition exception when deciding whether
the delete applies. A later update may alter the constructed metadata while
the source remains fixed. A matched source-rule counterfactual would hold
every non-source field, request, receipt and policy-visible metadata fixed,
change all equivalent source-rule statements consistently, and flip only the
private legal scan action. The edited text must be labelled constructed and
cannot count as a second real Iceberg revision or independent parent.

The intake must still reject shortcuts: deidentified source-free and
identity-only model runs, a fixed default-action probe, complete-source
reference solvability, exact tokenizer positions, two reader families,
irrelevant equal-length edits and source-rule removal are needed before any
claim of long-context source use. An identity cue such as “Iceberg v2” may
let a model answer from prior knowledge; a long file by itself is not a
dependency test. After a registry-approved checkout, scan the entire pinned
file for equivalent delete-scope and sequence rules, independently adjudicate
the oracle, and measure final-chat geometry before allocating provider calls.
This is an alternate distinct-project route if Kafka remains too short for
the benchmark's long-context parent gate.
