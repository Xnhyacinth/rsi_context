"""Subject-focused whole-chunk evidence retrieval."""

import math
import re

from rsicontext.policy import ContextPack


class Policy:
    """Rank exact subjects and titles ahead of broad lexical matches."""

    def assemble(self, artifact, query, budget):
        words = re.findall(r"[\w]+", query.casefold())
        stopwords = {
            "a",
            "an",
            "are",
            "country",
            "genre",
            "in",
            "is",
            "of",
            "occupation",
            "the",
            "what",
            "where",
            "which",
            "who",
            "whose",
        }
        subject_words = [word for word in words if word not in stopwords]
        subject = " ".join(subject_words)
        documents = [re.findall(r"[\w]+", chunk.text.casefold()) for chunk in artifact.chunks]
        document_count = len(documents)
        frequencies = {}
        for terms in documents:
            for term in set(terms):
                frequencies[term] = frequencies.get(term, 0) + 1

        ranked = []
        for index, chunk in enumerate(artifact.chunks):
            text = chunk.text.casefold()
            title = text.split("\n", 1)[0].strip()
            counts = {}
            for term in documents[index]:
                counts[term] = counts.get(term, 0) + 1
            score = 0.0
            for term in subject_words:
                count = counts.get(term, 0)
                if count:
                    score += count * math.log(
                        1.0 + document_count / frequencies.get(term, 1)
                    )
            if subject:
                if title == subject:
                    score += 40.0
                elif subject in title:
                    score += 24.0
                elif subject in text:
                    score += 8.0
            if subject_words and all(term in title.split() for term in subject_words):
                score += 12.0
            ranked.append((-score, index, chunk))

        selected = []
        remaining = budget.max_tokens
        chunk_limit = budget.max_chunks
        if chunk_limit is None or chunk_limit > 32:
            chunk_limit = 32
        for _, _, chunk in sorted(ranked):
            if len(selected) >= chunk_limit:
                break
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
