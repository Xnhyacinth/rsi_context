from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_SPEC_V1
from rsicontext.datasets.helmet_rag import (
    HelmetRagRecord,
    chunks_covering_documents,
    compile_helmet_rag,
    helmet_kilt_record,
    relabel_ruler_qa_gold,
    ruler_qa_record,
    select_helmet_kilt_records,
    select_ruler_supporting_documents,
    split_encoded_windows,
    split_ruler_documents,
)
from rsicontext.datasets.longmemeval_transfer import spec_v1_pack
from rsicontext.policy import Budget, LexicalPolicy, TruncationPolicy

_FIXTURE = Path(__file__).parent / "fixtures" / "helmet_rag_sample.jsonl"


def _words(text: str) -> int:
    return len(text.split())


def test_compile_helmet_rag_chunks_passages_and_marks_answer_bearing_gold() -> None:
    record = HelmetRagRecord(
        item_id="nq-1",
        query="Who wrote Hamlet?",
        answer="Shakespeare",
        passages=(
            "William Shakespeare wrote Hamlet in the early 1600s.",
            "Unrelated cricket scores from 1998.",
        ),
    )
    item = compile_helmet_rag(record, token_counter=_words, tokens_per_chunk=32)

    assert item.item_id == "nq-1"
    assert len(item.artifact.chunks) == 2
    assert item.gold_chunk_ids == frozenset({item.artifact.chunks[0].chunk_id})
    assert "Shakespeare" in item.artifact.chunks[0].text
    assert item.gold_chunk_ids <= item.artifact.chunk_ids


def test_compile_helmet_rag_splits_long_passages() -> None:
    record = HelmetRagRecord(
        item_id="split-1",
        query="needle",
        answer="needle",
        passages=("alpha beta gamma delta needle epsilon",),
    )
    item = compile_helmet_rag(record, token_counter=_words, tokens_per_chunk=2)

    assert len(item.artifact.chunks) == 3
    assert all(chunk.token_count <= 2 for chunk in item.artifact.chunks)
    assert item.gold_chunk_ids == frozenset({item.artifact.chunks[2].chunk_id})


def test_frozen_h_packers_run_on_compiled_helmet_items() -> None:
    record = HelmetRagRecord(
        item_id="hotpot-1",
        query="capital",
        answer="Ottawa",
        passages=("Ottawa is the capital of Canada.", "Paris is in France."),
    )
    item = compile_helmet_rag(record, token_counter=_words, tokens_per_chunk=32)
    budget = Budget(max_tokens=16)
    lexical = LexicalPolicy().assemble(item.artifact, item.query, budget)
    head = TruncationPolicy("head").assemble(item.artifact, item.query, budget)
    hybrid = spec_v1_pack(item.artifact, item.query, budget, HAND_HYBRID_SPEC_V1)

    assert lexical.token_count <= 16
    assert head.spans[0].chunk_id == item.artifact.chunks[0].chunk_id
    assert "Ottawa" in "\n".join(lexical.ordered_text())
    assert hybrid.token_count <= 16
    assert hybrid.notes == ()


def test_fixture_jsonl_compiles_rag_and_recall_style_items() -> None:
    records: list[HelmetRagRecord] = []
    for line in _FIXTURE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        records.append(
            HelmetRagRecord(
                item_id=str(raw["item_id"]),
                query=str(raw["query"]),
                answer=str(raw["answer"]),
                passages=tuple(str(passage) for passage in raw["passages"]),
            )
        )
    items = tuple(compile_helmet_rag(record, token_counter=_words) for record in records)

    assert {item.item_id for item in items} == {"nq-fixture-1", "niah-fixture-1"}
    assert all(item.gold_chunk_ids for item in items)
    assert all(
        item.answer in " ".join(chunk.text for chunk in item.artifact.chunks) for item in items
    )


def test_helmet_kilt_record_joins_title_and_text() -> None:
    record = helmet_kilt_record(
        {
            "question": "Who wrote Hamlet?",
            "answers": ["Shakespeare"],
            "ctxs": [
                {"title": "Hamlet", "text": "William Shakespeare wrote Hamlet."},
                {"title": "", "text": "Unrelated cricket scores."},
            ],
        },
        item_id="nq-0",
    )
    assert record.item_id == "nq-0"
    assert record.passages == (
        "Hamlet\nWilliam Shakespeare wrote Hamlet.",
        "Unrelated cricket scores.",
    )
    assert record.gold_passage_indices == ()


def test_helmet_kilt_record_uses_has_answer_as_gold_passages() -> None:
    record = helmet_kilt_record(
        {
            "question": "When was the feud?",
            "answers": ["1970s"],
            "ctxs": [
                {
                    "title": "Filler decade",
                    "text": "Many events happened in the 1970s.",
                    "has_answer": False,
                },
                {
                    "title": "Kreisky affair",
                    "text": "The feud took place then.",
                    "has_answer": True,
                },
            ],
        },
        item_id="hotpot-0",
    )
    assert record.gold_passage_indices == (1,)
    item = compile_helmet_rag(record, token_counter=_words)
    gold_text = " ".join(
        chunk.text for chunk in item.artifact.chunks if chunk.chunk_id in item.gold_chunk_ids
    )
    assert "Kreisky affair" in gold_text
    assert "Filler decade" not in gold_text


