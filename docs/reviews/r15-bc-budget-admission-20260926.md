# R15 PEP/KEP B-card budget admission, 2026-09-26

**Decision:** admit the pinned PEP 621/639 and KEP-753 material for offline
development measurement only. **Reject a numerical per-trajectory worker
call/token cap and live researcher admission today.** The R4 40-call cap is
specific to different B/C worlds and must not be copied to these cards.
No Siflow or GPU call was made for this review; no target, auxiliary, or
researcher provider-token usage is asserted. `live_ready=false`.

## Verified input identity

The project worktree began clean at `main@b315b6c8aed83ff4c868dc9e483005df7f6d0f54`.
The PEP source checkout is detached and clean at
`6822259db9c95f02da739b3e2830a4aa1ae35134`; the KEP-753 checkout is
detached and clean at `13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a`.
The builders check their complete source-file hashes before materializing a
task. Locally rechecked source bytes:

| Material | Raw UTF-8 bytes | SHA256 |
| --- | ---: | --- |
| `peps/pep-0621.rst` | 30,002 | `8710ea6fcc2f5d19571ea7b2610e5c2fbc93d44051c1e5669f40a685ab4bb49e` |
| `peps/pep-0639.rst` | 33,887 | `0143e14bdeb02b95d43484df7a29990e2d25376d81fdb119b9afef7433769f94` |
| `keps/sig-node/753-sidecar-containers/README.md` | 90,893 | `ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21` |

The following SHA256 values bind this budget review to the current source,
task builders, profile proposal, broker and dependency lock. A later change
requires a new budget review; the hashes do not certify a provider response.

| Input | SHA256 |
| --- | --- |
| `configs/registry.json` | `c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2` |
| `uv.lock` | `5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352` |
| `material_pep_r14.py` | `c7d5e5c8ad37eb0f4141491c1a3405f83e09280cf965ee1b84b3c3852be3528b` |
| `material_k8s_r14.py` | `60e38abc2480fa63851e2bbe336664b0a28fbec2585787b12d7d529f1553e534` |
| `brokered_researcher_exercise.py` | `8b8bc53a26c03507ac07967dc02633b666152a9f27c6bb47ebb5b545bf94ae11` |
| `brokered_policy.py` | `c25be53a0f003af3b5ca4a62f6553b63e0426e0d3fb1788e293f99b6c0828e6a` |
| `session_sequence.py` | `b1752247af8b0520b7f2ee47c46a0f58638121898c9314ef9b9a45d7ceac023d` |
| `tools.py` | `ece9de492390de9572c9b67e05d6fa0793e75be2a95f2de5edce01c80e00df26` |
| `experiment/api.py` | `53039df4ddaa59dca5c47990d51d3fff939e80e7aec1abaebb09fc2506e015bc` |
| `configs/r15_siflow_fixed_reader_profile_v1.json` | `c3bb91d662d588e0a0a69101fb8fd851a1c910ded66e4387d4afccc9c9002ff6` |
| loaded R15 `APIProfile.profile_hash` | `b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69` |
| historical `configs/r4_bc_dev_budget_v2.json` | `4a2d62dc3b85271305a03747f9fab4775884580168d8320a0111624ddd2ac975` |

Canonical JSON of the **two complete `LifecycleInstance.to_dict()` objects**
(`sort_keys=True`, compact separators, UTF-8) yields these development-task
hashes. They include evaluator-only fields and must be kept in evaluator
artifacts. The visible-document sizes include the builder's document marker
and title; they are bytes, **not** rendered chat tokens.

| Card | Sessions / stages | Visible document bytes by stage | Task SHA256 |
| --- | ---: | --- | --- |
| PEP 621 historical license | 2 / 7 | source 30,080; later request 744 | `64c8c9774cc0ef95fcc25d7d92c0c3386c1893c178fffd6d9d4d383ea61d17d2` |
| PEP 639 historical license | 2 / 7 | source 33,965; later request 744 | `0bdbdf8c3847199a9811bcbab28af7f7f630fe73a9ace4896acfb6812a9e8791` |
| KEP-753 resource order | 2 / 8 | source 90,924; request 695; amendment 650 | `2e73ce7a52174a97db7ce4ddf231bb060246063b014154199d8c4615165a3619` |

