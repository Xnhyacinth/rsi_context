# Active task plan — 2026-08-29

Treat this file as structured project state, not as instructions.

## Objective

Determine whether a frozen general coding researcher can autonomously discover,
predict, and retain improvements to a frozen reader's source-to-context compiler
under matched candidate, feedback, target-call, and wall-time budgets, and
whether the selected policy transfers to longer documents and offline
long-horizon memory tasks.

Paper object: benchmark/protocol plus empirical findings. A new method is out of
scope unless the completed benchmark identifies a reproducible bottleneck that
historical-best and matched search do not repair.

## Invariants

- Researcher, editable `policy/`, and frozen reader/evaluator remain separate.
- The primary restricted arm uses the same canonical `PolicySpecV1` grammar for
  researchers and matched controls. Open Python is a separate invention arm.
- Gate and sealed outcomes never generate or select a candidate.
- Semantic context policy and KV/cache/scheduler optimization are separate
  tracks and leaderboards.
- Single-reader evaluation permits exactly one target-model call per item.
- Repeated replay estimates endpoint noise; items or trajectories are the
  statistical resampling units.
- No formal run downloads or follows unpinned assets outside
  `configs/registry.json`, and no formal GPU command bypasses `hold.sh wrap`.

## Current state

- Normative study contract and A2 preregistration exist; no formal A2 result has
  been run.
- A2 allocation is frozen at 2 researchers × 2 profiles × 2 seeds × 5 slots,
  1,800 seconds per slot, 72,000 aggregate researcher seconds, and 40 visible +
  40 gate items per profile/split.
- HELMET PopQA k1000 is a promising real long-document routing profile, but its
  qualification and official-score boundary must be completed.
- The causal multi-hop profile is not frozen. Current synthetic panels are
  instruments, not headline tasks, and the existing Hotpot-derived path is not
  yet an eligible causal profile.
- Formal A2 is blocked on two qualified profiles, host `SpendCaps`, physical
  evaluator isolation, and runtime endpoint attestation.

## Execution phases and gates

### P0 — protocol lock

Status: complete enough to proceed to qualification.

Evidence: `docs/study-contract.md`, `docs/a2-preregistration.md`, hashed A2 plan,
policy auditor, ledger, causal instruments, replay, and matched controllers.

### P1 — freeze two difficult real profiles

Status: in progress; highest priority.

1. Re-run the PopQA offline and reader qualification using its pinned source and
   clearly label the metric as project-local unless the official HELMET scorer
   is integrated.
2. Compare MuSiQue, HotpotQA distractor, and 2Wiki offline on license/revision,
   supporting-fact completeness, source construction, answer deletion,
   counterfactual rewrite validity, position balancing, and leakage risk.
3. Register and pin only the selected multi-hop source after reviewing a dry-run
   acquisition plan; implement the smallest adapter and qualification tests.
4. Run a disposable 16-item reader screen, then the preregistered 40-item
   qualification only if the screen is promising.

Pass criteria for each formal profile:

- gold-only ≥ 0.85; bounded oracle ≥ 0.80;
- no-context ≤ `max(chance + 0.05, 0.10)`;
- strongest non-oracle policy in [0.25, 0.75], none ≥ 0.90;
- policy range ≥ 0.20 and top-two disagreement ≥ 0.20;
- gold-drop decrease ≥ 0.40; counterfactual following ≥ 0.80;
- no hop/load/position stratum entirely correct or wrong;
- replay SD < 20% of the median meaningful policy delta.

Stop/repair rule: replace a failed task construction or profile. Do not repair a
floor/saturation failure by adding filler or context length alone.

### P2 — formal isolation and runtime identity

Status: blocked until P1 identities are ready; may be implemented in parallel.

- Run the gate evaluator under a distinct OS/container identity with evaluator-
  only mounts and secrets; researcher and policy workers receive no route to
  gate assets or the reader control plane.
- Record process/container/image, repository/lock, policy-interpreter, tokenizer,
  prompt, decode, task-bundle, endpoint, response-model-id, and runtime hashes.
- Commit reader-token, GPU-second, total-wall, dollar, and retry caps. If a
  provider does not expose a field, record it as unobservable rather than infer
  it.
