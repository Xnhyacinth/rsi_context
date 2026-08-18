"""Query-led retrieval with schema anchors and identifier expansion."""

import re

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk


def _lead(text: str) -> str:
    """Discard repetitive padding after the first source statement."""

    return text.partition(". ")[0]


def _words(text: str) -> frozenset[str]:
    return frozenset(word.casefold() for word in re.findall(r"[A-Za-z0-9]+", text))


def _identifiers(text: str) -> frozenset[str]:
    return frozenset(
        value.casefold()
        for value in re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b", text)
    )


class Policy:
    """Retrieve direct evidence, its governing rule, and linked evidence."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        leads = tuple(_lead(chunk.text) for chunk in artifact.chunks)
        word_sets = tuple(_words(lead) for lead in leads)
        identifier_sets = tuple(_identifiers(lead) for lead in leads)
        query_words = _words(query)
        query_ids = _identifiers(query)
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "assigned",
            "currently",
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
        useful_words = query_words - stop_words

        def overlap(index: int) -> int:
            return len(useful_words & word_sets[index])

        direct = tuple(
            index
            for index, identifiers in enumerate(identifier_sets)
            if query_ids & identifiers
        )
        indirect = tuple(
            index
            for index, identifiers in enumerate(identifier_sets)
            if not query_ids & identifiers and overlap(index) >= 2
        )
        linked_ids = set(query_ids)
        if direct:
            best_direct = min(direct, key=lambda index: (-overlap(index), index))
            linked_ids.update(identifier_sets[best_direct])
        if indirect:
            best_indirect = min(indirect, key=lambda index: (-overlap(index), index))
            linked_ids.update(identifier_sets[best_indirect])

        def score(index: int) -> int:
            identifiers = identifier_sets[index]
            direct_matches = len(query_ids & identifiers)
            linked_matches = len((linked_ids - query_ids) & identifiers)
            joint_bonus = 80 if direct_matches and linked_matches else 0
            return 120 * direct_matches + 70 * linked_matches + joint_bonus + 8 * overlap(index)

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