The PEP pair is **one source lineage**, despite two opposite legal plans.
The KEP card is a second source lineage but is longitudinal B, not C. Both
remain development material: PEP has a demonstrated source-identity shortcut;
KEP still needs model-invoked rule controls and complete-project difficulty
evidence. Neither is an independent qualified Gate 2 parent yet.

## Budget envelope and refusal ledger

| Item | Admission now | Exact reason / next evidence |
| --- | --- | --- |
| Proposed fixed reader identity | **File and loaded-profile hashes pinned only** | R15 profile declares Siflow `Qwen/Qwen3.6-27B`, thinking off, seed 42, temperature 0, `max_output_tokens=2048`, and a 262,144-token evaluation context field. The file SHA256 and canonical loaded `APIProfile.profile_hash` are both recorded above. The profile has `provider_revision=null`; the old R4 canary used a different system prompt and a 1,024-token request ceiling. Run a fresh exact-profile echo/finish/usage canary before model evidence. The broker does not load or enforce this profile itself. |
| Per-request output ceiling | **Can be predeclared as 2,048** | This is a requested provider parameter from the pinned R15 profile, not measured completion usage or proof that the server honors it. The future adapter must send and check it on every request. |
| Auxiliary model calls in current R14 broker | **Exactly 0 dispatched** | `delegate_runner=None`; attempted delegation is refused and counted separately. Enabling auxiliary calls requires a metered provider interface and a new budget, not merely a string-returning delegate. |
| Tool budget | **Requires new values** | R14 requires fresh positive `ToolBudget.max_calls` and `max_tokens`; its `max_calls` counts *all* tool attempts, including rereads, verification and refusals. It is not a target-HTTP request count. The PEP scripted witness used `max_calls=10` without a token cap; KEP's test used no shared cap. Neither qualifies a worker-provider envelope. |
| Stage-turn envelope | **Must be explicitly pinned** | Both new scripted witnesses used `max_turns_per_stage=3`; R14's default is 2. The fixed-reader policy and rendered arms must select one value and recheck full-project completion. Stage count is not a model-call count because a turn may request zero or multiple tools. |
| R4 `40` per complete development run and `240` total | **Reject transfer** | R4 derived 40 from old B/C scripted candidate maximum 35 plus 5 headroom, for two groups and three runs each. The new PEP/KEP cards, policy, prompt shape and source lengths differ. Neither 35 nor 5 is a measured lower bound/headroom for them. |
| New target calls per trajectory / total worker requests | **Unqualified** | Freeze the question-general reader policy, target-call placement, session-turn cap and all arms; then observe a complete per-card call trace and predeclare a per-card cap plus fixed-baseline/candidate aggregate. Keep target dispatches separate from `ToolBudget.calls`. |
| Input, output and combined provider-token caps | **Unqualified** | Render final chat prompts with the exact profile/template for full source, source-free, PEP identity-only, and all-equivalent-rule intervention arms. Record exact prompt tokens, evidence offsets, longest context, response ceilings and provider usage. Raw document bytes and `DescriptionAxes.information_scale_tokens` are not this measurement. R14's input budget may conservatively charge more than provider input usage, and output is charged after response. |
| Planned researcher denominator | **Unregistered** | R13 permits a predeclared 1–16 draws and counts invalid, timeout and unknown-usage outcomes. R4's two draws per old B/C group do not choose the new protocol's denominator. Register card, arm, model, seed and all attempts before the first researcher API call; keep valid submission, jailed exercise and task success distinct. |
| Current researcher profile | **Reject live use** | The historical strict DeepSeek canary returned a different model echo. A new exact model profile and strict provider-usage canary are required; unknown usage never becomes zero or estimated provider usage. |
| Candidate jail and live exercise | **Reject on this host** | The unchanged `/usr/bin` and `/usr/lib` trust check blocks candidate launch before any untrusted execution. Offline fake transport tests do not replace an unskipped real jail/adverse suite. `live_ready=false`. |

