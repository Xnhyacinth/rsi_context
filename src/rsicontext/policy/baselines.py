"""Deterministic, dependency-free reference policies."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from typing import Literal

from .types import Artifact, Budget, ContextPack, DocumentChunk

_WORD = re.compile(r"[\w]+", re.UNICODE)


def _pack(chunks: Iterable[DocumentChunk], artifact: Artifact, budget: Budget) -> ContextPack:
    selected = tuple(chunks)
    pack = ContextPack(
        spans=selected,
        ordering=tuple(chunk.chunk_id for chunk in selected),
        token_count=sum(chunk.token_count for chunk in selected),
    )
    pack.validate(artifact, budget)
    return pack


def _take_until_full(chunks: Iterable[DocumentChunk], budget: Budget) -> tuple[DocumentChunk, ...]:
    selected: list[DocumentChunk] = []
    remaining = budget.max_tokens
    for chunk in chunks:
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            break
        if chunk.token_count > remaining:
            break
        selected.append(chunk)
        remaining -= chunk.token_count
    return tuple(selected)


def _select_that_fit(chunks: Iterable[DocumentChunk], budget: Budget) -> tuple[DocumentChunk, ...]:
    selected: list[DocumentChunk] = []
    remaining = budget.max_tokens
    for chunk in chunks:
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            break
        if chunk.token_count <= remaining:
            selected.append(chunk)
            remaining -= chunk.token_count
    return tuple(selected)


TruncationMode = Literal["head", "tail", "middle", "head_tail"]


class TruncationPolicy:
    """Whole-span truncation with no synthetic or partially sourced text."""

    def __init__(self, mode: TruncationMode = "head") -> None:
        if mode not in ("head", "tail", "middle", "head_tail"):
            raise ValueError(f"unsupported truncation mode: {mode}")
        self.mode = mode

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        del query
        chunks = artifact.chunks
        if self.mode == "head":
            candidates = chunks
        elif self.mode == "tail":
            candidates = tuple(reversed(chunks))
        elif self.mode == "middle":
            center = (len(chunks) - 1) / 2
            candidates = tuple(
                chunk
                for _, chunk in sorted(
                    enumerate(chunks), key=lambda pair: (abs(pair[0] - center), pair[0])
                )
            )
        else:
            candidates_list: list[DocumentChunk] = []
            left, right = 0, len(chunks) - 1
            while left <= right:
                candidates_list.append(chunks[left])
                if left != right:
                    candidates_list.append(chunks[right])
                left += 1
                right -= 1
            candidates = tuple(candidates_list)
        selected = _take_until_full(candidates, budget)
        source_position = {chunk.chunk_id: index for index, chunk in enumerate(artifact.chunks)}
        selected = tuple(sorted(selected, key=lambda chunk: source_position[chunk.chunk_id]))
        return _pack(selected, artifact, budget)


def _terms(text: str) -> list[str]:
    return [term.casefold() for term in _WORD.findall(text)]


class LexicalPolicy:
    """Small BM25-like whole-chunk retriever with stable source-order ties."""

    def __init__(self, *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 parameters require k1 > 0 and 0 <= b <= 1")
        self.k1 = k1
        self.b = b

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        query_terms = set(_terms(query))
        tokenized = [_terms(chunk.text) for chunk in artifact.chunks]
        document_count = len(tokenized)
        average_length = sum(map(len, tokenized)) / document_count if document_count else 0.0
        frequencies = Counter(term for terms in tokenized for term in set(terms))

        def score(index: int) -> float:
            terms = tokenized[index]
            counts = Counter(terms)
            value = 0.0
            for term in query_terms:
                frequency = counts[term]
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1 + (document_count - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                normalization = 1 - self.b
                if average_length:
                    normalization += self.b * len(terms) / average_length
                value += inverse_frequency * (
                    frequency * (self.k1 + 1) / (frequency + self.k1 * normalization)
                )
            return value

        ranked = tuple(
            chunk
            for index, chunk in sorted(
                enumerate(artifact.chunks), key=lambda pair: (-score(pair[0]), pair[0])
            )
        )
        return _pack(_select_that_fit(ranked, budget), artifact, budget)


BM25Policy = LexicalPolicy
