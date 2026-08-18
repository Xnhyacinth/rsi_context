"""Pack query-specific records, governing rules, and one-hop answers."""

import re

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk


def _lead(text: str) -> str:
    """Return the informative sentence at the front of a padded source chunk."""

    return text.partition(". ")[0]


def _identifiers(text: str) -> set[str]:
    """Extract structured identifiers suitable for exact evidence joins."""

    return {
        value.casefold()
        for value in re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b", text)
    }


def _words(text: str) -> set[str]:
    """Extract meaningful query-language words for selecting governing rules."""

    ignored = {
        "a",
        "an",
        "for",
        "in",
        "is",
        "its",
        "of",
        "the",
        "to",
        "under",
        "what",
        "which",
        "within",
    }
    return {
        value
        for value in re.findall(r"[A-Za-z]+", text.casefold())
        if len(value) > 2 and value not in ignored
    }


class Policy:
    """Select exact records, relevant rules, and one-hop answer records."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        leads = tuple(_lead(chunk.text) for chunk in artifact.chunks)
        identifiers = tuple(_identifiers(lead) for lead in leads)
        query_identifiers = _identifiers(query)
        query_words = _words(query)

        direct = tuple(
            index
            for index, values in enumerate(identifiers)
            if query_identifiers & values
        )
        joined_identifiers = set()
        for index in direct:
            joined_identifiers.update(identifiers[index] - query_identifiers)
        linked = tuple(
            index
            for index, values in enumerate(identifiers)
            if index not in direct and joined_identifiers & values
        )
        rules = tuple(
            index
            for index, lead in enumerate(leads)
            if index not in direct
            and index not in linked
            and len(query_words & _words(lead)) >= 2
        )

        if linked:
            candidates = linked + direct + rules
        else:
            candidates = rules + direct

        selected: list[DocumentChunk] = []
        remaining = budget.max_tokens
        for index in candidates:
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
