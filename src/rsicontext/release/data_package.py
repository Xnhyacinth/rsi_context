"""Build a deterministic, researcher-visible Hugging Face bootstrap package."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Final, cast

_SCHEMA_VERSION: Final = 1
_REQUIRED_ROOT_FIELDS: Final = {
    "description",
    "files",
    "formal_benchmark_eligible",
    "package_id",
    "package_version",
    "pretty_name",
    "repo_id",
    "schema_version",
}
_REQUIRED_FILE_FIELDS: Final = {
    "destination_path",
    "label_fields",
    "license",
    "provenance",
    "purpose",
    "source_path",
    "visibility",
}
_RESERVED_DESTINATIONS: Final = {"MANIFEST.json", "README.md", "checksums.sha256"}
_EXPLICIT_EXCLUSIONS: Final = [
    "gate/sealed questions or labels",
    "evaluator-only seeds and item scores",
    "raw API responses and experiment results",
    "upstream benchmark archives",
]


class ReleaseSpecError(ValueError):
    """Raised when a data-release specification is unsafe or malformed."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative_path(value: object, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ReleaseSpecError(f"{field} must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseSpecError(f"{field} must be a safe relative path")
    return path


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ReleaseSpecError(f"{field} must be a non-empty, trimmed string")
    return value


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReleaseSpecError(f"{field} must be a list of strings")
    strings = cast(list[str], value)
    if any(not item.strip() or item != item.strip() for item in strings):
        raise ReleaseSpecError(f"{field} entries must be non-empty and trimmed")
    if len(strings) != len(set(strings)):
        raise ReleaseSpecError(f"{field} entries must be unique")
    return strings


def _require_exact_fields(raw: Mapping[str, object], required: set[str], *, field: str) -> None:
    missing = sorted(required - raw.keys())
    extra = sorted(raw.keys() - required)
    if missing or extra:
        raise ReleaseSpecError(f"{field} fields mismatch; missing={missing}, extra={extra}")


