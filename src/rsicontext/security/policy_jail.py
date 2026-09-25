"""Offline-only staged CPython jail for one lifecycle policy session.

The caller owns two anonymous pipes and the host broker. This module never
loads policy code into the evaluator, never calls a model, and does not change
the live isolation gate. A jail is a single-use, root-owned, read-only copy
of a pinned interpreter, its observed stdlib import closure, linker libraries,
the trusted child, and the exact audited policy bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from rsicontext.lifecycle.policy import scan_policy
from rsicontext.security.audit import PolicyAuditor

_CHILD_SOURCE = Path(__file__).with_name("_policy_child.py")
_SET_PRIV = Path("/usr/bin/setpriv")
_UNSHARE = Path("/usr/bin/unshare")
_SECCOMP = Path("/usr/lib/x86_64-linux-gnu/libseccomp.so.2")
_PROBE = """
import __future__, builtins, ctypes, errno, hashlib, json, math, os, re, resource
import statistics, struct, sys, types, typing
import json as output_json
files = sorted({getattr(module, '__file__', '') for module in sys.modules.values()}
               - {''})
print(output_json.dumps({'prefix': sys.base_prefix, 'files': files}))
"""


class JailSetupError(RuntimeError):
    """A required runtime pin or filesystem boundary is unavailable."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _material_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _ldd_dependencies(path: Path) -> set[Path]:
    result = subprocess.run(
        ["/usr/bin/ldd", str(path)], check=True, capture_output=True, text=True, timeout=10
    )
    dependencies: set[Path] = set()
    for line in result.stdout.splitlines():
        matches = re.findall(r"(?<![A-Za-z0-9_])(/[^\s()]+)", line)
        for raw in matches:
            candidate = Path(raw)
            if candidate.is_file():
                dependencies.add(candidate)
    if not dependencies:
        raise JailSetupError(f"ldd found no runtime dependencies for {path}")
    return dependencies


