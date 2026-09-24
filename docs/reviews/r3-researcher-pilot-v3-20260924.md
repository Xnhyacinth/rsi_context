# R3 researcher usability pilot v3 (2026-09-24)

This is a two-attempt **A-development engineering pilot**, not a scored
comparison or an estimate of transfer. Both attempts received the same
development feedback. They were run and recorded in planned order; neither
policy was selected by its task score. The earlier v1 infrastructure failure
and v2 result (0/2) remain separate, unchanged artifacts.

## Frozen identity and materials

- Source commit: `b8801c4b25a038c1bff0e4cc72f24ed087de6110`; tracked patch
  empty at launch and completion. The run-identity digest was
  `6be3e8d5e364a9cc5de6edb447c0f37f2a62bfcc5d1e3dd6fb32207d0499f71e`;
  the recorded Git and source digests matched at the end.
- Development input: `artifacts/rsi-core-v1/r3-live.json`, SHA256
  `6b91bacf2cba871becf2e7f690a42fcb10690a658dbadbb1b3785fdfe5a0f9f8`.
  The manifest also hashes the complete A-development world, baseline policy,
  feedback, runtime source, `uv.lock`, and relevant configuration. It records
  requested model IDs and profiles; Siflow did not supply a pinned weight
  revision, so model weights cannot be certified byte-identical across runs.
- Result: `artifacts/rsi-core-v1/r3-researcher-pilot-v3-20260924.json`, SHA256
  `de03a4350268b081d23b80fd58bc9ca6a2d2cdb5ca8646de9b95131d686be30a`.
  Exact generated Python snapshots are in the sibling `draw-0.py` and
  `draw-1.py` files (SHA256 `456aa530be732315af6b01d3352eea8b338f101ff72953f573ea909a72a07806`
  and `7cea1452141f2ebdd375dc8a86fc49bd7ccb987904d9c7fb3cd9f1f639e5c430`).

The pilot used Siflow `deepseek-ai/deepseek-v4.1-flash` for the researcher
with thinking disabled, one HTTP attempt and at most 12,288 output tokens per
draw. It used `Qwen/Qwen3.6-27B` for the worker with thinking disabled, at
most 2,048 output tokens per request, 16 worker requests per draw, and 32
requests total. Model availability and thinking controls were checked with
separate small canaries before this run. The run recorded every provider
model echo, finish reason, token count, and missing-usage status.

## Observed results

| Draw | Researcher tokens (in/out/total) | Worker calls | Worker tokens (in/out/total) | Valid update | A-dev task |
| --- | ---: | ---: | ---: | --- | --- |
| 0 | 1,951 / 2,718 / 4,669 | 11 | 5,667 / 443 / 6,110 | yes | failed: calibration supplier |
| 1 | 1,951 / 2,307 / 4,258 | 15 | 13,320 / 3,269 / 16,589 | yes | passed |

Both policies loaded, changed from the baseline, and reached metered worker
calls without policy errors. All 26 worker responses had `finish_reason=stop`,
matching model echoes, and complete provider-reported usage. The researcher
used 8,927 total tokens; the worker used 22,699 total tokens over 26 of the
allowed 32 requests. The pilot script's predeclared **executable-update rate
is 2/2**. Its validity gate omitted the project's `PolicyAuditor` candidate
check. A post-run audit under the original auditor reported a `FILE_WRITE`
violation on draw 1's string `.replace()`; draw 0 passed. Thus the v3 2/2
must not be described as a 2/2 *candidate-admission* rate. The original
artifact and denominator are retained. A corrected, security-reviewed audit
and a prospective pilot with the audit before worker execution are separate
follow-up evidence.

The corrected auditor's **post-run** report is
`artifacts/rsi-core-v1/r3-researcher-pilot-v3-posthoc-audit-v3-20260924.json`,
SHA256 `1eb1a86e92d7e4df3d20066c098dee164c1080e566e18974e7ef35c3bca56cef`.
It records auditor source SHA256
`e446749836aceebd202a395be4c0f273763cc71d895df1b0d11b8d80b4a56363`
and finds both original Python candidates safe under that corrected static
rule. This repairs the string-operation false positive in the audit result;
it does not make the pilot's missing pre-execution gate prospective.

The v3 pilot also loaded generated Python in its main process before this
post-run audit. The exact saved candidates contain no observed escape code,
but static review cannot establish process isolation. Later live or formal
runs need an external execution boundary that keeps API credentials and
evaluator-only material outside the candidate process; the planned v4 live
rerun is paused until that boundary exists.

The v3 rate measures executable update delivery on one A-development world. The
different A-dev outcomes show that execution validity and task success must
be reported separately; two correlated attempts do not establish an efficacy
effect, a reliable update probability, or performance on unseen projects.

The corrected offline R3 wiring check is a distinct artifact:
`artifacts/rsi-core-v1/r3-corrected-offline-v3-20260924.json`, SHA256
`8c0efc815c92a372d90d1ea6ab1fdfd57a80e1fe651f96ea1790821696cc3fb6`.
Its run identity matched at start and end, and B development baseline passed
all six recorded decisions. Its scripted responder does not establish live
B/C difficulty or comparative method performance.

## Next admission decision

The A researcher interface now clears the narrow executable-update pretest.
The corrected `PolicyAuditor` passed both saved candidates after the run;
prospective candidate admission still requires an audit gate before loading
the policy, followed by an external execution boundary for live use.
That boundary should run candidate code in a separate low-privilege process
without credentials, evaluator-only files, or direct network access; the
evaluator should broker only the declared observation, tool, and model-call
interfaces. A malicious-candidate regression must prove it cannot read the
credential or sealed material before another live qualification attempt.
Before a scored A/B/C comparison, repeat the same usability checks for B and
C development traces, including a metered changed policy in each group;
qualify independent parent projects and realistic fixed-policy difficulty;
then freeze the full manifest, budgets, failure rules, and statistical
contract described in
[the R3 experiment plan](r3-correctness-and-next-experiments-20260924.md).
The old R3 live B/C deltas remain invalid because of the earlier sequence
state and memory-delivery defects.
