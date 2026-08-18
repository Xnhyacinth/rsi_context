"""Deterministic fictional multi-hop data for an independently held evaluator."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from rsicontext.eval import EvaluationItem
from rsicontext.experiment import Split
from rsicontext.policy import Artifact, DocumentChunk

_COLORS = ("amber", "violet", "silver", "cerulean", "ochre", "magenta", "teal")
_PREFIXES = ("Astra", "Boreal", "Cyra", "Demer", "Elyra", "Faron", "Galen", "Helio")
_SUFFIXES = ("nex", "vane", "lith", "dora", "quill", "mere", "taris", "wyn")


@dataclass(frozen=True, slots=True)
class PrivateItem:
    split: Split
    template_family: str
    entity: str
    evaluation_item: EvaluationItem


@dataclass(frozen=True, slots=True)
class CounterfactualDataset:
    """Evaluator-side fixture, not an in-process confidentiality boundary."""

    _evaluator_items: tuple[PrivateItem, ...]
    fingerprint: str

    def visible_items(self) -> tuple[PrivateItem, ...]:
        """Export the only split that may enter a researcher workspace."""

        return self.evaluator_items(Split.VISIBLE)

    def evaluator_items(self, split: Split) -> tuple[PrivateItem, ...]:
        """Read one split inside the isolated evaluator process only."""

        return tuple(item for item in self._evaluator_items if item.split is split)


def _digest(seed: str, split: Split, index: int) -> bytes:
    return hashlib.sha256(f"{seed}\x00{split.value}\x00{index}".encode()).digest()


def _fictional_name(digest: bytes, offset: int) -> str:
    prefix = _PREFIXES[digest[offset] % len(_PREFIXES)]
    suffix = _SUFFIXES[digest[offset + 1] % len(_SUFFIXES)]
    return f"{prefix}{suffix}-{digest[offset + 2]:02x}"


def _make_chunks(
    *, document_id: str, records: tuple[tuple[str, bool], ...], digest: bytes
) -> tuple[tuple[DocumentChunk, ...], frozenset[str]]:
    order = sorted(range(len(records)), key=lambda index: (digest[index + 8], index))

    chunks: list[DocumentChunk] = []
    gold_ids: set[str] = set()
    cursor = 0
    for index, record_index in enumerate(order):
        text, is_gold = records[record_index]
        end = cursor + len(text)
        chunk_id = f"{document_id}-c{index}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                start=cursor,
                end=end,
                text=text,
                token_count=len(text.split()),
            )
        )
        if is_gold:
            gold_ids.add(chunk_id)
        cursor = end + 1
    return tuple(chunks), frozenset(gold_ids)


def _template(
    *,
    split: Split,
    entity: str,
    record: str,
    answer: str,
    alternatives: tuple[tuple[str, str], ...],
) -> tuple[str, str, tuple[tuple[str, bool], ...]]:
    if split is Split.VISIBLE:
        family = "registry-ledger-v2"
        query = f"What access color is currently assigned to {entity}?"
        relation = f"The registry for {entity} routes its access record to ledger {record}."
        value = f"Ledger {record} records {answer} as its current access color."
        alternative_values = tuple(
            f"Ledger {name} records {color} as its current access color."
            for name, color in alternatives
        )
    elif split is Split.GATE:
        family = "dossier-folio-v2"
        query = f"Which clearance hue is currently assigned to {entity}?"
        relation = f"The dossier for {entity} routes its clearance entry through folio {record}."
        value = f"Folio {record} lists {answer} as its current clearance hue."
        alternative_values = tuple(
            f"Folio {name} lists {color} as its current clearance hue."
            for name, color in alternatives
        )
    else:
        family = "vault-capsule-v2"
        query = f"What signal shade currently belongs to {entity}?"
        relation = f"The vault index for {entity} points to capsule {record}."
        value = f"Capsule {record} carries {answer} as its current signal shade."
        alternative_values = tuple(
            f"Capsule {name} carries {color} as its current signal shade."
            for name, color in alternatives
        )
    noise = tuple(
        f"Archive {_fictional_name(hashlib.sha256(name.encode()).digest(), 3)} contains "
        "an unrelated maintenance note."
        for name, _ in alternatives
    )
    records = (
        (relation, True),
        (value, True),
        *((text, False) for text in alternative_values),
        *((text, False) for text in noise),
    )
    return family, query, records


def _make_item(seed: str, split: Split, index: int) -> PrivateItem:
    digest = _digest(seed, split, index)
    document_id = f"cf-{digest.hex()[:16]}"
    entity = _fictional_name(digest, 0)
    record = _fictional_name(digest, 17)
    answer = _COLORS[digest[20] % len(_COLORS)]
    other_colors = tuple(color for color in _COLORS if color != answer)
    alternatives = tuple(
        (
            f"{_fictional_name(digest, offset)}-distractor-{alternative_index}",
            other_colors[digest[24 + alternative_index] % len(other_colors)],
        )
        for alternative_index, offset in enumerate((21, 24, 27))
    )
    family, query, records = _template(
        split=split,
        entity=entity,
        record=record,
        answer=answer,
        alternatives=alternatives,
    )
    chunks, gold = _make_chunks(
        document_id=document_id,
        records=records,
        digest=digest,
    )
    if len(gold) != 2:
        raise AssertionError("counterfactual template must contain exactly two gold chunks")
    evaluation_item = EvaluationItem(
        item_id=document_id,
        query=query,
        answer=answer,
        artifact=Artifact(document_id=document_id, chunks=chunks),
        gold_chunk_ids=gold,
    )
    return PrivateItem(
        split=split,
        template_family=family,
        entity=entity,
        evaluation_item=evaluation_item,
    )


def generate_counterfactual_dataset(
    *, seed: str, counts: Mapping[Split, int]
) -> CounterfactualDataset:
    """Generate split-family-disjoint items; keep ``seed`` on the evaluator."""

    if not seed:
        raise ValueError("private dataset seed must be non-empty")
    normalized_counts: dict[Split, int] = {}
    for split in Split:
        count = counts.get(split, 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"count for {split.value} must be a non-negative integer")
        normalized_counts[split] = count
    items = tuple(
        _make_item(seed, split, index)
        for split in Split
        for index in range(normalized_counts[split])
    )
    canonical = [
        {
            "answer": item.evaluation_item.answer,
            "chunks": [
                hashlib.sha256(chunk.text.encode()).hexdigest()
                for chunk in item.evaluation_item.artifact.chunks
            ],
            "family": item.template_family,
            "item_id": item.evaluation_item.item_id,
            "split": item.split.value,
        }
        for item in items
    ]
    fingerprint = hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return CounterfactualDataset(_evaluator_items=items, fingerprint=fingerprint)
