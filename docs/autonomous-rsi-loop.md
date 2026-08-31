# Autonomous research loop for RSIBench-Context

Status: protocol decision and partial implementation, 2026-08-31. No formal A2
or A3 trajectory has been authorized.

## Decision

RSIBench-Context does not copy MGM's `hgm.py` loop. It uses a benchmark-owned,
fixed-budget research loop whose editable object is only the context policy.
The coding researcher may reason over prior visible evidence and rewrite
`policy/*.py`; it may not rewrite the researcher loop, reader, serving stack,
decoding, allocator, scorer, labels, split logic, or admission rule.

This preserves the paper's intended estimand: whether a coding researcher can
discover and retain a better information interface for a frozen reader. A loop
that also evolves its evaluator or agent scaffold would instead measure
harness evolution and would overlap MGM, Recuris, AHE, and DGM.

## What is borrowed from current RSI systems

MGM evolves executable coding-agent scaffolds through clonal, reaction-norm,
and cross-lineage evidence, using a fixed task-evaluation budget and an archive
search. Its reported main budget is 200 task evaluations and 24 expansions,
not a five-round linear dialogue. Its current implementation also gives the
outer improver information that would be evaluator-private under this
benchmark and exposes a much wider writable repository. We therefore borrow
comparative evidence packets, not its writable surface or tree controller.
See the [MGM paper](https://arxiv.org/html/2608.07645) and
[official implementation](https://github.com/RealLcz/MGM).

Recuris freezes the model and Meta-Agent while evolving four external memory
components from structured execution traces, then applies a validation gate.
This motivates component-scoped manifests and event-level traces. Recuris also
distinguishes committed packages from provisional exploration in its current
implementation; an uncommitted working lineage is not evidence of verified
improvement. Its long-horizon memory setting is a transfer baseline, not a
replacement for the static long-document identification surface. See the
[Recuris paper](https://arxiv.org/html/2608.24876) and
[official implementation](https://github.com/Gen-Verse/Recuris).

## Frozen loop

One trajectory is bound to an immutable contract before the first reader call:
dataset bytes and split, visible item digests, reader/researcher identities,
token axis, H0 bytes, policy grammar, rendered-input envelope, candidate slots,
target and auxiliary calls, retries, timeouts, feedback bytes, scorer, and
selection rule.

For each candidate slot, the benchmark performs this sequence:

1. Give the researcher only the visible parent artifact, prior visible
   structured trace, prior diff, scores allowed by the feedback contract, and
   remaining fixed resource ceilings.
2. Require a new Python-only `policy/` tree and a manifest that predicts item
   flips, affected policy components, and token/call changes.
3. Audit and snapshot the complete policy tree in a fresh worker. Invalid,
   missing, duplicate, timed-out, or unsafe submissions consume the slot.
4. Collect every item's desired rendered length and positive priority. The
   evaluator joins these preferences to evaluator-counted fixed overhead and
   applies frozen, order-invariant weighted water filling to the complete
   split. A policy cannot author overhead or allocation fields.
5. Assemble every `ContextPack`, render every complete chat request with the
   frozen tokenizer/template, and validate per-item maximum, output reserve,
   and batch input cap before the first target call. Any failure makes zero
   target calls.
6. Make exactly one target-reader call per valid item in the semantic
   single-reader track. Record the policy hash, selected provenance, allocation,
   order/compression/verification events, rendered prompt digest, answer,
   external score, and accounting.
7. Return only committed visible feedback. The next attempt follows the last
   valid attempt, while `historical-best` is maintained independently by the
   benchmark. Always report last, peak, regret, and peak-regression rate.

After all slots, visible scores select one artifact using score, then lower
pre-dispatch rendered tokens, then earlier attempt. Gate evaluates that frozen
artifact once and never returns item-level outcomes to the researcher. Sealed
evaluation occurs once after all policies and analysis rules are frozen.

## Editable surfaces

The primary matched A2 arm remains a finite evaluator-owned grammar so
researchers, Random-5, Sequential-5, and gold-aware search operate over the same
behavior classes. It exposes dataset-agnostic choices for desired length and
priority, evidence selection, bounded graph expansion, coverage allocation,
ordering, and pre-reader evidence verification with deterministic in-envelope
fallback. The primary arm still makes exactly one target call per valid item.

A secondary open-program arm may use multiple audited Python files under
`policy/` and may invent deterministic combinations of those operators. It is
reported separately because unrestricted Python cannot be matched to a finite
random-search baseline. Compression text must remain evaluator-produced and
source-linked; a policy may select trusted notes but may not write evidence or
an answer. Abstention and reread belong to separately cost-matched at-most-one
and adaptive tracks; they are not silently mixed into the exact-one-call
primary estimand.

Long-horizon transfer freezes tools, task policy, skills, environment, reader,
and official evaluator. Only trajectory selection, state/working-memory
compression, ordering, invocation triggers, memory update, and policy-level
verification may vary. It must include a frozen-memory retry control sharing
the first rollout and total call/attempt budget. These transfer outcomes never
feed back into A2 discovery fitness.

## Evidence modes and round counts

The base A2 feedback mode uses one policy's own visible failures. Two
pre-registered analysis arms can later reuse already paid traces without extra
reader calls:

- reaction-norm evidence compares the same policy across length, position, or
  task-profile conditions;
- cross-policy evidence compares two policies on the same visible item and
  resource envelope.

These are information ablations, not changes to the evaluator or extra search
budget.

Round counts are fixed by stage, not chosen by the researcher:

| Stage                        |           Autonomous candidate slots | Purpose                                                                     |
| ---------------------------- | -----------------------------------: | --------------------------------------------------------------------------- |
| infrastructure/qualification |                                    0 | establish replay, difficulty, causal, cost, and isolation gates             |
| A2 micro RSI                 |        5 per researcher/profile/seed | estimate discovery and immediate retention against matched five-call search |
| A3 main matrix               |       10 per researcher/profile/seed | estimate peak regression and longer-run retention only after A2 gates pass  |
| long-horizon transfer        | 0 policy updates on evaluation tasks | test a frozen selected policy with matched retries/attempts                 |

Stopping early because a researcher believes it has converged is not allowed in
the primary estimand. A pre-registered e-value stopping analysis may be reported
separately, while every matched arm retains the same maximum opportunity count.

## Current executable status

`elastic_envelope.py` now implements the evaluator-owned envelope, split-wide
integer allocator, complete rendered-batch preflight, and frozen chat-render
token counter. It deliberately separates policy-authored length preference
from evaluator-owned item identity and overhead. The A2 controller refuses the
legacy fixed-budget schema before any reader call.

The two-stage candidate worker, elastic `PolicySpec` grammar, schema-v2 A2
plan, matched elastic controls, independently pre-registered unseen hy3 signal
confirmation, and formal researcher/evaluator isolation remain launch gates.
Consequently the existing fixed-8K autonomous scripts are qualification
instruments, not the executable elastic A2 loop.

The next API-reader experiment is not another run on the observed PopQA panel.
The existing hy3 block found a meaningful lexical-versus-head point contrast
but failed its pre-registered uncertainty and unstable-item sensitivity gates.
Before any hy3 researcher receives scores, an unseen fixed-policy confirmation
must be committed and pass without changing the original failure record.
