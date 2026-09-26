# R16 independent-parent and KEP admission ledger

Status: KEP paid development gate stopped on an authentic full-source
second-session failure; no GPU call. See
[`r16-kep-live-result-20260927.md`](r16-kep-live-result-20260927.md) for the
four actual Siflow calls, provider usage and immutable evidence. All four R16
worktrees started from `main@93e77734ee392e0a601ec28c3b705d4ba8f85d03` with frozen
`uv.lock` SHA256 `5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
The original main checkout's unrelated untracked `logs/` is preserved.

R16 adds a new pinned Kafka-site intake entry to `configs/registry.json`,
changing its SHA256 to
`e063e0c4291de8e560d5928ce2c847b003ede8c0b2bd69a85265df0707a1a6a7`.
The R15 PEP paid artifact remains bound to its original registry bytes and
`main@93e7773`; replay it from that immutable commit, rather than treating
the changed R16 HEAD as byte-identical. The R16 KEP launch must bind the new
registry hash before any provider call.

| Isolated owner | Scope and initial evidence |
| --- | --- |
| `work/r16-kep` | Guarded live admission for the existing KEP-753 fixed-reader three-arm card; owns new runner, launch/geometry registration, targeted tests and preregistration. No paid call before parent review. |
| `work/r16-parents` | Screen pinned PG16/17 and OTel 1.24/1.43 source projects for a distinct, source-dependent two-session parent; implement only a defensible offline card and controls, or record rejections. |
| `work/r16-jail` | Read-only audit of the host `/usr/bin` trust refusal and a non-weakened execution path for the researcher adverse suite. |
| `work/r16-integration` | Reconcile branches, review hidden-oracle boundaries and budgets, run required gates, decide whether a small Siflow KEP screen is admitted, then merge/push main and clean worktrees. |

The KEP checkout is detached and clean at
`13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`. The two PostgreSQL source
checkouts are detached and clean at
`c372fbbd8e911f2412b80a8c39d7079366565d67` (16) and
`d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e` (17). The OpenTelemetry
checkouts are detached and clean at
`cafda7127683b7f667e27cdbd3220510b6f998c9` (1.24) and
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d` (1.43). Source file hashes,
task worlds and visible controls must still be rechecked by each builder.

## KEP preliminary budget and revised experiment gate

**Revision before any paid call:** independent scientific review found that
the R15 `source-free` arm still exposes `KEP-753` through its document marker,
while the benchmark-owned survey prompt names KEP and defines the candidate
formula labels. The two-block neutralization leaves additional upper-bound
and ordering cues. The three-arm figures below describe the existing offline
artifact only; they are **not an admitted R16 paid budget**. A new generic
fixed policy and five arms were subsequently built: authentic full source,
genuinely deidentified source-free, identity-only, rule-neutralized diagnostic,
and a separately labelled constructed same-identity rule flip. Their final
worlds, geometry and budget are recorded in the R16 preregistration. Even this
five-arm design remains diagnostic until actual controls are observed.

The R15 clean integrated KEP geometry artifact has SHA256
`a3930ea4be4b0821c4d9e76a68bfbf8808986b5b0625591982d2ead1cb5c3b8b`.
It registers twelve exact request variants across full-source, source-free,
and both-explicit-rule-neutralized cases. Local worst-path input by case is
21,819, 702 and 21,591 tokens: **44,112** across all three. Nine requested
outputs at 2,048 tokens add **18,432**, so the task planning envelope is
**62,544 local-input-plus-requested-output tokens**. At most two matching
62-input/2,048-requested-output canaries would add **4,220**, giving an
initial three-arm global planning envelope **66,764 tokens and 11 HTTP
attempts**; auxiliary call cap is zero. These are historical offline planning
figures, not the final five-arm budget, provider usage or price. The final registered live geometry must be rebuilt after any
selected producer-file change, and the launch manifest must bind its exact
SHA256, task/world/source identities, profile, endpoint and code bytes.

