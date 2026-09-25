# R6 lifecycle policy jail: offline evidence and scope

Status: **host admission blocked; live isolation gate remains closed**. This
slice does not wire the candidate launcher into live R3/R4 runs or call a
model. It accepts one audited `policy/seed.py`-shaped lifecycle policy source,
not an open-S directory or a general Python package.

Security review found that this host's `/usr/bin` and `/usr/lib` ancestor
directories are owned by UID 1000 with mode 0755. That owner can replace
`setpriv`, `unshare`, `ldd`, or system library source paths between a hash and
execution. The current code rejects such ancestors **before staging or
executing** anything from them. A non-skipped regression proves the exact
`non-root-owned path ancestor: /usr/bin` refusal on this host. Root-owned,
non-writable task parents under sticky root-owned `/tmp` remain admissible as
jail locations; a world-writable or non-root-owned child parent does not.

`stage_policy_jail` requires host root and a predeclared SHA256 for the Python
3.12 executable. It copies the executable, observed stdlib import closure,
dynamic loader/libraries, trusted child, and exact audited policy bytes into
one root-owned read-only jail under a trusted host-UID-65534-traversable parent. It
records every copied file hash in `MANIFEST.json` and rejects missing, added,
modified, symlinked, writable, or non-root-owned material before launch. The
staged interpreter and child hashes must also match the separate manifest
identity fields. Source interpreter, child, dependency, and launcher paths
must have root-owned non-writable ancestors before any root-side probe. The
launcher uses the staged loader and interpreter; it never symlinks `.venv`,
uses `preexec_fn`, or executes policy text in the parent.

The child starts as host UID 65534, enters separate user and network
namespaces, checks its UID map and its exact inherited FD set, then installs
CPU/address-space/file/core/process/FD limits, `no_new_privs`, Landlock ABI 1
read-only path rules, `chroot`, and a seccomp deny profile. Only afterward
does it open and hash the candidate bytes and call `exec`. It keeps the same
two anonymous broker pipes across stage turns, resetting protocol sequence
to zero for each turn. `JailedPolicyProcess` owns the child process group;
`wait(timeout)` terminates/reaps on wall deadline, and `close()` is required
in the host broker's `finally` block.

Before the path-trust correction, offline probes on this host observed: two
visible turns on one pipe pair; A/B/C
fixed seed **survey** turns each make a typed `ask_model` request and accept a
fake reply; a world-readable host sentinel, `/etc/passwd`, and `/proc` cannot
be read; jail writes, AF_INET socket creation, fork, 600 MiB allocation, and
an oversized output frame are denied; seccomp mode is 2; a CPU loop is killed
by the 3-second limit; an idle worker is reaped at a parent wall timeout; and
a reaped PID is not signalled again. **Those earlier observations do not
qualify the current host for launch** because they used replaceable `/usr`
paths. Under the corrected code, the same launch tests skip with the named
host blocker; path-trust and manifest cross-pin refusals still execute. The
tests use no provider or GPU.

These checks do **not** prove full `PolicyHook` equivalence or formal benchmark
readiness. The child supports the fixed A/B/C survey policy shape and an
action/tool façade, but full B/C session behavior, follow-up action/receipt
semantics, policy-created `TurnDecision` objects, and arbitrary candidate
imports are not validated. The future host broker must still constrain every
tool/model request, validate actions and visibility, monitor each read/write
deadline, and close the handle on every exit. Keep the existing live gate
unconditional until end-to-end paired behavior and adversarial tests pass.
The remaining host work is a predeclared, independently pinned set of
launchers and libraries copied into a root-owned location and executed only
there, without running host `ldd` from a replaceable path. This code assumes
host root and its non-writable paths are trusted; it does not claim resistance
to a malicious host root or a mutation by that trust principal.
