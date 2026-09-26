"""Fail-closed admission for a future brokered researcher update-rate pretest.

This module handles researcher output only as bytes. It never imports a candidate,
constructs an in-process PolicyHook, or contacts a model. The live researcher
adapter and candidate exercise remain closed until the host and provider gates
described in the R13 design are met.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rsicontext.lifecycle.brokered_policy import BrokeredPolicyHook
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.policy import PolicyBoundaryError, scan_policy
from rsicontext.lifecycle.runner import StageView
from rsicontext.lifecycle.spec import DescriptionAxes
from rsicontext.lifecycle.tools import ToolBudget
from rsicontext.security.audit import PolicyAuditor
from rsicontext.security.policy_jail import (
    StagedPolicyJail,
    launch_policy_jail,
    stage_policy_jail,
)

_TRUSTED_PROBE = b"def on_turn(turn):\n    return {'pack_text': '', 'actions': ()}\n"
_HEX = frozenset("0123456789abcdef")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")


@dataclass(frozen=True, slots=True)
class AdmissionPlan:
    """Immutable experiment inputs registered before any researcher draw."""

    planned_draws: int
    baseline_sha256: str
    source_sha256: str
    feedback_sha256: str
    researcher_model: str
    worker_model: str
    max_candidate_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if type(self.planned_draws) is not int or not 1 <= self.planned_draws <= 16:
            raise ValueError("planned_draws must be between 1 and 16")
        if (
            type(self.max_candidate_bytes) is not int
            or not 1 <= self.max_candidate_bytes <= 1_000_000
        ):
            raise ValueError("max_candidate_bytes must be between 1 and 1000000")
        for name in ("baseline_sha256", "source_sha256", "feedback_sha256"):
            _require_sha256(getattr(self, name), name)
        if not self.researcher_model.strip() or not self.worker_model.strip():
            raise ValueError("researcher and worker models must be named")

    def to_dict(self) -> dict[str, object]:
        return {
            "planned_draws": self.planned_draws,
            "baseline_sha256": self.baseline_sha256,
            "source_sha256": self.source_sha256,
            "feedback_sha256": self.feedback_sha256,
            "researcher_model": self.researcher_model,
            "worker_model": self.worker_model,
            "max_candidate_bytes": self.max_candidate_bytes,
        }


@dataclass(frozen=True, slots=True)
class ResearcherDraw:
    """Untrusted adapter result; absent provider usage stays absent."""

    policy_bytes: bytes | None = None
    model_echo: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: Literal["provider", "estimated", "unknown"] = "unknown"
    error_type: str | None = None


def preflight_runtime(*, python_executable: Path, expected_python_sha256: str) -> dict[str, str]:
    """Prove immutable material and a real jailed broker turn before API dispatch.

    The interpreter hash must be declared by the caller, never computed here as
    a self-certifying pin. Failure leaves no usable admission result.
    """

    _require_sha256(expected_python_sha256, "expected_python_sha256")
    # The jail verifier explicitly permits this sticky trusted ancestor.
    parent = Path(tempfile.mkdtemp(prefix="rsi-pretest-probe-", dir="/tmp"))  # nosec B108
    # The jailed UID 65534 must traverse this newly created parent.
    os.chmod(parent, 0o755)  # nosec B103
    child_read = host_write = host_read = child_write = -1
    hook: BrokeredPolicyHook | None = None
    worker = None
    try:
        artifact = stage_policy_jail(
            parent / "jail",
            _TRUSTED_PROBE,
            python_executable=python_executable,
            expected_python_sha256=expected_python_sha256,
        )
        child_read, host_write = os.pipe()
        host_read, child_write = os.pipe()
        worker = launch_policy_jail(artifact, read_fd=child_read, write_fd=child_write)
        os.close(child_read)
        os.close(child_write)
        child_read = child_write = -1
        hook = BrokeredPolicyHook(
            read_fd=host_read,
            write_fd=host_write,
            state={},
            tool_budget=ToolBudget(max_calls=0),
            env=ProjectState(),
            timeout_seconds=5,
            owned_worker=worker,
        )
        host_read = host_write = -1
        view = StageView(
            stage_id="trusted-runtime-probe",
            kind="survey",
            prompt_text="Run the trusted jail probe.",
            documents=(),
            axes=DescriptionAxes(1, 1, 0, "strong", 0),
            remaining_budget=1,
        )
        response = hook.on_stage(view)
        if response.pack_text or response.actions or hook.policy_errors or hook.model_calls:
            raise RuntimeError("trusted jail probe returned an unexpected decision")
        manifest = (artifact.root / "MANIFEST.json").read_bytes()
        return {
            "probe_policy_sha256": artifact.policy_sha256,
            "manifest_sha256": _sha256(manifest),
            "python_sha256": expected_python_sha256,
        }
    finally:
        try:
            if hook is not None:
                hook.close()
                worker = None
        finally:
            try:
                for fd in (child_read, child_write, host_read, host_write):
                    if fd >= 0:
                        with suppress(OSError):
                            os.close(fd)
                if worker is not None:
                    worker.close()
            finally:
                shutil.rmtree(parent)


def _persist(result_path: Path, result: dict[str, object]) -> None:
    temporary = result_path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, ensure_ascii=False)
        stream.write("\n")
    temporary.replace(result_path)


def _audit_snapshot(root: Path, policy_bytes: bytes, cap: int) -> dict[str, object]:
    """Write exact bytes once, then audit the sole policy/seed.py snapshot."""

    if len(policy_bytes) > cap:
        return {"status": "candidate-too-large", "bytes": len(policy_bytes)}
    root.mkdir(mode=0o700, exist_ok=False)
    candidate_root = root / "policy"
    candidate_root.mkdir(mode=0o700, exist_ok=False)
    candidate_path = candidate_root / "seed.py"
    fd = os.open(candidate_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(policy_bytes)
    disk_bytes = candidate_path.read_bytes()
    if disk_bytes != policy_bytes:
        return {"status": "snapshot-mismatch", "bytes": len(policy_bytes)}
    digest = _sha256(disk_bytes)
    try:
        text = disk_bytes.decode("utf-8")
    except UnicodeError:
        return {"status": "invalid-utf8", "bytes": len(disk_bytes), "policy_sha256": digest}
    report = PolicyAuditor().audit_tree(root)
    if report.files != ("policy/seed.py",) or not report.safe:
        return {
            "status": "audit-rejected",
            "bytes": len(disk_bytes),
            "policy_sha256": digest,
            "violations": [item.code for item in report.violations],
        }
    try:
        scan_policy(text)
    except PolicyBoundaryError as exc:
        return {
            "status": "policy-contract-rejected",
            "bytes": len(disk_bytes),
            "policy_sha256": digest,
            "error_type": type(exc).__name__,
        }
    return {"status": "audited", "bytes": len(disk_bytes), "policy_sha256": digest}


def stage_audited_snapshot(
    candidate_root: Path,
    *,
    expected_policy_sha256: str,
    jail_root: Path,
    python_executable: Path,
    expected_python_sha256: str,
) -> StagedPolicyJail:
    """Stage the same audited bytes in a trusted jail root without host import.

    This helper does not launch or exercise the candidate. The caller must own
    and clean ``jail_root`` and must supply the predeclared interpreter pin.
    """

    _require_sha256(expected_policy_sha256, "expected_policy_sha256")
    _require_sha256(expected_python_sha256, "expected_python_sha256")
    report = PolicyAuditor().audit_tree(candidate_root)
    if report.files != ("policy/seed.py",):
        raise ValueError("candidate snapshot must contain only policy/seed.py")
    report.require_safe()
    policy_bytes = (candidate_root / "policy/seed.py").read_bytes()
    if _sha256(policy_bytes) != expected_policy_sha256:
        raise ValueError("candidate snapshot differs from declared SHA256")
    artifact = stage_policy_jail(
        jail_root,
        policy_bytes,
        python_executable=python_executable,
        expected_python_sha256=expected_python_sha256,
    )
    if artifact.policy_sha256 != expected_policy_sha256:
        raise RuntimeError("staged jail policy differs from candidate snapshot")
    return artifact


def _provider_complete(draw: ResearcherDraw, expected_model: str) -> bool:
    return (
        draw.error_type is None
        and draw.finish_reason == "stop"
        and draw.model_echo == expected_model
        and draw.usage_source == "provider"
        and type(draw.input_tokens) is int
        and draw.input_tokens >= 0
        and type(draw.output_tokens) is int
        and draw.output_tokens >= 0
        and type(draw.total_tokens) is int
        and draw.total_tokens == draw.input_tokens + draw.output_tokens
    )


def run_offline_admission(
    plan: AdmissionPlan,
    *,
    baseline_policy_bytes: bytes,
    source_bytes: bytes,
    visible_feedback_bytes: bytes,
    output: Path,
    preflight: Callable[[], dict[str, str]],
    draw: Callable[[int], ResearcherDraw],
) -> dict[str, object]:
    """Count every registered draw; stop before draw on failed host preflight.

    The injected draw is for offline fixtures only. No candidate exercise or
    live researcher provider is wired, so audited-and-exercised remains zero.
    """

    for name, material, declared_sha256 in (
        ("baseline_policy_bytes", baseline_policy_bytes, plan.baseline_sha256),
        ("source_bytes", source_bytes, plan.source_sha256),
        ("visible_feedback_bytes", visible_feedback_bytes, plan.feedback_sha256),
    ):
        if not isinstance(material, bytes):
            raise TypeError(f"{name} must be exact bytes")
        if _sha256(material) != declared_sha256:
            raise ValueError(f"{name} differs from the declared SHA256")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"admission output exists: {output}")
    parent = output.parent.lstat()
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.geteuid()
        or parent.st_mode & 0o077
    ):
        raise PermissionError("admission output parent must be owned and private (0700)")
    host = preflight()
    if not isinstance(host, dict):
        raise RuntimeError("trusted runtime preflight returned no jail identity")
    host_identity: dict[str, str] = {}
    for field in ("manifest_sha256", "probe_policy_sha256", "python_sha256"):
        value = host.get(field)
        if not isinstance(value, str):
            raise RuntimeError(f"trusted runtime preflight omitted {field}")
        _require_sha256(value, field)
        host_identity[field] = value
    output.mkdir(mode=0o700, exist_ok=False)
    draws: list[dict[str, object]] = [
        {"draw_id": index, "status": "pending", "usage_source": "unknown"}
        for index in range(plan.planned_draws)
    ]
    result: dict[str, object] = {
        "schema_version": 1,
        "live_ready": False,
        "evidence_kind": "offline-admission-only",
        "plan": plan.to_dict(),
        "host_preflight": host_identity,
        "draws": draws,
        "valid_submitted": {"numerator": 0, "denominator": plan.planned_draws},
        "audited_and_exercised": {"numerator": 0, "denominator": plan.planned_draws},
    }
    _persist(output / "result.json", result)
    for index in range(plan.planned_draws):
        try:
            candidate = draw(index)
            if not isinstance(candidate, ResearcherDraw):
                raise TypeError("draw adapter must return ResearcherDraw")
        except Exception as exc:
            draws[index] = {
                "draw_id": index,
                "status": "draw-failed",
                "error_type": type(exc).__name__,
                "usage_source": "unknown",
            }
            _persist(output / "result.json", result)
            continue
        record: dict[str, object] = {
            "draw_id": index,
            "status": "missing-candidate",
            "model_echo": candidate.model_echo,
            "finish_reason": candidate.finish_reason,
            "input_tokens": candidate.input_tokens,
            "output_tokens": candidate.output_tokens,
            "total_tokens": candidate.total_tokens,
            "usage_source": candidate.usage_source,
            "error_type": candidate.error_type,
        }
        if candidate.policy_bytes is not None:
            if not isinstance(candidate.policy_bytes, bytes):
                record["status"] = "invalid-candidate-type"
            else:
                snapshot = _audit_snapshot(
                    output / f"draw-{index:02d}", candidate.policy_bytes, plan.max_candidate_bytes
                )
                record.update(snapshot)
                if snapshot["status"] == "audited":
                    if candidate.policy_bytes == baseline_policy_bytes:
                        record["status"] = "unchanged"
                    elif not _provider_complete(candidate, plan.researcher_model):
                        record["status"] = "researcher-response-unverified"
                    else:
                        record["status"] = "valid-submitted-awaiting-jailed-exercise"
                        rate = result["valid_submitted"]
                        if not isinstance(rate, dict):
                            raise RuntimeError("registered denominator was corrupted")
                        rate["numerator"] = int(rate["numerator"]) + 1
        draws[index] = record
        _persist(output / "result.json", result)
    return result
