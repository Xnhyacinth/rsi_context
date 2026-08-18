"""Content-based retrieval over the informative prefix of each source chunk."""

import re
from collections import Counter

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk

_WORD_PATTERN = r"[\w]+"
_IDENTIFIER_PATTERN = r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b"
_NUMBER_PATTERN = r"(?<![\w-])\d+(?![\w-])"
_STOP_WORDS = (
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
)


def _prefix(text: str) -> str:
    """Return the source-authored statement before long padding begins."""

    sentence, _, _ = text.partition(". ")
    return sentence


def _words(text: str) -> frozenset[str]:
    return frozenset(word.casefold() for word in re.findall(_WORD_PATTERN, text))


def _identifiers(text: str) -> frozenset[str]:
    return frozenset(
        value.casefold() for value in re.findall(_IDENTIFIER_PATTERN, text)
    )


class Policy:
    """Retrieve direct evidence and bounded relation-linked evidence."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        prefixes = tuple(_prefix(chunk.text) for chunk in artifact.chunks)
        prefix_words = tuple(_words(prefix) for prefix in prefixes)
        query_words = frozenset(word for word in _words(query) if word not in _STOP_WORDS)
        query_ids = _identifiers(query)
        query_numbers = frozenset(re.findall(_NUMBER_PATTERN, query))

        document_frequency = Counter(
            word for words in prefix_words for word in words
        )
        rarity_limit = max(2, len(prefixes) // 5)
        lexical_terms = frozenset(
            word
            for word in query_words
            if document_frequency[word] <= rarity_limit
        )

        linked_ids = set(query_ids)
        direct: set[int] = set()
        for index, prefix in enumerate(prefixes):
            ids = _identifiers(prefix)
            has_id = bool(query_ids & ids)
            has_numbers = not query_numbers or query_numbers <= prefix_words[index]
            if has_id and has_numbers:
                direct.add(index)

        frontier = set(direct)
        for _ in range(2):
            for index in frontier:
                linked_ids.update(_identifiers(prefixes[index]))
            next_frontier = {
                index
                for index, prefix in enumerate(prefixes)
                if index not in direct and linked_ids & _identifiers(prefix)
            }
            if not next_frontier:
                break
            direct.update(next_frontier)
            frontier = next_frontier

        def score(index: int) -> tuple[int, int, int]:
            ids = _identifiers(prefixes[index])
            direct_id_matches = len(query_ids & ids)
            linked_id_matches = len(linked_ids & ids)
            lexical_matches = len(lexical_terms & prefix_words[index])
            number_matches = len(query_numbers & prefix_words[index])
            value = (
                100 * direct_id_matches
                + 30 * linked_id_matches
                + 12 * number_matches
                + 3 * lexical_matches
            )
            return value, direct_id_matches, number_matches

        ranked = sorted(
            range(len(artifact.chunks)),
            key=lambda index: (*(-value for value in score(index)), index),
        )
        selected: list[DocumentChunk] = []
        remaining = budget.max_tokens
        for index in ranked:
            if score(index)[0] <= 0:
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
