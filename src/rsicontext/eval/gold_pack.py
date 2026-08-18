"""Evaluator-owned gold packs. Fill must not inject identifiers or split gold hops."""

from __future__ import annotations

import re

from rsicontext.eval.core import EvaluationItem
from rsicontext.policy import Budget, ContextPack

_OPAQUE_ID = re.compile(r"[a-z]{2}-[0-9a-f]{12}", re.IGNORECASE)


def gold_context_pack(item: EvaluationItem, budget_tokens: int, *, fill: bool) -> ContextPack:
    """Keep gold hops contiguous; leftover budget appends identifier-free haystack."""

    source_position = {chunk.chunk_id: index for index, chunk in enumerate(item.artifact.chunks)}
    gold = [chunk for chunk in item.artifact.chunks if chunk.chunk_id in item.gold_chunk_ids]
    gold.sort(key=lambda chunk: source_position[chunk.chunk_id])
    gold_tokens = sum(chunk.token_count for chunk in gold)
    if gold_tokens > budget_tokens:
        raise ValueError("gold evidence exceeds the bounded oracle budget")
    selected = list(gold)
    if fill:
        selected_ids = set(item.gold_chunk_ids)
        remaining = budget_tokens - gold_tokens
        for chunk in item.artifact.chunks:
            if chunk.chunk_id in selected_ids or chunk.token_count > remaining:
                continue
            if _OPAQUE_ID.search(chunk.text):
                continue
            selected.append(chunk)
            selected_ids.add(chunk.chunk_id)
            remaining -= chunk.token_count
    context = ContextPack(
        spans=tuple(selected),
        ordering=tuple(chunk.chunk_id for chunk in selected),
        token_count=sum(chunk.token_count for chunk in selected),
    )
    context.validate(item.artifact, Budget(budget_tokens))
    return context
