"""Compile HELMET-style RAG records into provenance-preserving artifacts.

This is a transfer adapter, not the official HELMET scorer. Frozen ``H`` packers
run on the compiled ``EvaluationItem``; researcher code does not answer.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from rsicontext.eval import EvaluationItem
from rsicontext.policy import Artifact, DocumentChunk


class EncodedWindowTokenizer(Protocol):
    """Minimal encode/decode surface for target-tokenizer window chunking."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]: ...

    def decode(self, token_ids: Sequence[int], skip_special_tokens: bool = True) -> str: ...


@dataclass(frozen=True, slots=True)
class HelmetRagRecord:
    """One RAG-style question with retrieved passages."""

    item_id: str
    query: str
    answer: str
    passages: tuple[str, ...]
    gold_passage_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "passages", tuple(self.passages))
        object.__setattr__(self, "gold_passage_indices", tuple(self.gold_passage_indices))
        if not self.item_id or not isinstance(self.item_id, str):
            raise ValueError("item_id must be a non-empty string")
        if not self.query or not isinstance(self.query, str):
            raise ValueError("query must be a non-empty string")
        if not self.answer or not isinstance(self.answer, str):
            raise ValueError("answer must be a non-empty string")
        if not self.passages:
            raise ValueError("passages must be non-empty")
        if any(not isinstance(passage, str) or not passage.strip() for passage in self.passages):
            raise ValueError("every passage must be non-empty text")
        indices = self.gold_passage_indices
        if any(
            not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in indices
        ):
            raise ValueError("gold_passage_indices must be non-negative integers")
        if any(index >= len(self.passages) for index in indices):
            raise ValueError("gold_passage_indices must refer to compiled passages")
        if len(indices) != len(set(indices)):
            raise ValueError("gold_passage_indices must be unique")


def _ctx_has_answer(ctx: Mapping[str, object]) -> bool:
    flag = ctx.get("has_answer")
    return flag is True or flag == 1


def _kilt_positive_keys(raw_positives: object) -> tuple[frozenset[int], frozenset[tuple[str, str]]]:
    if raw_positives is None:
        return frozenset(), frozenset()
    if not isinstance(raw_positives, list):
        raise ValueError("positive_ctxs must be a list when present")
    ids: set[int] = set()
    spans: set[tuple[str, str]] = set()
    for ctx in raw_positives:
        if not isinstance(ctx, dict):
            raise ValueError("each positive ctx must be an object")
        title = ctx.get("title") or ""
        text = ctx.get("text") or ""
        if not isinstance(title, str) or not isinstance(text, str):
            raise ValueError("positive ctx title and text must be strings")
        psg_id = ctx.get("psg_id")
        if psg_id is None:
            psg_id = ctx.get("id")
        if isinstance(psg_id, int) and not isinstance(psg_id, bool):
            ids.add(psg_id)
        if text.strip():
            spans.add((title.strip(), text.strip()))
    return frozenset(ids), frozenset(spans)


def _chunk_passage_index(chunk_id: str) -> int:
    parts = chunk_id.split("-")
    if len(parts) != 3 or parts[0] != "ck":
        raise ValueError(f"chunk_id is not a HELMET passage window: {chunk_id}")
    return int(parts[1])


def helmet_kilt_record(raw: Mapping[str, object], *, item_id: str) -> HelmetRagRecord:
    """Map HELMET KILT jsonl objects (question / answers / ctxs) into a pack record."""

    question = raw.get("question")
    answers = raw.get("answers")
    ctxs = raw.get("ctxs")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("HELMET KILT record requires a question")
    if not isinstance(answers, list) or not answers or not isinstance(answers[0], str):
        raise ValueError("HELMET KILT record requires string answers")
    if not isinstance(ctxs, list) or not ctxs:
        raise ValueError("HELMET KILT record requires ctxs")
    passages: list[str] = []
    gold_passage_indices: list[int] = []
    positive_ids, positive_spans = _kilt_positive_keys(raw.get("positive_ctxs"))
    for ctx in ctxs:
        if not isinstance(ctx, dict):
            raise ValueError("each ctx must be an object")
        title = ctx.get("title") or ""
        text = ctx.get("text")
        if not isinstance(title, str):
            raise ValueError("ctx title must be a string")
        if not isinstance(text, str) or not text.strip():
            continue
        passages.append(f"{title}\n{text}".strip() if title.strip() else text.strip())
        ctx_id = ctx.get("id")
        if ctx_id is None:
            ctx_id = ctx.get("psg_id")
        span_key = (title.strip(), text.strip())
        if (
            _ctx_has_answer(ctx)
            or (isinstance(ctx_id, int) and ctx_id in positive_ids)
            or span_key in positive_spans
        ):
            gold_passage_indices.append(len(passages) - 1)
    if not passages:
        raise ValueError("HELMET KILT record requires ctxs")
    return HelmetRagRecord(
        item_id,
        question,
        answers[0],
        tuple(passages),
        gold_passage_indices=tuple(gold_passage_indices),
    )


