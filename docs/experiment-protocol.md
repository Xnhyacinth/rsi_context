# Experiment protocol

The executable A2 factorial, difficulty thresholds, primary estimand, rival
hypotheses, and launch gates are frozen in
[`a2-preregistration.md`](a2-preregistration.md).
The project-level research question, RSI terminology, resource allocation, task
ladder, and post-Recuris claim boundary are normative in
[`study-contract.md`](study-contract.md).

## Pre-registered questions

- Does a researcher discover a policy better than its first valid attempt and
  matched static/search baselines?
- Does it retain that improvement after continuing to search?
- Are item-level improvement and regression predictions calibrated?
- Does a selected policy transfer across length, evidence topology, domain, and
  reader backbone?
- Does the same bounded context-policy locus transfer from static documents to
  offline agent trajectories?

## Tracks

`single_reader` permits exactly one target-reader call per item and is the only
implemented track. The configuration parser currently rejects `adaptive` and
`kv` so their unimplemented budgets cannot be mistaken for enforced contracts.
The future adaptive track must enforce verification/reread/recursive target and
auxiliary calls, input/output tokens, GPU seconds, and wall time. KV compression
will remain a separate systems track and never contribute to the semantic policy
leaderboard.

## Split contract

- Visible: item-level feedback and gold evidence are available to the
  researcher.
- Gate: used by the fixed promotion rule; no questions, labels, or item-level
  scores are returned.
- Sealed: private templates/seeds/labels on an isolated evaluator; run once
  after freezing the campaign.

Public LongBench variants are transfer sets, not sealed sets.

## Static and long-horizon profiles

The primary profile compiles a fixed long document into one bounded reader
context. A separate offline long-horizon profile compiles an immutable agent
trajectory (observations, errors, paths, decisions, and memory records) into the
same typed `ContextPack`. It may study selection, evaluator-produced
compression, ordering, memory retention, and abstention. Bounded reread is a
reserved schema surface and is rejected by the current evaluator. This profile
must not turn the researcher loop into the task-solving loop or grant online
tools to the policy.

LongMemEval-V2, RLM, and Meta-Harness are pinned integration targets for this
profile. The LongMemEval-V2 text-only offline compiler is implemented and records
source-file hashes, ordered state provenance, and full-haystack coverage, but no
long-horizon score is claimed yet. The remaining task adapters and all official
metrics still need budget-matched integration with the static-document track.

## Open and API reader blocks

The pinned open-weight reader is the reproducibility anchor. A remote API reader
is a separate experimental block and must pass pre/post protocol, returned-model,
usage, length, and replay canaries. It may not silently replace the open reader,
because a provider alias without an immutable revision can drift between rounds.
API results omit unavailable KV/HBM/GPU/cache measurements rather than estimating
them. See `docs/api-hy3-experiment-plan.md` for the registered `hy3-ioa` block.
Remote and local scores must not be pooled unless decoding contracts match. In
the current qualification the remote profile cannot explicitly toggle thinking,
whereas the local profile records `chat_template_enable_thinking=false`; the
per-task output cap must also be recorded with each protocol version.

The qualified open-reader identity is Qwen3.6-27B revision
`1b559cf7215ebe67ff10758e14f6293ba883223b` on vLLM 0.25.1. The current 128K
profile is BF16, TP8/DP1, model length 131,072, chunked prefill enabled, prefix
caching disabled, and serving seed 42. Scored exact-answer runs also freeze the
chat template with thinking disabled. Both the serving-profile hash and reader
profile hash must be present in every run artifact; a model alias alone is not
an identity.

### Length and decoding preflight

Nominal source length is not interchangeable with the model's maximum sequence
length. Before enabling a 128K or 256K cell, generate with the exact pinned
tokenizer and verify:

`system + query + delimiters + assembled context + output reserve <= max_model_len`.

The preflight must record requested source tokens, tokenizer-measured assembled
tokens, API/engine-reported input tokens, output cap, and stop reason. A cell is
invalid if reasoning consumes the output reserve before an exact answer; do not
repair it by scoring hidden reasoning or silently increasing only one policy's
budget. The 128K profile can test a tokenizer-calibrated source below 131,072
after overhead. A 256K source requires the separate 262,144-token profile and
the same overhead margin.

For local runs, persist engine version, model revision, TP/DP, dtype, KV dtype,
prefix-cache state, scheduler limits, engine-reported KV capacity, peak HBM,
wall time, and GPU-seconds in a runtime manifest. These are frozen conditions
and cost measurements in the semantic track, not researcher-editable fitness
variables.

## Candidate loop

Each trajectory starts from an identical policy, clean workspace, researcher
configuration, task order, and budget. One round consists of evidence review,
hypothesis and manifest submission, policy modification, external evaluation,
and benchmark-controlled promotion or rollback. Ten rounds is the main cap.
The seed policy is evaluated and persisted before round 0 and initializes the
historical-best incumbent; a first candidate that scores below H0 is never
promoted merely because it is the first valid submission.

