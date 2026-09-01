# Open-S harness track

Status: **executable seed and isolation contract; no paper-scale discovery result**.
This track is a separate leaderboard from restricted `PolicySpecV1` A2. Do not
pool it with matched-grammar A2, HELMET transfer, or KV/system runs.

## Estimand

Can a general coding researcher, starting from a **byte-identical seed
directory** and an isolated workspace, autonomously evolve a folder strategy
system \(S\) that compiles long source into one frozen-reader `ContextPack`
better than H0 and a matched control?

The loop is unchanged:

\(H_{t+1} = R(H_t, F_t; B)\), then \(F_{t+1} = E(M_0(H_{t+1}(x)))\).

Only files under the isolated `policy/` tree change. Reader, decode, scorer,
labels, envelope, and promotion stay frozen.

## Why a folder system, not a single compressor

Restricted A2 asks researchers to select a canonical `PolicySpecV1`. Open-S
borrows harness-evolution structure from Mendel Gödel Machine (archive/clone
from a fixed seed), Darwin Gödel Machine / AHE / HarnessCompass (component
files plus rollback), and Recuris (evolve memory/skills while freezing the
model and outer improver). The object is **long-context / long-horizon
information routing**, not weight RSI and not ACE playbooks inside the reader.

Related work that must not be copied blindly:

| Borrow | Do not copy |
| ------ | ----------- |
| Fixed seed, isolated clone per trajectory | Uncounted extra evals or live-bench retries |
| Rewritable retrieve / route / memory / merge files | Rewriting evaluator, reader, decode, or metrics |
| Logical parallel map then merge into one pack | Extra unlabeled target-model calls or auxiliary LLMs |
| Held-out gain vs matched sampling/refinement | Internet tools, gate labels, writes during sealed eval |

[Harness evolution vs matched search](https://arxiv.org/abs/2607.12227) is
mandatory here: an open folder is not an advantage until it beats matched
parallel sampling and sequential refinement under the same budget.

## Frozen initial state

Canonical seed: `seeds/open_s_v1/`.

- `seed.py` and `policy.py` are byte-identical at H0 (`seed.py` is the H0
  entrypoint; `policy.py` is the campaign candidate entrypoint).
- `retrieval.py`, `skills.py`, `memory.py` are local modules the researcher may
  replace. H0 re-exports frozen operators from `rsicontext.policy.open_s`.
- `task.py` states the job as Python constants. Task text is not a hashed
  secret; gate/sealed labels remain evaluator-only.
- Only `.py` files are allowed. Each trajectory is copied into a new
  workspace/`policy/` tree and re-hashed. Mutating one isolate cannot change
  the committed seed.

H0 composition: **source-order full-as-fits** (`pack_spans` on `artifact.chunks`).
Retrieve, route, shard, and memory helpers remain in sibling files for the
researcher to wire. A lexical retune of overlap ranking is one mode among
full, truncate, rag, parallel, and select-compress, not the default search.

## Operator budget

Allowed if accounted and they still produce **exactly one** target-reader call
on the primary semantic track:

- retrieve
- summarize with provenance (notes tied to source chunk ids)
- pack
- in-item memory write (no cross-item persistence on this track)
- skill route
- parallel map → merge into one pack (logical shards; no threads)

Forbidden: network, answering the question in policy code, calling the reader,
rewriting serving/decode/metrics, extra unlabeled reader calls, candidate-defined
limits, and leaking gate/sealed labels.

The frozen library is a convenience. A researcher may reimplement every operator
locally; the auditor still applies.

The **open-S pack envelope is the frozen reader window** minus output and a 16384
token render/axis reserve, not a historical 8K HELMET instrument. Full-as-fits is
H0. Retrieve/RAG, truncation, logical parallel merge, and smaller select-compress
packs are researcher hypotheses. Items longer than the window still require
selection. Policy-authored unbound summaries are forbidden. Extra reader calls
and auxiliary LLMs stay forbidden: the explorer is the researcher, not an
agentic reader loop.

## Isolation and audit

- Campaign materialization still copies only `policy/*.py` into a clean
  workspace and requires `manifest.json`.
- `PolicyAuditor` now allows imports of **sibling modules that exist in the
  same audited tree**, and submodules of allowlisted packages such as
  `rsicontext.policy.open_s`. Relative imports, `os.py` shadows, writes, and
  dynamic code remain forbidden.
- The fresh policy worker appends the audited tree to `sys.path` so local
  modules load without shadowing stdlib.

## Reporting

- Track id: `open-s-harness-v1`.
- `qualification_only` until isolation, replay noise, and matched controls are
  met.
- `rsi_launch_eligible` remains false for H0 canaries and skipped credential
  runs.
- hy3-ioa may be used as a one-item H0 canary or labelled replication reader.
  It is not the paper's frozen open reader.

## Built versus remaining

| Piece | Status |
| ----- | ------ |
| Byte-identical seed, isolated copy, digest | done |
| Sibling-module auditor + worker `sys.path` | done |
| Frozen retrieve/route/pack operators | done |
| Campaign prompt `policy_track="open-s"` | done |
| API researcher multi-file `policy_source` object | done |
| H0 hy3 canary (1 item, 0 rounds) | done; not discovery |
| Open-S researcher campaign on PopQA | 8K dual-role 2026-09-01 failed (identical H0 + JSON exit); window-envelope cell is `docs/open-s-visible-scenario.md` |
| Matched sampling / sequential control | missing; required before advantage |
| Reader-window pack envelope for open-S | done for visible launches; not the A2 elastic allocator |
| Formal isolation / A2 factorial | still refused |

Launch an open-S visible pilot with `policy_track="open-s"` and
`initial_policy_directory=seeds/open_s_v1`. Defaults bind the frozen window
scenario in `docs/open-s-visible-scenario.md`. Do not pool with restricted A2.
Do not pass `--pack-tokens 8192` on this track.

## Micro trial

```bash
uv run python scripts/open_s_hy3_h0.py --output results/open-s-h0-hy3
```

Without `COPILOT_API_KEY` / `COPILOT_BASE_URL` the script records
`credentials_missing` and exits 0. That is not a discovery curve.
