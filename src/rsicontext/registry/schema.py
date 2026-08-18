"""Strict, dependency-free schema for registered external artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

EntryKind = Literal["model", "dataset", "baseline"]
IntegrationMode = Literal["direct", "adapter", "cite-only"]
SourceType = Literal["huggingface", "git", "citation"]
AccessType = Literal["public", "gated", "manual"]


class RegistryError(ValueError):
    """Raised when a registry manifest is invalid."""


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{key!r} must be a non-empty string")
    return value


@dataclass(frozen=True)
class Checksum:
    """A pinned revision, content digest, or explicit unavailable marker."""

    algorithm: Literal["sha256", "git-revision", "hf-revision", "unavailable"]
    value: str | None
    verified: bool

    @classmethod
    def from_dict(cls, data: object) -> Checksum:
        if not isinstance(data, dict):
            raise RegistryError("checksum must be an object")
        algorithm = data.get("algorithm")
        if algorithm not in {"sha256", "git-revision", "hf-revision", "unavailable"}:
            raise RegistryError(f"unsupported checksum algorithm: {algorithm!r}")
        value = data.get("value")
        if value is not None and not isinstance(value, str):
            raise RegistryError("checksum.value must be a string or null")
        verified = data.get("verified")
        if not isinstance(verified, bool):
            raise RegistryError("checksum.verified must be a boolean")
        if algorithm == "unavailable" and value is not None:
            raise RegistryError("unavailable checksums must have a null value")
        if algorithm != "unavailable" and not value:
            raise RegistryError(f"{algorithm} requires a checksum value")
        return cls(algorithm=algorithm, value=value, verified=verified)


@dataclass(frozen=True)
class RegistryEntry:
    """One model, dataset, or baseline and its acquisition constraints."""

    id: str
    name: str
    kind: EntryKind
    integration: IntegrationMode
    source_type: SourceType
    url: str
    revision: str | None
    license: str
    size_bytes: int | None
    access: AccessType
    checksum: Checksum
    notes: str

    @classmethod
    def from_dict(cls, data: object) -> RegistryEntry:
        if not isinstance(data, dict):
            raise RegistryError("each registry entry must be an object")
        kind = data.get("kind")
        if kind not in {"model", "dataset", "baseline"}:
            raise RegistryError(f"unsupported entry kind: {kind!r}")
        integration = data.get("integration")
        if integration not in {"direct", "adapter", "cite-only"}:
            raise RegistryError(f"unsupported integration mode: {integration!r}")
        source_type = data.get("source_type")
        if source_type not in {"huggingface", "git", "citation"}:
            raise RegistryError(f"unsupported source type: {source_type!r}")
        access = data.get("access")
        if access not in {"public", "gated", "manual"}:
            raise RegistryError(f"unsupported access type: {access!r}")
        revision = data.get("revision")
        if revision is not None and not isinstance(revision, str):
            raise RegistryError("revision must be a string or null")
        size_bytes = data.get("size_bytes")
        if size_bytes is not None and (not isinstance(size_bytes, int) or size_bytes < 0):
            raise RegistryError("size_bytes must be a non-negative integer or null")
        entry = cls(
            id=_require_string(data, "id"),
            name=_require_string(data, "name"),
            kind=kind,
            integration=integration,
            source_type=source_type,
            url=_require_string(data, "url"),
            revision=revision,
            license=_require_string(data, "license"),
            size_bytes=size_bytes,
            access=access,
            checksum=Checksum.from_dict(data.get("checksum")),
            notes=_require_string(data, "notes"),
        )
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", entry.id) is None:
            raise RegistryError(f"unsafe registry id: {entry.id!r}")
        if not entry.url.startswith("https://"):
            raise RegistryError(f"registry URL must use HTTPS: {entry.url!r}")
        if entry.source_type == "huggingface" and not entry.url.startswith(
            "https://huggingface.co/"
        ):
            raise RegistryError(f"invalid Hugging Face URL: {entry.url!r}")
        if entry.revision is not None and (
            entry.revision.startswith("-") or re.search(r"\s", entry.revision)
        ):
            raise RegistryError(f"unsafe revision: {entry.revision!r}")
        if entry.integration == "cite-only" and entry.source_type != "citation":
            raise RegistryError(f"cite-only entry {entry.id!r} must use a citation source")
        if entry.source_type == "citation" and entry.revision is not None:
            raise RegistryError(f"citation entry {entry.id!r} cannot have a revision")
        if entry.checksum.algorithm in {"git-revision", "hf-revision"}:
            if entry.checksum.value != entry.revision:
                raise RegistryError(f"checksum and revision differ for {entry.id!r}")
            if (
                entry.checksum.verified
                and re.fullmatch(r"[0-9a-f]{40}", entry.revision or "") is None
            ):
                raise RegistryError(f"verified revision for {entry.id!r} must be a commit SHA")
        return entry


@dataclass(frozen=True)
class Registry:
    """A versioned set of uniquely named registry entries."""

    schema_version: int
    entries: tuple[RegistryEntry, ...]

    @classmethod
    def from_dict(cls, data: object) -> Registry:
        if not isinstance(data, dict):
            raise RegistryError("registry root must be an object")
        schema_version = data.get("schema_version")
        if schema_version != 1:
            raise RegistryError(f"unsupported schema_version: {schema_version!r}")
        raw_entries = data.get("entries")
        if not isinstance(raw_entries, list) or not raw_entries:
            raise RegistryError("entries must be a non-empty list")
        entries = tuple(RegistryEntry.from_dict(item) for item in raw_entries)
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise RegistryError("registry entry ids must be unique")
        return cls(schema_version=schema_version, entries=entries)

    def select(self, ids: list[str] | None = None) -> tuple[RegistryEntry, ...]:
        """Return all entries, or entries in the exact requested order."""
        if ids is None:
            return self.entries
        by_id = {entry.id: entry for entry in self.entries}
        missing = [entry_id for entry_id in ids if entry_id not in by_id]
        if missing:
            raise RegistryError(f"unknown registry ids: {', '.join(missing)}")
        return tuple(by_id[entry_id] for entry_id in ids)
