"""Immutable boundary types for context policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_MAX_REREAD_QUERY_BYTES = 32


def _require_nonempty(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value:
        raise ValueError(f"{field} must not be empty")


def _require_nonnegative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A source span whose identity and offsets establish its provenance."""

    chunk_id: str
    document_id: str
    start: int
    end: int
    text: str
    token_count: int
    role: str = "source"

    def __post_init__(self) -> None:
        _require_nonempty(self.chunk_id, "chunk_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonnegative_integer(self.start, "start")
        _require_nonnegative_integer(self.end, "end")
        _require_nonnegative_integer(self.token_count, "token_count")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        _require_nonempty(self.role, "role")
        if self.end < self.start:
            raise ValueError("chunk offsets must satisfy 0 <= start <= end")


@dataclass(frozen=True, slots=True)
class Artifact:
    """Query-independent, immutable policy input."""

    document_id: str
    chunks: tuple[DocumentChunk, ...] = ()
    notes: tuple[CompressedNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunks", tuple(self.chunks))
        object.__setattr__(self, "notes", tuple(self.notes))
        if any(not isinstance(chunk, DocumentChunk) for chunk in self.chunks):
            raise TypeError("artifact chunks must be DocumentChunk values")
        if any(not isinstance(note, CompressedNote) for note in self.notes):
            raise TypeError("artifact notes must be CompressedNote values")
        _require_nonempty(self.document_id, "document_id")
        ids = [chunk.chunk_id for chunk in self.chunks] + [note.note_id for note in self.notes]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk and note ids must be unique within an artifact")
        if any(chunk.document_id != self.document_id for chunk in self.chunks):
            raise ValueError("every chunk document_id must match the artifact")
        known_chunks = frozenset(chunk.chunk_id for chunk in self.chunks)
        if any(
            source_id not in known_chunks
            for note in self.notes
            for source_id in note.source_chunk_ids
        ):
            raise ValueError("note source provenance must be present in the artifact")

    @property
    def chunk_ids(self) -> frozenset[str]:
        return frozenset(chunk.chunk_id for chunk in self.chunks)


@dataclass(frozen=True, slots=True)
class Budget:
    """Hard semantic-context limits; all limits are inclusive."""

    max_tokens: int
    max_free_text_tokens: int = 0
    max_chunks: int | None = None

    def __post_init__(self) -> None:
        _require_nonnegative_integer(self.max_tokens, "max_tokens")
        _require_nonnegative_integer(self.max_free_text_tokens, "max_free_text_tokens")
        if self.max_chunks is not None:
            _require_nonnegative_integer(self.max_chunks, "max_chunks")
        if self.max_free_text_tokens > self.max_tokens:
            raise ValueError("free-text budget cannot exceed total token budget")


@dataclass(frozen=True, slots=True)
class CompressedNote:
    """Evaluator-produced compressed text tied to one or more source spans."""

    note_id: str
    source_chunk_ids: tuple[str, ...]
    text: str
    token_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_chunk_ids", tuple(self.source_chunk_ids))
        _require_nonempty(self.note_id, "note_id")
        if not self.source_chunk_ids:
            raise ValueError("compressed notes require source provenance")
        if len(self.source_chunk_ids) != len(set(self.source_chunk_ids)):
            raise ValueError("source provenance ids must be unique")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        _require_nonnegative_integer(self.token_count, "token_count")


@dataclass(frozen=True, slots=True)
class ContextPack:
    """The only semantic context a policy may pass to a frozen reader."""

    spans: tuple[DocumentChunk, ...] = ()
    notes: tuple[CompressedNote, ...] = ()
    ordering: tuple[str, ...] = ()
    token_count: int = 0
    abstain: bool = False
    request_reread: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "spans", tuple(self.spans))
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "ordering", tuple(self.ordering))
        if any(not isinstance(span, DocumentChunk) for span in self.spans):
            raise TypeError("context spans must be DocumentChunk values")
        if any(not isinstance(note, CompressedNote) for note in self.notes):
            raise TypeError("context notes must be CompressedNote values")
        _require_nonnegative_integer(self.token_count, "token_count")
        if not isinstance(self.abstain, bool):
            raise TypeError("abstain must be a boolean")
        if self.request_reread is not None and not isinstance(self.request_reread, str):
            raise TypeError("request_reread must be a string or null")
        ids = tuple(span.chunk_id for span in self.spans) + tuple(
            note.note_id for note in self.notes
        )
        if len(ids) != len(set(ids)):
            raise ValueError("context member ids must be unique")
        if len(self.ordering) != len(ids) or set(self.ordering) != set(ids):
            raise ValueError("ordering must contain every context member exactly once")
        actual_tokens = sum(span.token_count for span in self.spans) + sum(
            note.token_count for note in self.notes
        )
        if self.token_count != actual_tokens:
            raise ValueError(
                f"token_count must equal member total ({actual_tokens}), got {self.token_count}"
            )

    def validate(self, artifact: Artifact, budget: Budget) -> None:
        """Reject invented provenance and any hard-budget overrun."""

        known_ids = artifact.chunk_ids
        if any(span.chunk_id not in known_ids for span in self.spans):
            raise ValueError("span provenance is not present in the artifact")
        original = {chunk.chunk_id: chunk for chunk in artifact.chunks}
        if any(span != original.get(span.chunk_id) for span in self.spans):
            raise ValueError("span provenance does not match the original source span")
        if any(
            source_id not in known_ids for note in self.notes for source_id in note.source_chunk_ids
        ):
            raise ValueError("note provenance is not present in the artifact")
        trusted_notes = {note.note_id: note for note in artifact.notes}
        if any(note != trusted_notes.get(note.note_id) for note in self.notes):
            raise ValueError("compressed note is not a trusted evaluator-produced artifact member")
        if self.token_count > budget.max_tokens:
            raise ValueError("context pack exceeds the total token budget")
        free_text_tokens = sum(note.token_count for note in self.notes)
        if free_text_tokens > budget.max_free_text_tokens:
            raise ValueError("context pack exceeds the free-text token budget")
        if (
            self.request_reread is not None
            and len(self.request_reread.encode("utf-8")) > _MAX_REREAD_QUERY_BYTES
        ):
            raise ValueError("reread_query exceeds the conservative byte limit")
        if budget.max_chunks is not None and len(self.spans) > budget.max_chunks:
            raise ValueError("context pack exceeds the chunk budget")

    def ordered_text(self) -> tuple[str, ...]:
        by_id = {span.chunk_id: span.text for span in self.spans}
        by_id.update({note.note_id: note.text for note in self.notes})
        return tuple(by_id[item_id] for item_id in self.ordering)


