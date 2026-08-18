from __future__ import annotations

from rsicontext.datasets.ruler_niah import (
    RulerNiahRecord,
    compile_ruler_niah,
    json_kv_record,
    ruler_niah_record,
)


def _words(text: str) -> int:
    return len(text.split())


def test_compile_ruler_niah_marks_key_and_answer_span_as_gold() -> None:
    record = RulerNiahRecord(
        item_id="n0",
        query="What is the special magic number for precious-blog?",
        answer="1210562",
        needle_key="precious-blog",
        context=(
            "One of the special magic numbers for fearless-emotion is: 5009793. "
            "One of the special magic numbers for precious-blog is: 1210562. "
            "One of the special magic numbers for confused-customer is: 6884037."
        ),
    )
    item = compile_ruler_niah(record, token_counter=_words, tokens_per_chunk=8)

    assert item.answer == "1210562"
    assert item.gold_chunk_ids
    gold_text = " ".join(
        chunk.text for chunk in item.artifact.chunks if chunk.chunk_id in item.gold_chunk_ids
    )
    assert "precious-blog" in gold_text
    assert "1210562" in gold_text
    assert len(item.artifact.chunks) > len(item.gold_chunk_ids)
    distractors = [
        chunk.text for chunk in item.artifact.chunks if chunk.chunk_id not in item.gold_chunk_ids
    ]
    assert any("5009793" in text for text in distractors)


def test_ruler_niah_record_uses_prompt_suffix_as_query() -> None:
    raw = {
        "input": (
            "Memorize the number.\n"
            "One of the special magic numbers for precious-blog is: 1210562.\n"
            "What is the special magic number for precious-blog mentioned in the provided text?"
        ),
        "context": "One of the special magic numbers for precious-blog is: 1210562.",
        "query": "precious-blog",
        "answer": ["1210562"],
    }
    record = ruler_niah_record(raw, item_id="n1")
    assert record.needle_key == "precious-blog"
    assert record.answer == "1210562"
    assert "What is the special magic number" in record.query


def test_json_kv_record_uses_uuid_question_as_needle_key() -> None:
    record = json_kv_record(
        {
            "question": "bdd640fb-0667-4ad1-9c80-317fa3b1799d",
            "answer": "6b732c7a-8dca-44bd-850a-2d22b08c19fa",
            "context": (
                '{"bdd640fb-0667-4ad1-9c80-317fa3b1799d": "6b732c7a-8dca-44bd-850a-2d22b08c19fa"}'
            ),
        },
        item_id="kv-0",
    )
    assert record.needle_key == record.query == "bdd640fb-0667-4ad1-9c80-317fa3b1799d"
    assert record.answer.startswith("6b732c7a")


def test_compile_ruler_niah_honors_split_parts() -> None:
    record = RulerNiahRecord(
        item_id="n-split",
        query="key",
        answer="111",
        needle_key="key",
        context="aaa key 111 bbb",
    )
    item = compile_ruler_niah(
        record,
        token_counter=_words,
        split_parts=lambda text: ("aaa", "key 111", "bbb"),
    )
    assert [chunk.text for chunk in item.artifact.chunks] == ["aaa", "key 111", "bbb"]
    assert item.gold_chunk_ids == frozenset({"nk-0001"})
