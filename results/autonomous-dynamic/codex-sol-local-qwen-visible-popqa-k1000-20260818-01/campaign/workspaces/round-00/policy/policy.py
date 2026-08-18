"""Query-type-aware lexical retrieval of original evidence chunks."""

import re

from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk


def _words(text: str) -> tuple[str, ...]:
    return tuple(word.casefold() for word in re.findall(r"[\w]+", text))


def _subject(query: str) -> tuple[str, ...]:
    ignored = {
        "a", "an", "are", "birth", "born", "death", "did", "died", "do",
        "does", "genre", "is", "located", "location", "nationality", "occupation",
        "of", "profession", "the", "to", "was", "were", "what", "when", "where",
        "which", "who", "whose",
    }
    return tuple(word for word in _words(query) if word not in ignored)


def _cues(query_words: set[str]) -> set[str]:
    groups = (
        (("genre",), ("band", "music", "musical", "pop", "punk", "rock", "style")),
        (("occupation", "profession"), ("actor", "artist", "author", "composer", "director", "poet", "politician", "singer", "writer")),
        (("born", "birth"), ("born", "birth")),
        (("died", "death"), ("died", "death")),
        (("nationality",), ("american", "british", "canadian", "english", "french", "german", "irish", "nationality")),
        (("located", "location", "where"), ("city", "country", "located", "location")),
    )
    result = set()
    for triggers, values in groups:
        if query_words & set(triggers):
            result.update(values)
    return result


class Policy:
    """Rank exact subjects, then use expected answer vocabulary to resolve ties."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        query_words = set(_words(query))
        subject = _subject(query)
        subject_set = set(subject)
        phrase = " ".join(subject)
        cues = _cues(query_words)

        def score(index: int) -> tuple[int, int, int, int]:
            chunk = artifact.chunks[index]
            words = _words(chunk.text)
            word_set = set(words)
            folded = " ".join(words)
            lead = set(_words(chunk.text.partition("\n")[0]))
            overlap = len(subject_set & word_set)
            exact = int(bool(phrase) and phrase in folded)
            title_overlap = len(subject_set & lead)
            cue_matches = len(cues & word_set)
            value = 40 * exact + 12 * title_overlap + 5 * overlap + 3 * cue_matches
            return value, exact, cue_matches, overlap

        ranked = sorted(
            range(len(artifact.chunks)),
            key=lambda index: (*(-value for value in score(index)), index),
        )
        selected: list[DocumentChunk] = []
        remaining = budget.max_tokens
        for index in ranked:
            if score(index)[0] <= 0:
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
            abstain=not spans,
        )
        pack.validate(artifact, budget)
        return pack
