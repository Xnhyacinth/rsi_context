# R17 researcher runtime and B/C budget audit

**Decision: researcher effective-update-rate remains unmeasured.** A fresh
preflight from clean `main@ed871518041b5b97962432a6c7623a2527939eec`
again refused before any candidate code or provider call. The pinned CPython
executable SHA-256 was
`f7c6210eb40fadcd3c2889dddd24a15fc2c9f926aec5a03bf9da66e12d581526`.
`scripts/r13_brokered_researcher_pretest.py` exited 2 with
`JailSetupError: non-root-owned path ancestor: /usr/bin` and
`live_ready=false`; the private
[`preflight log`](/volume/pt-dev/qjiu/rsi_context_external/r17-preflight/researcher-host-preflight.log)
has SHA-256 `ab027812d2e2250cf30b0367bb66c9fd24b5ae2005ebaaf8987cab3cdffbc990`.

`/usr/bin` and `/usr/lib` are UID:GID 1000:1000, mode 0755. The fixed
`setpriv`, `unshare`, `ldd` and `libseccomp.so.2.5.3` files themselves are
root-owned; their non-root-owned ancestors make their bytes replaceable by
that owner. This host has `/usr/bin/unshare` and `/usr/sbin/chroot`, but no
installed `bwrap`, Podman or Docker command or daemon socket. A user
namespace that merely maps the same UID-1000-controlled paths to root would
not establish trusted provenance. The unchanged jail is right to reject this
host; do not relax its ownership check or change the host's `/usr` ownership
to produce a passing result.

The R13 admission contract pins baseline, source and visible-feedback bytes,
researcher/worker model names and **all planned draws**. Its offline path
counts changed, audited, provider-complete submissions over the planned
denominator, with invalid output, API failure and timeout still occupying a
draw. It sets `audited_and_exercised` to zero because the path has no live
researcher adapter and never runs a candidate. The separate brokered B/C
exercise stages exact audited policy bytes in the jail and records every
target call, provider usage and refused auxiliary delegation, but accepts
only an injected offline responder today. Focused offline tests for these
contracts passed **30/30**. Neither result measures an effective update rate.

## Budget scope

The active historical `r4_bc_dev_budget_v2.json` SHA-256 is
`4a2d62dc3b85271305a03747f9fab4775884580168d8320a0111624ddd2ac975`.
It bounds the **old scripted B/C development worlds** at 40 target calls per
complete run: B baseline/candidate observed 31/35, C 18/20. A fixed baseline
and two candidate runs per group give a ceiling of 240 target requests; two
researcher draws per group give four researcher attempts. The worker profile
requests up to 2,048 output tokens and the researcher profile up to 8,192,
so their combined requested-output ceilings would be 491,520 and 32,768
tokens respectively if the entire six-run design were launched. These are
capacity bounds, **not** observed provider usage, input-token ceilings,
prices, or an R17 Kafka/KEP budget.

The historical researcher profile SHA-256 is
`9a108303b35b120ca3302ac4bfd1b50ed0d4c912de717c5fab051fc9197e46da`.
Its strict requested model name differed from the provider echo in the R4
canary; that canary cannot authorize a live draw. Before any paid researcher
pretest, freeze an available exact model identity, endpoint, decoding and
provider-usage canary; register a **small** planned-draw denominator and a
per-draw target, auxiliary, input and requested-output envelope derived from
the actual selected B/C worlds. Missing provider usage must remain unknown,
never replaced by local estimates. This is separate from R16 KEP's observed
21,871 input / 28 output tokens across four calls.

The next runtime admission artifact must come from a host or complete
independently pinned launcher/interpreter/library image whose immutable paths
pass the unchanged ownership and hash checks, followed by **unskipped** jail,
adversarial policy and broker integration tests. Only then should a live
researcher adapter be connected to the already audited snapshot path. Until
those gates pass, no candidate policy should execute in a credentialed
evaluator process and no zero update-rate estimate should be reported.
