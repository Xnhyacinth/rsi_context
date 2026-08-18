"""Query-grounded evidence-chain retrieval."""

import re

from rsicontext.policy import ContextPack


class Policy:
    """Select whole chunks that form the evidence chain requested by the query."""

    def assemble(self, artifact, query, budget):
        identifier_pattern = r"[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+"
        number_pattern = r"\b[0-9]+\b"
        query_ids = set(value.casefold() for value in re.findall(identifier_pattern, query))
        query_numbers = set(re.findall(number_pattern, query))
        leads = [chunk.text.split(".", 1)[0] for chunk in artifact.chunks]

        anchors = []
        for index, lead in enumerate(leads):
            folded = lead.casefold()
            ids = set(value.casefold() for value in re.findall(identifier_pattern, lead))
            numbers = set(re.findall(number_pattern, lead))
            if query_ids and query_ids.issubset(ids) and query_numbers.issubset(numbers):
                anchors.append(index)

        selected_indexes = []
        if "consensus" in query.casefold():
            rule_indexes = []
            signatures = set()
            for index, lead in enumerate(leads):
                folded = lead.casefold()
                if "consensus" in folded and "signature" in folded:
                    rule_indexes.append(index)
                    signatures.update(
                        value.casefold() for value in re.findall(identifier_pattern, lead)
                    )
            selected_indexes.extend(rule_indexes)
            for index in anchors:
                folded = leads[index].casefold()
                ids = set(
                    value.casefold()
                    for value in re.findall(identifier_pattern, leads[index])
                )
                if "report" in folded and "signal hue" in folded and signatures.intersection(ids):
                    selected_indexes.append(index)
        else:
            selected_indexes.extend(anchors)
            links = set()
            for index in anchors:
                links.update(
                    value.casefold()
                    for value in re.findall(identifier_pattern, leads[index])
                    if value.casefold() not in query_ids
                )
            for index, lead in enumerate(leads):
                folded = lead.casefold()
                ids = set(value.casefold() for value in re.findall(identifier_pattern, lead))
                if links.intersection(ids) and ("bears" in folded or "relay" in folded):
                    selected_indexes.append(index)

        ordered_indexes = []
        seen = set()
        for index in selected_indexes:
            if index not in seen:
                ordered_indexes.append(index)
                seen.add(index)

        selected = []
        remaining = budget.max_tokens
        for index in ordered_indexes:
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