def test_helmet_kilt_record_matches_positive_ctxs_not_title_collisions() -> None:
    record = helmet_kilt_record(
        {
            "question": "When was the feud?",
            "answers": ["1970s"],
            "positive_ctxs": [
                {
                    "psg_id": 11,
                    "title": "Simon Wiesenthal",
                    "text": "The supporting biography paragraph.",
                }
            ],
            "ctxs": [
                {
                    "id": 99,
                    "title": "Simon Wiesenthal",
                    "text": "An unrelated later career paragraph.",
                    "has_answer": False,
                },
                {
                    "id": 11,
                    "title": "Simon Wiesenthal",
                    "text": "The supporting biography paragraph.",
                    "has_answer": False,
                },
            ],
        },
        item_id="hotpot-1",
    )
    assert record.gold_passage_indices == (1,)
    assert "supporting biography" in record.passages[1]
    assert "later career" in record.passages[0]


def test_select_helmet_kilt_records_drops_clones_and_head_gold() -> None:
    records = (
        HelmetRagRecord("a0", "What genre is Holiday?", "punk rock", ("g0", "n"), (0,)),
        HelmetRagRecord("a1", "What genre is Holiday?", "punk rock", ("n", "g1"), (1,)),
        HelmetRagRecord("b0", "What is Tadhg's occupation?", "poet", ("g0", "n"), (0,)),
        HelmetRagRecord("b1", "What is Tadhg's occupation?", "poet", ("n", "g1"), (1,)),
        HelmetRagRecord("c1", "Where is Wilcza Jama?", "Poland", ("n", "g1"), (1,)),
    )
    selected = select_helmet_kilt_records(records, limit=2, min_gold_passage_index=1)
    assert tuple(record.item_id for record in selected) == ("a1", "b1")


def test_helmet_kilt_record_skips_empty_ctx_text() -> None:
    record = helmet_kilt_record(
        {
            "question": "q",
            "answers": ["a"],
            "ctxs": [{"title": "t", "text": ""}, {"title": "keep", "text": "a fact"}],
        },
        item_id="nq-empty",
    )
    assert record.passages == ("keep\na fact",)
    with pytest.raises(ValueError, match="ctxs"):
        helmet_kilt_record(
            {"question": "q", "answers": ["a"], "ctxs": []},
            item_id="nq-0",
        )


def test_ruler_qa_record_uses_question_and_first_output() -> None:
    record = ruler_qa_record(
        {
            "question": "In what country is Normandy located?",
            "context": "Document 1: Normandy is in France.",
            "outputs": ["France", "france"],
        },
        item_id="qa-0",
    )
    assert record.query.startswith("In what country")
    assert record.answer == "France"
    assert record.passages == ("Document 1: Normandy is in France.",)


def test_helmet_rag_record_rejects_empty_passages() -> None:
    with pytest.raises(ValueError, match="passages"):
        HelmetRagRecord("id", "q", "a", ())


def test_split_encoded_windows_decodes_fixed_id_spans() -> None:
    class _OrdTokenizer:
        def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
            del add_special_tokens
            return [ord(char) for char in text]

        def decode(self, token_ids: Sequence[int], skip_special_tokens: bool = True) -> str:
            del skip_special_tokens
            return "".join(chr(token_id) for token_id in token_ids)

    assert split_encoded_windows("abcdefgh", _OrdTokenizer(), 3) == ("abc", "def", "gh")


def test_compile_helmet_rag_honors_split_parts() -> None:
    record = HelmetRagRecord("id", "q", "needle", ("keep needle drop",))
    item = compile_helmet_rag(
        record,
        token_counter=_words,
        split_parts=lambda _passage: ("keep", "needle", "drop"),
    )
    assert [chunk.text for chunk in item.artifact.chunks] == ["keep", "needle", "drop"]
    assert item.gold_chunk_ids == frozenset({item.artifact.chunks[1].chunk_id})


def test_oversized_passage_token_is_rejected() -> None:
    record = HelmetRagRecord("id", "q", "needle", ("needle",))
    with pytest.raises(ValueError, match="exceeds"):
        compile_helmet_rag(record, token_counter=len, tokens_per_chunk=3)


def test_split_ruler_documents_keeps_document_markers() -> None:
    context = (
        "Document 1:\nEd Wood\nEd Wood was an American filmmaker.\n"
        "Document 2:\nPaul Graham\nFiller essay about startups.\n"
        "Document 3:\nScott Derrickson\nScott Derrickson is an American director."
    )
    documents = split_ruler_documents(context)
    assert len(documents) == 3
    assert documents[0].startswith("Document 1:")
    assert "Scott Derrickson" in documents[2]


