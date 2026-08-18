"""Byte-identical visible round feedback shared by all primary controllers."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def _require_item_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if any(not isinstance(item_id, str) or not item_id.strip() for item_id in values):
        raise TypeError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return values


@dataclass(frozen=True, slots=True)
class RoundFeedback:
    """Visible-only fields that every matched controller may see for one round."""

    round_index: int
    visible_item_order: tuple[str, ...]
    parent_predictions: tuple[tuple[str, str], ...]
    parent_scores: tuple[tuple[str, float], ...]
    gold_chunk_ids: tuple[tuple[str, tuple[str, ...]], ...]
    gold_texts: tuple[tuple[str, tuple[str, ...]], ...]
    ledger: tuple[tuple[str, int | float], ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.round_index, int) or isinstance(self.round_index, bool):
            raise TypeError("round_index must be an integer")
        if self.round_index < 0:
            raise ValueError("round_index must be non-negative")
        if self.schema_version != 1:
            raise ValueError("unsupported RoundFeedback schema")
        order = _require_item_ids(self.visible_item_order, "visible_item_order")
        for field_name, pairs in (
            ("parent_predictions", self.parent_predictions),
            ("parent_scores", self.parent_scores),
            ("gold_chunk_ids", self.gold_chunk_ids),
            ("gold_texts", self.gold_texts),
        ):
            ids = _require_item_ids(tuple(item_id for item_id, _ in pairs), field_name)
            if ids != order:
                raise ValueError(f"{field_name} must follow visible_item_order")
        if any(not isinstance(prediction, str) for _, prediction in self.parent_predictions):
            raise TypeError("parent predictions must be strings")
        for _, score in self.parent_scores:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise TypeError("parent scores must be numeric")
            if not math.isfinite(float(score)):
                raise ValueError("parent scores must be finite")
        if any(not isinstance(key, str) or not key for key, _ in self.ledger):
            raise ValueError("ledger keys must be non-empty strings")
        keys = [key for key, _ in self.ledger]
        if len(keys) != len(set(keys)):
            raise ValueError("ledger keys must be unique")
        for _, value in self.ledger:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("ledger values must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError("ledger values must be finite")

    def canonical_bytes(self) -> bytes:
        payload = {
            "gold_chunk_ids": [
                [item_id, list(chunk_ids)] for item_id, chunk_ids in self.gold_chunk_ids
            ],
            "gold_texts": [[item_id, list(texts)] for item_id, texts in self.gold_texts],
            "ledger": [[key, value] for key, value in self.ledger],
            "parent_predictions": [list(item) for item in self.parent_predictions],
            "parent_scores": [list(item) for item in self.parent_scores],
            "round_index": self.round_index,
            "schema_version": self.schema_version,
            "visible_item_order": list(self.visible_item_order),
        }
        return json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
