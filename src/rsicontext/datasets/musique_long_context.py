"""Deterministic answer-clean long-context packing for MuSiQue records."""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Iterable
from typing import Literal

from rsicontext.datasets.musique import (
    MuSiQueEvaluatorItem,
    MuSiQueParagraph,
    MuSiQueRecord,
    MuSiQueStep,
    compile_musique_answerable,
)

MuSiQueGoldPosition = Literal["front", "middle", "tail", "distributed"]
_TaggedParagraph = tuple[MuSiQueParagraph, int | None]


def _contains_reference(text: str, record: MuSiQueRecord) -> bool:
    normalized = " ".join(text.split()).casefold()
    references = (
        record.answer,
        *record.answer_aliases,
        *(step.answer for step in record.steps),
    )
    return any(
        re.search(rf"(?<!\w){re.escape(' '.join(reference.split()).casefold())}(?!\w)", normalized)
        is not None
        for reference in references
    )


def _paragraph_text(paragraph: MuSiQueParagraph) -> str:
    return f"{paragraph.title}\n{paragraph.text}"


def _arrange(
    support: list[_TaggedParagraph],
    distractors: list[_TaggedParagraph],
    position: MuSiQueGoldPosition,
    token_count: Callable[[MuSiQueParagraph], int],
) -> list[_TaggedParagraph]:
    if position == "front":
        return support + distractors
    if position == "tail":
        return distractors + support
    distractor_total = sum(token_count(paragraph) for paragraph, _ in distractors)
    if position == "middle":
        target = distractor_total / 2
        cumulative = 0
        split = 0
        while split < len(distractors) and cumulative < target:
            cumulative += token_count(distractors[split][0])
            split += 1
        return distractors[:split] + support + distractors[split:]
    targets = [
        distractor_total * (offset + 1) / (len(support) + 1) for offset in range(len(support))
    ]
    arranged: list[_TaggedParagraph] = []
    cumulative = 0
    support_offset = 0
    for tagged in distractors:
        while support_offset < len(support) and cumulative >= targets[support_offset]:
            arranged.append(support[support_offset])
            support_offset += 1
        arranged.append(tagged)
        cumulative += token_count(tagged[0])
    arranged.extend(support[support_offset:])
    return arranged


def gold_token_centers(item: MuSiQueEvaluatorItem) -> tuple[float, ...]:
    """Return evaluator-only supporting-paragraph centers on the token axis."""

    chunks = item.policy_item.artifact.chunks
    total = sum(chunk.token_count for chunk in chunks)
    if total <= 0:
        raise ValueError("compiled MuSiQue item must contain positive source tokens")
    spans: dict[int, list[int]] = {}
    cursor = 0
    for chunk in chunks:
        end = cursor + chunk.token_count
        if chunk.chunk_id in item.gold_chunk_ids:
            paragraph_index = int(chunk.chunk_id.split(":", maxsplit=2)[1].removeprefix("p"))
            span = spans.setdefault(paragraph_index, [cursor, end])
            span[1] = end
        cursor = end
    if set(spans) != set(item.supporting_paragraph_indices):
        raise ValueError("compiled gold chunks do not match supporting paragraph indices")
    return tuple((spans[index][0] + spans[index][1]) / (2 * total) for index in sorted(spans))


def gold_position_matches(
    item: MuSiQueEvaluatorItem,
    expected: MuSiQueGoldPosition,
) -> bool:
    """Validate requested placement using compiled target-token offsets."""

    chunks = item.policy_item.artifact.chunks
    gold_offsets = [
        index for index, chunk in enumerate(chunks) if chunk.chunk_id in item.gold_chunk_ids
    ]
    if not gold_offsets:
        return False
    if expected == "front":
        return gold_offsets[0] == 0
    if expected == "tail":
        return gold_offsets[-1] == len(chunks) - 1
    centers = gold_token_centers(item)
    if expected == "middle":
        return 0.4 <= (centers[0] + centers[-1]) / 2 <= 0.6
    targets = tuple((offset + 1) / (len(centers) + 1) for offset in range(len(centers)))
    return all(
        abs(observed - target) <= 0.15 for observed, target in zip(centers, targets, strict=True)
    )


