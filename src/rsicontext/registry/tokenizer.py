"""Exact local tokenizer snapshot verification for replayable experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_SHA256_CHARACTERS = frozenset("0123456789abcdef")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _require_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def verify_tokenizer_snapshot(
    root: Path,
    expected_files: tuple[tuple[str, str], ...],
) -> str:
    """Verify exact tokenizer inputs and return their canonical manifest digest."""

    if not expected_files or tuple(name for name, _ in expected_files) != tuple(
        sorted({name for name, _ in expected_files})
    ):
        raise ValueError("expected tokenizer files must be non-empty, unique, and sorted")
    observed: list[tuple[str, str]] = []
    for name, expected_sha256 in expected_files:
        if Path(name).name != name:
            raise ValueError("tokenizer snapshot filenames must be flat basenames")
        _require_sha256(expected_sha256, f"expected digest for {name}")
        try:
            observed_sha256 = _file_sha256(root / name)
        except OSError as error:
            raise ValueError(f"cannot read tokenizer snapshot file {name!r}: {error}") from error
        if observed_sha256 != expected_sha256:
            raise ValueError(
                f"tokenizer snapshot digest mismatch for {name!r}: "
                f"expected {expected_sha256}, observed {observed_sha256}"
            )
        observed.append((name, observed_sha256))
    payload = json.dumps(observed, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()
