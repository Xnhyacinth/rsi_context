"""Focused query-entity retrieval with one-hop evidence linking."""

import re

from rsicontext.policy import Artifact, Budget, ContextPack


class Policy:
    """Pack direct entity records and their immediately linked records."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        identifier_pattern = r"\b[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+\b"
        word_pattern = r"[A-Za-z0-9]+"
        query_identifiers = set(
            value.casefold()
            for value in re.findall(identifier_pattern, query)
        )
        query_words = set(
            value.casefold() for value in re.findall(word_pattern, query)
            if len(value) > 2
        )

        heads = []
        identifiers = []
        words = []
        for chunk in artifact.chunks:
            head = chunk.text.split(".", 1)[0]
            heads.append(head.casefold())
            identifiers.append(
                set(
                    value.casefold()
                    for value in re.findall(identifier_pattern, head)
                )
            )
            words.append(
                set(value.casefold() for value in re.findall(word_pattern, head))
            )

        direct = set()
        for index, values in enumerate(identifiers):
            if query_identifiers.intersection(values):
                direct.add(index)

        linked_identifiers = set(query_identifiers)
        for index in direct:
            linked_identifiers.update(identifiers[index])

        linked = set(direct)
        for index, values in enumerate(identifiers):
            if linked_identifiers.intersection(values):
                linked.add(index)

        if linked:
            candidates = linked
        else:
            candidates = set(
                index for index, values in enumerate(words)
                if query_words.intersection(values)
            )

        def rank(index: int) -> tuple:
            head = heads[index]
            governing = (
                "consensus" in head
                or "counts only" in head
                or "adopted" in head
            )
            terminal = index in linked and index not in direct
            overlap = len(query_words.intersection(words[index]))
            return (
                0 if governing else 1 if terminal else 2,
                -overlap,
                index,
            )

        selected = []
        remaining = budget.max_tokens
        for index in sorted(candidates, key=rank):
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