def test_select_ruler_supporting_documents_uses_titles_for_yes_no() -> None:
    documents = (
        "Document 1:\nEd Wood\nEd Wood was an American filmmaker.",
        "Document 2:\nPaul Graham\nYes, startups are hard, yes they are.",
        "Document 3:\nScott Derrickson\nScott Derrickson is an American director.",
        "Document 4:\nYes Minister\nA British sitcom. yes yes yes.",
    )
    selected = select_ruler_supporting_documents(
        "Were Scott Derrickson and Ed Wood of the same nationality?",
        "yes",
        documents,
    )
    titles = "\n".join(selected)
    assert "Scott Derrickson" in titles
    assert "Ed Wood" in titles
    assert "Paul Graham" not in titles
    assert "Yes Minister" not in titles


def test_select_ruler_supporting_documents_unions_unique_answer_doc() -> None:
    documents = (
        "Document 1:\nKiss and Tell (1945 film)\nShirley Temple starred in the film.",
        "Document 2:\nShirley Temple\nShe later served as Chief of Protocol.",
        "Document 3:\nKiss (Carly Rae Jepsen album)\nUnrelated pop album.",
    )
    selected = select_ruler_supporting_documents(
        "What government position was held by the woman who portrayed Corliss Archer "
        "in the film Kiss and Tell?",
        "Chief of Protocol",
        documents,
    )
    joined = "\n".join(selected)
    assert "Kiss and Tell (1945 film)" in joined
    assert "Shirley Temple" in joined
    assert "Carly Rae Jepsen" not in joined


def test_select_ruler_supporting_documents_ranks_common_answer_spans() -> None:
    documents = (
        "Document 1:\nFrance is a republic in Western Europe with Paris as its capital.",
        "Document 2:\nNormandy is a region in the north of France known for the D-Day landings.",
        "Document 3:\nThe France national football team won the 1998 World Cup.",
        "Document 4:\nAir France is the flag carrier of France.",
        "Document 5:\nThe France-Germany border runs along the Rhine.",
    )
    selected = select_ruler_supporting_documents(
        "In what country is Normandy located?",
        "France",
        documents,
    )
    joined = "\n".join(selected)
    assert "Normandy is a region" in joined
    assert "football team" not in joined
    assert 1 <= len(selected) <= 3


def test_select_ruler_supporting_documents_filters_common_answer_spans() -> None:
    documents = (
        "Document 1:\nThe Black Death in the 9th century is filler.",
        "Document 2:\nThe Latin word Normanus was first recorded in the 9th century.",
        "Document 3:\nGermany in the 9th century had no maritime empire.",
        "Document 4:\nGreece in the 9th century is another unrelated mention.",
    )
    selected = select_ruler_supporting_documents(
        "When was the Latin version of the word Norman first recorded?",
        "9th century",
        documents,
    )
    joined = "\n".join(selected)
    assert "Normanus" in joined
    assert "Black Death" not in joined
    later_documents = (
        "Document 1:\nGuns N' Roses discography\nA 1999 promo appears in the list.",
        "Document 2:\nTrue Lies\nAn earlier Schwarzenegger film.",
        "Document 3:\nEnd of Days (film)\nReleased in 1999.",
    )
    selected = select_ruler_supporting_documents(
        "What year did Guns N Roses perform a promo for a movie starring "
        "Arnold Schwarzenegger as a former New York Police detective?",
        "1999",
        later_documents,
    )
    joined = "\n".join(selected)
    assert "Guns N' Roses" in joined
    assert "True Lies" not in joined


def test_relabel_ruler_qa_gold_does_not_keep_yes_haystack_windows() -> None:
    haystack = (
        "Document 1:\nEd Wood\nEd Wood was an American filmmaker.\n"
        + "yes filler " * 20
        + "Document 2:\nScott Derrickson\nScott Derrickson is an American director.\n"
        + "yes filler " * 20
        + "Document 3:\nPaul Graham\nyes yes yes startups yes.\n"
        + "yes filler " * 40
    )
    record = HelmetRagRecord(
        "qa-yes",
        "Were Scott Derrickson and Ed Wood of the same nationality?",
        "yes",
        (haystack,),
    )
    item = compile_helmet_rag(record, token_counter=_words, tokens_per_chunk=8)
    substring_gold = len(item.gold_chunk_ids)
    relabeled = relabel_ruler_qa_gold(item, haystack)
    assert substring_gold > len(relabeled.gold_chunk_ids)
    gold_text = " ".join(
        chunk.text for chunk in item.artifact.chunks if chunk.chunk_id in relabeled.gold_chunk_ids
    )
    assert "Ed Wood" in gold_text
    assert "Scott Derrickson" in gold_text
    assert "startups" not in gold_text
    assert len(relabeled.gold_chunk_ids) <= 8


def test_chunks_covering_documents_matches_title_windows() -> None:
    record = HelmetRagRecord(
        "id",
        "q",
        "needle",
        ("prefix text Document 1:\nNeedle Page\nneedle lives here suffix text",),
    )
    item = compile_helmet_rag(record, token_counter=_words, tokens_per_chunk=4)
    covered = chunks_covering_documents(
        item.artifact.chunks,
        ("Document 1:\nNeedle Page\nneedle lives here",),
    )
    assert covered
    assert any(
        "Needle Page" in chunk.text or "needle lives here" in chunk.text for chunk in covered
    )
