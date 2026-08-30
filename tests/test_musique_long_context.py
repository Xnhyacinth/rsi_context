from __future__ import annotations

import pytest

from rsicontext.datasets.musique import musique_answerable_record
from rsicontext.datasets.musique_long_context import (
    gold_position_matches,
    pack_musique_long_context,
)


def _record(item_id: str, answer: str, *, leaking_decoy: bool = False) -> dict[str, object]:
    decoy = f"This decoy says {answer}." if leaking_decoy else "This is an unrelated decoy."
    bridge = f"{item_id}-bridge"
    return {
        "id": item_id,
        "paragraphs": [
            {
                "idx": 0,
                "title": f"{item_id} bridge",
                "paragraph_text": f"The bridge value is {bridge}.",
                "is_supporting": True,
            },
            {
                "idx": 1,
                "title": f"{item_id} result",
                "paragraph_text": f"The final value is {answer}.",
                "is_supporting": True,
            },
            {
                "idx": 2,
                "title": f"{item_id} decoy",
                "paragraph_text": decoy,
                "is_supporting": False,
            },
        ],
        "question": "What is the final value?",
        "question_decomposition": [
            {
                "id": 1,
                "question": "Find the bridge",
                "answer": bridge,
                "paragraph_support_idx": 0,
            },
            {
                "id": 2,
                "question": "Find the result",
                "answer": answer,
                "paragraph_support_idx": 1,
            },
        ],
        "answer": answer,
        "answer_aliases": [],
        "answerable": True,
    }


def _words(text: str) -> int:
    return len(text.split())


def test_packer_is_deterministic_binding_and_answer_clean() -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    distractors = tuple(
        musique_answerable_record(_record(f"d{index}", f"answer-{index}")) for index in range(20)
    )

    first = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=100,
        position="middle",
        seed=7,
        tokens_per_chunk=50,
    )
    second = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=100,
        position="middle",
        seed=7,
        tokens_per_chunk=50,
    )

    assert first == second
    assert sum(chunk.token_count for chunk in first.policy_item.artifact.chunks) >= 100
    nongold = "\n".join(
        chunk.text
        for chunk in first.policy_item.artifact.chunks
        if chunk.chunk_id not in first.gold_chunk_ids
    )
    assert "saffron" not in nongold.casefold()
    assert first.answer == "saffron"
    assert len(first.supporting_paragraph_indices) == 2


def test_packer_controls_gold_position() -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    distractors = tuple(
        musique_answerable_record(_record(f"d{index}", f"answer-{index}")) for index in range(20)
    )

    front = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=100,
        position="front",
        seed=3,
    )
    tail = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=100,
        position="tail",
        seed=3,
    )

    front_gold = sorted(front.supporting_paragraph_indices)
    tail_gold = sorted(tail.supporting_paragraph_indices)
    assert front_gold == [0, 1]
    assert tail_gold[-1] == len(tail.policy_item.artifact.chunks) - 1
    assert tail_gold[0] > len(tail.policy_item.artifact.chunks) // 2
    assert gold_position_matches(front, "front")
    assert gold_position_matches(tail, "tail")


def test_packer_controls_middle_and_distributed_on_token_axis() -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    raw_distractors = [_record(f"d{index}", f"answer-{index}") for index in range(30)]
    for index, raw in enumerate(raw_distractors):
        raw["paragraphs"][2]["paragraph_text"] = "decoy " * (index % 7 + 1)  # type: ignore[index]
    distractors = tuple(musique_answerable_record(raw) for raw in raw_distractors)

    middle = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=200,
        position="middle",
        seed=4,
    )
    distributed = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=200,
        position="distributed",
        seed=4,
    )

    assert gold_position_matches(middle, "middle")
    assert gold_position_matches(distributed, "distributed")


def test_packer_rejects_native_answer_leakage() -> None:
    target = musique_answerable_record(_record("target", "saffron", leaking_decoy=True))
    distractors = tuple(
        musique_answerable_record(_record(f"d{index}", f"answer-{index}")) for index in range(20)
    )

    try:
        pack_musique_long_context(
            target,
            distractors,
            token_counter=_words,
            target_source_tokens=100,
            position="distributed",
            seed=1,
        )
    except ValueError as exc:
        assert "native non-supporting" in str(exc)
    else:
        raise AssertionError("answer-leaking target must be rejected")


def test_packer_filters_external_intermediate_answer_leakage() -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    leaking_raw = _record("leaking", "other-answer")
    leaking_raw["paragraphs"][2]["paragraph_text"] = (  # type: ignore[index]
        "This decoy repeats target-bridge."
    )
    distractors = (
        musique_answerable_record(leaking_raw),
        *(
            musique_answerable_record(_record(f"d{index}", f"answer-{index}"))
            for index in range(20)
        ),
    )

    packed = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=100,
        position="middle",
        seed=7,
    )

    nongold = "\n".join(
        chunk.text
        for chunk in packed.policy_item.artifact.chunks
        if chunk.chunk_id not in packed.gold_chunk_ids
    )
    assert "target-bridge" not in nongold.casefold()


def test_packer_tops_up_after_chunk_normalization() -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    distractors = tuple(
        musique_answerable_record(_record(f"d{index}", f"answer-{index}")) for index in range(30)
    )

    def newline_sensitive_counter(text: str) -> int:
        return len(text.split()) + text.count("\n")

    packed = pack_musique_long_context(
        target,
        distractors,
        token_counter=newline_sensitive_counter,
        target_source_tokens=100,
        position="middle",
        seed=11,
        tokens_per_chunk=50,
    )

    assert sum(chunk.token_count for chunk in packed.policy_item.artifact.chunks) >= 100


def test_packer_rejects_a_compiled_position_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    target = musique_answerable_record(_record("target", "saffron"))
    distractors = tuple(
        musique_answerable_record(_record(f"d{index}", f"answer-{index}")) for index in range(20)
    )
    monkeypatch.setattr(
        "rsicontext.datasets.musique_long_context.gold_position_matches",
        lambda _item, _position: False,
    )

    with pytest.raises(ValueError, match="does not satisfy requested"):
        pack_musique_long_context(
            target,
            distractors,
            token_counter=_words,
            target_source_tokens=100,
            position="middle",
            seed=11,
        )


def test_packer_deduplicates_external_copies_of_native_nonsupport() -> None:
    target_raw = _record("target", "saffron")
    duplicate_raw = _record("duplicate", "other-answer")
    target_decoy = target_raw["paragraphs"][2]  # type: ignore[index]
    duplicate_raw["paragraphs"][2] = target_decoy  # type: ignore[index]
    target = musique_answerable_record(target_raw)
    distractors = (
        musique_answerable_record(duplicate_raw),
        *(
            musique_answerable_record(_record(f"d{index}", f"answer-{index}"))
            for index in range(30)
        ),
    )

    packed = pack_musique_long_context(
        target,
        distractors,
        token_counter=_words,
        target_source_tokens=350,
        position="middle",
        seed=7,
    )

    normalized = [chunk.text.casefold() for chunk in packed.policy_item.artifact.chunks]
    assert len(normalized) == len(set(normalized))