def select_helmet_kilt_records(
    records: Iterable[HelmetRagRecord],
    *,
    limit: int,
    unique_queries: bool = True,
    min_gold_passage_index: int = 0,
) -> tuple[HelmetRagRecord, ...]:
    """Drop HELMET depth clones and prefix-planted gold rows.

    ``dep6`` PopQA/NQ files repeat each question at gold ranks 0/200/400/600/800/999.
    A visible panel must be unique questions, and packing fitness needs gold off the
    retrieval head.
    """

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if (
        not isinstance(min_gold_passage_index, int)
        or isinstance(min_gold_passage_index, bool)
        or min_gold_passage_index < 0
    ):
        raise ValueError("min_gold_passage_index must be a non-negative integer")
    selected: list[HelmetRagRecord] = []
    seen: set[str] = set()
    for record in records:
        if unique_queries and record.query in seen:
            continue
        gold = record.gold_passage_indices
        if gold and min(gold) < min_gold_passage_index:
            continue
        if unique_queries:
            seen.add(record.query)
        selected.append(record)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        raise ValueError("not enough unique HELMET KILT records after gold-rank filtering")
    return tuple(selected)


def ruler_qa_record(raw: Mapping[str, object], *, item_id: str) -> HelmetRagRecord:
    """Map RULER SQuAD-in-haystack records into a single-passage pack record."""

    question = raw.get("question")
    context = raw.get("context")
    outputs = raw.get("outputs")
    if outputs is None:
        outputs = raw.get("answer")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("RULER QA record requires a question")
    if not isinstance(context, str) or not context.strip():
        raise ValueError("RULER QA record requires context")
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], str):
        answer = outputs[0]
    elif isinstance(outputs, str) and outputs.strip():
        answer = outputs
    else:
        raise ValueError("RULER QA record requires a string answer")
    return HelmetRagRecord(item_id, question, answer, (context,))


def compile_helmet_rag(
    record: HelmetRagRecord,
    *,
    token_counter: Callable[[str], int],
    tokens_per_chunk: int = 512,
    split_parts: Callable[[str], tuple[str, ...]] | None = None,
) -> EvaluationItem:
    """Turn passages into 512-token source spans.

    Gold is ``has_answer`` passage windows when those indices are present;
    otherwise it falls back to answer-substring chunks.
    """

    if not isinstance(tokens_per_chunk, int) or isinstance(tokens_per_chunk, bool):
        raise TypeError("tokens_per_chunk must be an integer")
    if tokens_per_chunk <= 0:
        raise ValueError("tokens_per_chunk must be positive")
    document_id = f"hl-{record.item_id}"
    chunks: list[DocumentChunk] = []
    cursor = 0
    splitter = split_parts or (
        lambda passage: split_passage(passage, token_counter, tokens_per_chunk)
    )
    for passage_index, passage in enumerate(record.passages):
        for part_index, part in enumerate(splitter(passage)):
            if not part.strip():
                continue
            token_count = token_counter(part)
            if (
                not isinstance(token_count, int)
                or isinstance(token_count, bool)
                or token_count <= 0
            ):
                raise ValueError("target tokenizer counts must be positive integers")
            chunk_id = f"ck-{passage_index:04d}-{part_index:04d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    start=cursor,
                    end=cursor + len(part),
                    text=part,
                    token_count=token_count,
                )
            )
            cursor += len(part) + 1
    if not chunks:
        raise ValueError("HELMET passages produced no chunks")
    artifact = Artifact(document_id=document_id, chunks=tuple(chunks))
    if record.gold_passage_indices:
        gold_passages = frozenset(record.gold_passage_indices)
        gold = frozenset(
            chunk.chunk_id
            for chunk in chunks
            if _chunk_passage_index(chunk.chunk_id) in gold_passages
        )
    else:
        folded_answer = record.answer.casefold()
        gold = frozenset(
            chunk.chunk_id for chunk in chunks if folded_answer in chunk.text.casefold()
        )
    return EvaluationItem(
        item_id=record.item_id,
        query=record.query,
        answer=record.answer,
        artifact=artifact,
        gold_chunk_ids=gold,
    )


