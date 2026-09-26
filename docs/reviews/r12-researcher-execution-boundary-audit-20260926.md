# R12 researcher execution boundary audit, 2026-09-26

Status: **researcher-authored policy execution remains closed**. This was a
read-only source and host audit. It made no API call, changed no runtime file,
and did not run candidate code.

## Two independent blockers

The staged jail checks trusted ownership for every path ancestor before
copying runtime files. On this host, `/usr/bin` and `/usr/lib` are UID 1000
directories (mode 0755), although `/usr/bin/{ldd,setpriv,unshare}` and the
libseccomp target file are root owned. The root filesystem is a writable
overlay with no separate read-only `/usr` mount. The fixed launcher paths are defined in
`src/rsicontext/security/policy_jail.py`; `stage_policy_jail()` checks them
before creating a jail, and `launch_policy_jail()` rechecks launchers. The
existing Python 3.12 interpreter passes its own trust check, but changing
only that interpreter cannot make the `/usr` ancestors trusted. The skipped
`tests/test_policy_jail.py` and `tests/test_jailed_broker_integration.py`
therefore reflect the intended refusal.

The legacy paid R3 researcher pilot has a separate code-path blocker:
`scripts/r3_researcher_pilot.py:314` calls
`require_isolated_policy_executor()` before credentials, candidate loading,
or API calls. That function always raises in
`src/rsicontext/security/isolated_policy.py`. The shared live researcher
round in `scripts/r2a_compare.py` also calls the gate, and its existing
loadability/arm helpers would execute policy code in the evaluator process.
A trusted host alone cannot safely enable that legacy pilot. The gate must
stay unchanged; removing or monkeypatching it would reintroduce the unsafe
execution path.

## Existing safe components and the missing integration

The repository already has an offline jailed slice:
`stage_policy_jail(root, exact_policy_bytes, python_executable=...,
expected_python_sha256=...)` audits one `policy/seed.py`, pins copied runtime
bytes in a manifest, and creates a read-only jail. `launch_policy_jail()`
starts a single-use child with preopened broker pipes. `BrokeredPolicyHook`
mediates typed turn, tool, action, and metered model operations, and the
sequence runner can bind that hook across sessions. The offline jail and
broker tests exercise those pieces. No production script currently joins
them into a prospective researcher update-rate pretest.

The next implementation should be a **new** pilot entrypoint. It should
obtain researcher output as untrusted data through a trusted API client;
write its exact bytes only as `policy/seed.py` in a candidate snapshot;
audit and hash those bytes; stage and launch the jail; run the candidate only
through `BrokeredPolicyHook`; and supply a parent-owned Siflow responder that
returns `MeteredModelReply` with provider-reported usage. It must register
all planned researcher draws before the first draw, count invalid output,
timeout, API failure, audit rejection, and failed worker exercise in the
denominator, and keep task success separate from valid-update rate. The
broker must expose only visible observations and bounded operations; the
researcher must never access evaluator labels, credentials, or host files.
This is an implementation target, not a claim that the current host can run
it.

## Acceptance evidence before a paid researcher pretest

1. On a trusted immutable host, run the unchanged
   `tests/test_policy_jail.py`, `tests/test_jailed_broker_integration.py`,
   and `tests/test_brokered_sequence.py`; require the actual jail launch,
   adverse isolation, and broker integration cases to run without host-trust
   skips. A negative test specific to an untrusted host may skip by design.
   Record root/launcher/interpreter hashes and the jail manifest.
2. Add adversarial integration tests for attempted secret/label/host-file
   access, network and process escape, forged tool/model responses, call and
   byte caps, deadline and child cleanup, and unknown provider usage. Verify
   no researcher source reaches host `load_policy` or in-process `PolicyHook`.
3. Run a paired offline B/C candidate exercise through the broker, including
   a malicious candidate, before any paid draw. Freeze source/task/profile,
   initial policy, planned attempts, candidate snapshots, and feedback
   visibility before the live pretest.
4. Only then run the bounded Siflow researcher pretest, with provider target
   and auxiliary usage per attempt and both
   `valid_submitted / all_planned` and
   `audited_and_exercised / all_planned` reported.

This host fails the first condition today. The new brokered entrypoint is
also unimplemented; both conditions must change before live researcher
updates are admissible. Fixed benchmark-owned reader calls such as R11/R12
are a separate channel and do not satisfy this pretest.