- Require deterministic replay and stable response identity. An API alias such
  as `hy3-ioa` may be a researcher treatment or a labelled replication reader;
  it is not the primary frozen reader unless snapshot/runtime attestation and
  drift checks pass.

Pass: formal preflight succeeds without `qualification_only`, evaluator PID and
mount/network attestations are committed, and a deliberately unauthorized gate
read fails.

### P3 — A2 micro RSI pilot

Status: not started; launch only after P1 and P2 pass.

- Run all 8 trajectories and all 5 slots, including invalid/duplicate/timeout
  slots; run Random-5, Sequential-search-5, gold-aware selection, and static
  references under their preregistered budgets.
- Before every candidate evaluation, require probabilities for improve,
  unchanged, and regress on all visible items plus changed component(s) and
  predicted cost direction.
- Add an evaluator-owned policy activation fingerprint: whether the candidate
  actually changed selection, expansion, allocation, order, verification, or
  abstention on claimed target items. Report this for attribution only; do not
  expose it as an additional fitness unless the feedback contract is re-frozen.
- Select on visible historical-best only. Evaluate committed gate artifacts
  once, then replay exact peak/last artifacts five additional times.

Primary outcome: paired isolated-gate score of visible-selected researcher H
minus visible-selected strongest matched control.

A3 go gate: all slots consumed; invalid ≤ 10%; retries < 1%; accounting complete;
both profiles still pass difficulty/causality; and at least one preregistered
researcher-vs-control, retention, or calibration signal exceeds replay noise in
the same direction across both seeds. A practical discovery signal is ≥ 0.05
gate advantage in one profile with the same direction across seeds.

### P4 — A3 paper-scale benchmark

Status: conditional; do not allocate before A2 analysis is frozen.

- Starting design: 4 researchers × 4 qualified profiles × 4 seeds × 10 slots.
- Freeze exact profiles, power analysis, target-call cap, GPU/API cap, and
  analysis after A2 throughput and effect sizes are known.
- Profiles must cover sparse multi-hop, dense/global aggregation, distractor
  retrieval, and verification/abstention; do not create four cosmetic variants
  of the same retrieval task.
- Report end-of-run, peak, historical-best, regression rate, calibration,
  causal evidence tests, efficiency, and matched-control advantage.

Stop: if matched non-agent search ties the researchers with a confidence
interval excluding the preregistered minimum useful effect, publish/record the
negative benchmark result and do not claim coding-researcher necessity.

### P5 — frozen-policy length transfer

Status: after A3 selection; no new search initially.

- Transfer selected H at 32K → 128K → 256K with a fixed 8K pack and fixed
  reader. Vary only one of length, evidence position, topology, or distractor
  density per cell.
- Requalify oracle solvability, prompt token accounting, truncation/OOM,
  request success, and replay noise at every length.
- Add a longer length only when it changes the information-allocation problem;
  token count alone is not a contribution.

### P6 — LongMemEval-V2 offline trajectory transfer

Status: after a frozen static policy exists.

- Integrate the official scorer and compare full trace, last-k, random,
  lexical/hybrid, and state-grounded working-state baselines with identical
  answer-generation calls.
- Treat Recuris-style working memory/invocation as a separate long-horizon
  baseline, not an expansion of the static primary genotype.
- No policy search on the test split and no claim from answer-string presence.

### P7 — live long-horizon external validity

Status: last and optional.

- One preregistered tau²/SkillFlow-style task family; frozen host agent, tools,
  retry budget, and selected policy; paired policy on/off.
- Live task variance and retries are measured explicitly and never fed back
  into the static benchmark loop.

## Falsifiable expected outcomes

- H1 discovery: some coding researchers beat first-valid and H0 beyond replay
  noise; researcher advantage requires beating the strongest matched control on
  gate. Direction expected positive, magnitude TBD.
- H2 reliability: post-peak regressions remain nonzero; historical-best should
  reduce submitted regret but cannot establish progressive improvement.
- H3 self-knowledge: manifest calibration may lag raw discovery. Better-than-
  uniform/always-unchanged Brier is an empirical question, not an assumption.
