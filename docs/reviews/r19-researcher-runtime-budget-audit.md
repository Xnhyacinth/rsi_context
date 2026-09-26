# R19 researcher runtime and Iceberg B/C budget audit

**Decision, 2026-09-27:** the effective-update-rate live pretest is still
unmeasured. The current host fails the unchanged jail trust check before any
candidate launch. The R18 Iceberg geometry supports a bounded *prospective
fixed-reader feasibility screen*, not a researcher draw or a new B/C budget.
No candidate policy, GPU, or provider was run for this audit.

## Rechecked identities and host boundary

This isolated branch began clean at `main@9e551f4594c59689eb80dd5a86a192c8d4ef475d`.
The reviewed inputs were the R18 Iceberg geometry JSON, SHA-256
`aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448`,
R15 Qwen fixed-reader profile, SHA-256
`c3bb91d662d588e0a0a69101fb8fd851a1c910ded66e4387d4afccc9c9002ff6`,
and historical R4 budget v2, SHA-256
`4a2d62dc3b85271305a03747f9fab4775884580168d8320a0111624ddd2ac975`.
The actual jail implementation was
`src/rsicontext/security/policy_jail.py`, SHA-256
`fb03cb4f8f3d94e388e239b0b882541a301424956aea9a7c74224f8b52a2a196`.
These file hashes bind this review's inputs; they are not a live run identity.

The read-only host check observed effective UID 0, `/usr/bin` and `/usr/lib`
owned by UID:GID 1000:1000, mode 0755, while the pinned `unshare`, `setpriv`,
`ldd`, `chroot`, and `libseccomp.so.2.5.3` files themselves are root-owned.
Invoking the actual `_assert_trusted_file(Path("/usr/bin/unshare"))` guard in
the project `uv` environment exited 1 with the first causal error
`JailSetupError: non-root-owned path ancestor: /usr/bin`. `namei -l` also
showed `/usr/lib` as a UID-1000-owned ancestor of the fixed seccomp library.
No Docker/Podman/bwrap command or Docker/Podman socket was found. The host's
`max_user_namespaces` was 8,228,685, `unprivileged_userns_clone` was 1,
and a process-local `unshare --user --map-root-user --net /usr/bin/true`
returned 0. Namespace availability does not make the replaceable host
ancestors trusted. This audit did not change host ownership or bypass the
check.

`brokered_researcher_exercise.py` now implements an **offline** exact-snapshot
exercise through `BrokeredPolicyHook` and the session runner. It accepts an
injected target responder, sets `delegate_runner=None`, and reports target
and refused auxiliary calls. The R13 CLI still exposes only trusted-runtime
preflight; `run_offline_admission` accepts injected draws and fixes
`audited_and_exercised` at zero. There is no end-to-end live researcher draw,
worker adapter, or provider usage gate joining admission to this exercise.
The host trust refusal comes first, so the effective-update numerator and
denominator are both **unobserved**, rather than zero successes.

An admissible live path needs a separate trusted host or a complete,
independently pinned launcher/interpreter/library image whose ancestors and
bytes pass the **unchanged** jail checks. Run the jail and broker integration
tests without host skips, including adverse isolation and cleanup, then
re-run the R13 preflight with a predeclared interpreter digest. Only after
that should a live adapter bind exact audited `policy/seed.py` bytes to a
candidate-specific exercise. Freeze source, visible feedback, baseline,
task, model profile, every planned draw, and provider request/usage limits
before the first draw. Count invalid submissions, timeouts, API failures,
unknown usage, and failed exercises in the planned denominator; report
`valid_submitted / all_planned`, `audited_and_exercised / all_planned`, and
task success separately.

## Fixed-reader screen capacity versus researcher opportunity

The R18 artifact enumerates four session-1 arms and only three allowed
session-2 prompt variants. A future fixed reader that uses exactly one Qwen
target call in each session, no reread call, no auxiliary call, and aborts
unregistered or malformed S1 replies before S2 has this **local tokenizer
planning envelope**. It is conditional on the runner calling the frozen
prompt functions; no Iceberg provider parity or actual usage was observed.

| Unit | Target requests | Max local input tokens | Requested output tokens | Local input + requested output |
| --- | ---: | ---: | ---: | ---: |
| Authentic two-session trajectory | 2 | 25,204 | 4,096 | 29,300 |
| Constructed-rule two-session trajectory | 2 | 25,215 | 4,096 | 29,311 |
| Source-free two-session control | 2 | 447 | 4,096 | 4,543 |
| Identity-only two-session control | 2 | 582 | 4,096 | 4,678 |
| One four-arm Qwen screen | **8** | **51,448** | **16,384** | **67,832** |

The S1 inputs are respectively 24,883, 24,894, 126, and 261 final-chat
tokens. The maximum registered S2 input is 321; the all-unknown continuation
is 317. This table uses 321 for every arm and therefore covers all **listed**
S2 continuations. The longest single request plus its 2,048 requested output
is 26,942 tokens, inside the 32,768-token benchmark window. The full-file
42,169-token survey exceeds that window and is excluded. These are local
template counts, not billed Siflow input or output. Canaries, retries, a
second reader family, and any newly allowed continuation each need their own
registered requests and geometry; they are outside the eight requests.

This screen is a source-dependency feasibility experiment. Its eight target
requests must remain in a reader-screen ledger, with zero auxiliary dispatch
and provider-reported usage or explicit unknowns. It supplies **zero**
researcher draws. If a later researcher draw evaluates one Iceberg trajectory
through this same *fixed* reader, the largest listed two-session envelope is
2 target requests, 25,215 local input and 4,096 requested output tokens;
the researcher request is separate. A candidate-controlled `BrokeredPolicyHook`
can request additional model turns or tool actions within its own frozen
caps, so these fixed-reader numbers cannot be used as its per-draw cap.
The historical researcher profile permits 8,192 requested output tokens,
but its strict model echo failed a prior canary; no R19 researcher model,
input ceiling, valid provider usage, or planned-draw denominator is admitted.

The R4 `40` target calls per complete development run came from different
scripted B/C worlds (maximum observed candidate 35 plus five headroom), with
four researcher opportunities across two groups and a six-run 240-target
capacity. It is neither a measured Iceberg call count nor headroom for this
screen. Iceberg currently supplies one **longitudinal B-like** two-session
candidate with an unqualified source-rule contrast. It does not yet provide
a C-family perturbation or an independent qualified parent. Before B/C
researcher testing, freeze both task families, question-general policy,
session/turn paths, tool and target caps, source/control arms, exact-profile
canaries, provider input/output limits, and all planned researcher attempts.
Keep a separate per-draw target/auxiliary ledger; missing provider usage
must stay unknown, never be replaced with these local estimates.

## Reproduction of this no-provider check

From the project root, `stat -c '%n %u:%g %a %F' /usr/bin /usr/lib
/usr/bin/unshare /usr/lib/x86_64-linux-gnu/libseccomp.so.2.5.3` and
`namei -l /usr/bin/unshare
/usr/lib/x86_64-linux-gnu/libseccomp.so.2.5.3` show the relevant ownership
chain. The direct guard call was:

```sh
uv run --frozen --no-sync python -c 'from pathlib import Path; from rsicontext.security.policy_jail import _assert_trusted_file; _assert_trusted_file(Path("/usr/bin/unshare"))'
```

The table is the sum of `session_1[*].input_tokens` plus four times the
maximum `session_2_by_retained_rule[*].input_tokens` in
`docs/reviews/r18-iceberg-geometry.json`, with 2,048 requested output per
call. No test, provider request, or candidate launch was needed for this
documentation-only change.
