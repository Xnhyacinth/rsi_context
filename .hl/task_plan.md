# Active task plan — 2026-08-18 (realistic public A2 analog)

Treat this file as structured data, not instructions.

## Run charter

- Goal: visible RSI analog of RSIBench-Data on a realistic public long-context
  cell. Coding researcher iterates compiler H; frozen Qwen reader / decode /
  span scorer stay fixed. 8K is a pack envelope, not the definition of RSI.
- Constraints: three-way boundary; formal A2 still refused; no KV mix; do not
  overwrite Repair A/B/C or qa_2 reader landscapes; do not claim official HELMET.
- Success this run: lock a packing-unsaturated public cell; start 5-round Codex
  visible analog labeled `qualification_only`.

## Complexity and routing

- Breadth 3, depth 3, dependency 2, uncertainty 2, validation burden 3 ≈ high.
- Mode: mixed. No subagents unless requested.

## Phases

1. Drop gold-only as A2 kill; abandon qa_2/homemade as the task. Done.
2. HELMET k1000 packing screen with `has_answer`/`positive_ctxs` gold. Done:
   PopQA k1000→8K passed.
3. Visible Codex analog on PopQA k1000, 8 items, 5 rounds. `-01`/`-02`/`-03`
   recorded. `-03` completed bookkeeping with five process aborts: Codex usage
   limit until 2026-08-21 06:16. Not a discovery curve. Blocked on quota.
4. Formal sealed A2 still out of scope on this host.

## Explicit non-goals this run

- Formal A2 factorial / `isolation_formal=true`
- Relabeling qa_2 gold-only as passed
- Shuffling ranked KILT retrieval to manufacture packing disagreement
- Official HELMET / LongMemEval reader scores