Before live dispatch, require a clean producer and pinned tokenizer runtime,
the exact-profile canary's model echo/`stop`/provider usage and final-chat
input parity, a private fsynced attempt journal, the newly registered
case/call/token caps and
fail-closed case/stage request registration. The **full-source complete
two-session case runs first**. If it fails or has unknown usage/protocol
drift, stop before all controls and do not dispatch a post-canary. If it
passes, execute the model-invoked controls under the same fixed policy and
private oracle. A passing full-source case alone cannot qualify a parent:
source-free and rule-neutralized results must exclude model prior knowledge,
default-plan and residual-source-cue explanations. The current intervention
still retains an indirect upper-bound formula, so its interpretation is
limited even if it fails.

## Final R16 verification and next experiment

The reviewed five-arm launch registered **15 task calls, two canaries, zero
auxiliary calls**, 97,278 task local-input-plus-requested-output tokens and
101,498 globally. Its authentic full-source case failed the second session;
the runner correctly stopped after the pre-canary and three task calls. The
[live result](r16-kep-live-result-20260927.md) records the 21,871/28 provider
input/output tokens, exact local input parity and evidence file hashes.
All other arms remain unmeasured with the real model.

Final `codex review --base b1c3eb3` found no actionable regressions. The
clean integration checkout passed **1559 tests, 16 skipped, 80.86% branch
coverage**; full [pytest log](/volume/pt-dev/qjiu/rsi_context_external/r16-preflight/full-pytest-pinned-final.log)
SHA-256 is `138aec624705537c62c412b1c316794529409196c5b770df1732a1c789db6077`.
The test process used the seven pinned source/tokenizer roots listed in the
R16 source and launch manifests, plus a dummy `SIFLOW_API_KEY` with
`SIFLOW_BASE_URL` unset, so it made no real provider request. Repository Ruff
and configured strict mypy passed (383 files). Bandit reported the unchanged
baseline of 81 LOW and 2 MEDIUM findings; no R16 file appeared in its
[JSON report](/volume/pt-dev/qjiu/rsi_context_external/r16-preflight/bandit-integration.json),
SHA-256 `317294672b3b97ea413db0d78e0b470382f2eeb5924da0141e20c2849efac13f`.
The MEDIUM findings are older dynamic `exec` sites in
`scripts/arm_comparison_v2.py` and `scripts/trajectory_v3.py`; their live
isolation boundary warrants separate review before treating the count as
resolved. Fifteen jail/integration tests were skipped because this host
does not meet the unchanged `/usr/bin` root-ownership gate; the remaining
skip is live API smoke without a configured base URL.

Next, preregister a **new** KEP arithmetic diagnostic that separates rule
extraction from applying the retained rule to the amended order; preserve
this failed run as immutable development evidence. Audit the newly pinned
Kafka documentation as a distinct-project candidate, including all equivalent
migration rules and source-free/identity-only controls, before spending on
another parent. Run the researcher effective-update-rate pretest only in a
trusted runtime where the adverse jail suite is unskipped. Neither KEP nor
Kafka is currently a qualified independent parent.

## Parent and researcher gates

R15 PEP controls rejected that lineage: both identity-only cases passed.
R16 parent intake must use a **different source project**, preserve one
source lineage per project, and show why public version/path identity does
not reveal the legal plan. Candidate task material, source bytes, visible
feedback and evaluator-only oracle must have separate hashes. Do not acquire
unregistered upstream branches or treat constructed variants as independent
parents. A skipped/infeasible candidate remains in the rejection ledger.

The researcher effective-update-rate pretest remains unregistered on this
host. The unchanged jail gate refuses non-root-owned `/usr/bin` before
candidate execution. An offline fake broker exercise or a short worker
canary does not measure researcher updates. Admit paid planned draws only
after a trusted host/runtime, an unskipped adverse jail suite, frozen
researcher model profile and attempt denominator, and target/auxiliary
provider usage accounting.
