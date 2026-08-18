"""Generate shell-safe acquisition plans; never execute them."""

from __future__ import annotations

import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

from rsicontext.registry.schema import RegistryEntry, RegistryError


@dataclass(frozen=True)
class PlannedArtifact:
    """Commands and warnings for one external artifact."""

    id: str
    destination: str | None
    acquire_command: str | None
    verify_commands: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DownloadPlan:
    """A serializable, non-executing acquisition plan."""

    dry_run: bool
    artifacts: tuple[PlannedArtifact, ...]
    known_size_bytes: int
    unknown_size_count: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _destination(root: Path, entry: RegistryEntry) -> Path:
    category = {"model": "models", "dataset": "data", "baseline": "external"}[entry.kind]
    return root / category / entry.id


def _warnings(entry: RegistryEntry) -> tuple[str, ...]:
    warnings: list[str] = []
    if entry.access == "gated":
        warnings.append("Gated artifact: accept its license and authenticate with Hugging Face.")
    elif entry.access == "manual":
        warnings.append(
            "Manual access: follow the cited source; no automated acquisition is defined."
        )
    if entry.revision in {None, "main", "master"} and entry.integration != "cite-only":
        warnings.append(
            "Source is not pinned to an immutable revision; resolve and record one first."
        )
    if entry.checksum.algorithm == "unavailable":
        warnings.append("No upstream checksum is available; provenance cannot be fully verified.")
    elif not entry.checksum.verified:
        warnings.append("Recorded digest/revision has not yet been independently verified.")
    return tuple(warnings)


def _plan_entry(entry: RegistryEntry, root: Path) -> PlannedArtifact:
    warnings = _warnings(entry)
    if entry.integration == "cite-only":
        return PlannedArtifact(entry.id, None, None, (), warnings)
    if entry.revision is None:
        raise RegistryError(f"downloadable entry {entry.id!r} must declare a revision")
    destination = _destination(root, entry)
    verify: tuple[str, ...]
    if entry.source_type == "huggingface":
        repo_id = entry.url.removeprefix("https://huggingface.co/").rstrip("/")
        if entry.kind == "dataset":
            repo_id = repo_id.removeprefix("datasets/")
        repo_type = " --repo-type dataset" if entry.kind == "dataset" else ""
        acquire = (
            f"hf download {_quote(repo_id)}{repo_type} --revision {_quote(entry.revision)} "
            f"--local-dir {_quote(destination)}"
        )
        verify = (
            "uvx --with click==8.3.1 --from huggingface-hub==1.3.3 "
            f"hf cache verify {_quote(repo_id)}{repo_type} "
            f"--revision {_quote(entry.revision)} "
            f"--local-dir {_quote(destination)} --fail-on-missing-files",
        )
    elif entry.source_type == "git":
        acquire = (
            f"git clone --filter=blob:none {_quote(entry.url)} {_quote(destination)} "
            f"&& git -C {_quote(destination)} checkout --detach {_quote(entry.revision)}"
        )
        verify = (f"git -C {_quote(destination)} rev-parse --verify HEAD",)
        if entry.checksum.algorithm == "git-revision" and entry.checksum.value is not None:
            verify += (
                f'test "$(git -C {_quote(destination)} rev-parse HEAD)" = '
                f"{_quote(entry.checksum.value)}",
            )
    else:
        raise RegistryError(f"unsupported downloadable source for {entry.id!r}")
    return PlannedArtifact(entry.id, str(destination), acquire, verify, warnings)


def build_download_plan(
    entries: tuple[RegistryEntry, ...], destination_root: str | Path
) -> DownloadPlan:
    """Create commands for review; this function performs no network or filesystem writes."""
    root = Path(destination_root)
    artifacts = tuple(_plan_entry(entry, root) for entry in entries)
    sizes = [entry.size_bytes for entry in entries if entry.integration != "cite-only"]
    return DownloadPlan(
        dry_run=True,
        artifacts=artifacts,
        known_size_bytes=sum(size for size in sizes if size is not None),
        unknown_size_count=sum(size is None for size in sizes),
    )
