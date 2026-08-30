"""Clean-tree and file-stability attestations for offline qualification runs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import shutil
import subprocess  # nosec B404
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Hash one file without loading it wholly into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _head_blob_sha256(git: str, root: Path, revision: str, path: Path) -> str | None:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("producer files must be relative paths within the repository")
    object_name = f"{revision}:{path.as_posix()}"
    kind = subprocess.run(  # nosec B603
        [git, "cat-file", "-t", object_name],
        cwd=root,
        check=False,
        capture_output=True,
        timeout=10,
    )
    blob = subprocess.run(  # nosec B603
        [git, "cat-file", "blob", object_name],
        cwd=root,
        check=False,
        capture_output=True,
        timeout=10,
    )
    if kind.returncode != 0 or kind.stdout.strip() != b"blob" or blob.returncode != 0:
        return None
    return hashlib.sha256(blob.stdout).hexdigest()


def producer_attestation(
    root: Path,
    producer_files: tuple[Path, ...],
    *,
    package_names: tuple[str, ...] = (),
) -> dict[str, object]:
    """Observe Git, producer bytes, Python, and requested package versions."""

    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for qualification producer attestation")
    revision = subprocess.run(  # nosec B603
        [git, "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    status = subprocess.run(  # nosec B603
        [git, "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout
    top_level = subprocess.run(  # nosec B603
        [git, "rev-parse", "--show-toplevel"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    producer_file_sha256 = {str(path): file_sha256(root / path) for path in producer_files}
    producer_head_blob_sha256 = {
        str(path): _head_blob_sha256(git, root, revision, path) for path in producer_files
    }
    return {
        "git_revision": revision,
        "worktree_dirty": bool(status),
        "repository_root_matches": Path(top_level).resolve() == root.resolve(),
        "producer_files_match_head": producer_file_sha256 == producer_head_blob_sha256,
        "python_version": platform.python_version(),
        "package_versions": {
            name: importlib.metadata.version(name) for name in sorted(set(package_names))
        },
        "producer_file_sha256": producer_file_sha256,
        "producer_head_blob_sha256": producer_head_blob_sha256,
    }


def require_clean_producer(attestation: dict[str, object]) -> None:
    """Reject qualification from an uncommitted producer tree."""

    if attestation.get("worktree_dirty") is not False:
        raise RuntimeError("qualification requires a clean producer worktree")
    if attestation.get("repository_root_matches") is not True:
        raise RuntimeError("qualification root must equal the Git repository root")
    if attestation.get("producer_files_match_head") is not True:
        raise RuntimeError("qualification producer bytes must match HEAD")


def require_stable_attestation(
    before: dict[str, object],
    after: dict[str, object],
) -> None:
    """Reject producer changes during a qualification run."""

    if before != after:
        raise RuntimeError("qualification producer changed during execution")


def require_unchanged_file(path: Path, expected_sha256: str, *, label: str) -> None:
    """Reject a consumed file whose bytes drift during execution."""

    observed = file_sha256(path)
    if observed != expected_sha256:
        raise RuntimeError(
            f"{label} changed during execution: expected {expected_sha256}, observed {observed}"
        )
