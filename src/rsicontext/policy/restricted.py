"""Restricted V1 researcher artifacts: a canonical key, not arbitrary Python."""

from __future__ import annotations

from pathlib import Path

from rsicontext.policy import PolicySpecV1, PolicySpecV1Interpreter, PolicySpecV1Policy

RESTRICTED_SPEC_FILENAME = "spec_v1_key.txt"


class RestrictedPolicyError(ValueError):
    """Raised when a restricted V1 workspace is missing or off-grammar."""


def load_restricted_spec_v1(policy_directory: str | Path) -> PolicySpecV1:
    """Read the single committed canonical key from a restricted workspace."""

    directory = Path(policy_directory)
    path = directory / RESTRICTED_SPEC_FILENAME
    if not path.is_file():
        raise RestrictedPolicyError("restricted workspace must contain spec_v1_key.txt")
    extra = sorted(
        entry.name
        for entry in directory.iterdir()
        if entry.is_file() and entry.name != RESTRICTED_SPEC_FILENAME
    )
    if extra:
        raise RestrictedPolicyError("restricted workspace may contain only spec_v1_key.txt")
    key = path.read_text(encoding="utf-8").strip()
    if not key or "\n" in key:
        raise RestrictedPolicyError("canonical key must be a single non-empty line")
    try:
        return PolicySpecV1.from_canonical_key(key)
    except (TypeError, ValueError) as exc:
        raise RestrictedPolicyError("canonical key is not in the V1 grammar") from exc


def materialize_restricted_policy_v1(policy_directory: str | Path) -> PolicySpecV1Policy:
    """Materialize the interpreter-owned policy for a restricted submission."""

    spec = load_restricted_spec_v1(policy_directory)
    return PolicySpecV1Interpreter().materialize(spec)
