"""Retrieve whole source chunks using their informative leading statements."""

from __future__ import annotations

import re
from collections import Counter

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk

_WORD = re.compile(r"[\w]+", re.UNICODE)
_IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "in",
        "is",
        "of",
        "on",
        "the",
        "to",
        "under",
        "what",
        "which",
        "within",
    }
)


def _prefix(text: str) -> str:
    """Discard repeated padding after the first source-authored sentence."""

    return text.partition(". ")[0]


def _words(text: str) -> frozenset[str]:
    return frozenset(term.casefold() for term in _WORD.findall(text))


def _identifiers(text: str) -> frozenset[str]:
    return frozenset(value.casefold() for value in _IDENTIFIER.findall(text))


class Policy:
    """Rank direct matches, one-hop identifier links, and rare query terms."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        prefixes = tuple(_prefix(chunk.text) for chunk in artifact.chunks)
        prefix_words = tuple(_words(prefix) for prefix in prefixes)
        query_words = _words(query) - _STOP_WORDS
        query_ids = _identifiers(query)

        document_frequency = Counter(word for words in prefix_words for word in words)
        rarity_limit = max(2, len(prefixes) // 5)
        lexical_terms = {
            word for word in query_words if document_frequency[word] <= rarity_limit
        }

        direct = {
            index
            for index, prefix in enumerate(prefixes)
            if query_ids & _identifiers(prefix)
        }
        linked_ids = set(query_ids)
        for index in direct:
            linked_ids.update(_identifiers(prefixes[index]))

        def score(index: int) -> int:
            identifiers = _identifiers(prefixes[index])
            return (
                100 * len(query_ids & identifiers)
                + 30 * len(linked_ids & identifiers)
                + 3 * len(lexical_terms & prefix_words[index])
            )

        ranked = sorted(
            range(len(artifact.chunks)), key=lambda index: (-score(index), index)
        )
        selected: list[DocumentChunk] = []
        remaining = budget.max_tokens
        for index in ranked:
            if score(index) <= 0:
                break
            if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
                break
            chunk = artifact.chunks[index]
            if chunk.token_count <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_count

        spans = tuple(selected)
        pack = ContextPack(
            spans=spans,
            ordering=tuple(chunk.chunk_id for chunk in spans),
            token_count=sum(chunk.token_count for chunk in spans),
        )
        pack.validate(artifact, budget)
        return pack
