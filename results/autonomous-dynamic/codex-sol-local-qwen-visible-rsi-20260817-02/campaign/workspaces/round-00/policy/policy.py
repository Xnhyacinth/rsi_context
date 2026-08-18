"""Query-seeded entity expansion over immutable source chunks."""

import math
import re
from collections import Counter

from rsicontext.policy import Artifact, Budget, ContextPack


class Policy:
    """Prioritize direct evidence and one-hop records before lexical backfill."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        word_pattern = r"[\w]+"
        identifier_pattern = r"\b[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+\b"
        query_terms = set(
            term.casefold() for term in re.findall(word_pattern, query)
        )
        query_identifiers = set(
            term.casefold() for term in re.findall(identifier_pattern, query)
        )
        tokenized = [
            [term.casefold() for term in re.findall(word_pattern, chunk.text)]
            for chunk in artifact.chunks
        ]
        document_count = len(tokenized)
        frequencies = Counter(
            term for terms in tokenized for term in set(terms)
        )
        average_length = (
            sum(len(terms) for terms in tokenized) / document_count
            if document_count
            else 0.0
        )

        seed_indices = set()
        discovered = set(query_identifiers)
        for index, chunk in enumerate(artifact.chunks):
            lowered = chunk.text.casefold()
            if query_identifiers and any(
                identifier in lowered for identifier in query_identifiers
            ):
                seed_indices.add(index)
                discovered.update(
                    term.casefold()
                    for term in re.findall(identifier_pattern, chunk.text)
                )

        expanded_indices = set(seed_indices)
        if discovered:
            for index, chunk in enumerate(artifact.chunks):
                lowered = chunk.text.casefold()
                if any(identifier in lowered for identifier in discovered):
                    expanded_indices.add(index)

        def lexical_score(index: int) -> float:
            terms = tokenized[index]
            counts = Counter(terms)
            value = 0.0
            for term in query_terms:
                frequency = counts[term]
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1
                    + (document_count - frequencies[term] + 0.5)
                    / (frequencies[term] + 0.5)
                )
                normalization = 0.25
                if average_length:
                    normalization += 0.75 * len(terms) / average_length
                value += inverse_frequency * (
                    frequency * 2.2 / (frequency + 1.2 * normalization)
                )
            return value

        ranked = sorted(
            range(document_count),
            key=lambda index: (
                0 if index in seed_indices else 1 if index in expanded_indices else 2,
                -lexical_score(index),
                index,
            ),
        )
        selected = []
        remaining = budget.max_tokens
        for index in ranked:
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
            abstain=not spans,
        )
        pack.validate(artifact, budget)
        return pack
