from __future__ import annotations

from pathlib import Path

import pytest

from rsicontext.policy import CANONICAL_POLICY_SPECS_V1
from rsicontext.policy.restricted import (
    RestrictedPolicyError,
    load_restricted_spec_v1,
    materialize_restricted_policy_v1,
)


def test_restricted_workspace_accepts_only_a_canonical_key(tmp_path: Path) -> None:
    key = CANONICAL_POLICY_SPECS_V1[0].canonical_key
    (tmp_path / "spec_v1_key.txt").write_text(f"{key}\n", encoding="utf-8")

    spec = load_restricted_spec_v1(tmp_path)
    policy = materialize_restricted_policy_v1(tmp_path)

    assert spec == CANONICAL_POLICY_SPECS_V1[0]
    assert policy.spec == spec


def test_restricted_workspace_rejects_extra_python(tmp_path: Path) -> None:
    (tmp_path / "spec_v1_key.txt").write_text(
        CANONICAL_POLICY_SPECS_V1[0].canonical_key, encoding="utf-8"
    )
    (tmp_path / "policy.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(RestrictedPolicyError, match="only spec_v1_key"):
        load_restricted_spec_v1(tmp_path)
