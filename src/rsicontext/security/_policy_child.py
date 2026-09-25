"""Trusted, stdlib-only child for an isolated lifecycle policy session.

This file is copied byte-for-byte into a read-only jail. It must not import
evaluator modules. Candidate bytes are opened only after every kernel guard
has been installed. The host validates all returned wire messages again.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import math
import os
import re
import resource
import statistics
import struct
import sys
from types import SimpleNamespace
from typing import Any, cast

_FRAME_CAP = 1_048_576
_TOTAL_OUTPUT_CAP = 2 * _FRAME_CAP
_PR_SET_NO_NEW_PRIVS = 38
_PR_GET_NO_NEW_PRIVS = 39
_PR_GET_SECCOMP = 21
_LANDLOCK_CREATE_RULESET = 444
_LANDLOCK_ADD_RULE = 445
_LANDLOCK_RESTRICT_SELF = 446
_LANDLOCK_RULE_PATH_BENEATH = 1
_LANDLOCK_VERSION = 1
_FS_EXECUTE = 1 << 0
_FS_WRITE_FILE = 1 << 1
_FS_READ_FILE = 1 << 2
_FS_READ_DIR = 1 << 3
_FS_REMOVE_DIR = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_CHAR = 1 << 6
_FS_MAKE_DIR = 1 << 7
_FS_MAKE_REG = 1 << 8
_FS_MAKE_SOCK = 1 << 9
_FS_MAKE_FIFO = 1 << 10
_FS_MAKE_BLOCK = 1 << 11
_FS_MAKE_SYM = 1 << 12
_HANDLED_FS = (1 << 13) - 1  # Landlock ABI 1; REFER was added in ABI 2.
_ALLOWED_FS = _FS_EXECUTE | _FS_READ_FILE | _FS_READ_DIR
_DENIED_SYSCALLS = (
    "socket",
    "socketpair",
    "connect",
    "bind",
    "listen",
    "accept",
    "accept4",
    "clone",
    "clone3",
    "fork",
    "vfork",
    "execve",
    "execveat",
    "ptrace",
    "process_vm_readv",
    "process_vm_writev",
    "pidfd_getfd",
    "pidfd_open",
    "pidfd_send_signal",
    "open_by_handle_at",
    "io_uring_setup",
    "io_uring_enter",
    "io_uring_register",
    "userfaultfd",
    "kill",
    "tkill",
    "tgkill",
    "mount",
    "umount2",
    "pivot_root",
    "chroot",
    "setns",
    "unshare",
    "bpf",
    "perf_event_open",
    "keyctl",
    "init_module",
    "finit_module",
    "delete_module",
    "reboot",
    "kexec_load",
    "swapon",
    "swapoff",
    "mknod",
    "mknodat",
)
_SAFE_BUILTIN_NAMES = (
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "frozenset",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
)
_ALLOWED_IMPORTS = {"json": json, "re": re, "math": math, "statistics": statistics}


class JailError(RuntimeError):
    """The candidate execution boundary did not initialize."""


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _check_fd_inventory(read_fd: int, write_fd: int) -> None:
    expected = {0, 1, 2, read_fd, write_fd}
    opened = set()
    for name in os.listdir("/proc/self/fd"):
        fd = int(name)
        try:
            os.fstat(fd)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                continue  # listdir's transient descriptor closed on return.
            raise
        opened.add(fd)
    if opened != expected:
        raise JailError(f"unexpected inherited descriptors: {sorted(opened - expected)}")


def _check_namespaces(parent_netns: str) -> None:
    if os.uname().machine != "x86_64":
        raise JailError("policy jail currently supports x86_64 Linux only")
    with open("/proc/self/uid_map", encoding="utf-8") as stream:
        uid_map = stream.read().split()
    if uid_map[:3] != ["0", "65534", "1"]:
        raise JailError("worker user namespace is not mapped to host UID 65534")
    if os.geteuid() != 0 or os.getgroups():
        raise JailError("worker lacks isolated UID 0 or retains supplementary groups")
    if os.readlink("/proc/self/ns/net") == parent_netns:
        raise JailError("worker shares the host network namespace")


def _set_limits() -> None:
    limits = (
        (resource.RLIMIT_CPU, 3),
        (resource.RLIMIT_AS, 512 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 32),
        (resource.RLIMIT_NPROC, 0),
    )
    for kind, cap in limits:
        resource.setrlimit(kind, (cap, cap))


def _set_no_new_privs(libc: Any) -> None:
    libc.prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise JailError("PR_SET_NO_NEW_PRIVS failed")
    if libc.prctl(_PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1:
        raise JailError("no_new_privs was not observed")


def _landlock_jail(libc: Any, jail_root: str) -> None:
    libc.syscall.restype = ctypes.c_long
    if libc.syscall(_LANDLOCK_CREATE_RULESET, None, 0, _LANDLOCK_VERSION) < 1:
        raise JailError("Landlock ABI 1 unavailable")
    ruleset = _RulesetAttr(_HANDLED_FS)
    rules_fd = libc.syscall(
        _LANDLOCK_CREATE_RULESET, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0
    )
    if rules_fd < 0:
        raise JailError("Landlock ruleset creation failed")
    jail_fd = os.open(jail_root, os.O_PATH | os.O_CLOEXEC)
    try:
        rule = _PathBeneathAttr(_ALLOWED_FS, jail_fd)
        if (
            libc.syscall(
                _LANDLOCK_ADD_RULE, rules_fd, _LANDLOCK_RULE_PATH_BENEATH, ctypes.byref(rule), 0
            )
            != 0
        ):
            raise JailError("Landlock path rule failed")
        if libc.syscall(_LANDLOCK_RESTRICT_SELF, rules_fd, 0) != 0:
            raise JailError("Landlock restriction failed")
    finally:
        os.close(jail_fd)
        os.close(rules_fd)


def _seccomp_jail(libc: Any, seccomp: Any) -> None:
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    seccomp.seccomp_rule_add.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise JailError("seccomp filter allocation failed")
    try:
        deny = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
        for name in _DENIED_SYSCALLS:
            number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0 or seccomp.seccomp_rule_add(context, deny, number, 0) != 0:
                raise JailError(f"seccomp cannot deny syscall {name}")
        if seccomp.seccomp_load(context) != 0:
            raise JailError("seccomp filter installation failed")
    finally:
        seccomp.seccomp_release(context)
    if libc.prctl(_PR_GET_SECCOMP, 0, 0, 0, 0) != 2:
        raise JailError("seccomp filter was not observed")


def _apply_jail(jail_root: str, parent_netns: str, read_fd: int, write_fd: int) -> None:
    _check_namespaces(parent_netns)
    _check_fd_inventory(read_fd, write_fd)
    libc = ctypes.CDLL(None, use_errno=True)
    seccomp = ctypes.CDLL(jail_root + "/lib/x86_64-linux-gnu/libseccomp.so.2", use_errno=True)
    _set_limits()
    _set_no_new_privs(libc)
    _landlock_jail(libc, jail_root)
    os.chroot(jail_root)
    os.chdir("/")
    os.environ.clear()
    sys.path[:] = ["/lib/python3.12", "/lib/python3.12/lib-dynload"]
    _seccomp_jail(libc, seccomp)


def _read_exact(fd: int, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        part = os.read(fd, count - len(chunks))
        if not part:
            raise EOFError("policy pipe closed")
        chunks.extend(part)
    return bytes(chunks)


def _read_frame(fd: int) -> dict[str, Any]:
    size = struct.unpack(">I", _read_exact(fd, 4))[0]
    if size == 0 or size > _FRAME_CAP:
        raise JailError("invalid policy frame length")
    message = json.loads(_read_exact(fd, size).decode("utf-8"))
    if not isinstance(message, dict):
        raise JailError("policy frame is not an object")
    return cast(dict[str, Any], message)


def _write_frame(fd: int, message: dict[str, Any], output_count: list[int]) -> None:
    payload = json.dumps(
        message, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    if len(payload) > _FRAME_CAP or output_count[0] + len(payload) > _TOTAL_OUTPUT_CAP:
        raise JailError("policy output limit exceeded")
    output_count[0] += len(payload)
    frame = struct.pack(">I", len(payload)) + payload
    while frame:
        frame = frame[os.write(fd, frame) :]


class _Action:
    """Only the Action fields exposed by the existing TurnActions factory."""

    def __init__(
        self, kind: str, record_id: str, fields: dict[str, Any], provenance: tuple[str, ...] = ()
    ) -> None:
        self.kind = kind
        self.record_id = record_id
        self.fields = dict(fields)
        self.provenance = tuple(provenance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "record_id": self.record_id,
            "fields": dict(self.fields),
            "provenance": list(self.provenance),
            "precondition_refs": [],
            "precondition_current_revision": None,
            "precondition_revision_scope": [],
            "precondition_scope_constraint": None,
        }


class _Actions:
    def create_record(self, record_id: str, fields: dict[str, Any]) -> _Action:
        return _Action("create_record", record_id, fields)

    def update_record(self, record_id: str, fields: dict[str, Any]) -> _Action:
        return _Action("update_record", record_id, fields)

    def request_verification(self, record_id: str, check: str, subject: str) -> _Action:
        return _Action("request_verification", record_id, {"check": check, "subject": subject})

    def finalize(
        self, record_id: str, fields: dict[str, Any], provenance: tuple[str, ...]
    ) -> _Action:
        return _Action("finalize", record_id, fields, provenance)


class _Tools:
    def __init__(self, read_fd: int, write_fd: int, output_count: list[int]) -> None:
        self.read_fd = read_fd
        self.write_fd = write_fd
        self.output_count = output_count
        self.seq = 1

    def _call(self, tool: str, args: dict[str, Any]) -> SimpleNamespace:
        _write_frame(
            self.write_fd,
            {
                "version": 1,
                "seq": self.seq,
                "type": "tool_request",
                "body": {"tool": tool, "args": args},
            },
            self.output_count,
        )
        reply = _read_frame(self.read_fd)
        if (reply.get("version"), reply.get("seq"), reply.get("type")) != (
            1,
            self.seq + 1,
            "tool_reply",
        ):
            raise JailError("out-of-order tool reply")
        body = reply.get("body")
        if not isinstance(body, dict) or body.get("tool") != tool:
            raise JailError("mismatched tool reply")
        result = body.get("result")
        if not isinstance(result, dict):
            raise JailError("invalid tool reply")
        self.seq += 2
        return SimpleNamespace(**result)

    def reread(self, doc_id: str, span: tuple[int, int] | None = None) -> SimpleNamespace:
        return self._call("reread", {"doc_id": doc_id, "span": list(span) if span else None})

    def query_sandbox(self, pattern: str) -> SimpleNamespace:
        return self._call("query_sandbox", {"pattern": pattern})

    def request_verification(self, check: str, subject: str) -> SimpleNamespace:
        return self._call("request_verification", {"check": check, "subject": subject})

    def delegate(self, query: str, doc_ids: tuple[str, ...]) -> SimpleNamespace:
        return self._call("delegate", {"query": query, "doc_ids": list(doc_ids)})

    def ask_model(self, prompt: str) -> SimpleNamespace:
        reply = self._call("ask_model", {"prompt": prompt})
        return SimpleNamespace(
            ok=reply.ok,
            content=reply.answer,
            cause=reply.cause,
            tokens_in=reply.tokens_in,
            tokens_out=reply.tokens_out,
        )


def _safe_import(name: str, *_args: Any, **_kwargs: Any) -> Any:
    if name not in _ALLOWED_IMPORTS:
        raise ImportError(f"policy import {name!r} is unavailable")
    return _ALLOWED_IMPORTS[name]


def _load_policy(expected_sha: str) -> Any:
    with open("/policy/seed.py", "rb") as stream:
        source = stream.read()
    if hashlib.sha256(source).hexdigest() != expected_sha:
        raise JailError("audited policy SHA256 changed inside jail")
    import builtins

    safe = {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}
    safe["__import__"] = _safe_import
    namespace: dict[str, Any] = {"__builtins__": safe, **_ALLOWED_IMPORTS}
    exec(compile(source, "/policy/seed.py", "exec"), namespace)  # nosec B102
    policy = namespace.get("on_turn")
    if not callable(policy):
        raise JailError("policy has no on_turn function")
    return policy


def run_session(read_fd: int, write_fd: int, expected_sha: str) -> None:
    """Serve multiple turns on the same pipes, with seq reset for each turn."""

    policy = _load_policy(expected_sha)
    while True:
        try:
            start = _read_frame(read_fd)
        except EOFError:
            return
        if (start.get("version"), start.get("seq"), start.get("type")) != (1, 0, "stage_start"):
            raise JailError("host stage_start required")
        body = start.get("body")
        if not isinstance(body, dict) or not isinstance(body.get("view"), dict):
            raise JailError("invalid stage_start")
        state = body.get("state")
        if not isinstance(state, dict):
            raise JailError("invalid candidate state")
        output_count = [0]
        tools = _Tools(read_fd, write_fd, output_count)
        view = SimpleNamespace(**body["view"])
        view.documents = tuple(SimpleNamespace(**doc) for doc in view.documents)
        receipts = tuple(SimpleNamespace(**receipt) for receipt in view.receipts)
        view.receipts = receipts
        view.axes = SimpleNamespace(**view.axes)
        turn = SimpleNamespace(
            view=view,
            receipts=receipts,
            state=state,
            actions=_Actions(),
            tools=tools,
            ask_model=tools.ask_model,
        )
        turn.stage_kind = view.kind
        turn.documents_text = "\n\n".join(
            f"[[doc:{doc.doc_id}]] {doc.title}\n{doc.text}" for doc in view.documents
        )
        try:
            decision = policy(turn)
            if not isinstance(decision, dict):
                raise TypeError("on_turn must return a decision dict")
            writes = decision.get("memory_writes", {}) or {}
            if not isinstance(writes, dict):
                raise TypeError("memory_writes must be an object")
            state.update(writes)
            actions = decision.get("actions", ())
            if not isinstance(actions, (tuple, list)) or any(
                not isinstance(action, _Action) for action in actions
            ):
                raise TypeError("actions must come from turn.actions")
            final = {
                "pack_text": decision.get("pack_text", ""),
                "actions": [action.to_dict() for action in actions],
                "memory_writes": writes,
                "errors": list(decision.get("errors", ())),
            }
        except Exception as exc:
            final = {
                "pack_text": "policy turn error",
                "actions": [],
                "memory_writes": {},
                "errors": [f"on_turn raised {type(exc).__name__}: {exc}"[:500]],
            }
        _write_frame(
            write_fd,
            {
                "version": 1,
                "seq": tools.seq,
                "type": "turn_done",
                "body": {"decision": final, "state": state},
            },
            output_count,
        )


def _probe_controls(secret_path: str, write_fd: int) -> None:
    """Trusted offline self-test; launch_policy_jail never selects this mode."""

    results: dict[str, Any] = {}
    for name, path in (
        ("host_secret_hidden", secret_path),
        ("proc_hidden", "/proc/1/environ"),
        ("host_file_hidden", "/etc/passwd"),
    ):
        try:
            with open(path, "rb") as stream:
                stream.read(1)
        except OSError:
            results[name] = True
        else:
            results[name] = False
    try:
        fd = os.open("/policy/seed.py", os.O_WRONLY)
    except OSError:
        results["jail_write_denied"] = True
    else:
        os.close(fd)
        results["jail_write_denied"] = False
    libc = ctypes.CDLL(None, use_errno=True)
    sock = libc.socket(2, 1, 0)  # AF_INET, SOCK_STREAM
    results["network_denied"] = sock == -1 and ctypes.get_errno() == errno.EPERM
    if sock >= 0:
        os.close(sock)
    try:
        child_pid = os.fork()
    except OSError:
        results["fork_denied"] = True
    else:
        if child_pid == 0:
            os._exit(99)
        os.waitpid(child_pid, 0)
        results["fork_denied"] = False
    try:
        bytearray(600 * 1024 * 1024)
    except MemoryError:
        results["memory_denied"] = True
    else:
        results["memory_denied"] = False
    try:
        _write_frame(write_fd, {"oversized": "x" * _FRAME_CAP}, [0])
    except JailError:
        results["output_denied"] = True
    else:
        results["output_denied"] = False
    results["cpu_limit_seconds"] = resource.getrlimit(resource.RLIMIT_CPU)[0]
    results["seccomp_mode"] = libc.prctl(_PR_GET_SECCOMP, 0, 0, 0, 0)
    _write_frame(write_fd, {"probe": results}, [0])


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 and argv[1].startswith("--") else ""
    if mode:
        argv = [argv[0], *argv[2:]]
    if len(argv) != (7 if mode == "--self-test" else 6):
        raise JailError("expected jail_root, parent_netns, read_fd, write_fd, policy_sha")
    jail_root, parent_netns, read_arg, write_arg, policy_sha = argv[1:6]
    read_fd, write_fd = int(read_arg), int(write_arg)
    if len(policy_sha) != 64 or any(c not in "0123456789abcdef" for c in policy_sha):
        raise JailError("invalid audited policy SHA256")
    _apply_jail(jail_root, parent_netns, read_fd, write_fd)
    if mode == "--self-test":
        _probe_controls(argv[6], write_fd)
        return 0
    if mode == "--cpu-burn":
        while True:
            pass
    if mode:
        raise JailError("unsupported trusted child mode")
    run_session(read_fd, write_fd, policy_sha)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (JailError, OSError, ValueError) as exc:
        # Never emit the exception body: parent stderr is intentionally closed.
        raise SystemExit(73) from exc