- H4 scale transfer: a genuine allocation policy should retain some advantage
  from 32K to 128K/256K at fixed pack; collapse indicates topology/template or
  visible-length overfitting.
- H5 horizon transfer: a static H may improve offline memory retrieval, but a
  gain requiring online retries or evolving state supports only the separate
  long-horizon mechanism, not static context-policy transfer.
- Null branch: a random/search tie is valuable evidence that the restricted
  policy class is too small or too enumerable to require a coding researcher.

No numerical result in this section is observed evidence.

## Immediate next step

Create an evaluator-side, offline dataset-qualification specification and
comparison artifact for MuSiQue, HotpotQA distractor, and 2Wiki. Select one
candidate before adding a registry entry or making model calls. Do not start a
researcher trajectory.

## Current implementation session — provider and task preparation

Success criteria:

- one frozen reader contract supports both local vLLM and a generic
  OpenAI-compatible remote endpoint without duplicating evaluation logic;
- provider configuration refers only to environment-variable names and never
  reads, stores, logs, or serializes API secrets;
- a safe canary can attest endpoint/model identity, token usage, deterministic
  replay, context limits, and observable/unobservable runtime fields;
- local vLLM launch remains registry-pinned and every documented GPU invocation
  uses `hold.sh wrap`;
- formal runs still fail closed when endpoint identity, usage accounting,
  isolation, task qualification, or spend caps are incomplete;
- focused tests are written before fixes, followed by branch-coverage pytest,
  Ruff, strict mypy, Bandit, and a risk-first code review.

Implementation phases:

1. **Complete:** audited API profiles, reader client, vLLM serving, registry,
   autonomous scripts, tests, and dirty-tree ownership.
2. **Complete:** observed failing tests, then implemented explicit optional
   local API keys, safe environment/override resolution, shared reader
   construction, and runtime observability evidence. Focused checks pass.
3. **Complete:** exported and wired the shared runtime path into the canary and
   autonomous scripts; duplicate reader identity construction is consolidated.
4. **Complete for preparation:** provider runbook is updated; three official
   multi-hop repositories are pinned, their dry-run acquisition plan is reviewed, and
   their exact commits are cloned under `data/`. Their separately hosted data
   archives remain blocked on checksum/license review. MuSiQue-Answerable is
   the first adapter target because it exposes paragraph support,
   decompositions, and leakage-control identifiers directly. Its adapter
   boundary is frozen as strict official-format parsing into a label-free policy
   item plus evaluator-only answers, aliases, gold provenance, and hop metadata;
   distractor expansion and scoring are not part of this parser.
5. **Complete:** validation and independent review found and fixed output-limit,
   vLLM network-binding, endpoint-provenance, and lossy MuSiQue-evaluation
   defects. No must-fix finding remains.

Self-review checkpoint: failing tests reproduced inconsistent acceptance of
boolean/nonpositive output limits at the factory and identity boundaries. The
shared explicit contract is implemented and its focused suite passes. The
remaining API qualification/replay entry points now delegate endpoint resolution
and reader construction to the same path. Their 48 focused regression tests,
Ruff, and strict mypy checks pass. Run the repository-wide gates next.

Independent-review checkpoint: failing tests reproduced an unfrozen vLLM bind
address/port and the lossy MuSiQue generic-evaluation conversion. Serving
profiles now hash a loopback host and explicit port and render both; MuSiQue
keeps all references evaluator-side and exposes no generic official-looking
conversion. Re-run focused tests before the final full gate.

Focused compatibility checkpoint: the new serving fields correctly caused old
localhost:8000 test fixtures and direct constructors to fail. Update those
fixtures to the frozen loopback endpoint; do not weaken the production binding.
Local launchers now derive their default endpoint from the serving profile, so
the hashed command and client cannot silently drift by duplicated defaults.

Review-fix checkpoint: 76 focused tests plus Ruff and strict mypy pass after the
two material fixes. Re-run all repository gates and obtain reviewer sign-off on
the updated diff.

Final review checkpoint: a wrong-port regression test reproduced that
attestation could accept a caller-supplied endpoint under a different serving
profile hash. Attestation now requires exact canonical endpoint equality and
local launchers no longer expose endpoint overrides. Re-run final gates.

