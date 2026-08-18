"""Gold-evidence interventions for causal context audits."""

from typing import Literal

from rsicontext.policy import Artifact

from .core import EvaluationItem

CausalCondition = Literal["full", "gold_only", "gold_drop", "no_context"]


def causal_artifacts(item: EvaluationItem) -> dict[CausalCondition, Artifact]:
    """Create source-preserving keep/drop variants without synthesizing evidence."""

    gold = item.gold_chunk_ids
    full = item.artifact
    gold_notes = tuple(note for note in full.notes if set(note.source_chunk_ids).issubset(gold))
    dropped_chunks = full.chunk_ids - gold
    dropped_notes = tuple(
        note for note in full.notes if set(note.source_chunk_ids).issubset(dropped_chunks)
    )
    return {
        "full": full,
        "gold_only": Artifact(
            full.document_id,
            tuple(chunk for chunk in full.chunks if chunk.chunk_id in gold),
            gold_notes,
        ),
        "gold_drop": Artifact(
            full.document_id,
            tuple(chunk for chunk in full.chunks if chunk.chunk_id not in gold),
            dropped_notes,
        ),
        "no_context": Artifact(full.document_id),
    }
