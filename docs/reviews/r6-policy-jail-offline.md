# R6 lifecycle policy jail: offline evidence and scope

Status: **offline primitive only; live isolation gate remains closed**. This
slice does not wire the candidate launcher into live R3/R4 runs or call a
model. It accepts one audited `policy/seed.py`-shaped lifecycle policy source,
not an open-S directory or a general Python package.

`stage_policy_jail` requires host root and a predeclared SHA256 for the Python
3.12 executable. It copies the executable, observed stdlib import closure,
dynamic loader/libraries, trusted child, and exact audited policy bytes into
one root-owned read-only jail under a host-UID-65534-traversable parent. It
records every copied file hash in `MANIFEST.json` and rejects missing, added,
modified, symlinked, writable, or non-root-owned material before launch. The
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

Offline tests on this host prove: two visible turns on one pipe pair; A/B/C
fixed seed **survey** turns each make a typed `ask_model` request and accept a
fake reply; a world-readable host sentinel, `/etc/passwd`, and `/proc` cannot
be read; jail writes, AF_INET socket creation, fork, 600 MiB allocation, and
an oversized output frame are denied; seccomp mode is 2; a CPU loop is killed
by the 3-second limit; an idle worker is reaped at a parent wall timeout; and
a reaped PID is not signalled again. The tests use no provider or GPU.

These checks do **not** prove full `PolicyHook` equivalence or formal benchmark
readiness. The child supports the fixed A/B/C survey policy shape and an
action/tool façade, but full B/C session behavior, follow-up action/receipt
semantics, policy-created `TurnDecision` objects, and arbitrary candidate
imports are not validated. The future host broker must still constrain every
tool/model request, validate actions and visibility, monitor each read/write
deadline, and close the handle on every exit. Keep the existing live gate
unconditional until end-to-end paired behavior and adversarial tests pass.
