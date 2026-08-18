"""Evaluator-owned extractive notes; policies may select them but cannot mint them."""

from __future__ import annotations

from .types import Artifact, Budget, CompressedNote, ContextPack, DocumentChunk


def substitute_extractive_notes(
    pack: ContextPack, artifact: Artifact, budget: Budget
) -> ContextPack:
    """Replace selected source spans with shorter trusted notes that cite only them."""

    if budget.max_free_text_tokens <= 0 or not artifact.notes:
        return pack
    selected = {span.chunk_id: span for span in pack.spans}
    by_source: dict[str, CompressedNote] = {}
    for note in artifact.notes:
        if len(note.source_chunk_ids) != 1:
            continue
        source_id = note.source_chunk_ids[0]
        if source_id in selected and note.token_count < selected[source_id].token_count:
            by_source[source_id] = note
    if not by_source:
        return pack

    spans: list[DocumentChunk] = []
    notes: list[CompressedNote] = list(pack.notes)
    replacements = {source_id: note.note_id for source_id, note in by_source.items()}
    for span in pack.spans:
        replacement = by_source.get(span.chunk_id)
        if replacement is None:
            spans.append(span)
            continue
        notes.append(replacement)
    ordering = tuple(replacements.get(item_id, item_id) for item_id in pack.ordering)
    token_count = sum(span.token_count for span in spans) + sum(note.token_count for note in notes)
    replaced = ContextPack(
        spans=tuple(spans),
        notes=tuple(notes),
        ordering=ordering,
        token_count=token_count,
        abstain=pack.abstain,
        request_reread=pack.request_reread,
    )
    if (
        token_count > budget.max_tokens
        or sum(note.token_count for note in notes) > budget.max_free_text_tokens
    ):
        return pack
    replaced.validate(artifact, budget)
    return replaced
