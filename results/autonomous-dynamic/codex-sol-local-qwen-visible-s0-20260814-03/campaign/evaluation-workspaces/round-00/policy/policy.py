"""Query-directed retrieval with identifier-link expansion."""

import math
import re

from rsicontext.policy import ContextPack


class Policy:
    """Select whole source chunks by factual-prefix relevance and identifier links."""

    def assemble(self, artifact, query, budget):
        query_terms = set(
            term.casefold()
            for term in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", query)
        )
        leads = []
        term_documents = {}
        identifiers = []
        for chunk in artifact.chunks:
            lead = chunk.text.split(".", 1)[0]
            terms = set(
                term.casefold()
                for term in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", lead)
            )
            leads.append(terms)
            identifiers.append(
                set(
                    term.casefold()
                    for term in re.findall(
                        r"[A-Za-z]+[A-Z][A-Za-z]*-[A-Za-z0-9]+", lead
                    )
                )
            )
            for term in terms:
                term_documents[term] = term_documents.get(term, 0) + 1

        count = len(artifact.chunks)
        scores = []
        for index, terms in enumerate(leads):
            score = 0.0
            for term in query_terms & terms:
                score += math.log(1.0 + count / term_documents[term])
                if "-" in term:
                    score += 4.0
            scores.append(score)

        frontier = set()
        if scores:
            best = max(scores)
            for index, score in enumerate(scores):
                if score > 0.0 and score >= best * 0.45:
                    frontier.update(identifiers[index])
        for _ in range(2):
            added = set()
            for index, chunk_identifiers in enumerate(identifiers):
                links = frontier & chunk_identifiers
                if links:
                    scores[index] += 5.0 * len(links)
                    added.update(chunk_identifiers)
            frontier.update(added)

        ranked = sorted(
            enumerate(artifact.chunks),
            key=lambda pair: (-scores[pair[0]], pair[0]),
        )
        selected = []
        remaining = budget.max_tokens
        for index, chunk in ranked:
            if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
                break
            if chunk.token_count <= remaining:
                selected.append((index, chunk))
                remaining -= chunk.token_count
        selected.sort(key=lambda pair: pair[0])
        spans = tuple(pair[1] for pair in selected)
        pack = ContextPack(
            spans=spans,
            ordering=tuple(chunk.chunk_id for chunk in spans),
            token_count=sum(chunk.token_count for chunk in spans),
        )
        pack.validate(artifact, budget)
        return pack