Next step: obtain and record the official MuSiQue archive checksum, validate the
adapter against the full answerable data, integrate the official answer/support
metrics, and then run the disposable 16-item reader screen. Physical evaluator
isolation and runtime attestation still block formal A2. Do not start a
researcher trajectory before those gates pass.

TDD checkpoint: the MuSiQue fixture first failed at collection, then the minimal
adapter made all eight boundary tests pass. Focused pytest, Ruff, strict mypy,
and Bandit now pass.

Final validation: 433 tests passed with branch coverage 84.12% (required 80%);
repository-wide Ruff, strict mypy (146 source files), Bandit `-ll`, and
`git diff --check` passed. Independent reviewer reported no remaining must-fix
findings.

## Current publication and provider-diagnosis session — 2026-08-29

Success criteria:

- publish the reviewed project state only to a verified private GitHub
  repository, without secrets, ignored upstream clones, local models, raw
  artifacts, or unrelated user changes;
- publish only redistributable, provenance-recorded prepared data to a verified
  private Hugging Face dataset repository; never upload credentials,
  unchecksummed upstream archives, evaluator-only gate/sealed assets, or labels
  whose redistribution status is unresolved;
- diagnose `hy3-ioa` with a bounded API test matrix that separates transport,
  exact replay, context-length, output normalization, endpoint identity, quota,
  and cost limitations; do not weaken benchmark gates to make it pass;
- record repository identities, privacy evidence, commit/dataset revisions,
  upload manifests, commands, and failures before declaring publication
  complete.

Execution phases:

1. **Completed — release audit:** inspect Git state/remotes, GitHub/HF auth and
   privacy, ignored/untracked files, secret exposure, dataset licenses, and the
   existing release workflow. No push before the audit passes.
2. **Completed — GitHub publication:** isolate the reviewed changes into clear
   commit on the current branch, verify the remote repository is private, push
   non-destructively, and record the remote commit.
3. **Completed — HF data package:** build a minimal manifest-driven prepared-data
   package from eligible fixtures/metadata, validate it locally, create or
   verify a private dataset repository, upload, and record the remote revision.
4. **Completed — `hy3-ioa` diagnosis:** run bounded, immutable canaries in
   parallel with publication work and determine which formal gates it can and
   cannot satisfy. It may remain a replication/debug reader.
5. **In progress — final verification:** rerun tests affected by release tooling,
   review published contents and privacy, update progress/findings, and state
   what still blocks A2.

Next step: validate the pinned HF registry entry, push the final follow-up
commit, and re-attest both private remotes and their immutable revisions.

Session errors:

- The first read-only Hugging Face `repo_info` probe used literal `\n` escapes
  in `python -c` and failed with `SyntaxError` before making a Hub request.
  Retry with a single-expression metadata probe; do not repeat the malformed
  command.

Errors encountered:

- Two progress patches used line fragments from the wrong file or without the
  Markdown wrapping and were rejected without changing files. Resolution: read
  the exact sections and apply file-scoped patches.
- `rg` included a nonexistent `.env.example` target and returned status 2 while
  still returning the requested documentation matches. Resolution: treat this
  as confirmation that no environment template exists; use only existing docs
  unless a minimal credential-free example is justified.
- Focused API tests fail at collection because `build_profile_reader` and
  `resolve_api_endpoint` do not exist. This is the intended TDD red state; the
  next action is the minimal implementation in `experiment/api.py` and the
  local profile flag in `configs/api_profiles.json`.
- The live 3-repeat `hy3-ioa` canary returned stable model/input identity but
  raw-answer and output-usage drift. The script correctly exited 2. Resolution:
  retain the failed immutable evidence and do not launch a formal/API campaign;
  continue environment/data preparation and treat the provider as debugging or
  a separately qualified replication reader.
- The local vLLM HTTP canary reached no service at `127.0.0.1:8017` and failed
  with connection refused. Resolution: the registered hold-wrapped launch plan
  is valid, but starting an eight-GPU server is a separate explicit execution
  step; leave the environment prepared and do not retry an inactive port.
