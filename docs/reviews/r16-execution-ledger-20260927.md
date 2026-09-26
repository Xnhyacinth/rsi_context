# R16 independent-parent and KEP admission ledger

Status: in progress; no R16 provider or GPU call. All four R16 worktrees
started from `main@93e77734ee392e0a601ec28c3b705d4ba8f85d03` with frozen
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
fixed policy and at least four arms (full, genuinely deidentified source-free,
identity-only, rule-neutralized) are being built. Their task worlds, prompt
geometry, case/call counts and caps must be measured and frozen anew. Even a
four-arm run may remain diagnostic until residual equivalent rules and a
same-identity counterfactual legal-plan flip are audited.

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
figures, not the revised four-arm budget, provider usage or price. The final registered live geometry must be rebuilt after any
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