def split_encoded_windows(
    text: str,
    tokenizer: EncodedWindowTokenizer,
    tokens_per_chunk: int,
) -> tuple[str, ...]:
    """Split ``text`` into decoded windows of at most ``tokens_per_chunk`` ids."""

    if not isinstance(tokens_per_chunk, int) or isinstance(tokens_per_chunk, bool):
        raise TypeError("tokens_per_chunk must be an integer")
    if tokens_per_chunk <= 0:
        raise ValueError("tokens_per_chunk must be positive")
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if not token_ids:
        return ()
    parts: list[str] = []
    for start in range(0, len(token_ids), tokens_per_chunk):
        window = token_ids[start : start + tokens_per_chunk]
        part = tokenizer.decode(window, skip_special_tokens=True)
        if part.strip():
            parts.append(part)
    return tuple(parts)


def split_passage(
    passage: str,
    token_counter: Callable[[str], int],
    tokens_per_chunk: int,
) -> tuple[str, ...]:
    words: Sequence[str] = passage.split()
    parts: list[str] = []
    current: list[str] = []
    for word in words:
        if not current:
            if token_counter(word) > tokens_per_chunk:
                raise ValueError("a passage token exceeds the chunk budget")
            current.append(word)
            continue
        candidate = " ".join((*current, word))
        if token_counter(candidate) > tokens_per_chunk:
            parts.append(" ".join(current))
            if token_counter(word) > tokens_per_chunk:
                raise ValueError("a passage token exceeds the chunk budget")
            current = [word]
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return tuple(parts)


_DOC_SPLIT = re.compile(r"(?=Document\s+\d+:)")
_DOC_PREFIX = re.compile(r"^Document\s+\d+:\s*")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_YES_NO = frozenset({"yes", "no"})
_QUERY_STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "to",
        "and",
        "in",
        "is",
        "was",
        "were",
        "for",
        "on",
        "with",
        "by",
        "from",
        "as",
        "at",
        "that",
        "this",
        "it",
        "be",
        "are",
        "or",
        "not",
        "who",
        "what",
        "when",
        "where",
        "which",
        "how",
        "did",
        "does",
        "many",
        "both",
        "same",
    ]
)


def split_ruler_documents(context: str) -> tuple[str, ...]:
    """Split a RULER haystack on ``Document N:`` markers."""

    if not isinstance(context, str) or not context.strip():
        raise ValueError("RULER context must be non-empty text")
    parts = tuple(part.strip() for part in _DOC_SPLIT.split(context) if part.strip())
    if len(parts) <= 1:
        return (context.strip(),)
    return parts


def _folded(text: str) -> str:
    return _NON_ALNUM.sub(" ", text.casefold()).strip()


def _core_title(title: str) -> str:
    return _TRAILING_PAREN.sub("", title).strip()


def _document_title_and_body(block: str) -> tuple[str, str]:
    rest = _DOC_PREFIX.sub("", block, count=1).lstrip("\n")
    first, separator, remainder = rest.partition("\n")
    first = first.strip()
    if first and len(first) <= 80 and not first.endswith((".", "!", "?")):
        return first, remainder.lstrip() if separator else ""
    return "", rest


def ruler_document_title(block: str) -> str:
    """Return a short Wikipedia title line, or empty for untitled RULER paragraphs."""

    if not isinstance(block, str):
        raise TypeError("document block must be a string")
    title, _body = _document_title_and_body(block)
    return title


def _query_overlap(query: str, block: str) -> int:
    return sum(len(token) for token in _query_terms(query) & set(_folded(block).split()))


def _query_terms(query: str) -> set[str]:
    return {
        token for token in _folded(query).split() if token not in _QUERY_STOP and len(token) > 2
    }


def _answer_support_score(query: str, block: str, answer: str) -> tuple[int, int, int]:
    overlap = _query_overlap(query, block)
    folded_block = block.casefold()
    folded_answer = answer.casefold()
    position = folded_block.find(folded_answer)
    if position < 0:
        return (0, overlap, -len(block))
    left = max(0, position - 240)
    window = block[left : position + len(answer) + 240]
    return (_query_overlap(query, window), overlap, -len(block))


def _longest_phrase_hit(words: Sequence[str], folded_query: str) -> float:
    best = -1.0
    for width in range(len(words), 1, -1):
        for start in range(0, len(words) - width + 1):
            phrase = " ".join(words[start : start + width])
            if len(phrase) >= 10 and phrase in folded_query:
                best = max(best, float(len(phrase)))
        if best >= 0:
            break
    return best


