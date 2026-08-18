"""Query-focused whole-chunk retrieval with bounded relation following."""

import re

from rsicontext.policy import ContextPack


class Policy:
    """Select a governing statement and the query entity's evidence chain."""

    def assemble(self, artifact, query, budget):
        def lead(text):
            return text.partition(". ")[0]

        def words(text):
            return set(
                word.casefold() for word in re.findall(r"[A-Za-z0-9]+", text)
            )

        def identifiers(text):
            return set(
                value.casefold()
                for value in re.findall(
                    r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b", text
                )
            )

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
        leads = [lead(chunk.text) for chunk in artifact.chunks]
        word_sets = [words(text) for text in leads]
        identifier_sets = [identifiers(text) for text in leads]
        query_words = words(query) - stop_words
        query_ids = identifiers(query)

        direct = [
            index
            for index, values in enumerate(identifier_sets)
            if query_ids & values
        ]
        anchors = [
            index
            for index, values in enumerate(identifier_sets)
            if not query_ids & values
            and len(query_words & word_sets[index]) >= 2
        ]
        anchor = None
        if anchors:
            anchor = min(
                anchors,
                key=lambda index: (-len(query_words & word_sets[index]), index),
            )

        governing_ids = set()
        if anchor is not None:
            governing_ids.update(identifier_sets[anchor])
        valid_direct = [
            index
            for index in direct
            if not governing_ids or governing_ids & identifier_sets[index]
        ]
        if not valid_direct:
            valid_direct = direct

        linked_ids = set()
        for index in valid_direct:
            linked_ids.update(identifier_sets[index] - query_ids)
        linked = [
            index
            for index, values in enumerate(identifier_sets)
            if index not in valid_direct
            and index != anchor
            and linked_ids & values
            and (not governing_ids or governing_ids & values)
        ]

        ranked = []
        if anchor is not None:
            ranked.append(anchor)
        ranked.extend(valid_direct)
        ranked.extend(linked)
        seen = set()
        selected = []
        remaining = budget.max_tokens
        for index in ranked:
            if index in seen:
                continue
            seen.add(index)
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
