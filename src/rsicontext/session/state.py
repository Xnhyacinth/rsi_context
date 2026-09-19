"""Canonical state serialization and load-side validation.

Contract status: implements participant-interface-v1.md §State contract
clauses 1, 2, and 6 (frozen 2026-09-19; benchmark-contract-v2.md
§Protocol semantics "State-boundary contract"). This module owns the
serialization boundary itself: the byte cap is enforced here, not by
trust in the code that produced the state.

Canonical form is sorted-key JSON encoded as UTF-8 with minimal
separators and raw (non-escaped) Unicode — the same recipe as the
fresh-policy JSON protocol (``eval/fresh_policy.py``). A blob is valid
only if re-serializing its parsed value reproduces the exact input
bytes; anything else (unsorted keys, whitespace, escaped Unicode,
duplicate keys, non-finite floats) is rejected on load.

State blobs are untrusted-code-authored data. ``validate_state_bytes``
therefore also rejects strings that name filesystem locations (absolute
POSIX paths, Windows drive paths, ``~``/``./``/``../`` anchored
relative paths, ``file://`` URIs) in any key or value, enforcing the
"no filesystem persistence outside the declared store" rule. Only
prefix-anchored strings are rejected; ordinary text that merely contains
a slash is not a path reference.

The ``schema_digest`` parameter anchors a validated blob to the
participant's declared retainable-state schema ``Σ`` (a sha256 of the
schema's canonical bytes, computed by ``state_schema_digest``). A hash
cannot prove shape conformance; the digest is validated as a
well-formed sha256 reference so every validation is attributable to the
declared ``Σ`` it ran under, and callers can record that pairing.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import NoReturn

_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")
_WINDOWS_DRIVE = re.compile(r"\A[A-Za-z]:[\\/]")


class StateCanonicalizationError(TypeError):
    """Raised when a state object cannot become canonical JSON bytes."""


class StateValidationError(ValueError):
    """Raised when a persisted state blob fails load-side validation."""


def canonical_state_bytes(obj: object) -> bytes:
    """Serialize a JSON-native value to canonical state bytes.

    Only ``None``, booleans, finite floats, integers, strings, lists, and
    string-keyed dictionaries are accepted; anything else (sets, tuples,
    objects, non-finite floats, non-string keys) raises
    ``StateCanonicalizationError``.
    """

    _require_canonical_value(obj, "$")
    try:
        text = json.dumps(
            obj,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise StateCanonicalizationError(f"state value is not canonicalizable: {exc}") from exc


def validate_state_bytes(data: bytes, schema_digest: str, byte_cap: int) -> bytes:
    """Validate one persisted state blob and return its canonical bytes.

    Rejects blobs that are not bytes, exceed ``byte_cap``, are not valid
    JSON objects, contain filesystem-path strings, carry non-finite
    numbers, or are not in canonical byte form. The byte cap is enforced
    here — at the serialization boundary — never by silent truncation.
    """

    if not isinstance(data, bytes):
        raise TypeError("state bytes must be bytes")
    if not isinstance(schema_digest, str) or _SHA256_HEX.fullmatch(schema_digest) is None:
        raise StateValidationError("schema_digest must be a lowercase sha256 hex digest")
    if not isinstance(byte_cap, int) or isinstance(byte_cap, bool) or byte_cap <= 0:
        raise ValueError("byte_cap must be a positive integer")
    if len(data) > byte_cap:
        raise StateValidationError(
            f"state blob is {len(data)} bytes, exceeding the {byte_cap}-byte cap"
        )
    try:
        parsed = json.loads(data, parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise StateValidationError(f"state blob is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise StateValidationError("state blob must be a JSON object")
    _reject_filesystem_paths(parsed, "$")
    try:
        canonical = canonical_state_bytes(parsed)
    except StateCanonicalizationError as exc:
        raise StateValidationError(f"state blob is not canonicalizable: {exc}") from exc
    if canonical != data:
        raise StateValidationError("state blob is not in canonical form")
    return canonical


def state_schema_digest(schema: dict[str, object]) -> str:
    """Return the sha256 digest of a retainable-state schema's canonical bytes."""

    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict")
    return hashlib.sha256(canonical_state_bytes(schema)).hexdigest()


def _require_canonical_value(value: object, path: str) -> None:
    if value is None or isinstance(value, bool | str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StateCanonicalizationError(f"{path}: non-finite floats are not JSON state")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_canonical_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise StateCanonicalizationError(f"{path}: state keys must be strings")
            child = key if path == "$" else f"{path}.{key}"
            _require_canonical_value(item, child)
        return
    raise StateCanonicalizationError(f"{path}: {type(value).__name__} is not a JSON state value")


def _reject_json_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not valid JSON")


def _reject_filesystem_paths(value: object, path: str) -> None:
    if isinstance(value, str):
        if _looks_like_filesystem_path(value):
            raise StateValidationError(f"{path}: filesystem path {value!r} is not state")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_filesystem_paths(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and _looks_like_filesystem_path(key):
                raise StateValidationError(f"{path}: filesystem path key {key!r} is not state")
            child = key if path == "$" else f"{path}.{key}"
            _reject_filesystem_paths(item, child)


def _looks_like_filesystem_path(value: str) -> bool:
    return (
        value.startswith(("/", "\\"))
        or value.startswith(("~/", "~\\", "./", "../", ".\\", "..\\", "file://"))
        or _WINDOWS_DRIVE.match(value) is not None
    )