def _title_query_score(title: str, query: str) -> float:
    folded_query = _folded(query)
    core = _folded(_core_title(title))
    if len(core) < 4:
        return -1.0
    words = core.split()
    paren = re.search(r"\(([^)]*)\)\s*$", title)
    inner = _folded(paren.group(1)) if paren is not None else ""
    if core in folded_query:
        if len(words) == 1 and len(core) < 8:
            return -1.0
        score = float(len(core))
        if inner:
            score += 10.0 if inner in folded_query else -5.0
        return score
    best = _longest_phrase_hit(words, folded_query)
    if inner:
        best = max(best, _longest_phrase_hit(inner.split(), folded_query))
    return best


def select_ruler_supporting_documents(
    query: str,
    answer: str,
    documents: Sequence[str],
    *,
    max_answer_docs: int = 3,
) -> tuple[str, ...]:
    """Pick inserted wiki pages, not every haystack span that mentions the answer.

    Yes/no Hotpot items do not have an extractive answer span. Unique extractive
    answers are unioned with title matches so both hops can enter the gold pack.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be a non-empty string")
    if not documents:
        raise ValueError("documents must be non-empty")
    if (
        not isinstance(max_answer_docs, int)
        or isinstance(max_answer_docs, bool)
        or max_answer_docs < 1
    ):
        raise ValueError("max_answer_docs must be a positive integer")

    ranked: list[tuple[float, int, str]] = []
    for index, block in enumerate(documents):
        if not isinstance(block, str) or not block.strip():
            raise ValueError("every document must be non-empty text")
        score = _title_query_score(ruler_document_title(block), query)
        if score >= 0:
            ranked.append((score, index, block))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected: dict[int, str] = {}
    selected_cores: list[str] = []
    for _score, index, block in ranked:
        core = _folded(_core_title(ruler_document_title(block)))
        if any(core == seen or core in seen or seen in core for seen in selected_cores):
            continue
        selected[index] = block
        selected_cores.append(core)
        if len(selected) >= 4:
            break

    folded_answer = answer.casefold()
    if folded_answer not in _YES_NO:
        answer_docs = [
            (index, block)
            for index, block in enumerate(documents)
            if folded_answer in block.casefold()
        ]
        if 1 <= len(answer_docs) <= max_answer_docs:
            for index, block in answer_docs:
                selected[index] = block
        elif len(answer_docs) > max_answer_docs:
            content = {token for token in _query_terms(query) if len(token) >= 5}
            filtered = [
                (index, block)
                for index, block in answer_docs
                if content & set(_folded(block).split())
            ]
            pool = filtered or answer_docs
            scored = [
                (
                    _query_overlap(query, block),
                    _answer_support_score(query, block, answer)[0],
                    -len(block),
                    index,
                    block,
                )
                for index, block in pool
            ]
            scored.sort(reverse=True)
            for _overlap, _local, _length, index, block in scored[:3]:
                selected[index] = block
    return tuple(selected[index] for index in sorted(selected))


def chunks_covering_documents(
    chunks: Sequence[DocumentChunk],
    documents: Sequence[str],
) -> tuple[DocumentChunk, ...]:
    """Map supporting documents onto existing source windows by title or body probe."""

    if any(not isinstance(chunk, DocumentChunk) for chunk in chunks):
        raise TypeError("chunks must be DocumentChunk values")
    probes: list[tuple[str, str]] = []
    for block in documents:
        if not isinstance(block, str) or not block.strip():
            raise ValueError("every document must be non-empty text")
        title, body = _document_title_and_body(block)
        lead = (body.strip() or title or block)[:160]
        probes.append((title, lead))
    covered: list[DocumentChunk] = []
    seen: set[str] = set()
    for title, lead in probes:
        both = [
            chunk
            for chunk in chunks
            if title
            and title.casefold() in chunk.text.casefold()
            and (len(lead) < 24 or lead.casefold() in chunk.text.casefold())
        ]
        titled = [chunk for chunk in chunks if title and title.casefold() in chunk.text.casefold()]
        lead_only = [
            chunk
            for chunk in chunks
            if len(lead) >= 24 and lead.casefold() in chunk.text.casefold()
        ]
        chosen = (both or titled or lead_only)[:2]
        for chunk in chosen:
            if chunk.chunk_id not in seen:
                covered.append(chunk)
                seen.add(chunk.chunk_id)
    return tuple(covered)


def relabel_ruler_qa_gold(item: EvaluationItem, source_text: str) -> EvaluationItem:
    """Replace answer-substring gold with supporting-document windows."""

    documents = select_ruler_supporting_documents(
        item.query, item.answer, split_ruler_documents(source_text)
    )
    covered = chunks_covering_documents(item.artifact.chunks, documents)
    return EvaluationItem(
        item_id=item.item_id,
        query=item.query,
        answer=item.answer,
        artifact=item.artifact,
        gold_chunk_ids=frozenset(chunk.chunk_id for chunk in covered),
    )


_split_passage = split_passage
