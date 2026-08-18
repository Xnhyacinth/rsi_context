"""Read-only host checks for external artifact and GPU campaign readiness."""

from __future__ import annotations

import os
import shlex
import shutil

# Read-only nvidia-smi probing below uses a resolved executable and fixed argv.
import subprocess  # nosec B404
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    """One preflight observation."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """Read-only preflight output plus a suggested GPU hold wrapper."""

    read_only: bool
    checks: tuple[CheckResult, ...]
    gpu_hold_command: str

    @property
    def ready(self) -> bool:
        """Whether no required check failed."""
        return all(check.status != "fail" for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        result = asdict(self)
        result["ready"] = self.ready
        return result


def _check_disk(path: Path, required_bytes: int) -> CheckResult:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError as error:
        return CheckResult("disk", "fail", f"Cannot inspect {probe}: {error}")
    status = "pass" if free >= required_bytes else "fail"
    return CheckResult("disk", status, f"{free} bytes free; {required_bytes} bytes required")


def _check_gpu(expected_gpus: int, expected_gpu_name: str | None) -> CheckResult:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return CheckResult("gpu", "fail", "nvidia-smi is not on PATH")
    try:
        process = subprocess.run(  # nosec B603
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return CheckResult("gpu", "fail", f"nvidia-smi failed: {error}")
    if process.returncode != 0:
        return CheckResult("gpu", "fail", process.stderr.strip() or "nvidia-smi failed")
    devices = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    enough_devices = len(devices) >= expected_gpus
    expected_devices = devices[:expected_gpus]
    matching_devices = expected_gpu_name is None or all(
        expected_gpu_name.casefold() in device.casefold() for device in expected_devices
    )
    status = "pass" if enough_devices and matching_devices else "fail"
    expected = f"expected at least {expected_gpus}"
    if expected_gpu_name is not None:
        expected += f" matching {expected_gpu_name!r}"
    return CheckResult(
        "gpu", status, f"{expected}; found {len(devices)} GPU(s): {'; '.join(devices)}"
    )


def _check_hf_auth(required: bool) -> CheckResult:
    token_file = Path.home() / ".cache" / "huggingface" / "token"
    present = bool(os.environ.get("HF_TOKEN")) or token_file.is_file()
    if present:
        return CheckResult("hf_auth", "pass", "HF token source is present (value not read)")
    status = "fail" if required else "warn"
    return CheckResult("hf_auth", status, "No HF_TOKEN or Hugging Face token file detected")


def _check_hold_wrapper(wrapper: Path) -> CheckResult:
    if not wrapper.is_file():
        return CheckResult("gpu_hold", "fail", f"missing wrapper: {wrapper}")
    status = "pass" if os.access(wrapper, os.X_OK) else "warn"
    return CheckResult("gpu_hold", status, f"wrapper exists: {wrapper}")


def run_preflight(
    destination_root: str | Path,
    *,
    required_bytes: int,
    expected_gpus: int = 8,
    expected_gpu_name: str | None = "H200",
    hf_auth_required: bool = False,
    hold_wrapper: str | Path = "/workspace/wynckeliao/ops/gpu/hold.sh",
) -> PreflightReport:
    """Inspect the host without reserving GPUs, authenticating, or creating directories."""
    if required_bytes < 0:
        raise ValueError("required_bytes must be non-negative")
    if expected_gpus < 1:
        raise ValueError("expected_gpus must be positive")
    wrapper = Path(hold_wrapper)
    checks = (
        _check_disk(Path(destination_root), required_bytes),
        _check_gpu(expected_gpus, expected_gpu_name),
        _check_hf_auth(hf_auth_required),
        _check_hold_wrapper(wrapper),
    )
    gpu_ids = ",".join(str(index) for index in range(expected_gpus))
    command = f"bash {shlex.quote(str(wrapper))} wrap {gpu_ids} -- <COMMAND>"
    return PreflightReport(read_only=True, checks=checks, gpu_hold_command=command)
