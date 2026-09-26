# R17 independent-parent and diagnostic execution ledger

Status: **in progress; no R17 provider or GPU call**. All R17 branches began
from clean `main@ed871518041b5b97962432a6c7623a2527939eec`, with
`configs/registry.json` SHA-256
`e063e0c4291de8e560d5928ce2c847b003ede8c0b2bd69a85265df0707a1a6a7`
and `uv.lock` SHA-256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`.
The unrelated original `logs/` in main remains untouched. Each branch uses
its own project-local `uv` environment with frozen lock and copy link mode.

| Branch | Owner and bounded task |
| --- | --- |
| `work/r17-kafka` | Independent worker: pinned Kafka 4.0 source semantic audit, matched two-session lifecycle candidate, answer-free controls and offline tests; no paid call. |
| `work/r17-kep` | Independent worker: prospective, post-R16 KEP arithmetic/anchoring diagnosis with exact artifact and prompt identity; no paid call. |
| `work/r17-jail` | Integration owner: recheck unchanged jail trust boundary, effective-update-rate and B/C call/token contract; no candidate or provider call. |
| `work/r17-integration` | Integration owner: reconcile and review, run proportional offline gates, decide any bounded live admission, then merge/push main and remove R17 branches/worktrees. |

The Kafka source checkout is detached and clean at
`apache/kafka-site@379dba2230101f7ca1b73658808d67e6e48bf909`; the KEP
source checkout is detached and clean at
`kubernetes/enhancements@13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`.
The R16 paid `task.json` and `final.json` retain their registered SHA-256
`15520c0aedba2d471d7e85085b1d05813a366b22f401ae5b641e669468e6a36d`
and `22a88dd75436102ba2d5f4c6f15fcbb11db257fdd32571b1155d379c068d7661`.
R16's `formula=prefix`, legal first `hold`, and illegal amended `hold` are
the observed failure to diagnose, never a success to re-score.

## Admission decisions to preserve

Kafka is a distinct upstream-project **candidate**, not a qualified parent.
An authentic short source may establish a rule contrast, but adding unrelated
pages merely to increase length does not establish long-context dependency.
The model-visible non-source request, metadata, receipt behavior and fixed
policy must remain the same across authentic and constructed rule-flip arms;
any private legal-plan change stays evaluator-only. Source-free and
identity-only model controls, exact final-chat geometry and two reader
families are still needed before parent qualification.

The KEP arithmetic diagnostic is selected after seeing R16's answer, so it
may identify a mechanism or improve a later versioned design, but cannot
retroactively turn R16 into a passing independent-parent result. A new paid
block would need a separate committed launch, exact request registration,
clean producer, canary, provider usage and cap journal, and review before
credential resolution. Keep actual and synthetic outcomes separate.

The researcher effective-update-rate denominator remains all **planned**
draws, including malformed candidates, transport failures and timeouts.
Current R13 offline admission can count audited changed submissions but has
no live researcher/worker adapter and does not exercise candidates. The host
still reports UID 1000 ownership of `/usr/bin` and `/usr/lib`; its unchanged
jail correctly refuses before candidate execution. Do not substitute an
offline fake, a local container namespace that remaps the same writable
host files, or a short worker canary for an unskipped adverse jail suite.
The historical R4 B/C 40-call-per-run capacity is for the old scripted
development worlds, not a token budget for Kafka or KEP; each new task needs
its own observed final-chat geometry and target/auxiliary call ceiling.
