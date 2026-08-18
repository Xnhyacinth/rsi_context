"""Compile HELMET/RULER needle-in-a-haystack records into packable artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from rsicontext.datasets.helmet_rag import split_passage
from rsicontext.eval import EvaluationItem
from rsicontext.policy import Artifact, DocumentChunk


@dataclass(frozen=True, slots=True)
class RulerNiahRecord:
    """One RULER/HELMET recall item: haystack context plus a keyed needle."""

    item_id: str
    query: str
    answer: str
    context: str
    needle_key: str

    def __post_init__(self) -> None:
        if not self.item_id or not isinstance(self.item_id, str):
            raise ValueError("item_id must be a non-empty string")
        if not self.query or not isinstance(self.query, str):
            raise ValueError("query must be a non-empty string")
        if not self.answer or not isinstance(self.answer, str):
            raise ValueError("answer must be a non-empty string")
        if not self.context.strip() or not isinstance(self.context, str):
            raise ValueError("context must be non-empty text")
        if not self.needle_key.strip() or not isinstance(self.needle_key, str):
            raise ValueError("needle_key must be a non-empty string")


def ruler_niah_record(raw: Mapping[str, object], *, item_id: str) -> RulerNiahRecord:
    """Map HELMET RULER jsonl objects into a pack record."""

    context = raw.get("context")
    query_key = raw.get("query")
    answers = raw.get("answer")
    prompt = raw.get("input")
    if not isinstance(context, str) or not context.strip():
        raise ValueError("RULER record requires context")
    if not isinstance(query_key, str) or not query_key.strip():
        raise ValueError("RULER record requires query")
    if isinstance(answers, list) and answers and isinstance(answers[0], str):
        answer = answers[0]
    elif isinstance(answers, str) and answers.strip():
        answer = answers
    else:
        raise ValueError("RULER record requires a string answer")
    question = query_key
    if isinstance(prompt, str) and context in prompt:
        suffix = prompt.split(context, maxsplit=1)[1].strip()
        if suffix:
            question = suffix
    return RulerNiahRecord(
        item_id=item_id,
        query=question,
        answer=answer,
        context=context,
        needle_key=query_key,
    )


def json_kv_record(raw: Mapping[str, object], *, item_id: str) -> RulerNiahRecord:
    """Map HELMET JSON KV objects onto the same keyed-haystack record as RULER NIAH."""

    context = raw.get("context")
    question = raw.get("question")
    answer = raw.get("answer")
    if not isinstance(context, str) or not context.strip():
        raise ValueError("JSON KV record requires context")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("JSON KV record requires question")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("JSON KV record requires a string answer")
    return RulerNiahRecord(
        item_id=item_id,
        query=question,
        answer=answer,
        context=context,
        needle_key=question,
    )


def compile_ruler_niah(
    record: RulerNiahRecord,
    *,
    token_counter: Callable[[str], int],
    tokens_per_chunk: int = 512,
    split_parts: Callable[[str], tuple[str, ...]] | None = None,
) -> EvaluationItem:
    """Chunk the haystack; gold spans mention both the needle key and the answer."""

    if not isinstance(tokens_per_chunk, int) or isinstance(tokens_per_chunk, bool):
        raise TypeError("tokens_per_chunk must be an integer")
    if tokens_per_chunk <= 0:
        raise ValueError("tokens_per_chunk must be positive")
    parts = (
        split_parts(record.context)
        if split_parts is not None
        else split_passage(record.context, token_counter, tokens_per_chunk)
    )
    chunks: list[DocumentChunk] = []
    cursor = 0
    key = record.needle_key.casefold()
    answer = record.answer.casefold()
    gold: set[str] = set()
    for index, part in enumerate(parts):
        if not part.strip():
            continue
        token_count = token_counter(part)
        if not isinstance(token_count, int) or isinstance(token_count, bool) or token_count <= 0:
            raise ValueError("target tokenizer counts must be positive integers")
        chunk_id = f"nk-{index:04d}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=f"ruler-{record.item_id}",
                start=cursor,
                end=cursor + len(part),
                text=part,
                token_count=token_count,
            )
        )
        folded = part.casefold()
        if key in folded and answer in folded:
            gold.add(chunk_id)
        cursor += len(part) + 1
    if not chunks:
        raise ValueError("RULER context produced no chunks")
    return EvaluationItem(
        item_id=record.item_id,
        query=record.query,
        answer=record.answer,
        artifact=Artifact(document_id=f"ruler-{record.item_id}", chunks=tuple(chunks)),
        gold_chunk_ids=frozenset(gold),
    )