def _stdlib_import_closure(python: Path) -> tuple[Path, set[Path]]:
    result = subprocess.run(
        [str(python), "-I", "-S", "-c", _PROBE],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise JailSetupError("Python import closure probe returned invalid output")
    prefix = Path(str(payload["prefix"])).resolve()
    stdlib = prefix / "lib" / "python3.12"
    if not stdlib.is_dir():
        raise JailSetupError("pinned interpreter has no Python 3.12 stdlib")
    files: set[Path] = set()
    for item in payload["files"]:
        if not isinstance(item, str):
            raise JailSetupError("Python import closure contains a non-path")
        source = Path(item).resolve()
        if not source.is_file() or not source.is_relative_to(stdlib):
            raise JailSetupError(f"import closure escaped Python stdlib: {source}")
        files.add(source)
    return stdlib, files


def _copy_exact(
    source: Path, destination: Path, files: dict[str, str], root: Path, *, executable: bool = False
) -> None:
    if not source.is_file() or destination.exists():
        raise JailSetupError(f"missing or duplicate jail material: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    source_hash = _sha256(source)
    if _sha256(destination) != source_hash:
        raise JailSetupError(f"jail material changed during copy: {source}")
    os.chmod(destination, 0o555 if executable else 0o444)
    files[str(destination.relative_to(root))] = source_hash


def _assert_traversable_parent(root: Path) -> None:
    if not root.is_absolute() or root.is_symlink():
        raise JailSetupError("jail root must be an absolute, non-symlink path")
    for ancestor in root.parents:
        metadata = ancestor.stat()
        if (
            ancestor.is_symlink()
            or not stat.S_ISDIR(metadata.st_mode)
            or not metadata.st_mode & stat.S_IXOTH
        ):
            raise JailSetupError(f"host UID 65534 cannot traverse {ancestor}")


@dataclass(frozen=True, slots=True)
class StagedPolicyJail:
    """Immutable host-side handle for a single-use jail material snapshot."""

    root: Path
    policy_sha256: str
    manifest_sha256: str

    def verify(self) -> None:
        manifest_path = self.root / "MANIFEST.json"
        if manifest_path.is_symlink() or _sha256(manifest_path) != self.manifest_sha256:
            raise JailSetupError("jail manifest changed")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("policy_sha256") != self.policy_sha256:
            raise JailSetupError("jail policy identity changed")
        files = payload.get("files")
        if not isinstance(files, dict):
            raise JailSetupError("jail manifest files are missing")
        entries = tuple(self.root.rglob("*"))
        actual_files: set[str] = set()
        for entry in entries:
            if entry.is_symlink():
                raise JailSetupError(f"jail contains a symlink: {entry}")
            if entry.is_file():
                actual_files.add(str(entry.relative_to(self.root)))
            elif not entry.is_dir():
                raise JailSetupError(f"jail contains a special file: {entry}")
        if actual_files != set(files) | {"MANIFEST.json"}:
            raise JailSetupError("jail contains unmanifested or missing files")
        for relative, expected in files.items():
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise JailSetupError("invalid jail manifest entry")
            path = self.root / relative
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_uid != 0
                or path.stat().st_mode & 0o222
                or _sha256(path) != expected
            ):
                raise JailSetupError(f"jail material changed: {relative}")
        directories = (self.root, *(path for path in entries if path.is_dir()))
        for directory in directories:
            if (
                directory.is_symlink()
                or directory.stat().st_uid != 0
                or directory.stat().st_mode & 0o222
            ):
                raise JailSetupError(f"writable jail directory: {directory}")


class JailedPolicyProcess:
    """Own the whole worker process group through normal and failed exits."""

    def __init__(self, process: subprocess.Popen[bytes], artifact: StagedPolicyJail) -> None:
        self.process = process
        self.artifact = artifact
        self._closed = False

    def __enter__(self) -> JailedPolicyProcess:
        return self

    def __exit__(self, _type: object, exc: BaseException | None, _tb: object) -> None:
        try:
            self.close()
        except Exception as cleanup_error:
            if exc is None:
                raise
            exc.add_note(f"policy worker cleanup also failed: {cleanup_error}")

    def wait(self, timeout: float) -> int:
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            error = JailSetupError("policy worker wall deadline exceeded")
            try:
                self.close()
            except Exception as cleanup_error:
                error.add_note(f"cleanup also failed: {cleanup_error}")
            raise error from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self.process
        try:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    if process.poll() is None:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            else:
                process.wait(timeout=5)
        finally:
            if process.stderr is not None:
                process.stderr.close()
        self.artifact.verify()


def stage_policy_jail(
    root: Path,
    policy_bytes: bytes,
    *,
    python_executable: Path,
    expected_python_sha256: str,
) -> StagedPolicyJail:
    """Audit and stage exact bytes; refuse symlinks, unpinned runtime, or weak ownership.

    The caller must supply the interpreter's predeclared SHA256. The emitted
    manifest pins every copied runtime file and should be frozen with the run.
    Only one ``policy/seed.py`` file is supported by this first slice.
    """

    if os.geteuid() != 0:
        raise JailSetupError("staging needs host root to own immutable jail files")
    root = root.absolute()
    _assert_traversable_parent(root)
    if root.exists() or len(expected_python_sha256) != 64:
        raise JailSetupError("jail root exists or interpreter pin is missing")
    python = python_executable.resolve()
    if _sha256(python) != expected_python_sha256:
        raise JailSetupError("interpreter SHA256 differs from the declared pin")
    try:
        text = policy_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise JailSetupError("policy bytes are not UTF-8") from exc
    PolicyAuditor().audit_source(text, filename="policy/seed.py").require_safe()
    scan_policy(text)
    stdlib, modules = _stdlib_import_closure(python)
    child_hash = _sha256(_CHILD_SOURCE)
    root.mkdir(mode=0o700)
    files: dict[str, str] = {}
    _copy_exact(python, root / "bin/python3.12", files, root, executable=True)
    _copy_exact(_CHILD_SOURCE, root / "child.py", files, root)
    policy_file = root / "policy/seed.py"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_bytes(policy_bytes)
    os.chmod(policy_file, 0o444)
    policy_sha = hashlib.sha256(policy_bytes).hexdigest()
    files["policy/seed.py"] = policy_sha
    libraries: set[Path] = {python, _SECCOMP}
    for module in modules:
        relative = module.relative_to(stdlib)
        _copy_exact(module, root / "lib/python3.12" / relative, files, root)
        if module.suffix == ".so":
            libraries.add(module)
    dependencies = {_SECCOMP}
    for library in libraries:
        dependencies.update(_ldd_dependencies(library))
    for library in sorted(dependencies):
        destination = root / "lib" / "x86_64-linux-gnu" / library.name
        if library.name.startswith("ld-linux"):
            destination = root / "lib64" / library.name
        if destination.exists():
            if _sha256(destination) != _sha256(library):
                raise JailSetupError(f"conflicting runtime library: {library.name}")
            continue
        _copy_exact(
            library, destination, files, root, executable=library.name.startswith("ld-linux")
        )
    # Executables used before the jail starts are also bound into the manifest.
    launchers = {str(path): _sha256(path) for path in (_SET_PRIV, _UNSHARE)}
    manifest: dict[str, object] = {
        "schema_version": 1,
        "policy_sha256": policy_sha,
        "python_sha256": expected_python_sha256,
        "child_sha256": child_hash,
        "files": dict(sorted(files.items())),
        "pre_jail_launchers": launchers,
    }
    manifest_path = root / "MANIFEST.json"
    manifest_path.write_bytes(_material_json(manifest) + b"\n")
    os.chmod(manifest_path, 0o444)
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        os.chmod(directory, 0o555)  # nosec B103 - low UID needs read/search, never write
    os.chmod(root, 0o555)  # nosec B103 - low UID needs read/search, never write
    artifact = StagedPolicyJail(root, policy_sha, _sha256(manifest_path))
    artifact.verify()
    return artifact


def launch_policy_jail(
    artifact: StagedPolicyJail, *, read_fd: int, write_fd: int
) -> JailedPolicyProcess:
    """Launch only the trusted child with preopened broker FDs; never use preexec_fn."""

    artifact.verify()
    manifest = json.loads((artifact.root / "MANIFEST.json").read_text(encoding="utf-8"))
    launchers = cast(dict[str, str], manifest["pre_jail_launchers"])
    if any(_sha256(Path(path)) != digest for path, digest in launchers.items()):
        raise JailSetupError("pre-jail launcher binary changed")
    if read_fd == write_fd or min(read_fd, write_fd) < 3:
        raise JailSetupError("broker pipes must be distinct non-stdio descriptors")
    parent_netns = os.readlink("/proc/self/ns/net")
    command = [
        str(_SET_PRIV),
        "--reuid",
        "65534",
        "--regid",
        "65534",
        "--clear-groups",
        "--no-new-privs",
        str(_UNSHARE),
        "--user",
        "--map-root-user",
        "--net",
        str(artifact.root / "lib64/ld-linux-x86-64.so.2"),
        "--library-path",
        str(artifact.root / "lib/x86_64-linux-gnu"),
        str(artifact.root / "bin/python3.12"),
        "-S",
        "-P",
        str(artifact.root / "child.py"),
        str(artifact.root),
        parent_netns,
        str(read_fd),
        str(write_fd),
        artifact.policy_sha256,
    ]
    process = subprocess.Popen(  # nosec B603 - every argv element is trusted/validated
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={"PYTHONHOME": str(artifact.root)},
        cwd="/",
        close_fds=True,
        pass_fds=(read_fd, write_fd),
        start_new_session=True,
    )
    return JailedPolicyProcess(process, artifact)
