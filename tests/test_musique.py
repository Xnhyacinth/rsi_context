from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from rsicontext.datasets.musique import (
    MuSiQueDataError,
    compile_musique_answerable,
    musique_answerable_record,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "musique_answerable_sample.jsonl"


def _words(text: str) -> int:
    return len(text.split())


def _raw_fixture() -> dict[str, object]:
    return cast(dict[str, object], json.loads(_FIXTURE.read_text(encoding="utf-8")))


def test_compiles_official_answerable_record_with_explicit_gold_provenance() -> None:
    record = musique_answerable_record(_raw_fixture())

    evaluator_item = compile_musique_answerable(record, token_counter=_words)
    policy_item = evaluator_item.policy_item

    assert policy_item.item_id == "2hop__fixture_1_2"
    assert policy_item.query.startswith("In which country")
    assert len(policy_item.artifact.chunks) == 3
    assert evaluator_item.supporting_paragraph_indices == frozenset({0, 1})
    assert evaluator_item.answer == "England"
    assert evaluator_item.gold_chunk_ids == frozenset(
        {"musique:p0000:w0000", "musique:p0001:w0000"}
    )
    assert "also stopped in England" in policy_item.artifact.chunks[2].text
    assert policy_item.artifact.chunks[2].chunk_id not in evaluator_item.gold_chunk_ids


def test_policy_view_excludes_answers_aliases_and_decomposition() -> None:
    evaluator_item = compile_musique_answerable(
        musique_answerable_record(_raw_fixture()), token_counter=_words
    )
    policy_item = evaluator_item.policy_item

    assert not hasattr(policy_item, "answer")
    assert not hasattr(policy_item, "answer_aliases")
    assert not hasattr(policy_item, "question_decomposition")
    assert evaluator_item.answer == "England"
    assert evaluator_item.answer_aliases == ("the United Kingdom",)
    assert evaluator_item.references == ("England", "the United Kingdom")
    assert tuple(step.paragraph_support_idx for step in evaluator_item.steps) == (0, 1)
    assert not hasattr(evaluator_item, "evaluation_item")


def test_compilation_splits_paragraphs_and_marks_every_support_window() -> None:
    raw = _raw_fixture()
    paragraphs = raw["paragraphs"]
    assert isinstance(paragraphs, list)
    first = paragraphs[0]
    assert isinstance(first, dict)
    first["paragraph_text"] = "alpha beta gamma delta"

    evaluator_item = compile_musique_answerable(
        musique_answerable_record(raw), token_counter=_words, tokens_per_chunk=3
    )

    chunks = evaluator_item.policy_item.artifact.chunks
    assert [chunk.chunk_id for chunk in chunks[:2]] == [
        "musique:p0000:w0000",
        "musique:p0000:w0001",
    ]
    assert all(chunk.chunk_id in evaluator_item.gold_chunk_ids for chunk in chunks[:2])
    assert all(chunk.token_count <= 3 for chunk in chunks)


def test_rejects_unanswerable_full_variant_rows() -> None:
    raw = _raw_fixture()
    raw["answerable"] = False

    with pytest.raises(MuSiQueDataError, match="answerable split"):
        musique_answerable_record(raw)


def test_rejects_inconsistent_support_and_decomposition_indices() -> None:
    raw = _raw_fixture()
    steps = raw["question_decomposition"]
    assert isinstance(steps, list)
    second = steps[1]
    assert isinstance(second, dict)
    second["paragraph_support_idx"] = 2

    with pytest.raises(MuSiQueDataError, match="support indices"):
        musique_answerable_record(raw)


def test_accepts_official_integer_decomposition_ids() -> None:
    raw = _raw_fixture()
    steps = raw["question_decomposition"]
    assert isinstance(steps, list)
    first = steps[0]
    second = steps[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first["id"] = 460946
    second["id"] = 294723

    record = musique_answerable_record(raw)

    assert tuple(step.step_id for step in record.steps) == ("460946", "294723")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.update({"unexpected": "field"}), "unexpected schema"),
        (lambda raw: raw.update({"answer_aliases": ["alias", "alias"]}), "unique"),
        (lambda raw: raw.update({"paragraphs": []}), "paragraphs"),
    ],
)
def test_rejects_malformed_official_records(mutation: object, message: str) -> None:
    raw = _raw_fixture()
    assert callable(mutation)
    mutation(raw)

    with pytest.raises(MuSiQueDataError, match=message):
        musique_answerable_record(raw)
