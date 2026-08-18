from __future__ import annotations

from rsicontext.eval import EvaluationItem, gold_context_pack
from rsicontext.policy import Artifact, DocumentChunk


def _item() -> EvaluationItem:
    inert = DocumentChunk("i", "doc", 0, 20, "haystack with no terminal ids", 4)
    competing = DocumentChunk("c", "doc", 21, 40, "distractor fx-bbbbbbbbbbbb", 4)
    gold = DocumentChunk("g", "doc", 41, 60, "keep fx-aaaaaaaaaaaa", 4)
    return EvaluationItem(
        item_id="item",
        query="q",
        answer="a",
        artifact=Artifact("doc", (inert, competing, gold)),
        gold_chunk_ids=frozenset({"g"}),
    )


def test_gold_only_pack_keeps_gold_and_does_not_fill() -> None:
    pack = gold_context_pack(_item(), 12, fill=False)
    assert pack.ordering == ("g",)
    assert pack.token_count == 4


def test_bounded_oracle_appends_id_free_haystack_without_splitting_gold() -> None:
    pack = gold_context_pack(_item(), 12, fill=True)
    text = "\n".join(span.text for span in pack.spans)
    assert pack.ordering == ("g", "i")
    assert "fx-aaaaaaaaaaaa" in text
    assert "fx-bbbbbbbbbbbb" not in text
