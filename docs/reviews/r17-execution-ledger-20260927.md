# R17 independent-parent and diagnostic execution ledger

Status: **R17 KEP paid diagnostic completed; no GPU call and no qualified
independent parent**. All R17 branches began
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
| `work/r17-kep` | Independent worker: registered post-R16 KEP arithmetic/anchoring diagnostic, guarded paid runner and offline failure tests; integration owner admitted the bounded paid block after review. |
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

## R17 outcome and merge gates

The [Kafka offline candidate](r17-kafka-migration-candidate.md) passed its
five construction tests and a clean branch review, but remains **deferred**
as a long-context parent: its relevant authentic protocol file is 5,375
bytes, and longer pages in the pinned source do not carry the needed
migration rule. No Kafka model call was made. The
[Iceberg intake proposal](r17-iceberg-parent-intake-proposal.md) identifies a
separate, pinned multi-section specification route; it is a scouting record
only, with no registry-approved acquisition or task result.

The reviewed KEP launch registered four diagnostic target calls, two
canaries, zero auxiliary calls and a 13,618-token local-input-plus-requested-
output planning ceiling. A reviewer reproduced a final-reply format bug in
the first runner version; the accepted fix and regression test prevent a
malformed fourth answer from marking the block valid. A clean producer then
completed the [real R17 diagnostic](r17-kep-arithmetic-diagnostic-result-20260927.md):
**six Siflow requests, 1,330 provider input / 71 output tokens, unknown usage
zero**, with every request and response journaled. Its source-free and
identity-only parent controls were not run, because this was a post-hoc
mechanism diagnostic rather than a source-dependency screen. The observed
sidecar-membership reversal and 1200m answers do not qualify KEP.

Final `codex review --base origin/main` found no actionable defect; 14
focused tests passed under the pinned tokenizer. The full clean integration
gate passed **1573 tests, 16 skipped, 80.91% branch coverage**. The
[pytest log](/volume/pt-dev/qjiu/rsi_context_external/r17-preflight/full-pytest-integration.log)
SHA-256 is `ff7caedc8dbaa2e4886f378b1cabc26f1fdb94dbda00a63cdd7df9bf1df45789`.
The test process used the pinned source/tokenizer roots, a dummy
`SIFLOW_API_KEY` and no `SIFLOW_BASE_URL`, so it made no real provider call.
Repository Ruff and configured strict mypy passed (390 files). Bandit found
the unchanged 81 LOW and 2 MEDIUM baseline, with no R17 or Kafka file in its
[JSON report](/volume/pt-dev/qjiu/rsi_context_external/r17-preflight/bandit-integration.json)
(SHA-256 `b485899d38dfbbf7b8e55123ce9277c6be348956c6fe203b8556bb76a57aebb5`).
Fifteen skipped tests are jailed execution cases refused by the unchanged
host ownership gate; one is live API smoke without a configured base URL.

Next, calibrate a new KEP reader by providing the actual ordered-prefix
rule in model-visible carry and checking arithmetic with an oracle-projected
short-input baseline **before** another full-source spend. Then freeze a new
full-source/control budget only if that baseline is feasible. For a distinct
long-form parent, advance the Iceberg proposal through registry dry run,
immutable acquisition, semantic equivalent-rule audit and a matched offline
world; do not promote Kafka by adding unrelated source length. The researcher
pretest still needs a trusted runtime and live adapters, as detailed in the
[R17 runtime audit](r17-researcher-runtime-and-budget-audit-20260927.md).
