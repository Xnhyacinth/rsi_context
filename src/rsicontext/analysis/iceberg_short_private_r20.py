"""Evaluator-only row oracle for the R20 short Iceberg rule screen."""

from __future__ import annotations

import hashlib
import json

# These are private evaluator inputs, never model-visible registration fields.
TRUTH_TABLE: dict[str, tuple[str, int]] = {
    "data-counter-match": ("data", 42),
    "file-counter-match": ("file", 42),
    "data-counter-mismatch": ("data", 99),
}
ORACLE_SHA256 = "2597ec91086c07304288eb624fdd61c5bc60a9c1bfd015de8d022b7c0c1a86fb"


def _plan(counter: str, delete_value: int) -> str:
    """Apply sequence and value checks for the fixed same-partition fixture."""

    data_sequence, file_sequence, delete_sequence, row_value = 7, 12, 8, 42
    earlier = (data_sequence if counter == "data" else file_sequence) < delete_sequence
    return "plan=suppress-row" if earlier and row_value == delete_value else "plan=emit-row"


def verified_oracle() -> dict[str, str]:
    raw = json.dumps(TRUTH_TABLE, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(raw).hexdigest() != ORACLE_SHA256:
        raise ValueError("R20 private truth table differs from its declared identity")
    return {
        case: _plan(counter, value)
        for case, (counter, value) in TRUTH_TABLE.items()
    }
