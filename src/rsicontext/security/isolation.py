"""Observed Linux isolation evidence for formal evaluator eligibility."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
from dataclasses import asdict, dataclass
from pathlib import Path


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _covers(mount: str, required: str) -> bool:
    canonical_mount = posixpath.normpath(mount)
    canonical_required = posixpath.normpath(required)
    return canonical_required == canonical_mount or canonical_required.startswith(
        canonical_mount.rstrip("/") + "/"
    )


@dataclass(frozen=True, slots=True)
class IsolationAttestation:
    """Evaluator/researcher boundary facts, which may be incomplete or declared."""

    evidence_source: str
    observed_at: str
    evaluator_pid: int
    researcher_pid: int
    evaluator_container_namespace: str | None
    researcher_container_namespace: str | None
    evaluator_cgroup: str | None
    researcher_cgroup: str | None
    evaluator_pid_namespace: str | None
    researcher_pid_namespace: str | None
    network_mode: str
    read_only_mounts: tuple[str, ...]
    required_read_only_mounts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_source, str) or not self.evidence_source:
            raise ValueError("isolation evidence source must be non-empty")
        if not isinstance(self.observed_at, str) or not self.observed_at:
            raise ValueError("isolation observation timestamp must be non-empty")
        for field_name, pid in (
            ("evaluator_pid", self.evaluator_pid),
            ("researcher_pid", self.researcher_pid),
        ):
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if not isinstance(self.network_mode, str) or not self.network_mode:
            raise ValueError("isolation network mode must be non-empty")
        for field_name, mounts in (
            ("read_only_mounts", self.read_only_mounts),
            ("required_read_only_mounts", self.required_read_only_mounts),
        ):
            if not isinstance(mounts, tuple):
                raise TypeError(f"{field_name} must be an immutable tuple")
            if any(not isinstance(mount, str) or not mount.startswith("/") for mount in mounts):
                raise ValueError(f"{field_name} must contain absolute paths")
            if len(set(mounts)) != len(mounts):
                raise ValueError(f"{field_name} must not contain duplicates")

    @property
    def formal_failures(self) -> tuple[str, ...]:
        """Return every reason this observation cannot prove formal isolation."""

        failures: list[str] = []
        if self.evidence_source != "observed-linux":
            failures.append("isolation is declaration-only or incompletely observed")
        if self.evaluator_pid == self.researcher_pid:
            failures.append("evaluator and researcher share a process")
        boundaries = (
            (
                "container namespace",
                self.evaluator_container_namespace,
                self.researcher_container_namespace,
            ),
            ("cgroup", self.evaluator_cgroup, self.researcher_cgroup),
            ("PID namespace", self.evaluator_pid_namespace, self.researcher_pid_namespace),
        )
        for name, evaluator_value, researcher_value in boundaries:
            if evaluator_value is None or researcher_value is None:
                failures.append(f"{name} was not observed")
            elif evaluator_value == researcher_value:
                failures.append(f"evaluator and researcher share the {name}")
        if self.network_mode != "none":
            failures.append("evaluator no-network mode was not observed")
        missing_mounts = tuple(
            required
            for required in self.required_read_only_mounts
            if not any(_covers(mount, required) for mount in self.read_only_mounts)
        )
        if not self.required_read_only_mounts:
            failures.append("no required read-only mounts were declared")
        elif missing_mounts:
            failures.append(
                "required read-only mounts were not observed: " + ", ".join(missing_mounts)
            )
        return tuple(failures)

    @property
    def attestation_sha256(self) -> str:
        """Bind every observed isolation field into a stable digest."""

        return _canonical_digest(asdict(self))

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = asdict(self)
        result["attestation_sha256"] = self.attestation_sha256
        result["formal_failures"] = list(self.formal_failures)
        return result


def _read_namespace(proc_root: Path, pid: int, namespace: str) -> str:
    return os.readlink(proc_root / str(pid) / "ns" / namespace)


def _read_cgroup(proc_root: Path, pid: int) -> str:
    lines = (proc_root / str(pid) / "cgroup").read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("empty cgroup observation")
    return "|".join(sorted(lines))


def _read_only_mounts(proc_root: Path, pid: int) -> tuple[str, ...]:
    mounts: set[str] = set()
    lines = (proc_root / str(pid) / "mountinfo").read_text(encoding="utf-8").splitlines()
    for line in lines:
        before, separator, after = line.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        filesystem_fields = after.split()
        if len(fields) < 6 or len(filesystem_fields) < 3:
            continue
        mount_options = set(fields[5].split(","))
        super_options = set(filesystem_fields[2].split(","))
        if "ro" in mount_options or "ro" in super_options:
            mounts.add(fields[4].replace("\\040", " "))
    return tuple(sorted(mounts))


def _network_mode(proc_root: Path, pid: int) -> str:
    lines = (proc_root / str(pid) / "net" / "dev").read_text(encoding="utf-8").splitlines()
    interfaces = {line.partition(":")[0].strip() for line in lines[2:] if line.partition(":")[1]}
    if not interfaces:
        raise ValueError("empty network-interface observation")
    return "none" if interfaces <= {"lo"} else "available"


def observe_linux_isolation(
    *,
    researcher_pid: int,
    required_read_only_mounts: tuple[str, ...],
    evaluator_pid: int | None = None,
    observed_at: str,
    proc_root: str | Path = "/proc",
) -> IsolationAttestation:
    """Observe Linux boundaries; return incomplete evidence instead of guessing."""

    actual_evaluator_pid = os.getpid() if evaluator_pid is None else evaluator_pid
    proc_path = Path(proc_root)
    source = "observed-linux"
    evaluator_container: str | None = None
    researcher_container: str | None = None
    evaluator_cgroup: str | None = None
    researcher_cgroup: str | None = None
    evaluator_pid_namespace: str | None = None
    researcher_pid_namespace: str | None = None
    read_only_mounts: tuple[str, ...] = ()
    network_mode = "unknown"
    try:
        evaluator_container = _read_namespace(proc_path, actual_evaluator_pid, "mnt")
        researcher_container = _read_namespace(proc_path, researcher_pid, "mnt")
        evaluator_cgroup = _read_cgroup(proc_path, actual_evaluator_pid)
        researcher_cgroup = _read_cgroup(proc_path, researcher_pid)
        evaluator_pid_namespace = _read_namespace(proc_path, actual_evaluator_pid, "pid")
        researcher_pid_namespace = _read_namespace(proc_path, researcher_pid, "pid")
        read_only_mounts = _read_only_mounts(proc_path, actual_evaluator_pid)
        network_mode = _network_mode(proc_path, actual_evaluator_pid)
    except (OSError, ValueError):
        source = "incomplete-linux-observation"
    return IsolationAttestation(
        evidence_source=source,
        observed_at=observed_at,
        evaluator_pid=actual_evaluator_pid,
        researcher_pid=researcher_pid,
        evaluator_container_namespace=evaluator_container,
        researcher_container_namespace=researcher_container,
        evaluator_cgroup=evaluator_cgroup,
        researcher_cgroup=researcher_cgroup,
        evaluator_pid_namespace=evaluator_pid_namespace,
        researcher_pid_namespace=researcher_pid_namespace,
        network_mode=network_mode,
        read_only_mounts=read_only_mounts,
        required_read_only_mounts=required_read_only_mounts,
    )
