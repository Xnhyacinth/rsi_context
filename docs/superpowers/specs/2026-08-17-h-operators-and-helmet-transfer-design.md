# Design: widen H operators + HELMET transfer (not a new answerer)

Date: 2026-08-17
Status: T1 + T2 smoke implemented; HELMET clone still blocked on dry-run review
Scope: RSI harness for frozen-reader long context. Does not start A2.
Does not jointly optimize KV. Policy still must not answer.

## Decision already taken

Keep the three-way boundary. Widen the **compiler** `H` (source + query → 8K
`ContextPack`), then transfer a **frozen** `H` to real benchmarks. First public
cell is HELMET RAG + Recall. Do not skip the synthetic difficulty gate. Do not
let policy code emit answers.

## 1. “Only compress input” is already the wrong slogan

Naive truncation is incomplete. This repo’s `H` is already broader than
truncate-to-8K:

| Operator                                       | Who produces it                | Policy may                                                            | Status now                                                  |
| ---------------------------------------------- | ------------------------------ | --------------------------------------------------------------------- | ----------------------------------------------------------- |
| Span selection                                 | source chunks                  | choose ids                                                            | live (`PolicySpecV1`)                                       |
| Graph expansion                                | rare-ID adjacency              | hops 0/1/2                                                            | live                                                        |
| Allocation                                     | RANK / MMR / coverage          | choose                                                                | live                                                        |
| Order / position reserve                       | policy                         | choose                                                                | live                                                        |
| Abstention                                     | policy                         | `INSUFFICIENT`                                                        | live                                                        |
| Extractive / abstractive **notes**             | **evaluator** `CompressedNote` | select via `substitute_extractive_notes` under `max_free_text_tokens` | dense emits 6 score notes; default landscape budget still 0 |
| Registered compressor (LongLLMLingua / RECOMP) | hashed baseline `H`            | not researcher-authored strings                                       | scheduled after landscape                                   |
| Bounded reread                                 | policy requests a short query  | not executed                                                          | blocked until adaptive call ledger                          |
| KV eviction, tools, answering, weight updates  | —                              | no                                                                    | out of this paper                                           |

Long-context ability in this harness is **which evidence reaches a frozen
reader, in what form, under a budget**, plus later **whether a coding
researcher can discover a better `H` than matched search**. It is not
recursive self-improvement of Qwen.

## 2. Summary and similar strategies

**Yes, summary belongs in the harness. No, the policy must not write free-form
summaries.**

RECOMP’s extractive sentences, abstractive distillations, and empty context are
the right prior. They sit in the same slot as `H`. The type `CompressedNote`
already requires `source_chunk_ids` and forbids invented notes: a pack may only
include notes the evaluator already attached to the `Artifact`.

Allowed:

- Evaluator-owned **extractive** notes (sentence/clause kept from named spans).
- Evaluator-owned **registered abstractive** notes from a pinned transform
  (hash the transform id + source span ids + text). Policy only chooses whether
  the note enters the 8K pack.
- Empty/abstain (RECOMP’s “unhelpful → empty”).

Forbidden in the matched primary estimand:

- Researcher Python that generates new unbound text (“here is my summary: …”).
- Answer-shaped notes (must not contain the gold identifier).
- Unbounded ACE-style playbooks as the A2 object.

If a transform cannot point at source spans, it is not an `H` operator; it is a
second reader.

## 3. Real benchmarks

HELMET/RULER/LongBench/LME are the **A2 fitness landscape** once a public
cell passes `evaluate_public_offline_difficulty` (and later a reader gate).
They are not a way to declare the homemade 32K panel passed. Synthetic Repair
A/B/C landscapes stay immutable diagnostics. Pack budget stays an envelope
(default 8K); source length follows the public file (32K, 128K, k220, …).

First public cells (offline screen, Qwen tokenizer, 0 reader calls):

- Recall: RULER `niah_multikey_2` at 32K→8K, 128K→8K, and 128K→32K (lexical saturates)
- Recall: JSON KV k1800→8K (keyed lookup; lexical saturates once the UUID is intact)
- Recall: RULER `qa_2` / `qa_1` at 32K–256K with 4K or 8K packs
- RAG: KILT NQ k50→8K (negative control: not binding), k220→4K, k220→8K, k440→8K
- RAG: HotpotQA k220→8K and TriviaQA k220→8K

Offline v1 (NIAH/JSON-KV/RAG) failed every cell without relaxing 0.90. Offline v2
passed **RULER qa_2 128K→8K** (primary), plus qa_2 128K→4K, qa_2 256K→8K, and
qa_1 128K→4K. Do not treat 256K as primary while the tokenizer warns above 131072.

LongBench-v2 QA is not an extractive packing cell: most gold choice strings are
not literal source spans, so the answer-in-source kill would fire. Keep it as
later reader transfer, not T0-public identification.

Offline kills: pack not binding, answer missing from source, or any non-oracle
packer already placing the answer on ≥90% of items. Do not relax those
thresholds to force a pass. Official HELMET scores stay unlabeled until the
upstream scorer is wired.

## 4. Experiment tiers

**T0-synthetic — diagnostic only**  
Homemade 32K compositional/dense `evaluate_difficulty`. Failed landscapes are
kept. They no longer block choosing a public cell.

**T0-public — identification for A2 (new)**  
Offline screen passed on RULER `qa_2` 128K→8K. A reader landscape using
`evaluate_public_reader_difficulty` is still required. A2 stays refused until
that reader gate passes **and** isolation is attested. Official HELMET scores
remain unlabeled.

**T1 — operator completeness on the synthetic panel**  
Emit evaluator extractive `CompressedNote`s on hard artifacts. Give
`PolicySpecV1` (or one new canonical key) a note-vs-span allocation choice.
Lock: notes have provenance; notes do not contain answers; hops=0 still cannot
saturate dense scores.

**T2 — HELMET frozen-H qualification**  
Adapter: HELMET/RULER passages → `Artifact` chunks. Run head / lexical /
strongest `PolicySpecV1` / full-context (length permitting) on a small RAG+Recall
slice. No researcher in the loop. Kill if adapter silently truncates, unpins
revisions, or scores hidden reasoning.

**T3 — A2 then freeze `H` and transfer**  
Only after T0. 2×2×2×5 factorial vs Random-5 / Sequential-search-5. Selected
`H` evaluated once on HELMET RAG+Recall (and later LME). LongLLMLingua/RECOMP
enter as method baselines on the same 8K budget, not as grammar keys.

## 5. First implementation slice (after spec approval)

1. Tests for “policy cannot mint `CompressedNote`s”; generator emits at least
   one extractive note family on dense leftover (T1 minimum).
2. Registry dry-run for `helmet` + needed RAG data; do not download until the
   plan is reviewed in-session.
3. Thin HELMET RAG adapter + frozen packer runner (T2 smoke, N small).
4. Do not start A2. Do not overwrite Repair A/B/C landscapes.

## 6. Falsifiers

- Public-bench gain with no matched search and no synthetic gate → do not claim
  researcher RSI.
- Summary notes without provenance or with gold ids → treat as answerer leak.
- Joint KV+semantic scores on one leaderboard → reject.
- “SOTA compressor via RSI” before A2 + transfer → reject.

## 7. What this paper is for

A coding researcher can expand a frozen model’s long-context **accuracy and
efficiency** by improving a budgeted, provenance-preserving compiler `H`
(select / order / cover / abstain / registered notes), and that gain is
identifiable against matched search and then visible on HELMET-style tasks.
Not: a new compressor architecture, recursive weight RSI, or an agent that
answers the question.
