"""Evaluator-only oracle for the constructed R19 short rule contrast."""

from __future__ import annotations

import hashlib
import json

PRIVATE_ORACLE = {
    "data-counter": "plan=suppress-row",
    "file-counter": "plan=emit-row",
}
ORACLE_SHA256 = "f57d92eedf5905a0d89cac579c440d9c045ef39bb9daa04bb8e97ecebbbee24c"


def verified_oracle() -> dict[str, str]:
    raw = json.dumps(
        PRIVATE_ORACLE, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    if hashlib.sha256(raw).hexdigest() != ORACLE_SHA256:
        raise ValueError("R19 private oracle differs from its declared identity")
    return dict(PRIVATE_ORACLE)