DecisionAction = Literal["accept", "abstain", "reread"]


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    """A structured verifier result that cannot carry a replacement answer."""

    action: DecisionAction
    reread_query: str | None = None

    def __post_init__(self) -> None:
        if self.action not in ("accept", "abstain", "reread"):
            raise ValueError(f"unsupported verification action: {self.action}")
        if self.action == "reread" and not self.reread_query:
            raise ValueError("reread_query is required for a reread decision")
        if self.action != "reread" and self.reread_query is not None:
            raise ValueError("reread_query is only allowed for a reread decision")
        if (
            self.reread_query is not None
            and len(self.reread_query.encode("utf-8")) > _MAX_REREAD_QUERY_BYTES
        ):
            raise ValueError("reread_query exceeds the conservative byte limit")

    @classmethod
    def accept(cls) -> VerificationDecision:
        return cls("accept")

    @classmethod
    def abstain(cls) -> VerificationDecision:
        return cls("abstain")

    @classmethod
    def reread(
        cls, query: str, *, max_query_bytes: int = _MAX_REREAD_QUERY_BYTES
    ) -> VerificationDecision:
        _require_nonnegative_integer(max_query_bytes, "max_query_bytes")
        if len(query.encode("utf-8")) > max_query_bytes:
            raise ValueError("reread_query exceeds the conservative byte limit")
        return cls("reread", query)
