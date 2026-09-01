"""Byte-identical open-S seed isolation. Evaluator-owned; policies cannot import this."""

from __future__ import annotations

from pathlib import Path

from rsicontext.experiment.rsi_run import policy_tree_sha256

OPEN_S_TRACK_ID = "open-s-harness-v1"
REQUIRED_SEED_FILES = frozenset(
    {
        "memory.py",
        "policy.py",
        "retrieval.py",
        "seed.py",
        "skills.py",
        "task.py",
    }
)


class OpenSSeedError(ValueError):
    """Raised when an open-S seed tree is not a fixed, isolated Python directory."""


def repository_open_s_seed() -> Path:
    """Return the canonical seed directory committed in this repository."""

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "seeds" / "open_s_v1"
        if (candidate / "seed.py").is_file():
            return candidate
    raise OpenSSeedError("canonical open-S seed directory is missing")


def validate_open_s_seed(root: str | Path, *, exact_layout: bool = False) -> None:
    """Reject non-Python files, missing H0 files, and seed/policy byte drift."""

    seed_root = Path(root)
    if seed_root.is_symlink() or not seed_root.is_dir():
        raise OpenSSeedError("open-S seed root must be a regular directory")
    files = _python_relative_paths(seed_root)
    missing = sorted(REQUIRED_SEED_FILES - files)
    if missing:
        raise OpenSSeedError(f"open-S seed is missing required files: {missing}")
    if exact_layout and files != REQUIRED_SEED_FILES:
        extra = sorted(files - REQUIRED_SEED_FILES)
        raise OpenSSeedError(f"canonical open-S seed has unexpected Python files: {extra}")
    seed_bytes = (seed_root / "seed.py").read_bytes()
    policy_bytes = (seed_root / "policy.py").read_bytes()
    if seed_bytes != policy_bytes:
        raise OpenSSeedError("H0 seed.py and policy.py must be byte-identical")


def seed_tree_digest(root: str | Path) -> str:
    """Hash the Python tree after validating the open-S seed contract."""

    seed_root = Path(root)
    validate_open_s_seed(seed_root)
    return policy_tree_sha256(seed_root)


def materialize_isolated_seed(source: str | Path, destination: str | Path) -> str:
    """Copy a seed into a new workspace/policy directory and re-check the digest."""

    source_root = Path(source)
    destination_root = Path(destination)
    if destination_root.exists():
        raise OpenSSeedError("isolated destination must not exist")
    digest = seed_tree_digest(source_root)
    policy_root = destination_root / "policy"
    policy_root.mkdir(parents=True)
    _copy_python_tree(source_root, policy_root)
    copied = policy_tree_sha256(policy_root)
    if copied != digest:
        raise OpenSSeedError("isolated seed digest does not match the source seed")
    return digest


def _python_relative_paths(root: Path) -> set[str]:
    files: set[str] = set()
    for entry in sorted(root.rglob("*")):
        relative = entry.relative_to(root).as_posix()
        if entry.is_symlink():
            raise OpenSSeedError(f"open-S seed contains a symlink: {relative}")
        if entry.is_dir():
            continue
        if not entry.is_file() or entry.suffix != ".py":
            raise OpenSSeedError(
                f"open-S seed may contain only Python files: {relative}"
            )
        files.add(relative)
    if not files:
        raise OpenSSeedError("open-S seed must contain at least one Python file")
    return files


def _copy_python_tree(source: Path, destination: Path) -> None:
    for relative in sorted(_python_relative_paths(source)):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / relative).read_bytes())