The A2 screen uses five slots and a hard 1,800-second timeout per researcher
turn; the A3 ceiling is ten such slots per trajectory. The primary researcher
environment is a frozen, network-disabled repository image. Internet-enabled
open autonomy is a separate arm because changing available public information
changes the treatment. Wall time, candidate slots, feedback bytes, pack tokens,
and target calls are matched. Researcher/API cost and local GPU/HBM/runtime
measurements are reported but do not alter semantic-policy fitness.

The implementation treats invalid researcher output as process evidence, not a
zero-scored policy. A valid submission contains exactly `policy/` and
`manifest.json`; candidate policy trees contain Python files only and pass the
fail-closed `PolicyAuditor`. Evaluation rematerializes the content-addressed
candidate and executes each item in a fresh interpreter. The host process runner
cleans its process group but is not a confidentiality boundary: formal gate and
sealed runs still require cgroup/PID-namespace or node isolation.

The runtime preflight binds declared identities and records observed host facts,
but it cannot self-certify `formal_eligible=true`. Formal eligibility must be
issued inside the scored runner by the locked launcher that creates every policy
worker (or a fixed worker pool), because that worker—not the researcher CLI—is
the adversarial process that receives hidden questions and artifacts.

The current host is qualification-only. User/mount/network/PID namespaces and
read-only binds are available, but no container runtime or delegated writable
cgroup is available to provide a minimal rootfs and kill detached descendants.
Formal gate/sealed execution moves to a container-enabled worker/node. Each item
uses a pinned-image non-root container with a read-only rootfs, only the candidate
and worker mounted, tmpfs scratch, no network, all capabilities dropped,
`no-new-privileges`, seccomp, a PID namespace, and cgroup PID/memory/CPU limits.
The evaluator records pre/post image, candidate, runtime, mount, UID/capability,
seccomp, namespace, cgroup, and endpoint-to-serving-PID digests, then invokes
`cgroup.kill` and verifies the group is empty.

Report all of the following rather than a single selected score:

- last attempt;
- visible development best;
- gate-selected candidate;
- post-hoc hidden oracle best, clearly marked as non-deployable;
- discovery gain, last-minus-peak regret, post-peak regression, and selection
  regret;
- token, model-call, GPU-second, wall-time, and API-cost accounting.

Necessity, sufficiency, gold-drop, gold-only, no-context, and counterfactual
tests are audit instruments. Their results do not enter researcher fitness.

The included generated counterfactual data is a harness canary, not a private
test set. Formal gate/sealed data must be generated and audited on the isolated
evaluator, use policy-facing opaque IDs, contain competing second-hop values,
and never expose split metadata or literal answer markers.

## Statistical gates

Replay each pilot artifact five times and each key main artifact three times.
Do not begin the main matrix unless replay standard deviation is below 20% of
the median meaningful round-to-round change. Use paired bootstrap or
permutation tests for discovery, hierarchical bootstrap over item/trajectory/
researcher/profile for confidence intervals, and Wilson plus beta-binomial
sensitivity for regression rates.

Start with 64 trajectories: four researchers, four evidence profiles, and four
seeds. If fewer than 66 trajectories continue after a pre-final peak, add seeds
symmetrically across cells up to eight seeds and 128 trajectories.

The 2026-08-14 corrected-protocol visible qualification does not pass this
launch gate. It has one researcher, one seed, four items, two rounds, no matched
search control, and no isolated gate. Its completed local trajectory and
five-replay artifacts verify autonomous editing, H0-aware selection, and replay
only. Before A3, A2 must add the registered researchers/seeds, stable five-round
trajectories, matched random/search baselines, manifest calibration, and an
evaluator-isolated gate. The earlier `-03` trajectory predates the corrected
H0-initialized incumbent rule and remains legacy qualification only; `-04` is
the first current-protocol trajectory.

Current qualification evidence is indexed in
`docs/preliminary-results-2026-08-14.md`. In particular:

- remote fixed-policy repeats show one policy with non-zero API replay noise;
- an apparent remote discovery is falsified by exact-candidate replay;
- local non-thinking fixed-policy repeats and both completed autonomous
  candidates have zero observed score variance;
- the local `0.25 -> 0.00 -> 0.50` trajectory is visible-only provisional
  discovery evidence, not a benchmark result.

## Kill conditions

Stop or narrow the study if replay noise matches round changes, policies leak
labels, task profiles are saturated, matched random/Bayesian search dominates
without a process-level finding, policies collapse to one scalar compression
ratio, semantic and KV effects cannot be separated, or the sealed evaluator
cannot be physically isolated.
