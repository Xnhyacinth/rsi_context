"""Frozen operator library for the open-S harness track.

These helpers are evaluator-owned primitives. A researcher may import them from
an isolated policy tree or reimplement the same signatures locally. They never
call the reader, write files, or retain cross-item state.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .types import Artifact, Budget, ContextPack, DocumentChunk

_WORD = re.compile(r"[\w]+", re.UNICODE)
SkillName = str


def retrieve_by_query(chunks: tuple[DocumentChunk, ...], query: str) -> tuple[DocumentChunk, ...]:
    """Rank whole chunks by deterministic query-term overlap, then source index."""

    query_terms = tuple(term.casefold() for term in _WORD.findall(query))
    if not query_terms:
        return chunks

    def key(index: int) -> tuple[int, int]:
        terms = [term.casefold() for term in _WORD.findall(chunks[index].text)]
        overlap = sum(terms.count(term) for term in query_terms)
        return (-overlap, index)

    return tuple(chunk for _, chunk in sorted(enumerate(chunks), key=lambda pair: key(pair[0])))


def map_shards(
    chunks: tuple[DocumentChunk, ...], *, shard_count: int = 2
) -> tuple[tuple[DocumentChunk, ...], ...]:
    """Split spans into accounted logical shards. Physical threads are forbidden."""

    if not isinstance(shard_count, int) or isinstance(shard_count, bool) or shard_count < 1:
        raise ValueError("shard_count must be a positive integer")
    shards: list[list[DocumentChunk]] = [[] for _ in range(shard_count)]
    for index, chunk in enumerate(chunks):
        shards[index % shard_count].append(chunk)
    return tuple(tuple(shard) for shard in shards)


def merge_ranked(
    ranked_shards: tuple[tuple[DocumentChunk, ...], ...],
) -> tuple[DocumentChunk, ...]:
    """Round-robin merge of per-shard rankings, keeping first occurrence of each id."""

    if not ranked_shards:
        return ()
    merged: list[DocumentChunk] = []
    seen: set[str] = set()
    longest = max(len(shard) for shard in ranked_shards)
    for rank in range(longest):
        for shard in ranked_shards:
            if rank >= len(shard):
                continue
            chunk = shard[rank]
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            merged.append(chunk)
    return tuple(merged)


def route_skill(query: str) -> SkillName:
    """Tiny deterministic router. Empty queries fall back to source-order head."""

    if not query.strip():
        return "head"
    return "retrieve"


def record_working_set(query: str, chunks: tuple[DocumentChunk, ...]) -> tuple[str, ...]:
    """Pure in-item scratch. Cross-item memory is evaluator-forbidden on this track."""

    return (query, *(chunk.chunk_id for chunk in chunks[:8]))


def pack_spans(
    chunks: Iterable[DocumentChunk],
    artifact: Artifact,
    budget: Budget,
) -> ContextPack:
    """Pack ranked whole spans until the frozen envelope is exhausted."""

    selected: list[DocumentChunk] = []
    remaining = budget.max_tokens
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            break
        if chunk.token_count <= remaining:
            selected.append(chunk)
            remaining -= chunk.token_count
    pack = ContextPack(
        spans=tuple(selected),
        ordering=tuple(chunk.chunk_id for chunk in selected),
        token_count=sum(chunk.token_count for chunk in selected),
    )
    pack.validate(artifact, budget)
    return pack
