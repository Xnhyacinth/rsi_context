from __future__ import annotations

import pytest

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_SPEC_V1
from rsicontext.policy import (
    Artifact,
    Budget,
    CompressedNote,
    ContextPack,
    DocumentChunk,
    PolicySpecV1Interpreter,
    substitute_extractive_notes,
)


def _chunk(chunk_id: str, text: str, tokens: int) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id="doc",
        start=0,
        end=len(text),
        text=text,
        token_count=tokens,
    )


def test_substitute_extractive_notes_replaces_selected_sources_when_shorter() -> None:
    span = _chunk("ck-a", "long padded score statement filler " * 20, 80)
    other = _chunk("ck-b", "binding text", 10)
    note = CompressedNote("nt-a", ("ck-a",), "Dossier ds-abc records score 91", 6)
    artifact = Artifact("doc", chunks=(span, other), notes=(note,))
    pack = ContextPack(spans=(span, other), ordering=("ck-a", "ck-b"), token_count=90)
    budget = Budget(max_tokens=90, max_free_text_tokens=16)

    replaced = substitute_extractive_notes(pack, artifact, budget)

    assert {span.chunk_id for span in replaced.spans} == {"ck-b"}
    assert replaced.notes == (note,)
    assert replaced.ordering == ("nt-a", "ck-b")
    assert replaced.token_count == 16
    replaced.validate(artifact, budget)


def test_substitute_extractive_notes_skips_unselected_sources_and_zero_free_text() -> None:
    span = _chunk("ck-a", "score chunk", 40)
    note = CompressedNote("nt-a", ("ck-a",), "short", 1)
    artifact = Artifact("doc", chunks=(span,), notes=(note,))
    pack = ContextPack(spans=(span,), ordering=("ck-a",), token_count=40)

    unchanged = substitute_extractive_notes(pack, artifact, Budget(max_tokens=40))
    skipped = substitute_extractive_notes(
        ContextPack(), artifact, Budget(max_tokens=40, max_free_text_tokens=8)
    )

    assert unchanged.spans == pack.spans
    assert unchanged.notes == ()
    assert skipped.notes == ()
    assert skipped.spans == ()


def test_forged_notes_are_not_trusted_artifact_members() -> None:
    span = _chunk("ck-a", "score chunk", 40)
    artifact = Artifact("doc", chunks=(span,))
    with pytest.raises(ValueError, match="trusted"):
        ContextPack(
            notes=(CompressedNote("forged", ("ck-a",), "ANSWER: nd-deadbeef0000", 3),),
            ordering=("forged",),
            token_count=3,
        ).validate(artifact, Budget(max_tokens=40, max_free_text_tokens=8))


def test_policy_spec_v1_leaves_notes_unselected_at_zero_free_text() -> None:
    span = _chunk("ck-a", "needle long padded score statement filler", 8)
    note = CompressedNote("nt-a", ("ck-a",), "short note", 2)
    artifact = Artifact("doc", chunks=(span,), notes=(note,))
    pack = (
        PolicySpecV1Interpreter()
        .materialize(HAND_HYBRID_SPEC_V1)
        .assemble(artifact, "needle", Budget(max_tokens=8))
    )

    assert pack.spans == (span,)
    assert pack.notes == ()
    assert pack.token_count == 8
