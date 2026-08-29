"""Strict MuSiQue-Answerable parsing with evaluator-only labels."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from rsicontext.datasets.helmet_rag import split_passage
from rsicontext.policy import Artifact, DocumentChunk

_RECORD_FIELDS = frozenset(
    {
        "id",
        "paragraphs",
        "question",
        "question_decomposition",
        "answer",
        "answer_aliases",
        "answerable",
    }
)
_PARAGRAPH_FIELDS = frozenset({"idx", "title", "paragraph_text", "is_supporting"})
_STEP_FIELDS = frozenset({"id", "question", "answer", "paragraph_support_idx"})


class MuSiQueDataError(ValueError):
    """Raised when an official-format MuSiQue record violates the adapter contract."""


@dataclass(frozen=True, slots=True)
class MuSiQueParagraph:
    idx: int
    title: str
    text: str
    is_supporting: bool


@dataclass(frozen=True, slots=True)
class MuSiQueStep:
    step_id: str
    question: str
    answer: str
    paragraph_support_idx: int


@dataclass(frozen=True, slots=True)
class MuSiQueRecord:
    item_id: str
    question: str
    paragraphs: tuple[MuSiQueParagraph, ...]
    steps: tuple[MuSiQueStep, ...]
    answer: str
    answer_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MuSiQuePolicyItem:
    """Label-free input allowed to cross into the context-policy workspace."""

    item_id: str
    query: str
    artifact: Artifact


@dataclass(frozen=True, slots=True)
class MuSiQueEvaluatorItem:
    """Evaluator-side labels and causal metadata for one policy input."""

    policy_item: MuSiQuePolicyItem
    answer: str
    answer_aliases: tuple[str, ...]
    gold_chunk_ids: frozenset[str]
    supporting_paragraph_indices: frozenset[int]
    steps: tuple[MuSiQueStep, ...]

    @property
    def references(self) -> tuple[str, ...]:
        """All official answer strings retained inside the evaluator boundary."""

        return (self.answer, *self.answer_aliases)


def _record(raw: object, expected_fields: frozenset[str], location: str) -> Mapping[str, object]:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise MuSiQueDataError(f"{location} must be a JSON object with string keys")
    value = cast(dict[str, object], raw)
    if set(value) != expected_fields:
        missing = sorted(expected_fields - set(value))
        unexpected = sorted(set(value) - expected_fields)
        raise MuSiQueDataError(
            f"{location} has unexpected schema; missing={missing}, unexpected={unexpected}"
        )
    return value


def _string(value: object, field: str, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MuSiQueDataError(f"{location}.{field} must be a non-empty string")
    return value


def _index(value: object, field: str, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MuSiQueDataError(f"{location}.{field} must be a non-negative integer")
    return value


def _paragraphs(raw: object) -> tuple[MuSiQueParagraph, ...]:
    if not isinstance(raw, list) or not raw:
        raise MuSiQueDataError("record.paragraphs must be a non-empty list")
    paragraphs: list[MuSiQueParagraph] = []
    for offset, item in enumerate(raw):
        location = f"record.paragraphs[{offset}]"
        value = _record(item, _PARAGRAPH_FIELDS, location)
        idx = _index(value["idx"], "idx", location)
        if idx != offset:
            raise MuSiQueDataError("paragraph idx values must be contiguous and source ordered")
        is_supporting = value["is_supporting"]
        if not isinstance(is_supporting, bool):
            raise MuSiQueDataError(f"{location}.is_supporting must be a boolean")
        paragraphs.append(
            MuSiQueParagraph(
                idx=idx,
                title=_string(value["title"], "title", location),
                text=_string(value["paragraph_text"], "paragraph_text", location),
                is_supporting=is_supporting,
            )
        )
    return tuple(paragraphs)


def _steps(raw: object) -> tuple[MuSiQueStep, ...]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise MuSiQueDataError("record.question_decomposition must contain at least two steps")
    steps: list[MuSiQueStep] = []
    for offset, item in enumerate(raw):
        location = f"record.question_decomposition[{offset}]"
        value = _record(item, _STEP_FIELDS, location)
        steps.append(
            MuSiQueStep(
                step_id=_string(value["id"], "id", location),
                question=_string(value["question"], "question", location),
                answer=_string(value["answer"], "answer", location),
                paragraph_support_idx=_index(
                    value["paragraph_support_idx"], "paragraph_support_idx", location
                ),
            )
        )
    if len({step.step_id for step in steps}) != len(steps):
        raise MuSiQueDataError("question decomposition ids must be unique")
    return tuple(steps)


def _aliases(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise MuSiQueDataError("record.answer_aliases must be a list")
    aliases = tuple(
        _string(alias, "answer_aliases", f"record.answer_aliases[{offset}]")
        for offset, alias in enumerate(raw)
    )
    if len(aliases) != len(set(aliases)):
        raise MuSiQueDataError("answer aliases must be unique")
    return aliases


def musique_answerable_record(raw: Mapping[str, object]) -> MuSiQueRecord:
    """Parse one official MuSiQue-Answerable row and validate causal provenance."""

    value = _record(raw, _RECORD_FIELDS, "record")
    if value["answerable"] is not True:
        raise MuSiQueDataError("only rows from the MuSiQue answerable split are supported")
    paragraphs = _paragraphs(value["paragraphs"])
    steps = _steps(value["question_decomposition"])
    supporting = frozenset(paragraph.idx for paragraph in paragraphs if paragraph.is_supporting)
    step_support = frozenset(step.paragraph_support_idx for step in steps)
    if not supporting or supporting != step_support:
        raise MuSiQueDataError("paragraph and question-decomposition support indices must match")
    return MuSiQueRecord(
        item_id=_string(value["id"], "id", "record"),
        question=_string(value["question"], "question", "record"),
        paragraphs=paragraphs,
        steps=steps,
        answer=_string(value["answer"], "answer", "record"),
        answer_aliases=_aliases(value["answer_aliases"]),
    )


def compile_musique_answerable(
    record: MuSiQueRecord,
    *,
    token_counter: Callable[[str], int],
    tokens_per_chunk: int = 512,
) -> MuSiQueEvaluatorItem:
    """Compile source-ordered paragraphs without exposing evaluator labels to policy code."""

    if not isinstance(tokens_per_chunk, int) or isinstance(tokens_per_chunk, bool):
        raise TypeError("tokens_per_chunk must be an integer")
    if tokens_per_chunk <= 0:
        raise ValueError("tokens_per_chunk must be positive")
    document_id = f"musique-{record.item_id}"
    supporting = frozenset(
        paragraph.idx for paragraph in record.paragraphs if paragraph.is_supporting
    )
    chunks: list[DocumentChunk] = []
    gold_chunk_ids: set[str] = set()
    cursor = 0
    for paragraph in record.paragraphs:
        source = f"{paragraph.title}\n{paragraph.text}"
        for window_index, text in enumerate(split_passage(source, token_counter, tokens_per_chunk)):
            token_count = token_counter(text)
            if (
                not isinstance(token_count, int)
                or isinstance(token_count, bool)
                or token_count <= 0
            ):
                raise ValueError("target tokenizer counts must be positive integers")
            chunk_id = f"musique:p{paragraph.idx:04d}:w{window_index:04d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    start=cursor,
                    end=cursor + len(text),
                    text=text,
                    token_count=token_count,
                )
            )
            if paragraph.idx in supporting:
                gold_chunk_ids.add(chunk_id)
            cursor += len(text) + 1
    artifact = Artifact(document_id=document_id, chunks=tuple(chunks))
    policy_item = MuSiQuePolicyItem(record.item_id, record.question, artifact)
    return MuSiQueEvaluatorItem(
        policy_item=policy_item,
        answer=record.answer,
        answer_aliases=record.answer_aliases,
        gold_chunk_ids=frozenset(gold_chunk_ids),
        supporting_paragraph_indices=supporting,
        steps=record.steps,
    )