def pack_musique_long_context(
    target: MuSiQueRecord,
    distractor_records: Iterable[MuSiQueRecord],
    *,
    token_counter: Callable[[str], int],
    target_source_tokens: int,
    position: MuSiQueGoldPosition,
    seed: int,
    tokens_per_chunk: int = 512,
) -> MuSiQueEvaluatorItem:
    """Pack one target with answer-clean cross-item paragraphs under a fixed seed."""

    if (
        not isinstance(target_source_tokens, int)
        or isinstance(target_source_tokens, bool)
        or target_source_tokens <= 0
    ):
        raise ValueError("target_source_tokens must be a positive integer")
    if position not in {"front", "middle", "tail", "distributed"}:
        raise ValueError(f"unsupported gold position: {position!r}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")

    support: list[_TaggedParagraph] = [
        (paragraph, paragraph.idx) for paragraph in target.paragraphs if paragraph.is_supporting
    ]
    native_nonsupport = [
        paragraph for paragraph in target.paragraphs if not paragraph.is_supporting
    ]
    if any(
        _contains_reference(_paragraph_text(paragraph), target) for paragraph in native_nonsupport
    ):
        raise ValueError(
            "target final or intermediate answer appears in native non-supporting evidence"
        )

    seen_text = {_paragraph_text(paragraph).casefold() for paragraph in target.paragraphs}
    candidates: list[MuSiQueParagraph] = []
    for record in distractor_records:
        if record.item_id == target.item_id:
            continue
        for paragraph in record.paragraphs:
            rendered = _paragraph_text(paragraph)
            key = rendered.casefold()
            if key in seen_text or _contains_reference(rendered, target):
                continue
            seen_text.add(key)
            candidates.append(paragraph)

    # Non-cryptographic randomness is required for replayable benchmark packing.
    rng = random.Random(seed)  # nosec B311
    rng.shuffle(candidates)
    native_shuffled = list(native_nonsupport)
    rng.shuffle(native_shuffled)
    ordered_candidates = native_shuffled + candidates

    paragraph_counts: dict[MuSiQueParagraph, int] = {}

    def count(paragraph: MuSiQueParagraph) -> int:
        cached = paragraph_counts.get(paragraph)
        if cached is not None:
            return cached
        value = token_counter(_paragraph_text(paragraph))
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("target tokenizer counts must be positive integers")
        paragraph_counts[paragraph] = value
        return value

    selected: list[_TaggedParagraph] = []
    source_tokens = sum(count(paragraph) for paragraph, _ in support)
    next_candidate = 0
    while source_tokens < target_source_tokens and next_candidate < len(ordered_candidates):
        paragraph = ordered_candidates[next_candidate]
        next_candidate += 1
        source_tokens += count(paragraph)
        selected.append((paragraph, None))
    if source_tokens < target_source_tokens:
        raise ValueError("insufficient answer-clean distractors for the requested source length")

    def compile_selected() -> MuSiQueEvaluatorItem:
        arranged = _arrange(support, selected, position, count)
        support_index_by_original: dict[int, int] = {}
        paragraphs: list[MuSiQueParagraph] = []
        for index, (paragraph, original_support_idx) in enumerate(arranged):
            is_supporting = original_support_idx is not None
            paragraphs.append(
                MuSiQueParagraph(
                    idx=index,
                    title=paragraph.title,
                    text=paragraph.text,
                    is_supporting=is_supporting,
                )
            )
            if original_support_idx is not None:
                support_index_by_original[original_support_idx] = index
        steps = tuple(
            MuSiQueStep(
                step_id=step.step_id,
                question=step.question,
                answer=step.answer,
                paragraph_support_idx=support_index_by_original[step.paragraph_support_idx],
            )
            for step in target.steps
        )
        packed = MuSiQueRecord(
            item_id=f"{target.item_id}-packed-{position}-{seed}",
            question=target.question,
            paragraphs=tuple(paragraphs),
            steps=steps,
            answer=target.answer,
            answer_aliases=target.answer_aliases,
        )
        return compile_musique_answerable(
            packed,
            token_counter=token_counter,
            tokens_per_chunk=tokens_per_chunk,
        )

    while True:
        compiled = compile_selected()
        actual_tokens = sum(chunk.token_count for chunk in compiled.policy_item.artifact.chunks)
        if actual_tokens >= target_source_tokens:
            if not gold_position_matches(compiled, position):
                raise ValueError(
                    f"compiled gold evidence does not satisfy requested {position!r} token stratum"
                )
            return compiled
        if next_candidate >= len(ordered_candidates):
            raise ValueError("insufficient answer-clean distractors after chunk normalization")
        selected.append((ordered_candidates[next_candidate], None))
        next_candidate += 1
