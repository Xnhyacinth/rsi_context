"""Query-focused whole-chunk retrieval with identifier-link expansion."""

import math
import re

from rsicontext.policy import ContextPack


class Policy:
    """Select direct evidence and chunks linked by identifiers in that evidence."""

    def assemble(self, artifact, query, budget):
        words_pattern = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?"
        identifier_pattern = r"[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+"
        ignored = set(
            (
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
        )

        query_terms = set(
            term.casefold()
            for term in re.findall(words_pattern, query)
            if term.casefold() not in ignored
        )
        query_ids = set(term.casefold() for term in re.findall(identifier_pattern, query))
        leading_terms = []
        document_frequency = {}
        for chunk in artifact.chunks:
            lead = chunk.text.split(".", 1)[0]
            terms = set(term.casefold() for term in re.findall(words_pattern, lead))
            leading_terms.append(terms)
            for term in terms:
                document_frequency[term] = document_frequency.get(term, 0) + 1

        count = len(artifact.chunks)
        direct_scores = []
        for index, terms in enumerate(leading_terms):
            score = 0.0
            for term in query_terms:
                if term in terms:
                    rarity = math.log((count + 1) / (document_frequency.get(term, 0) + 1))
                    score += 2.0 + rarity
                    if term in query_ids:
                        score += 12.0
            direct_scores.append((score, index))

        direct = [pair for pair in direct_scores if pair[0] > 0.0]
        direct.sort(key=lambda pair: (-pair[0], pair[1]))
        linked_ids = set(query_ids)
        for _, index in direct:
            lead = artifact.chunks[index].text.split(".", 1)[0]
            linked_ids.update(term.casefold() for term in re.findall(identifier_pattern, lead))

        ranked = []
        for direct_score, index in direct_scores:
            links = len(linked_ids.intersection(leading_terms[index]))
            if direct_score > 0.0 or links:
                ranked.append((direct_score + 10.0 * links, direct_score, index))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))

        selected = []
        remaining = budget.max_tokens
        for _, _, index in ranked:
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
