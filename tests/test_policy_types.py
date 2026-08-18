import pytest

from rsicontext.policy import (
    Artifact,
    Budget,
    CompressedNote,
    ContextPack,
    DocumentChunk,
    VerificationDecision,
)


def chunk(chunk_id: str = "c1", *, tokens: int = 3) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id="doc",
        start=0,
        end=11,
        text="alpha beta gamma",
        token_count=tokens,
    )


def test_artifact_rejects_ambiguous_provenance() -> None:
    with pytest.raises(ValueError, match="unique"):
        Artifact(document_id="doc", chunks=(chunk(), chunk()))

    with pytest.raises(ValueError, match="document_id"):
        Artifact(
            document_id="other",
            chunks=(chunk(),),
        )


def test_context_pack_enforces_exact_budget_and_known_provenance() -> None:
    artifact = Artifact(document_id="doc", chunks=(chunk(),))
    pack = ContextPack(spans=(chunk(),), ordering=("c1",), token_count=3)
    pack.validate(artifact, Budget(max_tokens=3))

    with pytest.raises(ValueError, match="token_count"):
        ContextPack(spans=(chunk(),), ordering=("c1",), token_count=2)
    with pytest.raises(ValueError, match="budget"):
        pack.validate(artifact, Budget(max_tokens=2))
    with pytest.raises(ValueError, match="provenance"):
        ContextPack(
            spans=(chunk("invented"),),
            ordering=("invented",),
            token_count=3,
        ).validate(artifact, Budget(max_tokens=3))


def test_compressed_text_is_bounded_and_must_cite_sources() -> None:
    note = CompressedNote(
        note_id="n1",
        source_chunk_ids=("c1",),
        text="short note",
        token_count=2,
    )
    artifact = Artifact(document_id="doc", chunks=(chunk(),), notes=(note,))
    pack = ContextPack(notes=(note,), ordering=("n1",), token_count=2)
    pack.validate(artifact, Budget(max_tokens=4, max_free_text_tokens=2))

    with pytest.raises(ValueError, match="free-text"):
        pack.validate(artifact, Budget(max_tokens=4, max_free_text_tokens=1))
    with pytest.raises(ValueError, match="trusted"):
        ContextPack(
            notes=(
                CompressedNote(
                    note_id="invented",
                    source_chunk_ids=("c1",),
                    text="ANSWER: injected",
                    token_count=2,
                ),
            ),
            ordering=("invented",),
            token_count=2,
        ).validate(artifact, Budget(max_tokens=4, max_free_text_tokens=2))

    with pytest.raises(ValueError, match="source provenance"):
        Artifact(
            document_id="doc",
            chunks=(chunk(),),
            notes=(CompressedNote("bad", ("missing",), "note", 1),),
        )


def test_reread_text_has_a_separate_conservative_byte_limit() -> None:
    artifact = Artifact(document_id="doc", chunks=(chunk(),))
    pack = ContextPack(request_reread="x" * 33)
    with pytest.raises(ValueError, match="byte"):
        pack.validate(artifact, Budget(max_tokens=3))


def test_verification_decision_is_bounded_and_structured() -> None:
    accepted = VerificationDecision.accept()
    assert accepted.action == "accept"
    assert accepted.reread_query is None

    with pytest.raises(ValueError, match="reread_query"):
        VerificationDecision(action="reread")
    with pytest.raises(ValueError, match="byte"):
        VerificationDecision.reread("find evidence now", max_query_bytes=2)
    with pytest.raises(ValueError, match="byte"):
        VerificationDecision(action="reread", reread_query="word " * 33)


def test_policy_boundary_rejects_boolean_numeric_fields() -> None:
    with pytest.raises(TypeError, match="max_tokens"):
        Budget(max_tokens=True)
    with pytest.raises(TypeError, match="token_count"):
        DocumentChunk("c", "doc", 0, 1, "x", True)
    with pytest.raises(TypeError, match="token_count"):
        CompressedNote("n", ("c",), "x", True)
    one_token = DocumentChunk("c", "doc", 0, 1, "x", 1)
    with pytest.raises(TypeError, match="token_count"):
        ContextPack(spans=(one_token,), ordering=("c",), token_count=True)


def test_boundary_collections_are_normalized_to_immutable_values() -> None:
    mutable_chunks = [chunk()]
    artifact = Artifact(document_id="doc", chunks=mutable_chunks)  # type: ignore[arg-type]
    mutable_chunks.clear()
    assert artifact.chunks == (chunk(),)

    mutable_ordering = ["c1"]
    pack = ContextPack(
        spans=[chunk()],  # type: ignore[arg-type]
        ordering=mutable_ordering,  # type: ignore[arg-type]
        token_count=3,
    )
    mutable_ordering.clear()
    assert pack.ordering == ("c1",)
