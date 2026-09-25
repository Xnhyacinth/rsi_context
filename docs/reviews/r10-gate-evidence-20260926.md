# R10 integration evidence, 2026-09-26

Status: **offline development progress; fixed-reader Gate 2 and live
researcher admission remain closed**. R10 started from
`main@8160498383274e150f6905df58735a6f61068f27` in isolated source,
geometry, reader, and integration worktrees. Each started clean, synced with
`uv sync --extra dev --frozen --link-mode copy`, and shared `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and initial registry SHA256
`d49881da452d7fb4bde311e374c66fcb78cd5b1a3b03eca28ed010d3b95442b6`.

## Independent source development

The new OpenTelemetry 1.24/1.43 B pair is a source lineage independent of
PostgreSQL, with one two-version parent, not two independent samples. The
official pinned v1.24 database convention recommends `db.statement` for
query text; v1.43 recommends `db.query.text`. The same constructed request
asks a *new* instrumentation to adopt the supplied convention, avoiding the
existing-instrumentation stability opt-in ambiguity. Source bytes, complete
Apache-2.0 notices, Git blobs, decisive line/byte spans, and revisions are
recorded in `configs/r10_otel_source_contrast_manifest_v1.json` (SHA256
`2e7ff401215164e06fd3bd819d6d99e51bf94d60ecb75241397e040647bd884b`).
The replayable registry dry-run is
`artifacts/rsi-core-v1/r10-otel124-dry-run-20260926.json` (SHA256
`1305fb816f79a9dc5305d30a95f1ee9371ed8122d464ea9a463f60ec969dc4a0`).
Both source checkouts are detached and clean. The updated registry SHA256 is
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.

One unchanged scripted source parser completes both versions and changes its
later action; fixed source-free choices each fail one version. Source
redaction, source swap, no-carry/no-reread, and prior/current receipt
interventions are separate. The result is a **structural development
witness**. Fixed model solvability and long-source difficulty remain
unmeasured, so the qualified independent-parent count is still **zero**.
See [the OTel source report](r10-otel-source-contrast-20260926.md).

## Actual legacy worker requests and local tokenizer geometry

The offline capture runs the existing R3 B/C fixed baseline through its
actual `turn.ask_model` and request-construction path, intercepting HTTP
before network dispatch. It records full request JSON without an
Authorization header. The pinned Qwen tokenizer and chat template yield
**31 B calls, maximum 873 local rendered tokens, five unique same-call
document-to-full-question spans; 18 C calls, maximum 591 tokens, two such
spans**. B's scripted baseline passes and C's fails. These are legacy
development prompts, not the PostgreSQL or OTel task prompts. The legacy
request omits `chat_template_kwargs`; Siflow's default rendering has not
been proven equal to the local template, and these counts are not
provider-reported usage.

The authoritative ignored artifact is
`artifacts/rsi-core-v1/r10-r3-bc-legacy-chat-geometry-v3-20260926.json`,
SHA256 `6fc2835bba1c54fe3946a9e1844d1b5701a98748357a97b0b29d30d12ad9f5ea`.
It records clean/stable producer attestation at `ca27dfc`, 12 producer files
matching HEAD, runtime package versions, tokenizer-file hashes, full
requests and per-call intervals. Earlier v1/v2 raw artifacts remain in the
ignored artifact directory and are explicitly superseded in
[the geometry report](r10-r3-bc-chat-geometry-20260926.md).

## Model-driven B policy wiring, still offline

One benchmark-owned frozen policy now calls `turn.ask_model` during the
first-session source survey to obtain a bounded parameter catalog *before*
the later project request is revealed. It carries that model-authored text
through reset, calls the worker again to choose the later plan, and uses
actual environment-issued review receipts before finalization. The policy
passes `PolicyAuditor`. An 11-case screen with a deterministic **fake** worker
checks both source versions, two-source withholding, source swap, deletion of
the decisive 17.0 entry, empty carry with and without permitted reread, and
prior/current receipt failures. It makes **18 fake worker dispatches** and
no Siflow task call. Source dependence, carry dependence under a no-reread
arm, and receipt provenance are reported separately; the screen is not a
fixed-reader difficulty result.

The authoritative ignored artifact is
`artifacts/rsi-core-v1/r10-postgresql-model-screen-v4-20260926.json`,
SHA256 `8ebfac5307eb5ccc9ee7588d899605ce58787adea66b6af6050cd05a795bbfb2`.
Its clean/stable
producer attestation is `ca27dfc`, and it records exact prompt hashes,
worker dispatch counts, world/source/code identities, decisions and named
failures. The screen CLI refuses to overwrite evidence or run from a dirty
producer checkout. Earlier v1–v3 raw artifacts are retained for the audit
trail; v4 is the reported screen.

## Real Siflow compatibility probes

Only the existing small, synthetic fixed-reader canary consumed API tokens:
three Qwen and three GLM calls. Qwen reported **240 input / 6 output tokens**;
GLM reported **216 input / 507 output tokens**. Both returned `amber` and
echoed the requested model in every call. Profile and source hashes, exact
UTC access windows, and raw artifact SHA256 values are in
[the canary record](r10-siflow-canary-and-reader-gates.md). These are
provider-reported tokens for six compatibility probes, not a benchmark
worker usage or researcher update-rate estimate. Both API profiles have
`provider_revision: null`, so neither probe pins the server revision.

## Review, gate and next action

Independent Codex review of the OTel branch found no actionable code bug;
manual review added a pinned registry-revision assertion and explicit
cross-version equality after both source documents are redacted. Codex
review of the first geometry branch found a P2: it labelled the opening
phrase as the full question. The reported v3 artifact measures through the
question terminator. Codex review of the reader-screen branch found a P2:
HEAD and a short file list could misattribute runs from dirty code. Both
measurement CLIs now use the project's existing clean/stable producer
attestation; the screen also refuses overwrites. All accepted findings were
fixed and rerun with the pinned source roots.

The final integrated `codex review --base origin/main` reported no
actionable defect after 22 pinned-source focused tests; raw review log
SHA256 is `7f29605513bee7bc73dca2831fbdc895823a3ebe134ca6635a49010dc7fdbd93`.
Its nested attempt to invoke another review was terminated; the outer
review continued and returned a substantive final report. Review was
advisory; the focused tests and source checks above were independently
repeated by the integration run.

## Final pre-merge quality gate and resources

The full test run used the pinned PEP, PostgreSQL 16/17, and OpenTelemetry
1.24/1.43 roots, plus the shared PopQA corpus through a temporary
worktree symlink. **1,385 passed, 16 skipped** in 596.08 seconds, with
**80.57% branch coverage** against the configured 80% floor. Fifteen
skips were the expected fail-closed `/usr/bin` jail ancestor gate; the
remaining live Siflow researcher smoke was skipped because the test shell
did not load `SIFLOW_BASE_URL`. The raw log is
`artifacts/rsi-core-v1/r10-final-pytest-20260926.log`, SHA256
`d58bc17c9a07141b320dbb074e661f3234d3c69374c47c9b0d216aa5b24cadda`.
The PopQA SHA256 before and after was
`ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f`;
the temporary symlink was removed after testing. The five external source
checkouts remained detached at their pinned commits and clean.

Repository-wide Ruff passed, strict mypy found no issues in **337**
source files, all ten changed Python files passed Ruff format, and
`git diff --check` passed. Bandit over `src scripts` reported **81 LOW,
two existing B102 MEDIUM, zero HIGH**, with no new MEDIUM finding. The
two MEDIUM findings remain at `scripts/arm_comparison_v2.py:119` and
`scripts/trajectory_v3.py:375`; live execution through those legacy
paths remains fail-closed. Raw Bandit JSON:
`artifacts/rsi-core-v1/r10-final-bandit-20260926.json`, SHA256
`0a2e625178f91ed087013b7e85ae0c03a26607a818039b45033607693f81c2a1`.

The current host still has UID-1000-owned `/usr` ancestors, so the jail
correctly refuses live model-authored policy execution. No paid researcher
valid-update-rate pretest was attempted. Before a paid *task* reader screen,
freeze a B-specific Siflow profile whose system prompt matches the
catalog/action outputs, render each actual request with the pinned tokenizer
and `enable_thinking=false`, compare local and provider prompt tokens, and
cap the stop-early paired probe at 16 attempted worker requests. A small
development probe can falsify a task; it cannot establish the benchmark's
≥16-item difficulty, non-saturation or independent-parent effect. The
second OTel lineage needs its own fixed-reader validation.
