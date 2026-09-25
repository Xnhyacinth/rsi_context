# R4 model-authored policy isolation feasibility

Status: **live execution remains fail-closed**. Evidence collected on
2026-09-25 from `work/r4-isolation` at
`d7cd47771b76775e23b93fc84cde4bace5ec39f6`. No provider or GPU call was
made. These probes exercised kernel primitives in short-lived child processes;
they did not execute a candidate policy.

## Decision

This host can support a jailed candidate worker, but the repository does not
yet have one. `PolicyHook` and `load_policy` execute lifecycle Python in the
evaluator process; `FreshProcessPolicyFactory` starts a fresh interpreter with
a scrubbed environment but still exposes the host filesystem and network.
The existing `require_isolated_policy_executor()` gate must remain in place.
Neither a static `PolicyAuditor` pass nor the probes below authorizes a live
candidate run.

The immediate implementation gap is a typed, bounded turn/tool/model broker.
The evaluator must retain `ProjectState`, `ToolBudget`, reader credentials,
scoring, labels, and unrevealed material. The worker may receive only one
visible stage observation and candidate-owned state, then request named,
metered operations over a checked IPC protocol. Running today's `PolicyHook`
in a child would move evaluator state and the credentialed responder into
that child, defeating the boundary.

## Host evidence

| Primitive | Harmless probe and observed result | Consequence |
| --- | --- | --- |
| Bubblewrap/Firejail | `command -v bwrap` and `command -v firejail` returned no executable. | Do not build a launcher that assumes either is installed. |
| Network namespace | `unshare --net sh -c 'readlink /proc/self/ns/net; cat /proc/self/net/route'` produced a different namespace inode from the parent and an empty route table. | Direct AF_INET access can be removed. The inherited `/sys` mount still listed host interfaces, so `/proc/self/net/route`, not `/sys/class/net`, was the useful route check. |
| Mount namespace | `unshare --user --map-root-user --mount --net --propagation unchanged` succeeded, but `mount -t tmpfs tmpfs <temporary-directory>` returned 32: `cannot mount tmpfs read-only`. | A bind/tmpfs or `pivot_root` jail is unavailable in this environment. |
| Landlock | `landlock_create_ruleset(..., LANDLOCK_CREATE_RULESET_VERSION)` returned ABI 1. A forked child applied a read-only path-beneath rule after `PR_SET_NO_NEW_PRIVS`: the allowed test file remained readable and `/etc/passwd` failed with `PermissionError`/`EACCES` (13). | Landlock can restrict file access. ABI 1 covers filesystem operations, not network or process privileges. |
| Non-privileged chroot | `setpriv --reuid 65534 --regid 65534 --clear-groups --no-new-privs unshare --user --map-root-user --net /usr/bin/python3 -c '...os.chroot(jail); os.chdir("/")...'` succeeded for a temporary `/tmp` jail; `/etc/passwd` was invisible inside. | Chroot can supplement Landlock if the worker has no outside cwd or inherited file descriptor. The mapped root identity is host UID 65534, not host root. |
| Seccomp | In a forked child, `PR_SET_NO_NEW_PRIVS` returned 0; `libseccomp.so.2` loaded a filter denying syscall `getpid`, which returned `EACCES`, and `/proc/self/status` reported `Seccomp: 2`. | A deny policy can be installed after trusted initialization. It needs an explicit syscall profile and regression tests before use. |
| Local runtime access | `namei -l` on `.venv/bin/python` showed `/volume/pt-dev` and the uv runtime directory as mode `0700`; UID 65534 cannot traverse them. | Stage a minimal, SHA-checked Python 3.12 runtime in an accessible jail. Do not loosen project or shared-runtime directory permissions. |

The Landlock and chroot demonstrations ran in children and restored no host
state. Their success says that the primitives work; it does not prove that a
Python policy cannot escape a future worker implementation.

## Smallest secure implementation path

1. Add a trusted worker bootstrap that starts with an explicit environment
   allowlist and `close_fds=True`, stages a versioned Python runtime and the
   exact audited policy bytes in a root-owned, non-writable jail, then drops
   host UID/GID and capabilities. Enter a new user and network namespace;
   `chroot` and `chdir("/")`; apply Landlock to deny access outside the
   staged runtime and policy; apply `no_new_privs`, a tested seccomp policy,
   and CPU, memory, wall-time, process-count, and output limits. Fail if any
   required step fails. Record runtime and jail material SHA256 values.
2. Replace in-process `load_policy`/`PolicyHook` use for candidate text with a
   length-bounded, versioned IPC exchange. The first message contains only
   visible `StageView` fields, receipts, and candidate-owned state. The child
   may request `ask_model`, `reread`, `query_sandbox`, `request_verification`,
   or `delegate`; the parent validates exact argument shapes, enforces and
   charges `ToolBudget` before acting, and returns typed replies. The final
   `TurnDecision` must have validated actions, memory writes, and bounded
   text. Reject duplicate JSON keys, non-finite values, unknown fields,
   oversized frames, excess requests, and out-of-order messages. Keep every
   worker/model/tool call in the ledger, including refusals and failures.
3. Audit and hash the candidate before staging it. The evaluator may parse
   syntax, but must not use `_policy_loadable` to execute candidate text in
   its own process. The worker executes only the bytes whose digest passed
   the audit; check the digest again at launch and on completion.
4. Prove a legitimate A development turn with the offline responder through
   the new broker. Separately prove that malicious policies cannot read a
   sentinel environment variable, evaluator-only file, `/proc` parent state,
   or host socket; cannot write outside the jail; and cannot exceed call,
   time, memory, process, or output limits. Include reflective Python escape
   attempts, not only literal `open()`/`import os`. Confirm metering and
   action/receipt behavior match the in-process baseline before changing any
   live gate. B/C also need session-state continuity tests.

The first code change should be an isolated worker plus protocol test harness
that never imports or copies evaluator-only material. Keep
`require_isolated_policy_executor()` unconditional until the complete
negative and positive suites pass. The open-S fresh-process track needs its
own review against the same filesystem/network requirements; it is not made
safe by the lifecycle gate.