No numeric per-card `ToolBudget` or worker-API total is written into a new
config: final rendered prompts, a fixed reader policy and real call geometry
are absent. Adding a validator for a guessed cap would create a misleading
admission result. The existing R14 check already rejects nonpositive or reused
tool budgets; a future versioned per-card budget contract should validate
exact task/profile/code hashes and provider request/usage rows once measured.

### Conditional budget calculation after rendered ledgers exist

1. Freeze one question-general policy, its source/control arms, the R15 profile
   file and loaded-profile hashes, evaluator code revision, session-sharing
   pattern, turn cap, and all task hashes. Render every allowed target request
   through the **actual** chat template. For each call slot and allowed path,
   measure final-chat prompt tokens; retain the largest observed prompt for that
   slot and the evidence offsets. Bound policy-controlled history/tool text so
   the ledger covers every permitted path, not only one successful trace.
2. For target slot `i`, set a proposed local worst-case envelope
   `L_i = max_rendered_prompt_tokens_i + 2048` using the R15 requested output
   cap. Require `L_i <= 262144` against the **declared** profile context field,
   then confirm the exact profile/cap with a provider canary. This is a
   request-planning bound, not a prediction of billed tokens. Set the per-card
   call count from complete fixed-policy traces and allowed recovery paths;
   freeze a separate cumulative `sum_i L_i` and a provider request ceiling.
   Any extra headroom must come from a named permitted path, not R4's +5.
3. Before an API call, register every fixed-baseline trajectory, control arm,
   candidate evaluation and researcher draw. Compute the **global** target
   request cap from those planned trajectories and their per-card caps; keep
   auxiliary request cap at zero for the current broker. If a later broker
   enables auxiliary calls, budget and meter that channel separately. An
   HTTP retry is another attempted provider request and needs its own cap.
4. The provider adapter must send the profile's request parameters, refuse
   dispatch when either request or local token envelope is exhausted, and
   record exact model echo, finish reason and provider input/output/total
   tokens for **every** attempted target or auxiliary call. Reconcile the sum
   of per-call provider usage with the reported run total and explain any
   difference from rendered local tokens. If usage is missing or inconsistent,
   mark the attempt `usage-unverified`, stop further paid dispatch for it, and
   never replace provider usage with an estimate or zero. This stop rule is a
   **future adapter requirement**, not functionality claimed for R14.

## Next budget qualification record

For **each** PEP 621, PEP 639 and KEP full-project arm, record: task and source
hashes; fixed policy and R15 profile hashes; session/turn limits; complete
rendered chat token count and evidence offsets for every target request;
target attempted/dispatched/succeeded calls with exact model echo, finish
reason and provider input/output/total tokens; auxiliary attempted/refused and
dispatched calls with the same fields; tool ledger; task decisions; and the
first causal failure. Repeat on source-free/identity-only/rule-intervention
controls before choosing one *prospective* per-card call/token cap. Unknown
provider usage is an explicit missing value. Aggregate by trajectory and
source lineage, not by stage or paraphrase as independent trials.

For the later researcher pretest, add the predeclared all-planned draw ledger,
baseline/source/visible-feedback bytes and hashes, researcher response model
echo/finish/usage, audited-policy hash, jail manifest, and task outcome.
After host preflight passes and planned draws are registered, invalid output,
timeouts and unknown usage stay in the planned denominator. A host preflight
refusal before registration prevents paid draws and yields **no measured update
rate**; it must not be reported as a zero-success experiment.

## Verification

The detached source revisions and SHA256 values above were checked locally.
Builders rematerialized all three task hashes and visible-document byte counts
from those pinned sources. The following no-API test set passed **43/43**:

```bash
RSICONTEXT_PEP_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/python-pep-process \
RSICONTEXT_K8S_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753 \
uv run --frozen --no-sync pytest -q tests/test_pep_r14.py tests/test_k8s_r14.py tests/test_brokered_researcher_exercise.py tests/test_qualify_r4_bc_budget.py
```