def _load_spec(path: Path) -> tuple[dict[str, object], bytes]:
    try:
        encoded = path.read_bytes()
        raw = json.loads(encoded)
    except OSError as error:
        raise ReleaseSpecError(f"cannot read release specification {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ReleaseSpecError(f"invalid JSON in release specification {path}: {error}") from error
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ReleaseSpecError("release specification must be a JSON object")
    return cast(dict[str, object], raw), encoded


def _validate_source(repo_root: Path, source_path: PurePosixPath) -> Path:
    if source_path.parts[:2] != ("tests", "fixtures"):
        raise ReleaseSpecError("source_path must be under tests/fixtures")
    source = repo_root.joinpath(*source_path.parts)
    if source.is_symlink() or not source.is_file():
        raise ReleaseSpecError(f"source_path must name a regular file: {source_path}")
    try:
        source.resolve(strict=True).relative_to(repo_root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ReleaseSpecError(f"source_path escapes the repository: {source_path}") from error
    return source


def _validate_spec_location(spec_path: Path, repo_root: Path) -> PurePosixPath:
    if spec_path.is_symlink():
        raise ReleaseSpecError("release specification must not be a symlink")
    try:
        relative = spec_path.resolve(strict=True).relative_to(repo_root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ReleaseSpecError("release specification must be inside the repository") from error
    return PurePosixPath(relative.as_posix())


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise ReleaseSpecError(f"cannot execute Git provenance check: {error}") from error


def _committed_blob(repo_root: Path, source_revision: str, path: PurePosixPath) -> bytes:
    object_name = f"{source_revision}:{path.as_posix()}"
    try:
        kind = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-t", object_name],
            check=False,
            capture_output=True,
        )
        blob = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "blob", object_name],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise ReleaseSpecError(f"cannot execute Git blob check: {error}") from error
    if kind.returncode != 0 or kind.stdout.strip() != b"blob" or blob.returncode != 0:
        raise ReleaseSpecError(f"release input must be a regular blob in source_revision: {path}")
    return blob.stdout


def _validate_git_provenance(
    repo_root: Path,
    source_revision: str,
    inputs: Sequence[tuple[PurePosixPath, bytes]],
) -> None:
    top_level = _git(repo_root, "rev-parse", "--show-toplevel")
    if top_level.returncode != 0 or Path(top_level.stdout.strip()).resolve() != repo_root.resolve():
        raise ReleaseSpecError("repo_root must be the Git repository top level")
    exists = _git(repo_root, "cat-file", "-e", f"{source_revision}^{{commit}}")
    if exists.returncode != 0:
        raise ReleaseSpecError(f"source_revision does not exist: {source_revision}")
    head = _git(repo_root, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != source_revision:
        raise ReleaseSpecError("source_revision must equal the current HEAD")
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        raise ReleaseSpecError("cannot inspect Git worktree status")
    if status.stdout:
        raise ReleaseSpecError("Git worktree must be clean before building a release")
    for path, captured in inputs:
        if _committed_blob(repo_root, source_revision, path) != captured:
            raise ReleaseSpecError(f"release input bytes do not match source_revision: {path}")


def _validate_destination(destination_path: PurePosixPath) -> None:
    if destination_path.as_posix() in _RESERVED_DESTINATIONS:
        raise ReleaseSpecError(f"destination_path is reserved: {destination_path}")
    if destination_path.parts[0] != "fixtures":
        raise ReleaseSpecError("destination_path must be under fixtures")


def _readme(raw: Mapping[str, object], source_revision: str) -> str:
    pretty_name = _string(raw["pretty_name"], field="pretty_name")
    description = _string(raw["description"], field="description")
    return (
        "---\n"
        f"pretty_name: {pretty_name}\n"
        "license: other\n"
        "---\n\n"
        f"# {pretty_name}\n\n"
        f"{description}\n\n"
        "This private package is a schema-smoke artifact only. It is not a formal benchmark "
        "release and must not be used to claim RSIBench-Context results. It contains no gate "
        "or sealed items, evaluator seeds, raw API responses, or upstream dataset archives.\n\n"
        f"Producer Git revision: `{source_revision}`. See `MANIFEST.json` for provenance and "
        "file digests.\n"
    )


def _record_count(payload: bytes) -> int:
    return sum(bool(line.strip()) for line in payload.splitlines())


def _canonical_json(raw: Mapping[str, object]) -> bytes:
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def build_dataset_release(
    *,
    spec_path: Path,
    repo_root: Path,
    output_dir: Path,
    source_revision: str,
) -> dict[str, object]:
    """Build an allowlisted schema-smoke package and return its manifest."""
    if re.fullmatch(r"[0-9a-f]{40}", source_revision) is None:
        raise ReleaseSpecError("source_revision must be a 40-character lowercase Git SHA")
    if output_dir.exists():
        raise ReleaseSpecError("output_dir must be absent")

    raw, encoded_spec = _load_spec(spec_path)
    _require_exact_fields(raw, _REQUIRED_ROOT_FIELDS, field="release specification")
    if raw["schema_version"] != _SCHEMA_VERSION:
        raise ReleaseSpecError(f"schema_version must be {_SCHEMA_VERSION}")
    if raw["formal_benchmark_eligible"] is not False:
        raise ReleaseSpecError("bootstrap releases must set formal_benchmark_eligible to false")
    for field in ("package_id", "package_version", "repo_id", "pretty_name", "description"):
        _string(raw[field], field=field)

    raw_files = raw["files"]
    if not isinstance(raw_files, list) or not raw_files:
        raise ReleaseSpecError("files must be a non-empty list")

    manifest_files: list[dict[str, object]] = []
    payloads: list[tuple[PurePosixPath, bytes]] = []
    seen_destinations: set[str] = set()
    for index, value in enumerate(raw_files):
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise ReleaseSpecError(f"files[{index}] must be an object")
        file_raw = cast(dict[str, object], value)
        _require_exact_fields(file_raw, _REQUIRED_FILE_FIELDS, field=f"files[{index}]")
        source_path = _safe_relative_path(file_raw["source_path"], field="source_path")
        destination_path = _safe_relative_path(
            file_raw["destination_path"], field="destination_path"
        )
        _validate_destination(destination_path)
        destination = destination_path.as_posix()
        if destination in seen_destinations:
            raise ReleaseSpecError(f"destination_path must be unique: {destination}")
        seen_destinations.add(destination)
        source = _validate_source(repo_root, source_path)
        payload = source.read_bytes()
        payloads.append((destination_path, payload))
        manifest_files.append(
            {
                "path": destination,
                "sha256": _sha256_bytes(payload),
                "size_bytes": len(payload),
                "source_path": source_path.as_posix(),
                "license": _string(file_raw["license"], field="license"),
                "provenance": _string(file_raw["provenance"], field="provenance"),
                "visibility": _string(file_raw["visibility"], field="visibility"),
                "purpose": _string(file_raw["purpose"], field="purpose"),
                "record_count": _record_count(payload),
                "label_fields": _string_list(file_raw["label_fields"], field="label_fields"),
            }
        )

    spec_relative = _validate_spec_location(spec_path, repo_root)
    release_inputs = [(spec_relative, encoded_spec)]
    release_inputs.extend(
        (PurePosixPath(cast(str, item["source_path"])), payload)
        for item, (_, payload) in zip(manifest_files, payloads, strict=True)
    )
    _validate_git_provenance(repo_root, source_revision, release_inputs)

    manifest: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "package_id": raw["package_id"],
        "package_version": raw["package_version"],
        "repo_id": raw["repo_id"],
        "formal_benchmark_eligible": False,
        "source_revision": source_revision,
        "build_command": (
            f"uv run python scripts/build_hf_dataset_release.py --source-revision {source_revision}"
        ),
        "build_config_sha256": _sha256_bytes(encoded_spec),
        "qualification": "fixture-only; not a formal benchmark release",
        "boundary": {
            "classification": "researcher-visible",
            "allowed_splits": sorted(
                {cast(str, file_manifest["visibility"]) for file_manifest in manifest_files}
            ),
            "explicitly_excluded": _EXPLICIT_EXCLUSIONS,
        },
        "files": manifest_files,
    }
    fingerprint_input = dict(manifest)
    manifest["dataset_fingerprint"] = _sha256_bytes(_canonical_json(fingerprint_input))

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".rsicontext-release-", dir=output_dir.parent))
    try:
        for destination_path, payload in payloads:
            target = staging.joinpath(*destination_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        (staging / "README.md").write_text(_readme(raw, source_revision), encoding="utf-8")
        (staging / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (staging / "checksums.sha256").write_text(
            "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest_files),
            encoding="utf-8",
        )
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest
