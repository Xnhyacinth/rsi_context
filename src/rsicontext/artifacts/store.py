"""Content-addressed storage for immutable, replayable research artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

_DIGEST_LENGTH: Final = 64
_SCHEMA_VERSION: Final = 1


class ArtifactError(ValueError):
    """Base error for artifact validation and persistence failures."""


class ArtifactNotFoundError(ArtifactError):
    """Raised when an artifact identifier is not present in the store."""


class ArtifactIntegrityError(ArtifactError):
    """Raised when stored bytes do not match their immutable record."""


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """Immutable metadata used to address an artifact."""

    artifact_id: str
    content_sha256: str
    kind: str
    parents: tuple[str, ...]
    metadata: Mapping[str, str]
    size_bytes: int


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArtifactError("artifact metadata must be canonical JSON") from exc


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_digest(value: str, *, field: str) -> None:
    if len(value) != _DIGEST_LENGTH or any(char not in "0123456789abcdef" for char in value):
        raise ArtifactError(f"{field} must be a lowercase SHA-256 digest")


def _validate_kind(kind: str) -> None:
    if not kind or len(kind) > 64:
        raise ArtifactError("kind must contain between 1 and 64 characters")
    if any(not (char.isalnum() or char in "-_.") for char in kind):
        raise ArtifactError("kind contains unsupported characters")


def _normalize_bundle_path(raw_path: str) -> str:
    path = PurePosixPath(raw_path)
    if not raw_path or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactError(f"unsafe artifact path: {raw_path!r}")
    normalized = path.as_posix()
    if normalized.startswith("/"):
        raise ArtifactError(f"unsafe artifact path: {raw_path!r}")
    return normalized


class ArtifactStore:
    """Store immutable content-addressed artifacts under a local root.

    The artifact identifier hashes the content digest together with its kind,
    lineage, and metadata. Writes are staged in the destination filesystem and
    atomically renamed into place, so readers never observe partial artifacts.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.objects = self.root / "objects" / "sha256"
        self.objects.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        payload: bytes,
        *,
        kind: str,
        parents: tuple[str, ...] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> ArtifactRecord:
        """Persist bytes and return their deterministic immutable record."""

        _validate_kind(kind)
        parent_ids = tuple(parents)
        if len(parent_ids) != len(set(parent_ids)):
            raise ArtifactError("artifact parents must be unique")
        for parent in parent_ids:
            _validate_digest(parent, field="parent artifact id")
            if not self.contains(parent):
                raise ArtifactNotFoundError(f"parent artifact does not exist: {parent}")

        metadata_dict = dict(metadata or {})
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in metadata_dict.items()
        ):
            raise ArtifactError("artifact metadata must map strings to strings")

        content_sha256 = _sha256(payload)
        address = {
            "content_sha256": content_sha256,
            "kind": kind,
            "metadata": metadata_dict,
            "parents": list(parent_ids),
            "schema_version": _SCHEMA_VERSION,
            "size_bytes": len(payload),
        }
        artifact_id = _sha256(_canonical_json(address))
        record = ArtifactRecord(
            artifact_id=artifact_id,
            content_sha256=content_sha256,
            kind=kind,
            parents=parent_ids,
            metadata=MappingProxyType(metadata_dict),
            size_bytes=len(payload),
        )
        self._persist(record, payload)
        return record

    def put_text(
        self,
        text: str,
        *,
        kind: str,
        parents: tuple[str, ...] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> ArtifactRecord:
        """Persist UTF-8 text."""

        return self.put_bytes(text.encode("utf-8"), kind=kind, parents=parents, metadata=metadata)

    def put_files(
        self,
        files: Mapping[str, bytes | str],
        *,
        kind: str = "policy",
        parents: tuple[str, ...] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> ArtifactRecord:
        """Persist a deterministic multi-file bundle.

        Bundle paths are POSIX-relative and cannot contain traversal segments.
        The canonical JSON representation avoids archive timestamps and other
        host-dependent bytes.
        """

        normalized: dict[str, bytes] = {}
        for raw_path, content in files.items():
            path = _normalize_bundle_path(raw_path)
            if path in normalized:
                raise ArtifactError(f"duplicate normalized artifact path: {path}")
            normalized[path] = content.encode("utf-8") if isinstance(content, str) else content
        if not normalized:
            raise ArtifactError("artifact file bundle cannot be empty")

        entries = [
            {
                "content_base64": base64.b64encode(normalized[path]).decode("ascii"),
                "path": path,
                "sha256": _sha256(normalized[path]),
            }
            for path in sorted(normalized)
        ]
        return self.put_bytes(
            _canonical_json({"files": entries, "format": "rsicontext-file-bundle-v1"}),
            kind=kind,
            parents=parents,
            metadata=metadata,
        )

    def read_bytes(self, artifact_id: str) -> bytes:
        """Read and integrity-check an artifact payload."""

        record = self.get_record(artifact_id)
        content_path = self._artifact_path(artifact_id) / "content"
        try:
            payload = content_path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError(f"artifact content is missing: {artifact_id}") from exc
        if len(payload) != record.size_bytes or _sha256(payload) != record.content_sha256:
            raise ArtifactIntegrityError(f"artifact content failed integrity check: {artifact_id}")
        return payload

    def read_text(self, artifact_id: str) -> str:
        """Read an artifact as UTF-8 text."""

        try:
            return self.read_bytes(artifact_id).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactIntegrityError("artifact is not valid UTF-8 text") from exc

    def read_files(self, artifact_id: str) -> dict[str, bytes]:
        """Decode a deterministic file bundle and verify every member."""

        payload = self.read_bytes(artifact_id)
        try:
            decoded: object = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ArtifactIntegrityError("artifact is not a valid file bundle") from exc
        if not isinstance(decoded, dict) or decoded.get("format") != "rsicontext-file-bundle-v1":
            raise ArtifactIntegrityError("artifact is not a recognized file bundle")
        raw_files = decoded.get("files")
        if not isinstance(raw_files, list):
            raise ArtifactIntegrityError("artifact file bundle has invalid entries")

        result: dict[str, bytes] = {}
        for raw_entry in raw_files:
            if not isinstance(raw_entry, dict) or set(raw_entry) != {
                "content_base64",
                "path",
                "sha256",
            }:
                raise ArtifactIntegrityError("artifact file bundle has an invalid entry")
            raw_path = raw_entry["path"]
            raw_content = raw_entry["content_base64"]
            expected_digest = raw_entry["sha256"]
            if not all(
                isinstance(value, str) for value in (raw_path, raw_content, expected_digest)
            ):
                raise ArtifactIntegrityError("artifact file bundle entry has invalid types")
            path = _normalize_bundle_path(raw_path)
            try:
                content = base64.b64decode(raw_content, validate=True)
            except ValueError as exc:
                raise ArtifactIntegrityError(
                    "artifact file bundle contains invalid base64"
                ) from exc
            if _sha256(content) != expected_digest or path in result:
                raise ArtifactIntegrityError("artifact file bundle member failed integrity check")
            result[path] = content
        if not result:
            raise ArtifactIntegrityError("artifact file bundle is empty")
        return result

    def get_record(self, artifact_id: str) -> ArtifactRecord:
        """Load and validate an immutable artifact record."""

        _validate_digest(artifact_id, field="artifact id")
        record_path = self._artifact_path(artifact_id) / "record.json"
        try:
            raw: object = json.loads(record_path.read_bytes())
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError(f"artifact does not exist: {artifact_id}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ArtifactIntegrityError(f"artifact record is invalid: {artifact_id}") from exc
        record = self._decode_record(raw)
        if record.artifact_id != artifact_id:
            raise ArtifactIntegrityError("artifact record identifier does not match its path")
        expected_id = _sha256(_canonical_json(self._address_for(record)))
        if expected_id != artifact_id:
            raise ArtifactIntegrityError("artifact record failed address verification")
        return record

    def contains(self, artifact_id: str) -> bool:
        """Return whether a syntactically valid artifact directory exists."""

        try:
            _validate_digest(artifact_id, field="artifact id")
        except ArtifactError:
            return False
        return (self._artifact_path(artifact_id) / "record.json").is_file()

    def lineage(self, artifact_id: str, *, include_self: bool = True) -> tuple[ArtifactRecord, ...]:
        """Return ancestors in parent-before-child topological order."""

        ordered: list[ArtifactRecord] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(current_id: str) -> None:
            if current_id in visiting:
                raise ArtifactIntegrityError("artifact lineage contains a cycle")
            if current_id in visited:
                return
            visiting.add(current_id)
            current = self.get_record(current_id)
            for parent_id in current.parents:
                visit(parent_id)
            visiting.remove(current_id)
            visited.add(current_id)
            ordered.append(current)

        visit(artifact_id)
        if not include_self:
            ordered = [record for record in ordered if record.artifact_id != artifact_id]
        return tuple(ordered)

    def _persist(self, record: ArtifactRecord, payload: bytes) -> None:
        destination = self._artifact_path(record.artifact_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if self.get_record(record.artifact_id) != record:
                raise ArtifactIntegrityError("existing artifact record differs from candidate")
            self.read_bytes(record.artifact_id)
            return

        temporary = Path(tempfile.mkdtemp(prefix=".artifact-", dir=destination.parent))
        try:
            self._write_synced(temporary / "content", payload)
            record_payload = _canonical_json(self._record_json(record)) + b"\n"
            self._write_synced(temporary / "record.json", record_payload)
            self._sync_directory(temporary)
            try:
                os.rename(temporary, destination)
            except OSError as exc:
                if not destination.exists():
                    raise
                if self.get_record(record.artifact_id) != record:
                    raise ArtifactIntegrityError(
                        "concurrent artifact write produced a conflict"
                    ) from exc
                self.read_bytes(record.artifact_id)
            self._sync_directory(destination.parent)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def _artifact_path(self, artifact_id: str) -> Path:
        return self.objects / artifact_id[:2] / artifact_id

    @staticmethod
    def _write_synced(path: Path, payload: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _address_for(record: ArtifactRecord) -> dict[str, object]:
        return {
            "content_sha256": record.content_sha256,
            "kind": record.kind,
            "metadata": dict(record.metadata),
            "parents": list(record.parents),
            "schema_version": _SCHEMA_VERSION,
            "size_bytes": record.size_bytes,
        }

    @classmethod
    def _record_json(cls, record: ArtifactRecord) -> dict[str, object]:
        return {"artifact_id": record.artifact_id, **cls._address_for(record)}

    @staticmethod
    def _decode_record(raw: object) -> ArtifactRecord:
        expected_keys = {
            "artifact_id",
            "content_sha256",
            "kind",
            "metadata",
            "parents",
            "schema_version",
            "size_bytes",
        }
        if not isinstance(raw, dict) or set(raw) != expected_keys:
            raise ArtifactIntegrityError("artifact record has unexpected fields")
        if raw["schema_version"] != _SCHEMA_VERSION:
            raise ArtifactIntegrityError("unsupported artifact record schema")
        artifact_id = raw["artifact_id"]
        content_sha256 = raw["content_sha256"]
        kind = raw["kind"]
        parents = raw["parents"]
        metadata = raw["metadata"]
        size_bytes = raw["size_bytes"]
        if not isinstance(artifact_id, str) or not isinstance(content_sha256, str):
            raise ArtifactIntegrityError("artifact record has invalid digests")
        if (
            not isinstance(kind, str)
            or not isinstance(parents, list)
            or not isinstance(metadata, dict)
        ):
            raise ArtifactIntegrityError("artifact record has invalid collection fields")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
            raise ArtifactIntegrityError("artifact record has invalid size")
        if not all(isinstance(parent, str) for parent in parents):
            raise ArtifactIntegrityError("artifact record has invalid parent ids")
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
        ):
            raise ArtifactIntegrityError("artifact record has invalid metadata")
        try:
            _validate_digest(artifact_id, field="artifact id")
            _validate_digest(content_sha256, field="content digest")
            _validate_kind(kind)
            for parent in parents:
                _validate_digest(parent, field="parent artifact id")
        except ArtifactError as exc:
            raise ArtifactIntegrityError(str(exc)) from exc
        return ArtifactRecord(
            artifact_id=artifact_id,
            content_sha256=content_sha256,
            kind=kind,
            parents=tuple(parents),
            metadata=MappingProxyType(dict(metadata)),
            size_bytes=size_bytes,
        )
