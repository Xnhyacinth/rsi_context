"""Pack exact entity evidence and its one-hop supporting records."""

import re

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk


def _statement(text: str) -> str:
    """Return the informative leading statement of a padded chunk."""

    return text.partition(". ")[0]


def _identifiers(text: str) -> set[str]:
    """Extract the structured identifiers used to join evidence records."""

    return {
        value.casefold()
        for value in re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b", text)
    }


class Policy:
    """Select exact query records followed by one-hop supporting records."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        statements = tuple(_statement(chunk.text) for chunk in artifact.chunks)
        identifiers = tuple(_identifiers(statement) for statement in statements)
        query_identifiers = _identifiers(query)

        direct = tuple(
            index
            for index, values in enumerate(identifiers)
            if query_identifiers & values
        )
        discovered = set(query_identifiers)
        for index in direct:
            discovered.update(identifiers[index])
        linked = tuple(
            index
            for index, values in enumerate(identifiers)
            if index not in direct and (discovered - query_identifiers) & values
        )

        selected: list[DocumentChunk] = []
        remaining = budget.max_tokens
        for index in direct + linked:
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
