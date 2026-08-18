"""Query-aware retrieval with one-hop source identifier expansion."""

import re
from collections import Counter

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk


def _prefix(text: str) -> str:
    """Use the informative statement before repetitive source padding."""

    return text.partition(". ")[0]


def _words(text: str) -> frozenset[str]:
    return frozenset(term.casefold() for term in re.findall(r"[\w]+", text))


def _identifiers(text: str) -> frozenset[str]:
    return frozenset(
        value.casefold()
        for value in re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b", text)
    )


class Policy:
    """Select direct query evidence and chunks linked by source identifiers."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        prefixes = tuple(_prefix(chunk.text) for chunk in artifact.chunks)
        prefix_words = tuple(_words(prefix) for prefix in prefixes)
        query_words = _words(query)
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "assigned",
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
        query_words = query_words - stop_words
        query_ids = _identifiers(query)
        frequencies = Counter(word for words in prefix_words for word in words)
        rarity_limit = max(2, len(prefixes) // 5)
        lexical_terms = {
            word for word in query_words if frequencies[word] <= rarity_limit
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
                + 30 * len((linked_ids - query_ids) & identifiers)
                + 5 * len(lexical_terms & prefix_words[index])
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
